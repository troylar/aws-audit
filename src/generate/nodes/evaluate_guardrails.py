"""LangGraph node for evaluating guardrails against inventory resources."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, Optional

from ..state import GenerationState, emit_progress

logger = logging.getLogger(__name__)


def _get_bedrock_client() -> Optional[Any]:
    """Get a Bedrock runtime client for auto-fix.

    Returns:
        boto3 Bedrock runtime client, or None if unavailable.
    """
    try:
        import boto3

        return boto3.client("bedrock-runtime")
    except Exception as e:
        logger.warning(f"Failed to create Bedrock client for auto-fix: {e}")
        return None


def evaluate_guardrails(state: GenerationState) -> Dict[str, Any]:
    """LangGraph node that evaluates guardrails against resources.

    Reads from state:
        - resources: List[TrackedResource] - Parsed resources
        - best_practices_enabled: bool - Whether best-practice advisory mode is on
        - guardrails_enabled: bool - Whether full guardrails enforcement is enabled
        - guardrails_policy_path: str - Path to policy file
        - guardrails_environment: str - Environment for overrides
        - guardrails_strict: bool - Fail on any violation
        - guardrails_auto_fix: bool - Whether to enable AI auto-fix
        - output_format: str - Target output format

    Writes to state:
        - guardrails_report: Dict - Serialized GuardrailReport
        - guardrails_blocked: bool - Whether to block generation
        - guardrails_auto_fixes: Dict - Fixes to apply to resources

    Returns:
        State updates dictionary.
    """
    guardrails_enabled = state.get("guardrails_enabled", False)
    best_practices_enabled = state.get("best_practices_enabled", True)

    # Skip entirely if both are disabled
    if not guardrails_enabled and not best_practices_enabled:
        return {
            "guardrails_blocked": False,
            "guardrails_report": None,
            "guardrails_auto_fixes": {},
        }

    # Import here to avoid circular imports and loading if not needed
    from src.guardrails import GuardrailEvaluator, load_best_practice_guardrails, load_builtin_guardrails, load_policy
    from src.guardrails.models import Action, EvaluationResult, GuardrailPolicy

    resources = state.get("resources", [])
    policy_path = state.get("guardrails_policy_path")
    environment = state.get("guardrails_environment", "default")
    strict_mode = state.get("guardrails_strict", False)
    auto_fix_enabled = state.get("guardrails_auto_fix", True)
    snapshot_name = state.get("snapshot_name", "")
    output_format = state.get("output_format", "terraform")

    emit_progress(
        "guardrails_start",
        {
            "total_resources": len(resources),
            "mode": "enforcement" if guardrails_enabled else "best_practices",
        },
    )

    if guardrails_enabled:
        # Full enforcement mode (existing behavior)
        if policy_path:
            policy = load_policy(policy_path, environment=environment)
        else:
            builtin = load_builtin_guardrails()
            policy = GuardrailPolicy(
                name="builtin",
                version="1.0",
                description="Built-in guardrails",
                guardrails=builtin,
            )

        # Get Bedrock client for auto-fix if enabled
        bedrock_client = None
        if auto_fix_enabled:
            bedrock_client = _get_bedrock_client()
            if bedrock_client:
                logger.info("Auto-fix enabled with Bedrock AI")
            else:
                logger.warning("Auto-fix requested but Bedrock client unavailable")

        evaluator = GuardrailEvaluator(
            policy=policy,
            auto_fix_enabled=auto_fix_enabled and bedrock_client is not None,
            bedrock_client=bedrock_client,
            environment=environment,
            output_format=output_format,
        )
    else:
        # Best-practice advisory mode: load only best-practice guardrails,
        # downgrade all actions to WARN, disable auto-fix
        bp_guardrails = load_best_practice_guardrails()
        advisory_guardrails = [dataclasses.replace(g, action=Action.WARN) for g in bp_guardrails]
        policy = GuardrailPolicy(
            name="best-practices",
            version="1.0",
            description="Built-in best-practice guardrails (advisory)",
            guardrails=advisory_guardrails,
        )
        evaluator = GuardrailEvaluator(
            policy=policy,
            auto_fix_enabled=False,
            environment=environment,
            output_format=output_format,
        )

    # Progress callback with rich data
    def progress_callback(
        current: int,
        total: int,
        guardrail_id: str = "",
        resource_name: str = "",
        passed: int = 0,
        failed: int = 0,
        auto_fixed: int = 0,
        warnings: int = 0,
    ) -> None:
        emit_progress(
            "guardrails_progress",
            {
                "current": current,
                "total": total,
                "guardrail_id": guardrail_id,
                "resource_name": resource_name,
                "passed": passed,
                "failed": failed,
                "auto_fixed": auto_fixed,
                "warnings": warnings,
            },
        )

    # Evaluate all resources
    report = evaluator.evaluate_all(
        resources=resources,
        snapshot_name=snapshot_name,
        progress_callback=progress_callback,
    )

    # Determine if blocked
    blocked = False

    if guardrails_enabled:
        # Full enforcement: check blocking logic
        if strict_mode:
            failed_evals = [e for e in report.evaluations if e.result == EvaluationResult.FAIL]
            if failed_evals:
                blocked = True
                report.blocked = True
                report.block_reason = f"Strict mode: {len(failed_evals)} violations found"
        else:
            blocked = report.blocked
    # Best-practice mode never blocks

    auto_fixes = evaluator.get_auto_fixes()

    emit_progress(
        "guardrails_complete",
        {
            "passed": report.summary.passed,
            "failed": report.summary.failed,
            "auto_fixed": report.summary.auto_fixed,
            "warnings": report.summary.warnings,
            "blocked": blocked,
            "block_reason": report.block_reason if blocked else "",
            "mode": "enforcement" if guardrails_enabled else "best_practices",
        },
    )

    return {
        "guardrails_blocked": blocked,
        "guardrails_report": report.to_dict(),
        "guardrails_auto_fixes": auto_fixes,
    }
