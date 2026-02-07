"""Guardrails CLI commands for standalone compliance checking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from ..guardrails import (
    GuardrailEvaluator,
    GuardrailPolicy,
    export_builtin_policy_yaml,
    load_builtin_guardrails,
    load_policy,
)
from ..guardrails.models import Severity
from ..guardrails.reporter import format_terminal_report
from ..snapshot.storage import SnapshotStorage

console = Console()


class GuardrailsProgressDisplay:
    """Simple progress display for guardrails evaluation."""

    def __init__(self, con: Console, total_resources: int, total_guardrails: int) -> None:
        self.console = con
        self.total_resources = total_resources
        self.total_guardrails = total_guardrails
        self.current_resource = 0
        self.current_resource_name = ""
        self.current_guardrail = ""
        self.passed = 0
        self.failed = 0
        self.auto_fixed = 0
        self.warnings = 0
        self.live: Optional[Live] = None

    def _build_display(self) -> Group:
        """Build the Rich display."""
        elements = []

        # Header line
        header = Text()
        header.append("\n🛡️  ", style="bold")
        header.append("Guardrails Evaluation", style="bold cyan")
        elements.append(header)

        # Progress line
        progress_line = Text()
        progress_line.append("  Resources: ", style="dim")
        progress_line.append(f"{self.current_resource}/{self.total_resources}", style="cyan")
        progress_line.append("  Guardrails: ", style="dim")
        progress_line.append(f"{self.total_guardrails}", style="cyan")
        elements.append(progress_line)
        elements.append(Text("\n"))

        # Current evaluation
        if self.current_resource_name or self.current_guardrail:
            current_line = Text()
            current_line.append("  ● ", style="yellow")
            if self.current_guardrail:
                current_line.append(self.current_guardrail, style="yellow")
            if self.current_resource_name:
                current_line.append(f" → {self.current_resource_name}", style="dim")
            elements.append(current_line)
            elements.append(Text("\n"))

        # Counts table
        counts_line = Text()
        counts_line.append("  ")
        counts_line.append(f"✓ {self.passed} passed", style="green")
        counts_line.append("  ")
        counts_line.append(f"✗ {self.failed} failed", style="red")
        if self.auto_fixed > 0:
            counts_line.append("  ")
            counts_line.append(f"🔧 {self.auto_fixed} fixed", style="cyan")
        if self.warnings > 0:
            counts_line.append("  ")
            counts_line.append(f"⚠ {self.warnings} warnings", style="yellow")
        elements.append(counts_line)
        elements.append(Text("\n"))

        return Group(*elements)

    def update(
        self,
        current: int,
        total: int,
        guardrail_id: str = "",
        resource_name: str = "",
        passed: int = 0,
        failed: int = 0,
        auto_fixed: int = 0,
        warnings: int = 0,
    ) -> None:
        """Update progress."""
        self.current_resource = current
        self.current_guardrail = guardrail_id
        self.current_resource_name = resource_name
        self.passed = passed
        self.failed = failed
        self.auto_fixed = auto_fixed
        self.warnings = warnings
        if self.live:
            self.live.update(self._build_display())

    def start(self) -> None:
        """Start live display."""
        self.live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        )
        self.live.start()

    def stop(self) -> None:
        """Stop live display."""
        if self.live:
            self.live.stop()
            self.live = None


def _warn_missing_config(resources: list, con: Console) -> int:
    """Check resources for missing config data and warn/error accordingly.

    Returns count of resources missing config.
    """
    total = len(resources)
    if total == 0:
        return 0

    missing = 0
    for r in resources:
        config = getattr(r, "config", None)
        raw_config = getattr(r, "raw_config", None)
        has_config = (config is not None and config != {}) or (raw_config is not None and raw_config != {})
        if not has_config:
            missing += 1

    if missing == 0:
        return 0

    if missing == total:
        con.print(
            f"[red]Error:[/red] {missing} of {total} resources have no configuration data (config/raw_config).\n"
            "Guardrails cannot evaluate resources without configuration data.\n"
            "\nIf using a snapshot, re-take it with the latest version:\n"
            "  awsinv snapshot <name>\n"
            '\nIf using --from-file, ensure resources include a "config" or "raw_config" key.'
        )
        raise typer.Exit(1)

    con.print(
        f"[yellow]Warning:[/yellow] {missing} of {total} resources have no configuration data "
        "and will be skipped by guardrails."
    )
    return missing


# Create the guardrails command group
guardrails_app = typer.Typer(
    name="guardrails",
    help="Evaluate compliance guardrails against inventory snapshots.",
    no_args_is_help=True,
)


@guardrails_app.command("check")
def check(
    snapshot_name: Optional[str] = typer.Argument(None, help="Name of snapshot to evaluate"),
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
        console.print("[red]Error:[/red] Either provide a snapshot name or use --from-file")
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
            if not snapshot_name:
                console.print("[red]Error:[/red] Snapshot name is required")
                raise typer.Exit(1)
            storage = SnapshotStorage()
            snapshot_obj = storage.load_snapshot(snapshot_name)
            if not snapshot_obj:
                console.print(f"[red]Error:[/red] Snapshot not found: {snapshot_name}")
                raise typer.Exit(1)
            resources = snapshot_obj.resources or []
            snapshot_display_name = snapshot_name
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
                    self.resource_type = data.get("resource_type", data.get("type", "unknown"))
                    self.name = data.get("name", "unknown")
                    self.arn = data.get("arn", "")
                    self.config = data.get("config", data.get("raw_config", {}))

            resource_objects.append(ResourceWrapper(r))
        else:
            resource_objects.append(r)

    _warn_missing_config(resource_objects, console)

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

    # Create progress display
    progress_display = GuardrailsProgressDisplay(console, num_resources, num_guardrails)

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
        progress_display.update(
            current=current,
            total=total,
            guardrail_id=guardrail_id,
            resource_name=resource_name,
            passed=passed,
            failed=failed,
            auto_fixed=auto_fixed,
            warnings=warnings,
        )

    # Run evaluation with progress
    progress_display.start()
    try:
        report = evaluator.evaluate_all(
            resources=resource_objects,
            snapshot_name=snapshot_display_name,
            progress_callback=progress_callback,
        )
    finally:
        progress_display.stop()

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
            console.print(f"[red]Error:[/red] Invalid severity: {severity}. Use: CRITICAL, HIGH, MEDIUM, LOW, INFO")
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


def _get_bedrock_client():
    """Get Bedrock client for AI operations."""
    try:
        import boto3

        return boto3.client("bedrock-runtime")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to create Bedrock client: {e}")
        console.print("Make sure you have AWS credentials configured.")
        return None


@guardrails_app.command("validate")
def validate_policy_file(
    policy: str = typer.Argument(..., help="Path to policy YAML file to validate"),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed error context and suggestions",
    ),
) -> None:
    """Validate a guardrails policy file.

    Checks for syntax errors, invalid values, and common issues
    before using the policy.

    Examples:
        awsinv guardrails validate ./policy.yaml
        awsinv guardrails validate ~/.awsinv/policies/production.yaml
        awsinv guardrails validate ./policy.yaml --verbose
    """
    import yaml

    policy_path = Path(policy)
    if not policy_path.exists():
        console.print(f"[red]Error:[/red] Policy file not found: {policy}")
        raise typer.Exit(1)

    try:
        with open(policy_path) as f:
            policy_dict = yaml.safe_load(f)
    except yaml.YAMLError as e:
        console.print("[red]Error:[/red] Invalid YAML syntax")
        console.print(f"  {e}")
        console.print()
        console.print("[dim]Tip: Check for proper indentation and special characters.[/dim]")
        raise typer.Exit(1)

    if not policy_dict:
        console.print("[red]Error:[/red] Empty policy file")
        raise typer.Exit(1)

    # Import validator
    from ..guardrails.validator import validate_policy

    errors = validate_policy(policy_dict)

    if errors:
        console.print(f"[red]Validation failed with {len(errors)} error(s):[/red]")
        console.print()

        # Group errors by guardrail
        guardrail_errors: dict = {}
        other_errors: list = []
        for error in errors:
            if error.startswith("guardrails["):
                # Extract guardrail index and error
                import re

                match = re.match(r"guardrails\[(\d+)\]: (.+)", error)
                if match:
                    idx = int(match.group(1))
                    err_msg = match.group(2)
                    guardrail = (
                        policy_dict.get("guardrails", [])[idx] if idx < len(policy_dict.get("guardrails", [])) else {}
                    )
                    gid = guardrail.get("id", f"guardrails[{idx}]")
                    if gid not in guardrail_errors:
                        guardrail_errors[gid] = []
                    guardrail_errors[gid].append(err_msg)
                else:
                    other_errors.append(error)
            else:
                other_errors.append(error)

        # Show other errors first
        for error in other_errors:
            console.print(f"  [yellow]•[/yellow] {error}")

        # Show guardrail errors grouped
        for gid, errs in guardrail_errors.items():
            console.print(f"  [cyan]{gid}[/cyan]:")
            for err in errs:
                console.print(f"    [yellow]•[/yellow] {err}")
                # Show helpful tips for common errors
                if verbose:
                    _print_error_tip(err, console)

        console.print()

        # Show helpful summary
        if any("condition" in e.lower() or "formula" in e.lower() for e in errors):
            console.print("[dim]Tip: See formula syntax docs at docs/guardrails/formula-syntax.md[/dim]")
        if any("id" in e.lower() and "pattern" in e.lower() for e in errors):
            console.print("[dim]Tip: IDs must match PREFIX-CATEGORY-NNN (e.g., GR-ENC-001)[/dim]")

        raise typer.Exit(1)
    else:
        # Show summary of what was validated
        guardrails = policy_dict.get("guardrails", [])
        envs = list(policy_dict.get("overrides", {}).keys())
        context_vars = list(policy_dict.get("context", {}).keys())

        console.print("[green]✓ Policy is valid[/green]")
        console.print()
        console.print(f"  Name: {policy_dict.get('name', 'unnamed')}")
        console.print(f"  Version: {policy_dict.get('version', 'unspecified')}")
        console.print(f"  Guardrails: {len(guardrails)}")
        if envs:
            console.print(f"  Environments with overrides: {', '.join(envs)}")
        if context_vars:
            console.print(f"  Context variables: {', '.join(context_vars)}")

        # Show action breakdown
        if guardrails:
            action_counts = {}
            for g in guardrails:
                action = g.get("action", "UNKNOWN")
                action_counts[action] = action_counts.get(action, 0) + 1
            console.print(f"  Actions: {', '.join(f'{k}={v}' for k, v in action_counts.items())}")

    raise typer.Exit(0)


@guardrails_app.command("export")
def export_guardrails(
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save to file instead of stdout",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category: encryption, network, tagging, logging",
    ),
) -> None:
    """Export built-in guardrails as a standard YAML policy file.

    Outputs the built-in best-practice guardrails in the standard policy
    format so you can customize them.

    Examples:
        awsinv guardrails export > my-policy.yaml
        awsinv guardrails export --output my-policy.yaml
        awsinv guardrails export --category encryption --output enc-policy.yaml
    """
    yaml_content = export_builtin_policy_yaml(category=category)

    if output:
        output_path = Path(output)
        try:
            with open(output_path, "w") as f:
                f.write(yaml_content)
            console.print(f"[green]Exported to {output_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to write file: {e}")
            raise typer.Exit(1)
    else:
        console.print(yaml_content, highlight=False)

    raise typer.Exit(0)


def _print_error_tip(error: str, console: Console) -> None:
    """Print a helpful tip for common errors."""
    error_lower = error.lower()

    tips = {
        "severity": "      [dim]Valid severities: CRITICAL, HIGH, MEDIUM, LOW, INFO[/dim]",
        "action": "      [dim]Valid actions: BLOCK, AUTO-FIX, WARN[/dim]",
        "applies_to": '      [dim]Format: ["service:resource"] e.g., ["s3:bucket", "ec2:instance"][/dim]',
        "ai_context is recommended": (
            "      [dim]Add ai_context with fix instructions for better auto-fix results[/dim]"
        ),
        "not exists": "      [dim]Use: 'Attribute not exists' (with space before 'not')[/dim]",
        "unbalanced": "      [dim]Check for matching opening/closing parentheses and quotes[/dim]",
        "unknown function": "      [dim]Available functions: get(), exists(), count(), env(), matches()[/dim]",
    }

    for key, tip in tips.items():
        if key in error_lower:
            console.print(tip)
            return


@guardrails_app.command("create")
def create_guardrail(
    requirement: str = typer.Argument(..., help="Natural language requirement for the guardrail"),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Append to policy file instead of stdout",
    ),
) -> None:
    """Generate a guardrail from a natural language requirement.

    Uses AI to create a guardrail definition from your description.
    Outputs YAML that can be added to your policy file.

    Examples:
        awsinv guardrails create "S3 buckets must have encryption enabled"
        awsinv guardrails create "No public security groups" >> policy.yaml
        awsinv guardrails create "RDS instances need backups" -o policy.yaml
    """
    from ..guardrails.generator import generate_guardrail, guardrail_to_yaml

    bedrock = _get_bedrock_client()
    if not bedrock:
        raise typer.Exit(1)

    console.print(f"[dim]Generating guardrail for: {requirement}[/dim]")
    console.print()

    guardrail = generate_guardrail(requirement, bedrock_client=bedrock)

    if not guardrail:
        console.print("[red]Error:[/red] Failed to generate guardrail")
        raise typer.Exit(1)

    yaml_output = guardrail_to_yaml(guardrail)

    if output:
        # Append to file
        output_path = Path(output)
        mode = "a" if output_path.exists() else "w"

        with open(output_path, mode) as f:
            if mode == "a":
                f.write("\n")
            f.write(yaml_output)
            f.write("\n")

        console.print(f"[green]Guardrail appended to {output}[/green]")
        console.print()
        console.print(yaml_output)
    else:
        # Output to stdout
        console.print(yaml_output)

    raise typer.Exit(0)


@guardrails_app.command("generate")
def generate_guardrails(
    description: str = typer.Argument(..., help="High-level policy description"),
    count: int = typer.Option(
        5,
        "--count",
        "-n",
        help="Number of guardrails to generate",
    ),
    types: Optional[str] = typer.Option(
        None,
        "--types",
        "-t",
        help="Comma-separated resource types to focus on (e.g., s3,ec2,rds)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save to policy file",
    ),
) -> None:
    """Generate multiple guardrails from a policy description.

    Uses AI to create a set of guardrails based on your high-level
    security or compliance requirements.

    Examples:
        awsinv guardrails generate "production security baseline"
        awsinv guardrails generate "HIPAA compliance" --count 10
        awsinv guardrails generate "secure S3 and RDS" --types s3,rds
        awsinv guardrails generate "PCI-DSS requirements" -o pci-policy.yaml
    """
    from ..guardrails.generator import generate_guardrails_batch, guardrail_to_yaml

    bedrock = _get_bedrock_client()
    if not bedrock:
        raise typer.Exit(1)

    resource_types = None
    if types:
        resource_types = [t.strip() for t in types.split(",")]

    console.print(f"[dim]Generating {count} guardrails for: {description}[/dim]")
    if resource_types:
        console.print(f"[dim]Focusing on: {', '.join(resource_types)}[/dim]")
    console.print()

    guardrails = generate_guardrails_batch(
        description=description,
        count=count,
        resource_types=resource_types,
        bedrock_client=bedrock,
    )

    if not guardrails:
        console.print("[red]Error:[/red] Failed to generate guardrails")
        raise typer.Exit(1)

    console.print(f"[green]Generated {len(guardrails)} guardrails:[/green]")
    console.print()

    yaml_parts = []
    for g in guardrails:
        yaml_output = guardrail_to_yaml(g)
        yaml_parts.append(yaml_output)
        console.print(yaml_output)
        console.print()

    if output:
        output_path = Path(output)

        # Create policy structure if new file
        if not output_path.exists():
            header = """name: generated-policy
version: "1.0"
description: AI-generated guardrails policy

guardrails:
"""
            content = header + "\n".join(yaml_parts)
        else:
            # Append to existing
            content = "\n" + "\n".join(yaml_parts)

        with open(output_path, "a" if output_path.exists() else "w") as f:
            f.write(content)

        console.print(f"[green]Guardrails saved to {output}[/green]")

    raise typer.Exit(0)
