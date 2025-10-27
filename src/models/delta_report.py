"""Delta report models for tracking resource changes."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class ResourceChange:
    """Represents a modified resource in a delta report."""

    resource: Any  # Current Resource instance
    baseline_resource: Any  # Baseline Resource instance
    change_type: str  # 'modified'
    old_config_hash: str
    new_config_hash: str
    changes_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'arn': self.resource.arn,
            'resource_type': self.resource.resource_type,
            'name': self.resource.name,
            'region': self.resource.region,
            'change_type': self.change_type,
            'tags': self.resource.tags,
            'old_config_hash': self.old_config_hash,
            'new_config_hash': self.new_config_hash,
            'changes_summary': self.changes_summary,
        }


@dataclass
class DeltaReport:
    """Represents differences between current AWS state and a baseline snapshot."""

    generated_at: datetime
    baseline_snapshot_name: str
    current_snapshot_name: str
    added_resources: List[Any] = field(default_factory=list)  # List[Resource]
    deleted_resources: List[Any] = field(default_factory=list)  # List[Resource]
    modified_resources: List[ResourceChange] = field(default_factory=list)
    baseline_resource_count: int = 0
    current_resource_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'generated_at': self.generated_at.isoformat(),
            'baseline_snapshot_name': self.baseline_snapshot_name,
            'current_snapshot_name': self.current_snapshot_name,
            'added_resources': [r.to_dict() for r in self.added_resources],
            'deleted_resources': [r.to_dict() for r in self.deleted_resources],
            'modified_resources': [r.to_dict() for r in self.modified_resources],
            'baseline_resource_count': self.baseline_resource_count,
            'current_resource_count': self.current_resource_count,
            'summary': {
                'added': len(self.added_resources),
                'deleted': len(self.deleted_resources),
                'modified': len(self.modified_resources),
                'unchanged': self.unchanged_count,
                'total_changes': self.total_changes,
            }
        }

    @property
    def total_changes(self) -> int:
        """Total number of changes detected."""
        return len(self.added_resources) + len(self.deleted_resources) + len(self.modified_resources)

    @property
    def unchanged_count(self) -> int:
        """Number of unchanged resources."""
        # Resources that existed in baseline and still exist unchanged
        return self.baseline_resource_count - len(self.deleted_resources) - len(self.modified_resources)

    @property
    def has_changes(self) -> bool:
        """Whether any changes were detected."""
        return self.total_changes > 0

    def group_by_service(self) -> Dict[str, Dict[str, List]]:
        """Group changes by service type.

        Returns:
            Dictionary mapping service type to changes dict with 'added', 'deleted', 'modified' lists
        """
        grouped = {}

        for resource in self.added_resources:
            service = resource.resource_type
            if service not in grouped:
                grouped[service] = {'added': [], 'deleted': [], 'modified': []}
            grouped[service]['added'].append(resource)

        for resource in self.deleted_resources:
            service = resource.resource_type
            if service not in grouped:
                grouped[service] = {'added': [], 'deleted': [], 'modified': []}
            grouped[service]['deleted'].append(resource)

        for change in self.modified_resources:
            service = change.resource.resource_type
            if service not in grouped:
                grouped[service] = {'added': [], 'deleted': [], 'modified': []}
            grouped[service]['modified'].append(change)

        return grouped
