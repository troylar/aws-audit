"""Core guardrail evaluation engine."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .auto_fix import attempt_auto_fix
from .models import (
    Action,
    Condition,
    EvaluationResult,
    Guardrail,
    GuardrailEvaluation,
    GuardrailPolicy,
    GuardrailReport,
    ReportSummary,
)

logger = logging.getLogger(__name__)


def evaluate_condition(
    condition: Condition,
    resource_config: Dict[str, Any],
) -> Tuple[bool, str]:
    """Evaluate a condition against resource configuration.

    Args:
        condition: Condition to evaluate.
        resource_config: Resource's configuration dictionary.

    Returns:
        Tuple of (passed: bool, reason: str).
    """
    # Get the attribute value from config (supports nested paths like "Tags.Environment")
    value = _get_nested_value(resource_config, condition.attribute)

    operator = condition.operator
    expected = condition.value

    # Handle each operator
    if operator == "exists":
        if value is None:
            return False, f"Attribute '{condition.attribute}' does not exist"
        return True, ""

    if operator == "not_exists":
        if value is not None:
            return False, f"Attribute '{condition.attribute}' exists but should not"
        return True, ""

    if operator == "equals":
        if value == expected:
            return True, ""
        return False, f"Attribute '{condition.attribute}' equals {value}, expected {expected}"

    if operator == "not_equals":
        if value != expected:
            return True, ""
        return False, f"Attribute '{condition.attribute}' equals {value}, should not equal {expected}"

    if operator == "contains":
        if isinstance(value, str) and isinstance(expected, str):
            if expected in value:
                return True, ""
            return False, f"Attribute '{condition.attribute}' ({value}) does not contain '{expected}'"
        if isinstance(value, (list, tuple)):
            if expected in value:
                return True, ""
            return False, f"Attribute '{condition.attribute}' list does not contain '{expected}'"
        return False, f"Attribute '{condition.attribute}' is not a string or list"

    if operator == "not_contains":
        if isinstance(value, str) and isinstance(expected, str):
            if expected not in value:
                return True, ""
            return False, f"Attribute '{condition.attribute}' ({value}) contains '{expected}'"
        if isinstance(value, (list, tuple)):
            if expected not in value:
                return True, ""
            return False, f"Attribute '{condition.attribute}' list contains '{expected}'"
        return True, ""  # If not string/list, not_contains passes

    if operator == "matches":
        if value is None:
            return False, f"Attribute '{condition.attribute}' not found for regex match"
        try:
            pattern = re.compile(str(expected))
            if pattern.match(str(value)):
                return True, ""
            return False, f"Attribute '{condition.attribute}' ({value}) does not match pattern '{expected}'"
        except re.error as e:
            return False, f"Invalid regex pattern: {e}"

    if operator == "in":
        if not isinstance(expected, list):
            return False, f"Operator 'in' requires list value, got {type(expected)}"
        if value in expected:
            return True, ""
        return False, f"Attribute '{condition.attribute}' ({value}) not in allowed values: {expected}"

    if operator == "not_in":
        if not isinstance(expected, list):
            return False, f"Operator 'not_in' requires list value, got {type(expected)}"
        if value not in expected:
            return True, ""
        return False, f"Attribute '{condition.attribute}' ({value}) is in forbidden values: {expected}"

    if operator == "greater_than":
        if value is None:
            return False, f"Attribute '{condition.attribute}' not found for comparison"
        if expected is None:
            return False, "Expected value not specified for greater_than comparison"
        try:
            if float(value) > float(expected):
                return True, ""
            return False, f"Attribute '{condition.attribute}' ({value}) is not greater than {expected}"
        except (TypeError, ValueError) as e:
            return False, f"Cannot compare values: {e}"

    if operator == "less_than":
        if value is None:
            return False, f"Attribute '{condition.attribute}' not found for comparison"
        if expected is None:
            return False, "Expected value not specified for less_than comparison"
        try:
            if float(value) < float(expected):
                return True, ""
            return False, f"Attribute '{condition.attribute}' ({value}) is not less than {expected}"
        except (TypeError, ValueError) as e:
            return False, f"Cannot compare values: {e}"

    return False, f"Unknown operator: {operator}"


def _get_nested_value(config: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a config dictionary using dot notation.

    Args:
        config: Configuration dictionary.
        path: Dot-separated path (e.g., "Tags.Environment").

    Returns:
        The value at the path, or None if not found.
    """
    parts = path.split(".")
    current = config

    for part in parts:
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]

    return current


