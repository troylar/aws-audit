"""Deterministic pattern comparison engine."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .loader import load_library, load_pattern
from .models import (
    ComparisonReport,
    ExpectViolation,
    GuardrailViolationRef,
    Pattern,
    PatternMatch,
)

logger = logging.getLogger(__name__)


def compliance_report(
    snapshot_names: List[str],
    library_path: str,
    threshold: float = 0.25,
    target_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """Run compare_snapshot across multiple snapshots and aggregate results.

    Args:
        snapshot_names: List of snapshot names to compare.
        library_path: Path to the pattern library directory.
        threshold: Minimum score to include a pattern match.
        target_pattern: If set, compare against only this single pattern.

    Returns:
        A dict with:
        - snapshots: list of per-snapshot summaries
        - pattern_adoption: dict mapping pattern name -> number of snapshots it matched
        - total_snapshots: int
        - accounts_with_no_matches: list of snapshot names with 0 matches
    """
    results: List[Dict[str, Any]] = []
    pattern_adoption: Dict[str, int] = {}
    no_matches: List[str] = []

    for snap_name in snapshot_names:
        try:
            report = compare_snapshot(
                snapshot_name=snap_name,
                library_path=library_path,
                threshold=threshold,
                target_pattern=target_pattern,
            )
            summary: Dict[str, Any] = {
                "snapshot_name": snap_name,
                "match_count": len(report.matches),
                "top_pattern": report.matches[0].pattern.name if report.matches else None,
                "top_score": report.matches[0].score if report.matches else 0.0,
            }
            results.append(summary)

            if not report.matches:
                no_matches.append(snap_name)

            for match in report.matches:
                pname = match.pattern.name
                pattern_adoption[pname] = pattern_adoption.get(pname, 0) + 1
        except Exception as exc:
            results.append(
                {
                    "snapshot_name": snap_name,
                    "error": str(exc),
                }
            )

    return {
        "snapshots": results,
        "pattern_adoption": pattern_adoption,
        "total_snapshots": len(snapshot_names),
        "accounts_with_no_matches": no_matches,
    }


_NOT_FOUND = object()


def resolve_config_path(config: Dict[str, Any], dotted_path: str) -> Any:
    """Traverse a nested dict using a dotted key path.

    Args:
        config: The nested dictionary to traverse.
        dotted_path: Dot-separated key path (e.g., "SSEDescription.Status").

    Returns:
        The value at the path, or _NOT_FOUND sentinel if any key is missing.
    """
    current: Any = config
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return _NOT_FOUND
        current = current[key]
    return current


def evaluate_expect_value(actual: Any, expected: str) -> bool:
    """Evaluate whether an actual value meets an expected condition.

    Supports operator prefixes (>=, <=, >, <, !=) with numeric coercion,
    and exact string match for plain values.

    Args:
        actual: The value found in the resource config.
        expected: The expected value string, optionally operator-prefixed.

    Returns:
        True if the expectation is met, False if violated.
    """
    operators = (">=", "<=", "!=", ">", "<")
    for op in operators:
        if expected.startswith(op + " "):
            rhs_str = expected[len(op) + 1 :].strip()
            try:
                actual_num = float(actual)
                rhs_num = float(rhs_str)
            except (TypeError, ValueError):
                return False
            if op == ">=":
                return actual_num >= rhs_num
            if op == "<=":
                return actual_num <= rhs_num
            if op == ">":
                return actual_num > rhs_num
            if op == "<":
                return actual_num < rhs_num
            if op == "!=":
                return actual_num != rhs_num
    return str(actual) == expected


def score_pattern(
    pattern: Pattern,
    snapshot_types: Dict[str, int],
) -> Tuple[float, Dict[str, Tuple[int, int]], Dict[str, int], Dict[str, int]]:
    """Calculate alignment score between a pattern and snapshot resource types.

    Score = aligned types / total pattern resource types.

    Args:
        pattern: The pattern to score.
        snapshot_types: Mapping of resource type to count from the snapshot.

    Returns:
        Tuple of (score, aligned, missing, extra) where:
        - score: 0.0 to 1.0 fraction of pattern types found in snapshot
        - aligned: {type: (found_count, expected_count)} for types in both
        - missing: {type: expected_count} for types in pattern but not snapshot
        - extra: {type: found_count} for types in snapshot but not in any pattern resource
    """
    pattern_types: Dict[str, int] = {}
    for resource in pattern.resources:
        pattern_types[resource.type] = pattern_types.get(resource.type, 0) + resource.count

    aligned: Dict[str, Tuple[int, int]] = {}
    missing: Dict[str, int] = {}

    for rtype, expected_count in pattern_types.items():
        if rtype in snapshot_types:
            aligned[rtype] = (snapshot_types[rtype], expected_count)
        else:
            missing[rtype] = expected_count

    pattern_type_set: Set[str] = set(pattern_types.keys())
    extra: Dict[str, int] = {rtype: count for rtype, count in snapshot_types.items() if rtype not in pattern_type_set}

    total_pattern_types = len(pattern_types)
    if total_pattern_types == 0:
        score = 0.0
    else:
        score = len(aligned) / total_pattern_types

    return score, aligned, missing, extra


def evaluate_expects(
    pattern: Pattern,
    snapshot_resources: Dict[str, List[Any]],
) -> List[ExpectViolation]:
    """Evaluate expect fields for each pattern resource against snapshot instances.

    Args:
        pattern: The pattern whose expect fields to evaluate.
        snapshot_resources: Mapping of resource type to list of Resource objects.

    Returns:
        List of ExpectViolation for each failed expectation.
    """
    violations: List[ExpectViolation] = []

    for pat_resource in pattern.resources:
        if not pat_resource.expect:
            continue

        instances = snapshot_resources.get(pat_resource.type, [])
        for instance in instances:
            raw_config = getattr(instance, "raw_config", None)
            if raw_config is None:
                logger.warning(
                    "Resource '%s' (%s) has no raw_config; skipping expect evaluation",
                    getattr(instance, "name", "unknown"),
                    pat_resource.type,
                )
                continue

            instance_name = getattr(instance, "name", "") or getattr(instance, "arn", "unknown")

            for config_key, expected_value in pat_resource.expect.items():
                actual = resolve_config_path(raw_config, config_key)
                if actual is _NOT_FOUND:
                    violations.append(
                        ExpectViolation(
                            resource_type=pat_resource.type,
                            resource_name=instance_name,
                            config_key=config_key,
                            actual_value=None,
                            expected_value=expected_value,
                        )
                    )
                elif not evaluate_expect_value(actual, expected_value):
                    violations.append(
                        ExpectViolation(
                            resource_type=pat_resource.type,
                            resource_name=instance_name,
                            config_key=config_key,
                            actual_value=actual,
                            expected_value=expected_value,
                        )
                    )

    return violations


def evaluate_pattern_guardrails(
    pattern: Pattern,
    snapshot_resources: Dict[str, List[Any]],
    guardrails_policy_path: Optional[str] = None,
) -> List[GuardrailViolationRef]:
    """Evaluate referenced guardrails against snapshot resources.

    Args:
        pattern: The pattern whose guardrails to evaluate.
        snapshot_resources: Mapping of resource type to list of Resource objects.
        guardrails_policy_path: Optional custom guardrails policy file path.

    Returns:
        List of GuardrailViolationRef for each guardrail failure.
    """
    if not pattern.guardrails:
        return []

    from src.guardrails.evaluator import GuardrailEvaluator
    from src.guardrails.loader import load_builtin_guardrails, load_policy
    from src.guardrails.models import (
        EvaluationResult,
        Guardrail,
        GuardrailPolicy,
    )

    all_guardrails: List[Guardrail] = load_builtin_guardrails()

    if guardrails_policy_path:
        try:
            policy = load_policy(guardrails_policy_path)
            all_guardrails.extend(policy.guardrails)
        except Exception:
            logger.warning(
                "Failed to load guardrails policy from '%s'; using builtins only",
                guardrails_policy_path,
            )

    guardrail_map: Dict[str, Guardrail] = {g.id: g for g in all_guardrails}

    matched_guardrails: List[Guardrail] = []
    for name in pattern.guardrails:
        if name in guardrail_map:
            matched_guardrails.append(guardrail_map[name])
        else:
            logger.warning(
                "Referenced guardrail '%s' not found in builtin or policy guardrails; skipping",
                name,
            )

    if not matched_guardrails:
        return []

    wrapper_policy = GuardrailPolicy(
        name="pattern-compare",
        version="1.0",
        guardrails=matched_guardrails,
    )
    evaluator = GuardrailEvaluator(
        policy=wrapper_policy,
        auto_fix_enabled=False,
    )

    violations: List[GuardrailViolationRef] = []

    all_resources: List[Any] = []
    for resources in snapshot_resources.values():
        all_resources.extend(resources)

    for resource in all_resources:
        evaluations = evaluator.evaluate_resource(resource)
        for evaluation in evaluations:
            if evaluation.result == EvaluationResult.FAIL:
                violations.append(
                    GuardrailViolationRef(
                        guardrail_name=evaluation.guardrail_id,
                        resource_type=evaluation.resource_type,
                        resource_name=evaluation.resource_name,
                        detail=evaluation.failure_reason,
                    )
                )

    return violations


def compute_coverage(
    matches: List[PatternMatch],
    snapshot_types: Dict[str, int],
) -> Dict[str, int]:
    """Compute unaccounted resource types not covered by any matched pattern.

    Args:
        matches: List of PatternMatch results.
        snapshot_types: Mapping of resource type to count from the snapshot.

    Returns:
        Dict of unaccounted types: {resource_type: count}.
    """
    covered: Set[str] = set()
    for match in matches:
        covered.update(match.aligned.keys())

    return {rtype: count for rtype, count in snapshot_types.items() if rtype not in covered}


def compare_snapshot(
    snapshot_name: str,
    library_path: str,
    threshold: float = 0.25,
    target_pattern: Optional[str] = None,
    guardrails_policy_path: Optional[str] = None,
) -> ComparisonReport:
    """Compare a snapshot against the pattern library.

    Args:
        snapshot_name: Name of the snapshot to compare.
        library_path: Path to the pattern library directory.
        threshold: Minimum score to include a pattern match (0.0-1.0).
        target_pattern: If set, compare against only this single pattern file.
        guardrails_policy_path: Optional custom guardrails policy file path.

    Returns:
        ComparisonReport with all matches above threshold, sorted by score descending.

    Raises:
        FileNotFoundError: If snapshot or target pattern is not found.
    """
    from src.snapshot.storage import SnapshotStorage

    storage = SnapshotStorage()
    snapshot = storage.load_snapshot(snapshot_name)

    snapshot_resources: Dict[str, List[Any]] = defaultdict(list)
    for resource in snapshot.resources:
        snapshot_resources[resource.resource_type].append(resource)

    snapshot_types: Dict[str, int] = {rtype: len(resources) for rtype, resources in snapshot_resources.items()}

    if target_pattern:
        patterns = [load_pattern(target_pattern)]
    else:
        patterns = load_library(library_path)

    matches: List[PatternMatch] = []
    for pattern in patterns:
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        if score < threshold:
            continue

        expect_violations = evaluate_expects(pattern, snapshot_resources)
        guardrail_violations = evaluate_pattern_guardrails(pattern, snapshot_resources, guardrails_policy_path)

        matches.append(
            PatternMatch(
                pattern=pattern,
                score=score,
                aligned=aligned,
                missing=missing,
                extra=extra,
                expect_violations=expect_violations,
                guardrail_violations=guardrail_violations,
            )
        )

    matches.sort(key=lambda m: m.score, reverse=True)

    unaccounted_types = compute_coverage(matches, snapshot_types)

    return ComparisonReport(
        snapshot_name=snapshot_name,
        matches=matches,
        threshold=threshold,
        unaccounted_types=unaccounted_types,
    )
