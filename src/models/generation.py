"""Data models for Terraform/CDK code generation."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ResourceMap:
    """Bidirectional mapping between AWS resource IDs and Terraform references.

    Enables replacing hardcoded AWS IDs in generated code with proper
    Terraform resource references for dependency management.
    """

    id_to_ref: Dict[str, str] = field(default_factory=dict)
    ref_to_id: Dict[str, str] = field(default_factory=dict)
    id_to_type: Dict[str, str] = field(default_factory=dict)

    def add(self, aws_id: str, tf_ref: str, resource_type: str) -> None:
        """Register a mapping between an AWS ID and Terraform reference.

        Args:
            aws_id: AWS resource identifier (e.g., ARN, ID)
            tf_ref: Terraform resource reference (e.g., aws_vpc.main)
            resource_type: AWS resource type (e.g., ec2:vpc)
        """
        self.id_to_ref[aws_id] = tf_ref
        self.ref_to_id[tf_ref] = aws_id
        self.id_to_type[aws_id] = resource_type

    def get_reference(self, aws_id: str, attribute: str = "id") -> Optional[str]:
        """Get Terraform reference for an AWS ID.

        Args:
            aws_id: AWS resource identifier
            attribute: Terraform attribute to reference (default: id)

        Returns:
            Terraform reference string (e.g., aws_vpc.main.id) or None if not found
        """
        tf_ref = self.id_to_ref.get(aws_id)
        if tf_ref is None:
            return None
        return f"{tf_ref}.{attribute}"

    def replace_ids_in_code(self, code: str) -> str:
        """Replace hardcoded AWS IDs in code with Terraform references.

        Scans generated code for known AWS IDs and replaces them with
        proper Terraform resource references.

        Args:
            code: Generated Terraform/CDK code

        Returns:
            Code with AWS IDs replaced by Terraform references
        """
        result = code
        for aws_id, tf_ref in self.id_to_ref.items():
            quoted_patterns = [
                f'"{aws_id}"',
                f"'{aws_id}'",
            ]
            for pattern in quoted_patterns:
                if pattern in result:
                    result = result.replace(pattern, f"{tf_ref}.id")
        return result


@dataclass
class TrackedResource:
    """A resource tracked for IaC generation with generation metadata.

    Extends the base inventory resource data with fields needed during
    the code generation workflow.
    """

    arn: str
    resource_type: str
    name: str
    region: str
    tags: Dict[str, str] = field(default_factory=dict)
    raw_config: Dict[str, Any] = field(default_factory=dict)
    layer: str = ""
    terraform_name: str = ""
    terraform_code: str = ""
    is_generated: bool = False
    error: Optional[str] = None

    @classmethod
    def from_inventory(cls, resource: Dict[str, Any]) -> TrackedResource:
        """Create TrackedResource from inventory resource dictionary.

        Args:
            resource: Resource dictionary from snapshot/inventory

        Returns:
            TrackedResource instance
        """
        return cls(
            arn=resource.get("arn", ""),
            resource_type=resource.get("type", resource.get("resource_type", "")),
            name=resource.get("name", ""),
            region=resource.get("region", ""),
            tags=resource.get("tags", {}),
            raw_config=resource.get("raw_config", {}),
        )

    def get_terraform_name(self) -> str:
        """Generate a valid Terraform resource name from the resource name.

        Sanitizes the name to comply with Terraform naming rules:
        - Lowercase alphanumeric and underscores only
        - Must start with a letter
        - Invalid characters replaced with underscores

        Returns:
            Valid Terraform resource name
        """
        if self.terraform_name:
            return self.terraform_name

        name = self.name.lower()
        name = re.sub(r"[^a-z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name)
        name = name.strip("_")

        if not name:
            name = "resource"

        if not name[0].isalpha():
            name = "r_" + name

        self.terraform_name = name
        return name


@dataclass
class LambdaCode:
    """Lambda function code storage and extraction metadata.

    Tracks how Lambda code was stored and provides extraction capability
    for embedding in generated IaC.
    """

    function_name: str
    runtime: str
    handler: str
    storage_type: str
    code_stored: bool
    code_base64: Optional[str] = None
    code_file_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    s3_version: Optional[str] = None
    image_uri: Optional[str] = None
    code_sha256: Optional[str] = None
    code_size_bytes: Optional[int] = None

    @classmethod
    def from_resource(cls, resource: TrackedResource) -> LambdaCode:
        """Create LambdaCode from a Lambda TrackedResource.

        Extracts code storage information from the resource's raw_config.

        Args:
            resource: TrackedResource for a Lambda function

        Returns:
            LambdaCode instance
        """
        config = resource.raw_config
        code_config = config.get("Code", {})

        storage_type = "unknown"
        if code_config.get("ImageUri"):
            storage_type = "image"
        elif code_config.get("S3Bucket"):
            storage_type = "s3"
        elif code_config.get("ZipFile"):
            storage_type = "inline"

        return cls(
            function_name=resource.name,
            runtime=config.get("Runtime", ""),
            handler=config.get("Handler", ""),
            storage_type=storage_type,
            code_stored=bool(code_config.get("ZipFile")),
            code_base64=code_config.get("ZipFile"),
            s3_bucket=code_config.get("S3Bucket"),
            s3_key=code_config.get("S3Key"),
            s3_version=code_config.get("S3ObjectVersion"),
            image_uri=code_config.get("ImageUri"),
            code_sha256=config.get("CodeSha256"),
            code_size_bytes=config.get("CodeSize"),
        )

    def extract_to(self, output_dir: Path) -> Optional[str]:
        """Extract Lambda code to a zip file.

        Decodes base64 code content and writes to a zip file in the
        specified output directory.

        Args:
            output_dir: Directory to write the zip file

        Returns:
            Path to extracted zip file, or None if no inline code
        """
        if not self.code_base64:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", self.function_name)
        zip_path = output_dir / f"{safe_name}.zip"

        try:
            code_bytes = base64.b64decode(self.code_base64)
            zip_path.write_bytes(code_bytes)
            self.code_file_path = str(zip_path)
            return str(zip_path)
        except Exception:
            return None


@dataclass
class Layer:
    """A generation layer grouping resources by dependency order.

    Layers are processed in order to ensure resources are generated
    with proper dependencies (e.g., VPCs before subnets).
    """

    name: str
    order: int
    resources: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    generated_code: str = ""
    validation_errors: List[str] = field(default_factory=list)
    attempt_count: int = 0
