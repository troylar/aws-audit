"""IaC Generation Guardrails - Policy enforcement for infrastructure code."""

from __future__ import annotations

from .evaluator import GuardrailEvaluator, evaluate_condition
from .loader import load_builtin_guardrails, load_policy
from .models import (
    Action,
    AutoFixError,
    Condition,
    EvaluationResult,
    Guardrail,
    GuardrailError,
    GuardrailEvaluation,
    GuardrailEvaluationError,
    GuardrailLoadError,
    GuardrailPolicy,
    GuardrailReport,
    GuardrailValidationError,
    PolicyOverride,
    ReportSummary,
    Severity,
)
from .reporter import (
    format_guardrails_table,
    format_terminal_report,
    save_json_report,
    save_yaml_report,
)

__all__ = [
    # Enums
    "Severity",
    "Action",
    "EvaluationResult",
    # Models
    "Condition",
    "Guardrail",
    "PolicyOverride",
    "GuardrailPolicy",
    "GuardrailEvaluation",
    "ReportSummary",
    "GuardrailReport",
    # Exceptions
    "GuardrailError",
    "GuardrailValidationError",
    "GuardrailLoadError",
    "GuardrailEvaluationError",
    "AutoFixError",
    # Loader functions
    "load_policy",
    "load_builtin_guardrails",
    # Evaluator
    "evaluate_condition",
    "GuardrailEvaluator",
    # Reporter functions
    "format_terminal_report",
    "format_guardrails_table",
    "save_json_report",
    "save_yaml_report",
]
