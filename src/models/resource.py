"""Resource data model representing a single AWS resource."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Resource:
    """Represents a single AWS resource captured in a snapshot."""

    arn: str
    resource_type: str
    name: str
    region: str
    config_hash: str
    raw_config: Optional[Dict[str, Any]] = None  # Optional for backward compatibility with v1.0 snapshots
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    source: str = "direct_api"  # Collection source: "config" or "direct_api"

    def to_dict(self) -> Dict[str, Any]:
        """Convert resource to dictionary for serialization.

        Note: raw_config is included in v1.1+ snapshots for drift analysis support.
        """
        return {
            "arn": self.arn,
            "type": self.resource_type,
            "name": self.name,
            "region": self.region,
            "tags": self.tags,
            "config_hash": self.config_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "raw_config": self.raw_config if self.raw_config is not None else {},
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Resource":
        """Create resource from dictionary.

        Supports both v1.0 (without raw_config) and v1.1+ (with raw_config) snapshots.
        """
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"])
            else:
                created_at = data["created_at"]  # Already a datetime

        return cls(
            arn=data["arn"],
            resource_type=data["type"],
            name=data["name"],
            region=data["region"],
            config_hash=data["config_hash"],
            raw_config=data.get("raw_config"),  # Optional for backward compatibility
            tags=data.get("tags", {}),
            created_at=created_at,
            source=data.get("source", "direct_api"),  # Default for older snapshots
        )

    def validate(self) -> bool:
        """Validate resource data integrity.

        Returns:
            True if valid, raises ValueError if invalid
        """
        # Validate ARN format
        arn_pattern = r"^arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:.*$"
        if not re.match(arn_pattern, self.arn):
            raise ValueError(f"Invalid ARN format: {self.arn}")

        # Validate config_hash is 64-character hex string (SHA256)
        if not re.match(r"^[a-fA-F0-9]{64}$", self.config_hash):
            raise ValueError(f"Invalid config_hash: {self.config_hash}. Must be 64-character SHA256 hex string.")

        # Validate region format
        valid_regions = ["global"] + [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
            "ap-northeast-2",
            "ca-central-1",
            "sa-east-1",
            "ap-south-1",
        ]
        # Basic validation - starts with region pattern or is 'global'
        if self.region != "global" and not any(self.region.startswith(r[:6]) for r in valid_regions if r != "global"):
            # Allow it anyway - AWS adds new regions regularly
            pass

        return True

    @property
    def service(self) -> str:
        """Extract service name from resource type.

        Example: 'iam:role' -> 'iam'
        """
        return self.resource_type.split(":")[0] if ":" in self.resource_type else self.resource_type
