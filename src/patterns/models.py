"""Data models for the Infrastructure Pattern Library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PatternResource:
    """A resource entry within a Pattern."""

    type: str
    count: int
    description: str = ""
    expect: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type, "count": self.count}
        if self.description:
            d["description"] = self.description
        if self.expect:
            d["expect"] = dict(self.expect)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PatternResource:
        return cls(
            type=data["type"],
            count=data.get("count", 1),
            description=data.get("description", ""),
            expect=data.get("expect", {}),
        )


@dataclass
class Pattern:
    """A reusable infrastructure architecture definition."""

    name: str
    description: str
    version: int
    tags: List[str]
    owner: str
    resources: List[PatternResource]
    guardrails: List[str] = field(default_factory=list)
    source_snapshot: Optional[str] = None
    source_account: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": list(self.tags),
            "owner": self.owner,
            "resources": [r.to_dict() for r in self.resources],
        }
        if self.guardrails:
            d["guardrails"] = list(self.guardrails)
        if self.source_snapshot:
            d["source_snapshot"] = self.source_snapshot
        if self.source_account:
            d["source_account"] = self.source_account
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Pattern:
        resources = [PatternResource.from_dict(r) for r in data.get("resources", [])]
        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", 1),
            tags=data.get("tags", []),
            owner=data.get("owner", ""),
            resources=resources,
            guardrails=data.get("guardrails", []),
            source_snapshot=data.get("source_snapshot"),
            source_account=data.get("source_account"),
        )


@dataclass
class ExpectViolation:
    """An expect field mismatch found during comparison."""

    resource_type: str
    resource_name: str
    config_key: str
    actual_value: Any
    expected_value: str


@dataclass
class GuardrailViolationRef:
    """A guardrail failure found during comparison."""

    guardrail_name: str
    resource_type: str
    resource_name: str
    detail: str


@dataclass
class PatternMatch:
    """Result of comparing one pattern against one snapshot."""

    pattern: Pattern
    score: float
    aligned: Dict[str, Tuple[int, int]]
    missing: Dict[str, int]
    extra: Dict[str, int]
    expect_violations: List[ExpectViolation]
    guardrail_violations: List[GuardrailViolationRef]
    guidance: Optional[str] = None


@dataclass
class ComparisonReport:
    """Top-level result of a comparison run."""

    snapshot_name: str
    matches: List[PatternMatch]
    threshold: float
    coverage_summary: Optional[str] = None
    unaccounted_types: Dict[str, int] = field(default_factory=dict)
