"""Data models for IaC Generation Guardrails."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Severity levels for guardrail violations."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Action(str, Enum):
    """Actions to take when a guardrail violation is detected."""

    BLOCK = "BLOCK"
    AUTO_FIX = "AUTO-FIX"
    WARN = "WARN"


class EvaluationResult(str, Enum):
    """Result of evaluating a guardrail against a resource."""

    PASS = "PASS"
    FAIL = "FAIL"
    AUTO_FIXED = "AUTO_FIXED"
    SKIPPED = "SKIPPED"


@dataclass
class Condition:
    """Evaluation condition for a guardrail.

    Attributes:
        attribute: JSON path to the attribute to check in resource config.
        operator: The comparison operator (equals, exists, contains, matches, etc.).
        value: Expected value (None for exists/not_exists checks).
        type: Type of condition check (attribute_check, nested_check, compound).
    """

    attribute: str
    operator: str
    value: Optional[Any] = None
    type: str = "attribute_check"


@dataclass
class Guardrail:
    """A single guardrail control definition.

    Attributes:
        id: Unique control ID in format GR-{CATEGORY}-{NUMBER} (e.g., GR-ENC-001).
        short_description: Human-readable summary (max 100 chars).
        severity: CRITICAL, HIGH, MEDIUM, LOW, or INFO.
        action: BLOCK, AUTO-FIX, or WARN.
        applies_to: List of resource type patterns this guardrail applies to.
        condition: The evaluation condition.
        ai_context: Context for AI-assisted auto-fix (WHY + HOW TO FIX).
        enabled: Whether this guardrail is active (default True).
        tags: Categorization tags (e.g., compliance, security, encryption).
    """

    id: str
    short_description: str
    severity: Severity
    action: Action
    applies_to: List[str]
    condition: Condition
    ai_context: str = ""
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def matches_resource_type(self, resource_type: str) -> bool:
        """Check if this guardrail applies to a resource type.

        Args:
            resource_type: The resource type to check (e.g., "s3:bucket").

        Returns:
            True if the guardrail applies to this resource type.
        """
        for pattern in self.applies_to:
            if pattern == "*":
                return True
            if pattern == resource_type:
                return True
            # Support wildcard patterns like "ec2:*"
            if pattern.endswith("*") and resource_type.startswith(pattern[:-1]):
                return True
        return False


@dataclass
class PolicyOverride:
    """Environment-specific override for a guardrail.

    Allows modifying severity, action, or disabling a guardrail for specific environments.

    Attributes:
        guardrail_id: ID of the guardrail to override.
        severity: Override severity level (None to keep original).
        action: Override action (None to keep original).
        enabled: Set to False to disable guardrail (None to keep enabled).
    """

    guardrail_id: str
    severity: Optional[Severity] = None
    action: Optional[Action] = None
    enabled: Optional[bool] = None


@dataclass
class GuardrailPolicy:
    """A guardrail policy with optional environment overrides.

    Attributes:
        name: Policy name (e.g., "production", "development").
        version: Policy version string.
        description: Human-readable policy description.
        guardrails: List of guardrail definitions.
        overrides: Environment-specific overrides keyed by environment name.
    """

    name: str
    version: str
    description: str = ""
    guardrails: List[Guardrail] = field(default_factory=list)
    overrides: Dict[str, List[PolicyOverride]] = field(default_factory=dict)

    def get_guardrails_for_env(self, environment: str = "default") -> List[Guardrail]:
        """Get guardrails with environment-specific overrides applied.

        Args:
            environment: Environment name (e.g., "production", "development").

        Returns:
            List of guardrails with overrides applied for the environment.
        """
        result = []
        env_overrides = {o.guardrail_id: o for o in self.overrides.get(environment, [])}

        for gr in self.guardrails:
            if gr.id in env_overrides:
                override = env_overrides[gr.id]
                if override.enabled is False:
                    continue  # Skip disabled guardrails
                # Apply overrides
                gr = dataclasses.replace(
                    gr,
                    severity=override.severity or gr.severity,
                    action=override.action or gr.action,
                )
            result.append(gr)
        return result


@dataclass
class GuardrailEvaluation:
    """Result of evaluating a guardrail against a resource.

    Attributes:
        guardrail_id: ID of the evaluated guardrail.
        guardrail_short_description: Short description for display.
        severity: Severity level of the guardrail.
        action: Action type (BLOCK, AUTO-FIX, WARN).
        resource_type: Type of the evaluated resource.
        resource_name: Name of the resource.
        resource_arn: Full ARN of the resource.
        result: Evaluation outcome (PASS, FAIL, AUTO_FIXED, SKIPPED).
        failure_reason: Why it failed (if FAIL).
        auto_fix_applied: What was changed (if AUTO_FIXED).
        timestamp: When the evaluation occurred.
    """

    guardrail_id: str
    guardrail_short_description: str
    severity: Severity
    action: Action
    resource_type: str
    resource_name: str
    resource_arn: str
    result: EvaluationResult
    failure_reason: str = ""
    auto_fix_applied: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_blocking(self) -> bool:
        """Check if this evaluation should block generation.

        Returns:
            True if this is a failed evaluation with BLOCK action and
            CRITICAL or HIGH severity.
        """
        return (
            self.result == EvaluationResult.FAIL
            and self.action == Action.BLOCK
            and self.severity in (Severity.CRITICAL, Severity.HIGH)
        )


@dataclass
class ReportSummary:
    """Summary statistics for a guardrail report.

    Attributes:
        total_resources: Number of resources evaluated.
        total_evaluations: Total guardrail evaluations (resources × applicable guardrails).
        passed: Number of passing evaluations.
        failed: Number of failed evaluations.
        auto_fixed: Number of auto-fixed evaluations.
        warnings: Number of warning evaluations.
        skipped: Number of skipped evaluations.
        by_severity: Count of evaluations by severity level.
        by_category: Count of evaluations by category (extracted from guardrail ID).
    """

    total_resources: int
    total_evaluations: int
    passed: int = 0
    failed: int = 0
    auto_fixed: int = 0
    warnings: int = 0
    skipped: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)


@dataclass
class GuardrailReport:
    """Complete guardrail evaluation report for a generation run.

    Attributes:
        run_id: Unique identifier for this run.
        policy_name: Name of the policy used.
        policy_version: Version of the policy.
        snapshot_name: Source snapshot name.
        started_at: When the run started.
        completed_at: When the run completed.
        summary: Aggregated statistics.
        evaluations: List of all individual evaluations.
        blocked: Whether generation was blocked.
        block_reason: Why generation was blocked (if blocked).
    """

    run_id: str
    policy_name: str
    policy_version: str
    snapshot_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    summary: ReportSummary = field(default_factory=lambda: ReportSummary(0, 0))
    evaluations: List[GuardrailEvaluation] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""

    def add_evaluation(self, evaluation: GuardrailEvaluation) -> None:
        """Add an evaluation and update summary statistics.

        Args:
            evaluation: The evaluation result to add.
        """
        self.evaluations.append(evaluation)
        self.summary.total_evaluations += 1

        if evaluation.result == EvaluationResult.PASS:
            self.summary.passed += 1
        elif evaluation.result == EvaluationResult.FAIL:
            self.summary.failed += 1
        elif evaluation.result == EvaluationResult.AUTO_FIXED:
            self.summary.auto_fixed += 1
        elif evaluation.result == EvaluationResult.SKIPPED:
            self.summary.skipped += 1

        # Track by severity
        sev = evaluation.severity.value
        self.summary.by_severity[sev] = self.summary.by_severity.get(sev, 0) + 1

        # Track by category (extract from ID like GR-ENC-001 -> ENC)
        parts = evaluation.guardrail_id.split("-")
        category = parts[1] if len(parts) >= 2 else "OTHER"
        self.summary.by_category[category] = self.summary.by_category.get(category, 0) + 1

    def get_blocking_violations(self) -> List[GuardrailEvaluation]:
        """Get all violations that should block generation.

        Returns:
            List of evaluations where is_blocking is True.
        """
        return [e for e in self.evaluations if e.is_blocking]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON output.
        """
        return {
            "run_id": self.run_id,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "snapshot_name": self.snapshot_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "summary": {
                "total_resources": self.summary.total_resources,
                "total_evaluations": self.summary.total_evaluations,
                "passed": self.summary.passed,
                "failed": self.summary.failed,
                "auto_fixed": self.summary.auto_fixed,
                "warnings": self.summary.warnings,
                "skipped": self.summary.skipped,
                "by_severity": self.summary.by_severity,
                "by_category": self.summary.by_category,
            },
            "evaluations": [
                {
                    "guardrail_id": e.guardrail_id,
                    "guardrail_short_description": e.guardrail_short_description,
                    "severity": e.severity.value,
                    "action": e.action.value,
                    "resource_type": e.resource_type,
                    "resource_name": e.resource_name,
                    "resource_arn": e.resource_arn,
                    "result": e.result.value,
                    "failure_reason": e.failure_reason,
                    "auto_fix_applied": e.auto_fix_applied,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.evaluations
            ],
        }


# Exception classes


class GuardrailError(Exception):
    """Base exception for guardrail errors."""

    pass


class GuardrailValidationError(GuardrailError):
    """Raised when guardrail/policy definition is invalid."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__(f"Validation errors: {', '.join(errors)}")


class GuardrailLoadError(GuardrailError):
    """Raised when guardrail/policy file cannot be loaded."""

    pass


class GuardrailEvaluationError(GuardrailError):
    """Raised when evaluation fails unexpectedly."""

    pass


class AutoFixError(GuardrailError):
    """Raised when auto-fix fails."""

    pass
