"""Core guardrail evaluation engine."""

from __future__ import annotations

import dataclasses
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .auto_fix import attempt_auto_fix
from .formula import FormulaError, evaluate_formula
from .models import (
    Action,
    EvaluationResult,
    FixConflictInfo,
    Guardrail,
    GuardrailEvaluation,
    GuardrailPolicy,
    GuardrailReport,
    ReportSummary,
    Severity,
)

logger = logging.getLogger(__name__)


@dataclass
class FixConflict:
    """Represents a conflict where an auto-fix caused a new violation.

    Attributes:
        resource_id: The resource that was fixed.
        original_guardrail_id: The guardrail that triggered the auto-fix.
        conflicting_guardrail_id: The guardrail that now fails after the fix.
        description: Explanation of the conflict.
    """

    resource_id: str
    original_guardrail_id: str
    conflicting_guardrail_id: str
    description: str


# AI evaluation prompt template
AI_EVAL_PROMPT = """You are a cloud security compliance evaluator. Evaluate if the given AWS resource configuration matches the rule condition.

RULE TO EVALUATE:
{rule}

RESOURCE:
Type: {resource_type}
Name: {resource_name}
ARN: {resource_arn}

CONFIGURATION:
{config}

Respond ONLY with JSON (no markdown, no explanation):
{{"matches": true or false, "reason": "brief explanation"}}"""


def _truncate_config(config: Dict[str, Any], max_size: int = 8000) -> str:
    """Truncate config JSON to max size."""
    config_str = json.dumps(config, indent=2, default=str)
    if len(config_str) <= max_size:
        return config_str
    return config_str[:max_size] + "\n... (truncated)"


