"""Report generation for guardrail evaluations."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import (
    Action,
    EvaluationResult,
    Guardrail,
    GuardrailEvaluation,
    GuardrailReport,
    Severity,
)


def _report_from_dict(report_dict: Dict[str, Any]) -> GuardrailReport:
    """Convert a dict (from to_dict()) back to a GuardrailReport-like object.

    Args:
        report_dict: Dictionary representation of a GuardrailReport.

    Returns:
        A GuardrailReport object reconstructed from the dict.
    """
    from datetime import datetime

    from .models import ReportSummary

    summary_dict = report_dict.get("summary", {})
    summary = ReportSummary(
        total_resources=summary_dict.get("total_resources", 0),
        total_evaluations=summary_dict.get("total_evaluations", 0),
        passed=summary_dict.get("passed", 0),
        failed=summary_dict.get("failed", 0),
        warnings=summary_dict.get("warnings", 0),
        auto_fixed=summary_dict.get("auto_fixed", 0),
        skipped=summary_dict.get("skipped", 0),
    )

    evaluations_data = report_dict.get("evaluations", [])
    evaluations: List[GuardrailEvaluation] = []
    for e in evaluations_data:
        eval_obj = GuardrailEvaluation(
            guardrail_id=e.get("guardrail_id", ""),
            guardrail_short_description=e.get("guardrail_short_description", ""),
            resource_type=e.get("resource_type", ""),
            resource_name=e.get("resource_name", ""),
            resource_arn=e.get("resource_arn", ""),
            result=EvaluationResult[e.get("result", "PASS")],
            severity=Severity[e.get("severity", "INFO")],
            action=Action[e.get("action", "WARN")],
            failure_reason=e.get("failure_reason"),
            auto_fix_applied=e.get("auto_fix_applied"),
        )
        evaluations.append(eval_obj)

    # Parse started_at if present, otherwise use current time
    started_at_str = report_dict.get("started_at")
    if started_at_str and isinstance(started_at_str, str):
        try:
            started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        except ValueError:
            started_at = datetime.now()
    else:
        started_at = datetime.now()

    report = GuardrailReport(
        run_id=report_dict.get("run_id", ""),
        snapshot_name=report_dict.get("snapshot_name", ""),
        policy_name=report_dict.get("policy_name", ""),
        policy_version=report_dict.get("policy_version", ""),
        started_at=started_at,
    )
    report.summary = summary
    report.evaluations = evaluations
    report.blocked = report_dict.get("blocked", False)
    report.block_reason = report_dict.get("block_reason") or ""

    return report


def format_terminal_report(
    report: GuardrailReport | Dict[str, Any],
    console: Optional[Console] = None,
) -> None:
    """Print a Rich-formatted guardrails report to terminal.

    Args:
        report: GuardrailReport object or dict (from to_dict()) to display.
        console: Optional Rich Console (uses default if None).
    """
    if console is None:
        console = Console()

    # Handle both GuardrailReport object and dict (serialized form)
    if isinstance(report, dict):
        report = _report_from_dict(report)

    # Summary section
    summary = report.summary
    console.print()
    console.print("  \U0001f6e1\ufe0f  GUARDRAILS SUMMARY", style="bold")
    console.print()

    # Create summary text with icons
    passed_text = Text(f"  \u2705 Passed:     {summary.passed} resources")
    console.print(passed_text)

    if summary.auto_fixed > 0:
        auto_fixed_text = Text(f"  \u26a1 Auto-Fixed: {summary.auto_fixed} resources")
        console.print(auto_fixed_text)

    if summary.failed > 0:
        failed_text = Text(f"  \u274c Blocked:    {summary.failed} resources", style="red")
        console.print(failed_text)

    if summary.warnings > 0:
        warn_text = Text(f"  \u26a0\ufe0f  Warnings:   {summary.warnings} resources", style="yellow")
        console.print(warn_text)

    console.print()

    # Blocking violations section
    blocking_violations = report.get_blocking_violations()
    if blocking_violations:
        console.print(
            "  \u274c BLOCKED VIOLATIONS (must fix before generation):",
            style="bold red",
        )
        console.print()

        for eval in blocking_violations:
            _print_violation(console, eval)

        console.print()

    # Auto-fixed section
    auto_fixed_evals = [e for e in report.evaluations if e.result == EvaluationResult.AUTO_FIXED]
    if auto_fixed_evals:
        console.print(
            "  \u26a1 AUTO-FIXED (will be applied to generated code):",
            style="bold green",
        )
        console.print()

        # Group by guardrail ID
        by_guardrail: Dict[str, List[GuardrailEvaluation]] = {}
        for eval in auto_fixed_evals:
            if eval.guardrail_id not in by_guardrail:
                by_guardrail[eval.guardrail_id] = []
            by_guardrail[eval.guardrail_id].append(eval)

        for guardrail_id, evals in by_guardrail.items():
            first = evals[0]
            console.print(f"  {guardrail_id} [{first.severity.value}] {first.guardrail_short_description}")
            resource_names = [e.resource_name for e in evals[:3]]
            resource_list = ", ".join(resource_names)
            if len(evals) > 3:
                resource_list += f", +{len(evals) - 3} more"
            console.print(f"    Resources: {resource_list}")
            if first.auto_fix_applied:
                console.print(f"    Applied: {first.auto_fix_applied}")
            console.print()

    # Warning violations section
    warn_evals = [e for e in report.evaluations if e.result == EvaluationResult.FAIL and e.action == Action.WARN]
    if warn_evals:
        console.print("  \u26a0\ufe0f  WARNINGS:", style="bold yellow")
        console.print()

        for eval in warn_evals[:5]:  # Show first 5 warnings
            console.print(f"  {eval.guardrail_id} [{eval.severity.value}] {eval.guardrail_short_description}")
            console.print(f"    Resource: {eval.resource_type}/{eval.resource_name}")

        if len(warn_evals) > 5:
            console.print(f"    ... and {len(warn_evals) - 5} more warnings")

        console.print()

    # Final status
    if report.blocked:
        console.print(
            f"  Generation blocked. Fix {len(blocking_violations)} CRITICAL/HIGH violations and re-run.",
            style="bold red",
        )
    else:
        console.print("  Generation complete. All blocking checks passed.", style="bold green")

    console.print()


def _print_violation(console: Console, eval: GuardrailEvaluation) -> None:
    """Print a single violation to the console."""
    console.print(f"  {eval.guardrail_id} [{eval.severity.value}] {eval.guardrail_short_description}")
    console.print(f"    Resource: {eval.resource_type}/{eval.resource_name}")
    if eval.failure_reason:
        console.print(f"    Fix: {eval.failure_reason}")
    console.print()


def save_json_report(
    report: GuardrailReport,
    output_path: str,
) -> None:
    """Save guardrails report as JSON file.

    Args:
        report: GuardrailReport to save.
        output_path: Path for output JSON file.
    """
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)


def save_yaml_report(
    report: GuardrailReport,
    output_path: str,
) -> None:
    """Save guardrails report as YAML file.

    Args:
        report: GuardrailReport to save.
        output_path: Path for output YAML file.
    """
    with open(output_path, "w") as f:
        yaml.dump(report.to_dict(), f, default_flow_style=False, sort_keys=False)


def format_guardrails_table(
    guardrails: List[Guardrail],
    console: Optional[Console] = None,
) -> None:
    """Print a table of guardrails.

    Args:
        guardrails: List of guardrails to display.
        console: Optional Rich Console (uses default if None).
    """
    if console is None:
        console = Console()

    if not guardrails:
        console.print("  No guardrails found.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Description")
    table.add_column("Severity")
    table.add_column("Action")

    for g in guardrails:
        # Color severity
        severity_style = _severity_style(g.severity)
        severity_text = Text(g.severity.value, style=severity_style)

        # Color action
        action_style = _action_style(g.action)
        action_text = Text(g.action.value, style=action_style)

        table.add_row(
            g.id,
            g.short_description,
            severity_text,
            action_text,
        )

    console.print(table)
    console.print(f"\n{len(guardrails)} guardrails shown")


def _severity_style(severity: Severity) -> str:
    """Get Rich style for severity level."""
    return {
        Severity.CRITICAL: "red bold",
        Severity.HIGH: "red",
        Severity.MEDIUM: "yellow",
        Severity.LOW: "blue",
        Severity.INFO: "dim",
    }.get(severity, "")


def _action_style(action: Action) -> str:
    """Get Rich style for action type."""
    return {
        Action.BLOCK: "red",
        Action.AUTO_FIX: "green",
        Action.WARN: "yellow",
    }.get(action, "")