class GuardrailEvaluator:
    """Evaluates resources against guardrails."""

    def __init__(
        self,
        policy: GuardrailPolicy,
        auto_fix_enabled: bool = True,
        bedrock_client: Optional[Any] = None,
        environment: str = "default",
        output_format: str = "terraform",
    ) -> None:
        """Initialize the evaluator.

        Args:
            policy: GuardrailPolicy to evaluate against.
            auto_fix_enabled: Whether to attempt AI auto-fixes.
            bedrock_client: Optional Bedrock client for auto-fix.
            environment: Environment name for policy overrides.
            output_format: Target IaC format (terraform, cdk-typescript, cdk-python).
        """
        self._policy = policy
        self._auto_fix_enabled = auto_fix_enabled
        self._bedrock_client = bedrock_client
        self._environment = environment
        self._output_format = output_format
        self._auto_fixes: Dict[str, Dict[str, Any]] = {}

        # Get guardrails with environment overrides applied
        self._guardrails = policy.get_guardrails_for_env(environment)

    def evaluate_resource(
        self,
        resource: Any,  # TrackedResource from inventory
    ) -> List[GuardrailEvaluation]:
        """Evaluate a single resource against all applicable guardrails.

        Args:
            resource: TrackedResource from inventory.

        Returns:
            List of GuardrailEvaluation results (one per applicable guardrail).
        """
        evaluations: List[GuardrailEvaluation] = []

        resource_type = getattr(resource, "resource_type", "")
        resource_name = getattr(resource, "name", "")
        resource_arn = getattr(resource, "arn", "")
        resource_config = getattr(resource, "config", {}) or {}

        for guardrail in self._guardrails:
            # Skip disabled guardrails
            if not guardrail.enabled:
                continue

            # Check if guardrail applies to this resource type
            if not guardrail.matches_resource_type(resource_type):
                continue

            # Evaluate the condition
            passed, failure_reason = evaluate_condition(guardrail.condition, resource_config)

            result = EvaluationResult.PASS
            auto_fix_description = ""

            if not passed:
                # Determine result based on action
                if guardrail.action == Action.AUTO_FIX and self._auto_fix_enabled:
                    # Attempt auto-fix with Bedrock AI
                    fix_success, fix_config, fix_description = self._attempt_auto_fix(
                        guardrail=guardrail,
                        resource=resource,
                    )
                    if fix_success:
                        result = EvaluationResult.AUTO_FIXED
                        auto_fix_description = fix_description
                        # Store the fix for later application
                        resource_id = resource_arn or f"{resource_type}/{resource_name}"
                        if resource_id not in self._auto_fixes:
                            self._auto_fixes[resource_id] = {}
                        self._auto_fixes[resource_id][guardrail.id] = fix_config
                        logger.info(f"Auto-fix applied for {guardrail.id} on {resource_name}: {fix_description}")
                    else:
                        # Auto-fix failed, mark as FAIL
                        result = EvaluationResult.FAIL
                        logger.warning(f"Auto-fix failed for {guardrail.id} on {resource_name}: {fix_description}")
                else:
                    result = EvaluationResult.FAIL

            evaluation = GuardrailEvaluation(
                guardrail_id=guardrail.id,
                guardrail_short_description=guardrail.short_description,
                severity=guardrail.severity,
                action=guardrail.action,
                resource_type=resource_type,
                resource_name=resource_name,
                resource_arn=resource_arn,
                result=result,
                failure_reason=failure_reason if result == EvaluationResult.FAIL else "",
                auto_fix_applied=auto_fix_description,
            )
            evaluations.append(evaluation)

        return evaluations

    def _attempt_auto_fix(
        self,
        guardrail: Guardrail,
        resource: Any,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """Attempt to auto-fix a guardrail violation.

        Args:
            guardrail: The violated guardrail.
            resource: The resource that violated.

        Returns:
            Tuple of (success, fix_config, description).
        """
        return attempt_auto_fix(
            guardrail=guardrail,
            resource=resource,
            output_format=self._output_format,
            bedrock_client=self._bedrock_client,
        )

    def evaluate_all(
        self,
        resources: List[Any],
        snapshot_name: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> GuardrailReport:
        """Evaluate all resources against the policy.

        Args:
            resources: List of TrackedResource objects.
            snapshot_name: Name of the source snapshot.
            progress_callback: Optional callback(current, total) for progress.

        Returns:
            Complete GuardrailReport with all evaluations.
        """
        run_id = f"gr-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

        report = GuardrailReport(
            run_id=run_id,
            policy_name=self._policy.name,
            policy_version=self._policy.version,
            snapshot_name=snapshot_name,
            started_at=datetime.now(timezone.utc),
            summary=ReportSummary(
                total_resources=len(resources),
                total_evaluations=0,
            ),
        )

        total = len(resources)
        for i, resource in enumerate(resources):
            evaluations = self.evaluate_resource(resource)
            for evaluation in evaluations:
                report.add_evaluation(evaluation)

            if progress_callback:
                progress_callback(i + 1, total)

        # Check for blocking violations
        blocking_violations = report.get_blocking_violations()
        if blocking_violations:
            report.blocked = True
            report.block_reason = f"{len(blocking_violations)} CRITICAL/HIGH violations with BLOCK action"

        report.completed_at = datetime.now(timezone.utc)
        return report

    def get_auto_fixes(self) -> Dict[str, Dict[str, Any]]:
        """Get accumulated auto-fixes to apply to resources.

        Returns:
            Dict mapping resource_id to configuration changes.
        """
        return self._auto_fixes.copy()