def evaluate_ai_rule(
    rule_text: str,
    resource_type: str,
    resource_name: str,
    resource_arn: str,
    resource_config: Dict[str, Any],
    bedrock_client: Optional[Any] = None,
) -> Tuple[bool, str]:
    """Evaluate an AI rule against a resource using Bedrock.

    Args:
        rule_text: The AI rule text describing what to check.
        resource_type: Type of the resource.
        resource_name: Name of the resource.
        resource_arn: ARN of the resource.
        resource_config: Resource configuration dictionary.
        bedrock_client: Bedrock client for AI evaluation.

    Returns:
        Tuple of (matches: bool, reason: str).
        matches=True means the rule condition matched (potential violation).
    """
    if bedrock_client is None:
        logger.warning("No Bedrock client provided for AI rule evaluation")
        return False, "AI evaluation skipped - no Bedrock client"

    try:
        prompt = AI_EVAL_PROMPT.format(
            rule=rule_text,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_arn=resource_arn,
            config=_truncate_config(resource_config),
        )

        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "{}")

        # Parse JSON response
        try:
            result = json.loads(content)
            matches = result.get("matches", False)
            reason = result.get("reason", "")
            return bool(matches), reason
        except json.JSONDecodeError:
            # Try to extract boolean from text
            content_lower = content.lower()
            if "true" in content_lower or "matches" in content_lower:
                return True, content
            return False, content

    except Exception as e:
        logger.error(f"AI rule evaluation failed: {e}")
        return False, f"AI evaluation error: {e}"


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
            bedrock_client: Optional Bedrock client for AI rules and auto-fix.
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

        # Get context with environment overrides applied
        self._context = policy.get_context_for_env(environment)

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
        # Support .config (TrackedResource, test mocks) and .raw_config (snapshot Resource)
        resource_config = getattr(resource, "config", None)
        if resource_config is None:
            resource_config = getattr(resource, "raw_config", None) or {}

        for guardrail in self._guardrails:
            # Skip disabled guardrails
            if not guardrail.enabled:
                continue

            # Check if guardrail applies to this resource type
            if not guardrail.matches_resource_type(resource_type):
                continue

            # Evaluate based on guardrail type
            if guardrail.condition:
                # Formula-based condition
                evaluation = self._evaluate_formula(
                    guardrail, resource_type, resource_name, resource_arn, resource_config
                )
            elif guardrail.is_ai_rule():
                # AI-based rule
                evaluation = self._evaluate_ai_rule(
                    guardrail, resource_type, resource_name, resource_arn, resource_config
                )
            else:
                # No condition or AI rule - skip
                continue

            evaluations.append(evaluation)

        return evaluations

    def _evaluate_formula(
        self,
        guardrail: Guardrail,
        resource_type: str,
        resource_name: str,
        resource_arn: str,
        resource_config: Dict[str, Any],
    ) -> GuardrailEvaluation:
        """Evaluate a formula-based condition."""
        result = EvaluationResult.PASS
        failure_reason = ""
        auto_fix_description = ""

        try:
            passed, reason = evaluate_formula(
                guardrail.condition or "",
                resource_config,
                context=self._context,
            )

            if not passed:
                failure_reason = reason
                # Handle auto-fix
                if guardrail.action == Action.AUTO_FIX and self._auto_fix_enabled:
                    fix_success, fix_config, fix_description = self._attempt_auto_fix(
                        guardrail=guardrail,
                        resource_type=resource_type,
                        resource_name=resource_name,
                        resource_arn=resource_arn,
                        resource_config=resource_config,
                    )
                    if fix_success:
                        result = EvaluationResult.AUTO_FIXED
                        auto_fix_description = fix_description
                        resource_id = resource_arn or f"{resource_type}/{resource_name}"
                        if resource_id not in self._auto_fixes:
                            self._auto_fixes[resource_id] = {}
                        self._auto_fixes[resource_id][guardrail.id] = fix_config
                        logger.info(f"Auto-fix applied for {guardrail.id} on {resource_name}: {fix_description}")
                    else:
                        result = EvaluationResult.FAIL
                        logger.warning(f"Auto-fix failed for {guardrail.id} on {resource_name}: {fix_description}")
                else:
                    result = EvaluationResult.FAIL

        except FormulaError as e:
            result = EvaluationResult.FAIL
            failure_reason = str(e)
            logger.error(f"Formula evaluation error for {guardrail.id}: {e}")

        return GuardrailEvaluation(
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

    def _evaluate_ai_rule(
        self,
        guardrail: Guardrail,
        resource_type: str,
        resource_name: str,
        resource_arn: str,
        resource_config: Dict[str, Any],
    ) -> GuardrailEvaluation:
        """Evaluate an AI-based rule."""
        ai_rule = guardrail.get_ai_rule()
        if not ai_rule:
            return GuardrailEvaluation(
                guardrail_id=guardrail.id,
                guardrail_short_description=guardrail.short_description,
                severity=guardrail.severity,
                action=guardrail.action,
                resource_type=resource_type,
                resource_name=resource_name,
                resource_arn=resource_arn,
                result=EvaluationResult.SKIPPED,
                failure_reason="No AI rule defined",
            )

        rule_text, rule_type = ai_rule

        # Evaluate with AI
        matches, reason = evaluate_ai_rule(
            rule_text=rule_text,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_arn=resource_arn,
            resource_config=resource_config,
            bedrock_client=self._bedrock_client,
        )

        # Determine result based on rule type
        # For ai_fail_if/ai_warn_if/ai_notify_if, matches=True means violation
        if matches:
            result = EvaluationResult.FAIL
            failure_reason = reason
        else:
            result = EvaluationResult.PASS
            failure_reason = ""

        # Override severity based on rule type
        severity = guardrail.severity
        if rule_type == "fail":
            # ai_fail_if -> CRITICAL/HIGH severity
            if severity not in (Severity.CRITICAL, Severity.HIGH):
                severity = Severity.HIGH
        elif rule_type == "warn":
            # ai_warn_if -> MEDIUM severity
            severity = Severity.MEDIUM
        elif rule_type == "notify":
            # ai_notify_if -> LOW/INFO severity
            if severity not in (Severity.LOW, Severity.INFO):
                severity = Severity.LOW

        return GuardrailEvaluation(
            guardrail_id=guardrail.id,
            guardrail_short_description=guardrail.short_description,
            severity=severity,
            action=guardrail.action,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_arn=resource_arn,
            result=result,
            failure_reason=failure_reason if result == EvaluationResult.FAIL else "",
        )

    def _attempt_auto_fix(
        self,
        guardrail: Guardrail,
        resource_type: str,
        resource_name: str,
        resource_arn: str,
        resource_config: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any], str]:
        """Attempt to auto-fix a guardrail violation."""

        # Create a simple resource-like object for the auto_fix function
        class ResourceProxy:
            def __init__(self) -> None:
                self.resource_type = resource_type
                self.name = resource_name
                self.arn = resource_arn
                self.config = resource_config

        return attempt_auto_fix(
            guardrail=guardrail,
            resource=ResourceProxy(),
            output_format=self._output_format,
            bedrock_client=self._bedrock_client,
        )

    def evaluate_all(
        self,
        resources: List[Any],
        snapshot_name: str = "",
        progress_callback: Optional[Callable[..., None]] = None,
        validate_fixes: bool = True,
    ) -> GuardrailReport:
        """Evaluate all resources against the policy.

        Args:
            resources: List of TrackedResource objects.
            snapshot_name: Name of the source snapshot.
            progress_callback: Optional callback for progress updates.
                Supports two signatures:
                - Simple: callback(current, total)
                - Rich: callback(current, total, **kwargs) with guardrail_id, resource_name,
                        passed, failed, auto_fixed, warnings
            validate_fixes: Whether to validate that fixes don't cause conflicts.

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

        all_evaluations: List[GuardrailEvaluation] = []
        total = len(resources)
        passed_count = 0
        failed_count = 0
        auto_fixed_count = 0
        warnings_count = 0

        for i, resource in enumerate(resources):
            resource_name = getattr(resource, "name", str(i))
            evaluations = self.evaluate_resource(resource)

            # Track last guardrail evaluated for this resource
            last_guardrail_id = ""
            for evaluation in evaluations:
                report.add_evaluation(evaluation)
                all_evaluations.append(evaluation)
                last_guardrail_id = evaluation.guardrail_id

                # Track counts
                if evaluation.result == EvaluationResult.PASS:
                    passed_count += 1
                elif evaluation.result == EvaluationResult.FAIL:
                    if evaluation.severity in (Severity.LOW, Severity.INFO):
                        warnings_count += 1
                    else:
                        failed_count += 1
                elif evaluation.result == EvaluationResult.AUTO_FIXED:
                    auto_fixed_count += 1

            if progress_callback:
                try:
                    # Try rich callback signature first
                    progress_callback(
                        i + 1,
                        total,
                        guardrail_id=last_guardrail_id,
                        resource_name=resource_name,
                        passed=passed_count,
                        failed=failed_count,
                        auto_fixed=auto_fixed_count,
                        warnings=warnings_count,
                    )
                except TypeError:
                    # Fall back to simple signature
                    progress_callback(i + 1, total)

        # Check for blocking violations
        blocking_violations = report.get_blocking_violations()
        if blocking_violations:
            report.blocked = True
            report.block_reason = f"{len(blocking_violations)} CRITICAL/HIGH violations with BLOCK action"

        # Post-fix validation: detect conflicts
        if validate_fixes and self._auto_fixes:
            conflicts = self.validate_fixes(resources, all_evaluations)
            for conflict in conflicts:
                report.fix_conflicts.append(
                    FixConflictInfo(
                        resource_id=conflict.resource_id,
                        original_guardrail_id=conflict.original_guardrail_id,
                        conflicting_guardrail_id=conflict.conflicting_guardrail_id,
                        description=conflict.description,
                    )
                )
            if conflicts:
                logger.warning(
                    f"Post-fix validation found {len(conflicts)} conflict(s) where auto-fixes caused new violations"
                )
                # Add to block reason if conflicts found
                if report.blocked:
                    report.block_reason += f"; {len(conflicts)} fix conflict(s) detected"
                else:
                    report.blocked = True
                    report.block_reason = (
                        f"{len(conflicts)} fix conflict(s) detected - auto-fixes caused new violations"
                    )

        report.completed_at = datetime.now(timezone.utc)
        return report

    def get_auto_fixes(self) -> Dict[str, Dict[str, Any]]:
        """Get accumulated auto-fixes to apply to resources.

        Returns:
            Dict mapping resource_id to configuration changes.
        """
        return self._auto_fixes.copy()

    def validate_fixes(
        self,
        resources: List[Any],
        original_evaluations: List[GuardrailEvaluation],
    ) -> List[FixConflict]:
        """Validate that auto-fixes don't cause new guardrail violations.

        This performs post-fix validation by:
        1. Identifying resources that had auto-fixes applied
        2. Merging fix configs into original resource configs
        3. Re-evaluating against all guardrails
        4. Flagging any NEW violations as conflicts

        Args:
            resources: Original list of resources.
            original_evaluations: Evaluations from first pass.

        Returns:
            List of FixConflict objects describing conflicts found.
        """
        conflicts: List[FixConflict] = []

        if not self._auto_fixes:
            return conflicts

        # Build lookup maps
        resource_map: Dict[str, Any] = {}
        for resource in resources:
            resource_arn = getattr(resource, "arn", "")
            resource_type = getattr(resource, "resource_type", "")
            resource_name = getattr(resource, "name", "")
            resource_id = resource_arn or f"{resource_type}/{resource_name}"
            resource_map[resource_id] = resource

        # Track which guardrails triggered fixes for each resource
        fix_sources: Dict[str, List[str]] = {}
        for evaluation in original_evaluations:
            if evaluation.result == EvaluationResult.AUTO_FIXED:
                resource_id = evaluation.resource_arn or f"{evaluation.resource_type}/{evaluation.resource_name}"
                if resource_id not in fix_sources:
                    fix_sources[resource_id] = []
                fix_sources[resource_id].append(evaluation.guardrail_id)

        # Track original failures to distinguish from new violations
        original_failures: Dict[str, set] = {}
        for evaluation in original_evaluations:
            if evaluation.result == EvaluationResult.FAIL:
                resource_id = evaluation.resource_arn or f"{evaluation.resource_type}/{evaluation.resource_name}"
                if resource_id not in original_failures:
                    original_failures[resource_id] = set()
                original_failures[resource_id].add(evaluation.guardrail_id)

        # Re-evaluate each fixed resource
        for resource_id, fix_configs in self._auto_fixes.items():
            if resource_id not in resource_map:
                continue

            resource = resource_map[resource_id]
            original_config = getattr(resource, "config", {}) or {}

            # Merge all fixes into the config
            fixed_config = self._merge_configs(original_config, fix_configs)

            # Create a proxy resource with the fixed config
            resource_type = getattr(resource, "resource_type", "")
            resource_name = getattr(resource, "name", "")
            resource_arn = getattr(resource, "arn", "")

            class FixedResourceProxy:
                def __init__(self, rtype: str, rname: str, rarn: str, config: Dict) -> None:
                    self.resource_type = rtype
                    self.name = rname
                    self.arn = rarn
                    self.config = config

            fixed_resource = FixedResourceProxy(resource_type, resource_name, resource_arn, fixed_config)

            # Re-evaluate with fixed config
            new_evaluations = self.evaluate_resource(fixed_resource)

            # Check for new failures
            original_fail_ids = original_failures.get(resource_id, set())
            source_guardrails = fix_sources.get(resource_id, [])

            for evaluation in new_evaluations:
                if evaluation.result == EvaluationResult.FAIL:
                    # Is this a NEW failure (not from original evaluation)?
                    if evaluation.guardrail_id not in original_fail_ids:
                        # This is a conflict - the fix caused a new violation
                        for source_id in source_guardrails:
                            conflicts.append(
                                FixConflict(
                                    resource_id=resource_id,
                                    original_guardrail_id=source_id,
                                    conflicting_guardrail_id=evaluation.guardrail_id,
                                    description=(
                                        f"Auto-fix for {source_id} caused {evaluation.guardrail_id} to fail: "
                                        f"{evaluation.failure_reason}"
                                    ),
                                )
                            )

        return conflicts

    def _merge_configs(
        self,
        original: Dict[str, Any],
        fixes: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Deep merge fix configs into original config.

        Args:
            original: Original resource configuration.
            fixes: Dict of guardrail_id -> fix_config.

        Returns:
            Merged configuration with all fixes applied.
        """
        import copy

        result = copy.deepcopy(original)

        for guardrail_id, fix_config in fixes.items():
            result = self._deep_merge(result, fix_config)

        return result

    def _deep_merge(self, base: Dict, overlay: Dict) -> Dict:
        """Recursively merge overlay dict into base dict."""
        import copy

        result = copy.deepcopy(base)

        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result
