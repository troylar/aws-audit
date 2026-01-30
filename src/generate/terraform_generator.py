"""Terraform generator - high-level API for IaC generation."""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models.generation import Layer
from .agent import compile_terraform_agent
from .layers import LayerStatus
from .state import GenerationConfig, GenerationState


@dataclass
class GenerationResult:
    """Result of Terraform generation."""

    success: bool
    output_dir: str
    generated_files: List[str] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if generated code passed terraform validation."""
        return len(self.validation_errors) == 0

    @property
    def summary(self) -> Dict[str, Any]:
        """Get generation summary."""
        completed = sum(1 for layer in self.layers if layer.status == LayerStatus.COMPLETED)
        failed = sum(1 for layer in self.layers if layer.status == LayerStatus.FAILED)
        total_resources = sum(len(layer.resources) for layer in self.layers)

        return {
            "success": self.success,
            "is_valid": self.is_valid,
            "total_layers": len(self.layers),
            "completed_layers": completed,
            "failed_layers": failed,
            "total_resources": total_resources,
            "generated_files": len(self.generated_files),
            "errors": len(self.errors),
            "validation_errors": len(self.validation_errors),
        }


class TerraformGenerator:
    """High-level Terraform generator from AWS inventory snapshots.

    Uses AWS Bedrock for AI-powered code generation.

    Usage:
        generator = TerraformGenerator(
            output_dir="./terraform",
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            region="us-east-1",
        )
        result = generator.run("my-snapshot")

        if result.success:
            print(f"Generated {len(result.generated_files)} files")
        else:
            print(f"Errors: {result.errors}")
    """

    def __init__(
        self,
        output_dir: str = "./terraform",
        model_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """Initialize generator.

        Args:
            output_dir: Directory to write Terraform files
            model_id: Bedrock model ID (or use AWSINV_BEDROCK_MODEL_ID env)
            region: AWS region for Bedrock (or use AWSINV_BEDROCK_REGION env)
        """
        self.output_dir = output_dir

        base_config = GenerationConfig.from_env()

        self.config = GenerationConfig(
            bedrock_model_id=model_id or base_config.bedrock_model_id,
            bedrock_region=region or base_config.bedrock_region,
            max_retries=base_config.max_retries,
        )

        self.agent = compile_terraform_agent()

    def run(self, snapshot_name: str) -> GenerationResult:
        """Generate Terraform from a snapshot.

        Args:
            snapshot_name: Name of the snapshot to generate from

        Returns:
            GenerationResult with generated files and any errors
        """
        os.makedirs(self.output_dir, exist_ok=True)

        initial_state: GenerationState = {
            "snapshot_name": snapshot_name,
            "output_dir": self.output_dir,
            "output_format": "terraform",
            "inventory": [],
            "resource_map": {},
            "layers": {},
            "layer_order": [],
            "current_layer_index": 0,
            "current_layer_status": "pending",
            "attempt_count": 0,
            "max_attempts": self.config.max_retries,
            "validation_errors": [],
            "generated_code": {},
            "generated_files": [],
            "lambda_code_paths": {},
            "total_resources": 0,
            "processed_resources": 0,
            "errors": [],
            "messages": [],
        }

        try:
            final_state = self.agent.invoke(initial_state)

            self._generate_provider_config()
            self._generate_variables_file(final_state)
            self._generate_outputs_file(final_state)

            generated_files = final_state.get("generated_files", [])
            layers_dict = final_state.get("layers", {})
            layer_order = final_state.get("layer_order", [])
            errors = final_state.get("errors", [])
            validation_errors = final_state.get("validation_errors", [])

            layers = [layers_dict[layer_name] for layer_name in layer_order if layer_name in layers_dict]

            success = len(errors) == 0 and len(generated_files) > 0

            return GenerationResult(
                success=success,
                output_dir=self.output_dir,
                generated_files=generated_files,
                layers=layers,
                errors=[str(e) for e in errors],
                validation_errors=[str(e) for e in validation_errors],
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                output_dir=self.output_dir,
                errors=[f"Generation failed: {e}"],
            )

    def _generate_provider_config(self) -> None:
        """Generate main.tf with provider configuration."""
        provider_tf = """# Provider Configuration
# Generated by aws-inventory-manager

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy = "terraform"
      GeneratedFrom = "aws-inventory-manager"
    }
  }
}
"""
        filepath = os.path.join(self.output_dir, "main.tf")
        with open(filepath, "w") as f:
            f.write(provider_tf)

    def _generate_variables_file(self, state: Dict[str, Any]) -> None:
        """Generate variables.tf from state."""
        regions = set()
        layers_dict = state.get("layers", {})
        for layer in layers_dict.values():
            if hasattr(layer, "resources"):
                for resource in layer.resources:
                    if hasattr(resource, "region") and resource.region:
                        regions.add(resource.region)

        default_region = sorted(regions)[0] if regions else "us-east-1"

        variables_tf = f"""# Variables
# Generated by aws-inventory-manager

variable "aws_region" {{
  description = "AWS region for resources"
  type        = string
  default     = "{default_region}"
}}

variable "environment" {{
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}}

variable "project" {{
  description = "Project name for resource tagging"
  type        = string
  default     = "inventory-managed"
}}
"""
        filepath = os.path.join(self.output_dir, "variables.tf")
        with open(filepath, "w") as f:
            f.write(variables_tf)

    def _generate_outputs_file(self, state: Dict[str, Any]) -> None:
        """Generate outputs.tf from state."""
        outputs_tf = """# Outputs
# Generated by aws-inventory-manager

# Add outputs for important resource attributes as needed
"""
        filepath = os.path.join(self.output_dir, "outputs.tf")
        with open(filepath, "w") as f:
            f.write(outputs_tf)


def generate_terraform(
    snapshot_name: str,
    output_dir: str = "./terraform",
    model_id: Optional[str] = None,
    region: Optional[str] = None,
) -> GenerationResult:
    """Generate Terraform from a snapshot.

    Args:
        snapshot_name: Name of the snapshot
        output_dir: Output directory for Terraform files
        model_id: Bedrock model ID
        region: AWS region for Bedrock

    Returns:
        GenerationResult
    """
    generator = TerraformGenerator(
        output_dir=output_dir,
        model_id=model_id,
        region=region,
    )
    return generator.run(snapshot_name)
