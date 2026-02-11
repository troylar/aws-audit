"""Output formatting for pattern comparison and library display."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from .models import ComparisonReport, Pattern


def format_pattern_list(patterns: List[Pattern], as_json: bool = False) -> str:
    """Format a list of patterns for terminal display or JSON output.

    Args:
        patterns: Patterns to display.
        as_json: If True, return JSON string instead of Rich table.

    Returns:
        Formatted string.
    """
    if as_json:
        items = []
        for p in patterns:
            items.append(
                {
                    "name": p.name,
                    "description": p.description,
                    "version": p.version,
                    "tags": p.tags,
                    "resource_count": len(p.resources),
                    "owner": p.owner,
                }
            )
        return json.dumps(items, indent=2)

    if not patterns:
        return "No patterns found."

    console = Console(record=True, width=120)
    table = Table(title="Pattern Library")
    table.add_column("Name", style="cyan")
    table.add_column("Version", justify="right")
    table.add_column("Description")
    table.add_column("Tags")
    table.add_column("Resources", justify="right")
    table.add_column("Owner")

    for p in patterns:
        table.add_row(
            p.name,
            str(p.version),
            p.description,
            ", ".join(p.tags) if p.tags else "",
            str(len(p.resources)),
            p.owner,
        )

    console.print(table)
    return console.export_text()


def format_pattern_detail(pattern: Pattern, as_json: bool = False) -> str:
    """Format detailed pattern view.

    Args:
        pattern: Pattern to display.
        as_json: If True, return JSON string.

    Returns:
        Formatted string.
    """
    if as_json:
        return json.dumps(pattern.to_dict(), indent=2)

    lines: List[str] = []
    lines.append(f"Pattern: {pattern.name} (v{pattern.version})")
    lines.append(f"Description: {pattern.description}")
    lines.append(f"Owner: {pattern.owner}")
    lines.append(f"Tags: {', '.join(pattern.tags) if pattern.tags else '(none)'}")

    if pattern.guardrails:
        lines.append(f"Guardrails: {', '.join(pattern.guardrails)}")

    if pattern.source_snapshot:
        lines.append(f"Source Snapshot: {pattern.source_snapshot}")
    if pattern.source_account:
        lines.append(f"Source Account: {pattern.source_account}")

    lines.append("")
    lines.append(f"Resources ({len(pattern.resources)}):")
    for r in pattern.resources:
        count_str = f"count: {r.count}"
        lines.append(f"  {r.type}  ({count_str})")
        if r.description:
            lines.append(f"    {r.description}")
        if r.expect:
            for key, value in r.expect.items():
                lines.append(f"    expect {key} = {value}")

    return "\n".join(lines)


def format_terminal_report(report: ComparisonReport) -> str:
    """Format comparison report for terminal display.

    Args:
        report: ComparisonReport to format.

    Returns:
        Rich-formatted string.
    """
    lines: List[str] = []

    if not report.matches:
        lines.append(f"No patterns matched above {report.threshold * 100:.0f}% threshold.")
        return "\n".join(lines)

    # Combined coverage
    total_types = len(report.unaccounted_types)
    covered_types = 0
    all_aligned: set[str] = set()
    for m in report.matches:
        all_aligned.update(m.aligned.keys())
    covered_types = len(all_aligned)
    total_snapshot_types = covered_types + total_types

    lines.append("=== Combined Coverage ===")
    lines.append("")
    lines.append(
        f"  {len(report.matches)} pattern(s) matched. Together they account for "
        f"{covered_types} of {total_snapshot_types} resource types in your snapshot "
        f"({_pct(covered_types, total_snapshot_types)} coverage)."
    )

    if report.unaccounted_types:
        unaccounted = ", ".join(f"{t} ({c})" for t, c in sorted(report.unaccounted_types.items()))
        lines.append(f"\n  Unaccounted resources: {unaccounted}")
    else:
        lines.append("\n  Unaccounted resources: (none)")

    lines.append("")

    # Per-pattern reports
    for match in report.matches:
        p = match.pattern
        pct = f"{match.score * 100:.0f}%"
        total_resource_types = len(match.aligned) + len(match.missing)
        lines.append(f"--- {p.name} ({pct} match) ---")
        lines.append("")

        # Aligned
        if match.aligned:
            lines.append(f"  Aligned ({len(match.aligned)}/{total_resource_types} resource types):")
            for rtype, (found, expected) in sorted(match.aligned.items()):
                suffix = ""
                if found != expected:
                    suffix = " (count mismatch)"
                lines.append(f"    {rtype:<30} {found} found, {expected} expected{suffix}")
            lines.append("")

        # Missing
        if match.missing:
            lines.append(f"  Missing ({len(match.missing)} resource types):")
            for rtype, expected in sorted(match.missing.items()):
                lines.append(f"    {rtype:<30} 0 found, {expected} expected")
            lines.append("")

        # Extra
        if match.extra:
            lines.append(f"  Extra ({len(match.extra)} resource types):")
            for rtype, found in sorted(match.extra.items()):
                lines.append(f"    {rtype:<30} {found} found (not in pattern)")
            lines.append("")

        # Expect violations
        if match.expect_violations:
            lines.append(f"  Design-choice violations ({len(match.expect_violations)}):")
            for v in match.expect_violations:
                lines.append(f"    {v.resource_type}  {v.config_key} = {v.actual_value}")
                lines.append(f"                    pattern expects: {v.expected_value}")
            lines.append("")

        # Guardrail violations
        if match.guardrail_violations:
            lines.append(f"  Guardrail violations ({len(match.guardrail_violations)}):")
            current_guardrail = None
            for gv in match.guardrail_violations:
                if gv.guardrail_name != current_guardrail:
                    lines.append(f"    {gv.guardrail_name}:")
                    current_guardrail = gv.guardrail_name
                lines.append(f"      {gv.resource_type}  {gv.detail}")
            lines.append("")

    # Guidance
    for match in report.matches:
        if match.guidance:
            lines.append("=== Guidance (AI-generated) ===")
            lines.append("")
            for line in match.guidance.split("\n"):
                lines.append(f"  {line}")
            lines.append("")
            break

    if report.coverage_summary:
        lines.append("=== Coverage Summary ===")
        lines.append("")
        lines.append(f"  {report.coverage_summary}")
        lines.append("")

    return "\n".join(lines)


def format_json_report(report: ComparisonReport) -> Dict[str, Any]:
    """Convert ComparisonReport to a JSON-serializable dict.

    Args:
        report: ComparisonReport to convert.

    Returns:
        JSON-serializable dictionary.
    """
    matches = []
    for m in report.matches:
        match_dict: Dict[str, Any] = {
            "pattern_name": m.pattern.name,
            "pattern_version": m.pattern.version,
            "score": m.score,
            "aligned": {k: {"found": v[0], "expected": v[1]} for k, v in m.aligned.items()},
            "missing": m.missing,
            "extra": m.extra,
            "expect_violations": [
                {
                    "resource_type": v.resource_type,
                    "resource_name": v.resource_name,
                    "config_key": v.config_key,
                    "actual_value": v.actual_value,
                    "expected_value": v.expected_value,
                }
                for v in m.expect_violations
            ],
            "guardrail_violations": [
                {
                    "guardrail_name": gv.guardrail_name,
                    "resource_type": gv.resource_type,
                    "resource_name": gv.resource_name,
                    "detail": gv.detail,
                }
                for gv in m.guardrail_violations
            ],
        }
        if m.guidance is not None:
            match_dict["guidance"] = m.guidance
        matches.append(match_dict)

    return {
        "snapshot_name": report.snapshot_name,
        "threshold": report.threshold,
        "matches": matches,
        "unaccounted_types": report.unaccounted_types,
        "coverage_summary": report.coverage_summary,
    }


def format_compliance_report(data: Dict[str, Any], as_json: bool = False) -> str:
    """Format a compliance report for terminal or JSON output.

    Args:
        data: Compliance report dict from comparator.compliance_report().
        as_json: If True, return JSON string instead of terminal table.

    Returns:
        Formatted string.
    """
    if as_json:
        return json.dumps(data, indent=2)

    lines: List[str] = []
    total = data.get("total_snapshots", 0)
    lines.append(f"Compliance Report ({total} snapshots)")
    lines.append("")

    snapshots = data.get("snapshots", [])
    if snapshots:
        lines.append("Per-snapshot summary:")
        for snap in snapshots:
            name = snap.get("snapshot_name", "unknown")
            if "error" in snap:
                lines.append(f"  {name}: ERROR - {snap['error']}")
            else:
                count = snap.get("match_count", 0)
                top = snap.get("top_pattern") or "(none)"
                lines.append(f"  {name}: {count} match(es), top pattern: {top}")
        lines.append("")

    adoption = data.get("pattern_adoption", {})
    if adoption:
        lines.append("Pattern adoption:")
        for pname, count in sorted(adoption.items()):
            lines.append(f"  {pname}: {count} snapshot(s)")
        lines.append("")

    no_matches = data.get("accounts_with_no_matches", [])
    if no_matches:
        lines.append("Accounts with no matches:")
        for name in no_matches:
            lines.append(f"  - {name}")
        lines.append("")

    return "\n".join(lines)


def _pct(part: int, total: int) -> str:
    """Format percentage string."""
    if total == 0:
        return "0%"
    return f"{part / total * 100:.0f}%"
