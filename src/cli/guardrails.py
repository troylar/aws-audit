"""Guardrails CLI commands for standalone compliance checking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..guardrails import (
    GuardrailEvaluator,
    GuardrailPolicy,
    load_builtin_guardrails,
    load_policy,
)
from ..guardrails.models import Severity
from ..guardrails.reporter import format_terminal_report
from ..snapshot.storage import SnapshotStorage

console = Console()

# Create the guardrails command group
guardrails_app = typer.Typer(
    name="guardrails",
    help="Evaluate compliance guardrails against inventory snapshots.",
    no_args_is_help=True,
)


@guardrails_app.command("check")
def check(
    snapshot_name: Optional[str] = typer.Argument(
        None, help="Name of snapshot to evaluate"
    ),
    policy: Optional[str] = typer.Option(
        None,
        "--policy",
        "-p",
        help="Path to custom guardrails policy file (YAML)",
    ),
    env: str = typer.Option(
        "default",
        "--env",
        "-e",
        help="Environment for policy overrides (e.g., dev, staging, prod)",
    ),
    from_file: Optional[str] = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Path to JSON/YAML inventory file (alternative to snapshot)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save report to file (JSON or YAML based on extension)",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table, json, yaml",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Strict mode: exit 1 on any violation (not just CRITICAL/HIGH)",
    ),
) -> None:
    """Evaluate guardrails against an inventory snapshot.

    Checks resources for compliance without generating IaC.
    Useful for CI/CD gates and compliance audits.

    Examples:
        awsinv guardrails check my-snapshot
        awsinv guardrails check my-snapshot --policy ./policy.yaml
        awsinv guardrails check --from-file inventory.yaml --strict
        awsinv guardrails check my-snapshot --output report.json
    """
    # Validate input
    if not snapshot_name and not from_file:
        console.print(
            "[red]Error:[/red] Either provide a snapshot name or use --from-file"
        )
        raise typer.Exit(1)

    # Load resources
    resources = []
    snapshot_display_name = ""

    if from_file:
        # Load from file
        file_path = Path(from_file)
        if not file_path.exists():
            console.print(f"[red]Error:[/red] File not found: {from_file}")
            raise typer.Exit(1)

        snapshot_display_name = file_path.name
        try:
            import yaml

            with open(file_path) as f:
                if file_path.suffix in (".yaml", ".yml"):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            # Extract resources from various formats
            if isinstance(data, dict):
                resources = data.get("resources", [])
            elif isinstance(data, list):
                resources = data
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to load file: {e}")
            raise typer.Exit(1)
    else:
        # Load from snapshot
        try:
            storage = SnapshotStorage()
            snapshot_data = storage.load_snapshot(snapshot_name)
            if not snapshot_data:
                console.print(f"[red]Error:[/red] Snapshot not found: {snapshot_name}")
                raise typer.Exit(1)
            resources = snapshot_data.get("resources", [])
            snapshot_display_name = snapshot_name or ""
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to load snapshot: {e}")
            raise typer.Exit(1)

    # Convert dict resources to objects with attributes if needed
    resource_objects = []
    for r in resources:
        if isinstance(r, dict):
            # Create a simple object with required attributes
            class ResourceWrapper:
                def __init__(self, data: dict):
                    self.resource_type = data.get("resource_type", "unknown")
                    self.name = data.get("name", "unknown")
                    self.arn = data.get("arn", "")
                    self.config = data.get("config", {})

            resource_objects.append(ResourceWrapper(r))
        else:
            resource_objects.append(r)

    # Load policy
    if policy:
        policy_path = Path(policy)
        if not policy_path.exists():
            console.print(f"[red]Error:[/red] Policy file not found: {policy}")
            raise typer.Exit(1)
        loaded_policy = load_policy(str(policy_path), environment=env)
    else:
        # Use built-in guardrails
        builtin = load_builtin_guardrails()
        loaded_policy = GuardrailPolicy(
            name="builtin",
            version="1.0",
            description="Built-in guardrails",
            guardrails=builtin,
        )

    # Create evaluator and run evaluation
    evaluator = GuardrailEvaluator(
        policy=loaded_policy,
        auto_fix_enabled=False,
        environment=env,
    )

    num_resources = len(resource_objects)
    num_guardrails = len(loaded_policy.guardrails)
    console.print(
        f"Evaluating [cyan]{num_resources}[/cyan] resources against "
        f"[cyan]{num_guardrails}[/cyan] guardrails..."
    )
    console.print()

    report = evaluator.evaluate_all(
        resources=resource_objects,
        snapshot_name=snapshot_display_name,
    )

    # Determine exit status
    has_blocking_violations = report.blocked
    has_any_violations = report.summary.failed > 0

    if strict and has_any_violations:
        exit_code = 1
    elif has_blocking_violations:
        exit_code = 1
    else:
        exit_code = 0

    # Output results
    if format == "json":
        console.print(json.dumps(report.to_dict(), indent=2, default=str))
    elif format == "yaml":
        import yaml

        console.print(yaml.dump(report.to_dict(), default_flow_style=False))
    else:
        # Table format (default)
        format_terminal_report(report, console)

    # Save to file if requested
    if output:
        output_path = Path(output)
        try:
            if output_path.suffix == ".json":
                with open(output_path, "w") as f:
                    json.dump(report.to_dict(), f, indent=2, default=str)
            else:
                import yaml

                with open(output_path, "w") as f:
                    yaml.dump(report.to_dict(), f, default_flow_style=False)
            console.print(f"\nReport saved to: {output_path}")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to save report: {e}")

    # Print summary
    console.print()
    if exit_code == 0:
        console.print("[green]All checks passed.[/green]")
    else:
        if strict:
            console.print("[red]Violations found (strict mode).[/red]")
        else:
            console.print("[red]Blocking violations found.[/red]")

    raise typer.Exit(exit_code)


@guardrails_app.command("list")
def list_guardrails(
    policy: Optional[str] = typer.Option(
        None,
        "--policy",
        "-p",
        help="Path to custom guardrails policy file (YAML)",
    ),
    env: str = typer.Option(
        "default",
        "--env",
        "-e",
        help="Environment for policy overrides",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        "-s",
        help="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW, INFO",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (e.g., ENC, NET, TAG, LOG)",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table, json, yaml",
    ),
) -> None:
    """List available guardrails.

    Shows all guardrails from built-in rules or a custom policy file.

    Examples:
        awsinv guardrails list
        awsinv guardrails list --policy ./policy.yaml
        awsinv guardrails list --severity CRITICAL
        awsinv guardrails list --category ENC
        awsinv guardrails list --format json
    """
    # Load guardrails
    if policy:
        policy_path = Path(policy)
        if not policy_path.exists():
            console.print(f"[red]Error:[/red] Policy file not found: {policy}")
            raise typer.Exit(1)
        loaded_policy = load_policy(str(policy_path), environment=env)
        guardrails = loaded_policy.guardrails
    else:
        guardrails = load_builtin_guardrails()

    # Apply filters
    filtered = guardrails

    if severity:
        try:
            sev = Severity[severity.upper()]
            filtered = [g for g in filtered if g.severity == sev]
        except KeyError:
            console.print(
                f"[red]Error:[/red] Invalid severity: {severity}. "
                f"Use: CRITICAL, HIGH, MEDIUM, LOW, INFO"
            )
            raise typer.Exit(1)

    if category:
        # Filter by category in ID (e.g., GR-ENC-001 -> ENC)
        cat_upper = category.upper()
        filtered = [g for g in filtered if f"-{cat_upper}-" in g.id]

    # Output results
    if format == "json":
        data = [
            {
                "id": g.id,
                "description": g.short_description,
                "severity": g.severity.value,
                "action": g.action.value,
                "applies_to": g.applies_to,
            }
            for g in filtered
        ]
        console.print(json.dumps(data, indent=2))
    elif format == "yaml":
        import yaml

        data = [
            {
                "id": g.id,
                "description": g.short_description,
                "severity": g.severity.value,
                "action": g.action.value,
                "applies_to": g.applies_to,
            }
            for g in filtered
        ]
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        # Table format (default)
        if not filtered:
            console.print("[yellow]No guardrails found matching criteria.[/yellow]")
            raise typer.Exit(0)

        table = Table(title="Available Guardrails")
        table.add_column("ID", style="cyan")
        table.add_column("Description")
        table.add_column("Severity", justify="center")
        table.add_column("Action", justify="center")
        table.add_column("Applies To")

        severity_colors = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "orange1",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "blue",
            Severity.INFO: "dim",
        }

        for g in filtered:
            sev_color = severity_colors.get(g.severity, "white")
            table.add_row(
                g.id,
                g.short_description[:50] + ("..." if len(g.short_description) > 50 else ""),
                f"[{sev_color}]{g.severity.value}[/{sev_color}]",
                g.action.value,
                ", ".join(g.applies_to[:3]) + ("..." if len(g.applies_to) > 3 else ""),
            )

        console.print(table)
        console.print(f"\nTotal: {len(filtered)} guardrails")

    raise typer.Exit(0)
