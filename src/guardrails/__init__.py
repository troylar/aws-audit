"""IaC Generation Guardrails - Policy enforcement for infrastructure code."""

from __future__ import annotations

from .evaluator import GuardrailEvaluator
from .file_parser import parse_rules_file
from .formula import FormulaError, evaluate_formula, validate_formula
from .generator import (
    generate_guardrail,
    generate_guardrail_from_violation,
    generate_guardrails_batch,
    guardrail_to_yaml,
    translate_rules_to_guardrails,
)
from .loader import export_builtin_policy_yaml, load_best_practice_guardrails, load_builtin_guardrails, load_policy
from .models import (
    Action,
    AutoFixError,
    EvaluationResult,
    FixConflictInfo,
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
    "Guardrail",
    "PolicyOverride",
    "GuardrailPolicy",
    "GuardrailEvaluation",
    "ReportSummary",
    "GuardrailReport",
    "FixConflictInfo",
    # Exceptions
    "GuardrailError",
    "GuardrailValidationError",
    "GuardrailLoadError",
    "GuardrailEvaluationError",
    "AutoFixError",
    "FormulaError",
    # Loader functions
    "load_policy",
    "load_builtin_guardrails",
    "load_best_practice_guardrails",
    "export_builtin_policy_yaml",
    # Formula evaluation
    "evaluate_formula",
    "validate_formula",
    # File parsing
    "parse_rules_file",
    # Guardrail generation
    "generate_guardrail",
    "generate_guardrails_batch",
    "generate_guardrail_from_violation",
    "guardrail_to_yaml",
    "translate_rules_to_guardrails",
    # Evaluator
    "GuardrailEvaluator",
    # Reporter functions
    "format_terminal_report",
    "format_guardrails_table",
    "save_json_report",
    "save_yaml_report",
]
