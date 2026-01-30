"""EFS resource model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from ..utils.hash import compute_config_hash


@dataclass
class EFSFileSystem:
    """Represents an AWS EFS file system."""

    file_system_id: str
    arn: str
    encryption_enabled: bool
    kms_key_id: Optional[str]
    performance_mode: str  # "generalPurpose" or "maxIO"
    lifecycle_state: str  # "available", "creating", "deleting", "deleted"
    tags: Dict[str, str]
    region: str
    created_at: datetime

    def validate(self) -> bool:
        """Validate EFS file system data.

        Returns:
            True if valid, raises ValueError if invalid
        """
        # Validate file_system_id format (must start with fs-)
        if not re.match(r"^fs-[a-fA-F0-9]+$", self.file_system_id):
            raise ValueError(f"Invalid file_system_id format: {self.file_system_id}. Must match pattern: fs-*")

        # Validate performance_mode
        valid_performance_modes = ["generalPurpose", "maxIO"]
        if self.performance_mode not in valid_performance_modes:
            raise ValueError(
                f"Invalid performance_mode: {self.performance_mode}. "
                f"Must be one of: {', '.join(valid_performance_modes)}"
            )

        # Validate lifecycle_state
        valid_states = ["available", "creating", "deleting", "deleted"]
        if self.lifecycle_state not in valid_states:
            raise ValueError(
                f"Invalid lifecycle_state: {self.lifecycle_state}. Must be one of: {', '.join(valid_states)}"
            )

        return True

    def to_resource_dict(self) -> Dict[str, Any]:
        """Convert to Resource-compatible dictionary.

        Returns:
            Dictionary that can be used to create a Resource object
        """
        # Build raw_config with all EFS-specific attributes
        raw_config = {
            "file_system_id": self.file_system_id,
            "arn": self.arn,
            "encryption_enabled": self.encryption_enabled,
            "kms_key_id": self.kms_key_id,
            "performance_mode": self.performance_mode,
            "lifecycle_state": self.lifecycle_state,
            "region": self.region,
        }

        return {
            "arn": self.arn,
            "resource_type": "efs:file-system",
            "name": self.file_system_id,
            "region": self.region,
            "tags": self.tags,
            "created_at": self.created_at,
            "raw_config": raw_config,
            "config_hash": compute_config_hash(raw_config),
        }
