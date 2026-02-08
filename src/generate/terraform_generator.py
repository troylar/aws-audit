"""Terraform generator - high-level API for IaC generation."""

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..models.generation import Layer
from .agent import compile_terraform_agent
from .layers import LayerStatus
from .state import GenerationConfig, GenerationState, set_progress_callback

# Progress callback type: (step_name, step_data) -> None
ProgressCallback = Callable[[str, Dict[str, Any]], None]


@dataclass
class GenerationResult:
    """Result of Terraform generation."""

    success: bool
    output_dir: str
    generated_files: List[str] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    guardrails_blocked: bool = False
    guardrails_report: Optional[Dict[str, Any]] = None

    @property
    def is_valid(self) -> bool:
        """Check if generated code passed terraform validation."""
        return len(self.validation_errors) == 0

    @property
    def summary(self) -> Dict[str, Any]:
        """Get generation summary."""
        # Handle both List[Layer] and List[List[TrackedResource]] formats
        total_resources = 0
        completed = 0
        failed = 0

        for layer in self.layers:
            if isinstance(layer, Layer):
                total_resources += len(layer.resources)
                if layer.status in (LayerStatus.COMPLETED, LayerStatus.COMPLETED.value):
                    completed += 1
                elif layer.status in (LayerStatus.FAILED, LayerStatus.FAILED.value):
                    failed += 1
            elif isinstance(layer, list):
                total_resources += len(layer)
                completed += 1  # Assume completed if we have the resources

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
        progress_callback: Optional[ProgressCallback] = None,
        guardrails_enabled: bool = False,
        guardrails_policy_path: Optional[str] = None,
        guardrails_environment: str = "default",
        guardrails_strict: bool = False,
        guardrails_auto_fix: bool = True,
        best_practices_enabled: bool = True,
    ):
        """Initialize generator.

        Args:
            output_dir: Directory to write Terraform files
            model_id: Bedrock model ID (or use AWSINV_BEDROCK_MODEL_ID env)
            region: AWS region for Bedrock (or use AWSINV_BEDROCK_REGION env)
            progress_callback: Optional callback for progress updates
            guardrails_enabled: Enable guardrails evaluation
            guardrails_policy_path: Path to custom policy file
            guardrails_environment: Environment for policy overrides
            guardrails_strict: Enable strict mode (any violation blocks)
            guardrails_auto_fix: Enable AI auto-fix for AUTO-FIX guardrails
            best_practices_enabled: Enable advisory best-practice guardrails
        """
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self.guardrails_enabled = guardrails_enabled
        self.guardrails_policy_path = guardrails_policy_path
        self.guardrails_environment = guardrails_environment
        self.guardrails_strict = guardrails_strict
        self.guardrails_auto_fix = guardrails_auto_fix
        self.best_practices_enabled = best_practices_enabled

        base_config = GenerationConfig.from_env()

        self.config = GenerationConfig(
            bedrock_model_id=model_id or base_config.bedrock_model_id,
            bedrock_region=region or base_config.bedrock_region,
            max_retries=base_config.max_retries,
        )

        self.agent = compile_terraform_agent()

    def run(
        self,
        snapshot_name: Optional[str] = None,
        input_file: Optional[str] = None,
    ) -> GenerationResult:
        """Generate Terraform from a snapshot or export file.

        Args:
            snapshot_name: Name of the snapshot to generate from
            input_file: Path to JSON/YAML export file (alternative to snapshot)

        Returns:
            GenerationResult with generated files and any errors

        Raises:
            ValueError: If neither snapshot_name nor input_file is provided
        """
        if not snapshot_name and not input_file:
            raise ValueError("Either snapshot_name or input_file must be provided")

        os.makedirs(self.output_dir, exist_ok=True)

        initial_state: GenerationState = {
            "snapshot_name": snapshot_name or "",
            "input_file": input_file or "",
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
            # Guardrails fields
            "best_practices_enabled": self.best_practices_enabled,
            "guardrails_enabled": self.guardrails_enabled,
            "guardrails_policy_path": self.guardrails_policy_path,
            "guardrails_environment": self.guardrails_environment,
            "guardrails_strict": self.guardrails_strict,
            "guardrails_auto_fix": self.guardrails_auto_fix,
            "guardrails_report": None,
            "guardrails_blocked": False,
            "guardrails_auto_fixes": {},
        }

        try:
            final_state = self._run_with_progress(initial_state)

            self._generate_provider_config()
            self._generate_variables_file(final_state)
            self._generate_outputs_file(final_state)

            generated_files = final_state.get("generated_files") or []
            layers_dict = final_state.get("layers") or {}
            layer_order = final_state.get("layer_order") or []
            errors = final_state.get("errors") or []
            validation_errors = final_state.get("validation_errors") or []
            comparison_result = final_state.get("comparison_result") or {}
            guardrails_blocked = final_state.get("guardrails_blocked", False)
            guardrails_report = final_state.get("guardrails_report")

            layers = [layers_dict[layer_name] for layer_name in layer_order if layer_name in layers_dict]

            # If guardrails blocked, generation was stopped early
            if guardrails_blocked:
                success = False
                if not errors:
                    errors = ["Generation blocked by guardrails policy violations"]
            else:
                success = len(errors) == 0 and len(generated_files) > 0

            result = GenerationResult(
                success=success,
                output_dir=self.output_dir,
                generated_files=generated_files,
                layers=layers,
                errors=[str(e) for e in errors] if errors else [],
                validation_errors=([str(e) for e in validation_errors] if validation_errors else []),
                guardrails_blocked=guardrails_blocked,
                guardrails_report=guardrails_report,
            )

            if self.progress_callback and comparison_result:
                self.progress_callback("comparison_complete", {"result": comparison_result})

            return result

        except Exception as e:
            return GenerationResult(
                success=False,
                output_dir=self.output_dir,
                errors=[f"Generation failed: {e}"],
            )

    def _run_with_progress(self, initial_state: GenerationState) -> Dict[str, Any]:
        """Run the agent with progress streaming.

        Args:
            initial_state: Initial state for the agent

        Returns:
            Final state after agent execution
        """
        if not self.progress_callback:
            return self.agent.invoke(initial_state)

        # Set the global progress callback for nodes to use
        set_progress_callback(self.progress_callback)

        final_state = dict(initial_state)
        last_node = None
        last_layer_index = -1

        try:
            for event in self.agent.stream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    if node_name != last_node:
                        self.progress_callback("node_start", {"node": node_name})
                        last_node = node_name

                        # Emit layer_start when generate_layer begins
                        if node_name == "generate_layer":
                            layer_order: list = final_state.get("layer_order", [])
                            current_idx: int = final_state.get("current_layer_index", 0)
                            if current_idx != last_layer_index and current_idx < len(layer_order):
                                layer_name = layer_order[current_idx]
                                self.progress_callback(
                                    "layer_start",
                                    {
                                        "layer_name": layer_name,
                                        "layer_index": current_idx,
                                        "total_layers": len(layer_order),
                                    },
                                )
                                last_layer_index = current_idx

                    final_state.update(state_update)

                    if node_name == "parse_inventory":
                        resources = state_update.get("resources", [])
                        self.progress_callback(
                            "resources_loaded",
                            {
                                "count": len(resources),
                                "resources": resources,
                            },
                        )

                    elif node_name == "categorize_layers":
                        layers = state_update.get("layers", {})
                        layer_order = state_update.get("layer_order", [])
                        self.progress_callback(
                            "layers_categorized",
                            {
                                "layers": layers,
                                "layer_order": layer_order,
                            },
                        )

                    elif node_name == "generate_layer":
                        layer_order_list: list = final_state.get("layer_order", [])
                        current_idx_val: int = state_update.get("current_layer_index", 0) - 1
                        if 0 <= current_idx_val < len(layer_order_list):
                            layer_name = layer_order_list[current_idx_val]
                            status = state_update.get("current_layer_status", "")
                            generated_code = state_update.get("generated_code", {})
                            generated_files = state_update.get("generated_files", [])

                            self.progress_callback(
                                "layer_complete",
                                {
                                    "layer_name": layer_name,
                                    "status": status,
                                    "generated_code": generated_code.get(layer_name, ""),
                                    "generated_file": (generated_files[0] if generated_files else None),
                                },
                            )

                    elif node_name == "compare_inventory":
                        comparison = state_update.get("comparison_result", {})
                        if comparison:
                            self.progress_callback("comparison_complete", {"result": comparison})

                    elif node_name == "terraform_init":
                        init_success = state_update.get("init_success", False)
                        init_errors = state_update.get("validation_errors", [])
                        self.progress_callback(
                            "terraform_init_complete",
                            {
                                "success": init_success,
                                "errors": init_errors,
                            },
                        )

                    elif node_name == "terraform_validate":
                        errors = state_update.get("validation_errors", [])
                        self.progress_callback("validation_complete", {"errors": errors})

                    self.progress_callback("node_complete", {"node": node_name})

            return final_state
        finally:
            # Clear the global progress callback
            set_progress_callback(None)

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
    snapshot_name: Optional[str] = None,
    output_dir: str = "./terraform",
    model_id: Optional[str] = None,
    region: Optional[str] = None,
    input_file: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    guardrails_enabled: bool = False,
    guardrails_policy_path: Optional[str] = None,
    guardrails_environment: str = "default",
    guardrails_strict: bool = False,
    guardrails_auto_fix: bool = True,
    best_practices_enabled: bool = True,
) -> GenerationResult:
    """Generate Terraform from a snapshot or export file.

    Args:
        snapshot_name: Name of the snapshot (use this OR input_file)
        output_dir: Output directory for Terraform files
        model_id: Bedrock model ID
        region: AWS region for Bedrock
        input_file: Path to JSON/YAML export file (use this OR snapshot_name)
        progress_callback: Optional callback for progress updates
        guardrails_enabled: Enable guardrails evaluation
        guardrails_policy_path: Path to custom policy file
        guardrails_environment: Environment for policy overrides
        guardrails_strict: Enable strict mode (any violation blocks)
        guardrails_auto_fix: Enable AI auto-fix for AUTO-FIX guardrails
        best_practices_enabled: Enable advisory best-practice guardrails

    Returns:
        GenerationResult
    """
    generator = TerraformGenerator(
        output_dir=output_dir,
        model_id=model_id,
        region=region,
        progress_callback=progress_callback,
        guardrails_enabled=guardrails_enabled,
        guardrails_policy_path=guardrails_policy_path,
        guardrails_environment=guardrails_environment,
        guardrails_strict=guardrails_strict,
        guardrails_auto_fix=guardrails_auto_fix,
        best_practices_enabled=best_practices_enabled,
    )
    return generator.run(snapshot_name=snapshot_name, input_file=input_file)
