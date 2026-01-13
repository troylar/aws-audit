"""Protection rule model.

Configuration defining which resources should never be deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RuleType(Enum):
    """Protection rule type."""

    TAG = "tag"
    TYPE = "type"
    AGE = "age"
    COST = "cost"
    NATIVE = "native"


@dataclass
class ProtectionRule:
    """Protection rule entity.

    Configuration defining which resources should never be deleted. Rules are
    evaluated against resources before deletion, with higher priority rules
    taking precedence.

    Rule types and patterns:
        - TAG: Match resources by tag key/value
            patterns: {tag_key: str, tag_values: list, match_mode: str}
        - TYPE: Match resources by AWS type
            patterns: {resource_types: list, match_mode: str}
        - AGE: Protect resources younger than threshold
            patterns: {environment: str}, threshold_value: days
        - COST: Protect resources exceeding cost threshold
            patterns: {action: str}, threshold_value: USD/month
        - NATIVE: Check AWS native protection flags
            patterns: {protection_types: list}

    Validation rules:
        - patterns cannot be empty
        - priority must be 1-100
        - AGE and COST rules require threshold_value >= 0

    Attributes:
        rule_id: Unique identifier
        rule_type: Rule type (tag, type, age, cost, native)
        enabled: Whether rule is active
        priority: Rule precedence (1=highest)
        patterns: Type-specific match patterns
        threshold_value: Numeric threshold for age/cost rules (optional)
        description: Human-readable explanation (optional)
    """

    rule_id: str
    rule_type: RuleType
    enabled: bool
    priority: int
    patterns: dict = field(default_factory=dict)
    threshold_value: Optional[float] = None
    description: Optional[str] = None

    def validate(self) -> bool:
        """Validate rule configuration.

        Returns:
            True if validation passes

        Raises:
            ValueError: If any validation rule fails
        """
        # Threshold requirements
        if self.rule_type in [RuleType.AGE, RuleType.COST]:
            if self.threshold_value is None or self.threshold_value < 0:
                raise ValueError(f"{self.rule_type.value} rule requires positive threshold")

        # Pattern validation
        if not self.patterns:
            raise ValueError("Patterns cannot be empty")

        # Priority range
        if not (1 <= self.priority <= 100):
            raise ValueError("Priority must be 1-100")

        return True

    def matches(self, resource: dict) -> bool:
        """Check if resource matches this rule.

        Args:
            resource: Resource metadata dictionary

        Returns:
            True if resource matches this protection rule
        """
        if not self.enabled:
            return False

        if self.rule_type == RuleType.TAG:
            tag_key = self.patterns.get("tag_key")
            tag_values = self.patterns.get("tag_values", [])
            resource_tag_value = resource.get("tags", {}).get(tag_key)
            return resource_tag_value in tag_values

        elif self.rule_type == RuleType.TYPE:
            resource_types = self.patterns.get("resource_types", [])
            return resource.get("resource_type") in resource_types

        elif self.rule_type == RuleType.AGE:
            resource_age_days = resource.get("age_days", 0)
            return resource_age_days < self.threshold_value

        elif self.rule_type == RuleType.COST:
            resource_cost = resource.get("estimated_monthly_cost", 0)
            return resource_cost >= self.threshold_value

        elif self.rule_type == RuleType.NATIVE:
            return resource.get("has_native_protection", False)

        return False
