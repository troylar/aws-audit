"""Tests for SafetyChecker class.

Test coverage for protection rule evaluation against resources.
"""

from __future__ import annotations

from src.models.protection_rule import ProtectionRule, RuleType
from src.restore.safety import SafetyChecker


class TestSafetyChecker:
    """Test suite for SafetyChecker class."""

    def test_init_with_empty_rules(self) -> None:
        """Test initialization with empty rules list."""
        checker = SafetyChecker(rules=[])
        assert checker.rules == []

    def test_init_loads_rules_from_list(self) -> None:
        """Test initialization loads rules from provided list."""
        rules = [
            ProtectionRule(
                rule_id="rule_001",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
            )
        ]

        checker = SafetyChecker(rules=rules)
        assert len(checker.rules) == 1
        assert checker.rules[0].rule_id == "rule_001"

    def test_is_protected_returns_false_for_unprotected_resource(self) -> None:
        """Test is_protected returns (False, None) for unprotected resource."""
        checker = SafetyChecker(rules=[])
        resource = {"resource_id": "i-001", "tags": {}}

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is False
        assert reason is None

    def test_is_protected_by_tag_rule(self) -> None:
        """Test resource protected by tag-based rule."""
        rules = [
            ProtectionRule(
                rule_id="rule_tag",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true", "critical"]},
                description="Protect tagged resources",
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-protected",
            "tags": {"Protection": "true", "Environment": "prod"},
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        assert "rule_tag" in reason or "Protect tagged resources" in reason or "Protection" in reason

    def test_is_protected_by_type_rule(self) -> None:
        """Test resource protected by type-based rule."""
        rules = [
            ProtectionRule(
                rule_id="rule_type",
                rule_type=RuleType.TYPE,
                enabled=True,
                priority=1,
                patterns={"resource_types": ["AWS::IAM::Role", "AWS::KMS::Key"]},
                description="Never delete IAM roles",
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "admin-role",
            "resource_type": "AWS::IAM::Role",
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        assert "type" in reason.lower() or "IAM" in reason

    def test_is_protected_by_age_rule(self) -> None:
        """Test resource protected by age-based rule."""
        rules = [
            ProtectionRule(
                rule_id="rule_age",
                rule_type=RuleType.AGE,
                enabled=True,
                priority=1,
                patterns={"environment": "production"},
                threshold_value=30.0,
                description="Production resources must be 30+ days old",
            )
        ]

        checker = SafetyChecker(rules=rules)

        # Young resource (protected)
        young_resource = {
            "resource_id": "i-young",
            "age_days": 15,
        }

        is_protected, reason = checker.is_protected(young_resource)

        assert is_protected is True
        assert "age" in reason.lower() or "30" in reason

        # Old resource (not protected)
        old_resource = {
            "resource_id": "i-old",
            "age_days": 45,
        }

        is_protected, reason = checker.is_protected(old_resource)

        assert is_protected is False

    def test_is_protected_by_cost_rule(self) -> None:
        """Test resource protected by cost-based rule."""
        rules = [
            ProtectionRule(
                rule_id="rule_cost",
                rule_type=RuleType.COST,
                enabled=True,
                priority=1,
                patterns={"action": "block"},
                threshold_value=5000.0,
                description="Block deletion of resources >$5000/month",
            )
        ]

        checker = SafetyChecker(rules=rules)

        # Expensive resource (protected)
        expensive_resource = {
            "resource_id": "db-prod",
            "estimated_monthly_cost": 6000.0,
        }

        is_protected, reason = checker.is_protected(expensive_resource)

        assert is_protected is True
        assert "cost" in reason.lower() or "5000" in reason

        # Cheap resource (not protected)
        cheap_resource = {
            "resource_id": "i-test",
            "estimated_monthly_cost": 10.0,
        }

        is_protected, reason = checker.is_protected(cheap_resource)

        assert is_protected is False

    def test_disabled_rule_does_not_protect(self) -> None:
        """Test disabled protection rule does not protect resources."""
        rules = [
            ProtectionRule(
                rule_id="rule_disabled",
                rule_type=RuleType.TAG,
                enabled=False,  # Disabled!
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-001",
            "tags": {"Protection": "true"},
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is False
        assert reason is None

    def test_multiple_rules_first_match_wins(self) -> None:
        """Test with multiple rules, first matching rule determines protection."""
        rules = [
            ProtectionRule(
                rule_id="rule_high_priority",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,  # Higher priority
                patterns={"tag_key": "Critical", "tag_values": ["yes"]},
                description="High priority protection",
            ),
            ProtectionRule(
                rule_id="rule_low_priority",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=2,  # Lower priority
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
                description="Low priority protection",
            ),
        ]

        checker = SafetyChecker(rules=rules)

        # Resource matches first rule
        resource = {
            "resource_id": "i-critical",
            "tags": {"Critical": "yes", "Protection": "true"},
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        assert "High priority" in reason or "Critical" in reason

    def test_check_all_protections_returns_all_matching_rules(self) -> None:
        """Test check_all_protections returns all matching rules."""
        rules = [
            ProtectionRule(
                rule_id="rule_001",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
                description="Tag protection",
            ),
            ProtectionRule(
                rule_id="rule_002",
                rule_type=RuleType.TYPE,
                enabled=True,
                priority=2,
                patterns={"resource_types": ["AWS::EC2::Instance"]},
                description="Type protection",
            ),
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-001",
            "resource_type": "AWS::EC2::Instance",
            "tags": {"Protection": "true"},
        }

        matching_rules = checker.check_all_protections(resource)

        assert len(matching_rules) == 2
        assert matching_rules[0].rule_id == "rule_001"
        assert matching_rules[1].rule_id == "rule_002"

    def test_check_all_protections_empty_for_unprotected_resource(self) -> None:
        """Test check_all_protections returns empty list for unprotected resource."""
        rules = [
            ProtectionRule(
                rule_id="rule_001",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-unprotected",
            "tags": {"Environment": "dev"},
        }

        matching_rules = checker.check_all_protections(resource)

        assert len(matching_rules) == 0

    def test_check_all_protections_skips_disabled_rules(self) -> None:
        """Test check_all_protections skips disabled rules."""
        rules = [
            ProtectionRule(
                rule_id="rule_enabled",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
            ),
            ProtectionRule(
                rule_id="rule_disabled",
                rule_type=RuleType.TAG,
                enabled=False,  # Disabled
                priority=2,
                patterns={"tag_key": "Protection", "tag_values": ["true"]},
            ),
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-001",
            "tags": {"Protection": "true"},
        }

        matching_rules = checker.check_all_protections(resource)

        # Only enabled rule should match
        assert len(matching_rules) == 1
        assert matching_rules[0].rule_id == "rule_enabled"

    def test_protection_reason_with_tag_rule_no_description(self) -> None:
        """Test _get_protection_reason generates default reason for tag rule without description."""
        rules = [
            ProtectionRule(
                rule_id="rule_tag_no_desc",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={"tag_key": "Critical", "tag_values": ["yes"]},
                # No description provided
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-001",
            "tags": {"Critical": "yes"},
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        # Should include tag key and value in default reason
        assert "Critical" in reason
        assert "yes" in reason
        assert "rule_tag_no_desc" in reason

    def test_protection_reason_with_type_rule_no_description(self) -> None:
        """Test _get_protection_reason generates default reason for type rule without description."""
        rules = [
            ProtectionRule(
                rule_id="rule_type_no_desc",
                rule_type=RuleType.TYPE,
                enabled=True,
                priority=1,
                patterns={"resource_types": ["AWS::RDS::DBInstance"]},
                # No description provided
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "db-001",
            "resource_type": "AWS::RDS::DBInstance",
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        # Should include resource type in default reason
        assert "AWS::RDS::DBInstance" in reason
        assert "type" in reason.lower() or "protected" in reason.lower()
        assert "rule_type_no_desc" in reason

    def test_protection_reason_with_age_rule_no_description(self) -> None:
        """Test _get_protection_reason generates default reason for age rule without description."""
        rules = [
            ProtectionRule(
                rule_id="rule_age_no_desc",
                rule_type=RuleType.AGE,
                enabled=True,
                priority=1,
                patterns={},
                threshold_value=14.0,
                # No description provided
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-young",
            "age_days": 7,
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        # Should include age days and threshold in default reason
        assert "7" in reason
        assert "14" in reason
        assert "age" in reason.lower() or "days" in reason.lower()
        assert "rule_age_no_desc" in reason

    def test_protection_reason_with_cost_rule_no_description(self) -> None:
        """Test _get_protection_reason generates default reason for cost rule without description."""
        rules = [
            ProtectionRule(
                rule_id="rule_cost_no_desc",
                rule_type=RuleType.COST,
                enabled=True,
                priority=1,
                patterns={},
                threshold_value=100.0,
                # No description provided
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "db-expensive",
            "estimated_monthly_cost": 500.0,
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        # Should include cost and threshold in default reason
        assert "500" in reason
        assert "100" in reason
        assert "cost" in reason.lower()
        assert "rule_cost_no_desc" in reason

    def test_is_protected_by_native_rule(self) -> None:
        """Test resource protected by native protection rule."""
        rules = [
            ProtectionRule(
                rule_id="rule_native",
                rule_type=RuleType.NATIVE,
                enabled=True,
                priority=1,
                patterns={"protection": "termination_protection"},
                description="Native protection enabled",
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-protected-instance",
            "has_native_protection": True,
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        assert "native" in reason.lower() or "rule_native" in reason

    def test_protection_reason_with_native_rule_no_description(self) -> None:
        """Test _get_protection_reason generates default reason for native rule without description."""
        rules = [
            ProtectionRule(
                rule_id="rule_native_no_desc",
                rule_type=RuleType.NATIVE,
                enabled=True,
                priority=1,
                patterns={},
                # No description provided
            )
        ]

        checker = SafetyChecker(rules=rules)
        resource = {
            "resource_id": "i-native-protected",
            "has_native_protection": True,
        }

        is_protected, reason = checker.is_protected(resource)

        assert is_protected is True
        # Should include "native" in reason
        assert "native" in reason.lower() or "rule_native_no_desc" in reason
