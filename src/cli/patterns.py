"""Infrastructure Pattern Library CLI commands."""

from __future__ import annotations

from typing import List, Optional

import typer
import yaml
from rich.console import Console

from ..patterns.loader import (
    delete_pattern as _delete_pattern,
)
from ..patterns.loader import (
    get_library_path,
    list_pattern_versions,
    load_library,
    load_pattern,
    save_pattern,
    validate_pattern,
)
from ..patterns.reporter import (
    format_compliance_report,
    format_json_report,
    format_pattern_detail,
    format_pattern_list,
    format_terminal_report,
)

console = Console()

patterns_app = typer.Typer(
    name="patterns",
    help="Infrastructure pattern library (define, compare, and browse reusable architecture patterns)",
    no_args_is_help=True,
)


@patterns_app.command("add")
def add_pattern(
    file_path: str = typer.Argument(..., help="Path to pattern YAML file"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Add a pattern YAML file to the library."""
    try:
        pattern = load_pattern(file_path)
    except (ValueError, FileNotFoundError, OSError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    issues = validate_pattern(pattern)
    errors = [i for i in issues if "warning" not in i.lower() and "guardrail" not in i.lower()]
    warnings = [i for i in issues if "warning" in i.lower() or "guardrail" in i.lower()]

    if errors:
        console.print("[red]Validation errors:[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(code=1)

    lib_path = get_library_path(library)
    existing = load_library(lib_path)
    for existing_pattern in existing:
        if existing_pattern.name == pattern.name and existing_pattern.version == pattern.version:
            console.print(f"[red]Error:[/red] Pattern '{pattern.name}' v{pattern.version} already exists.")
            raise typer.Exit(code=1)

    for warn in warnings:
        console.print(f"[yellow]{warn}[/yellow]")

    saved_path = save_pattern(pattern, lib_path)
    console.print(f"Pattern '{pattern.name}' v{pattern.version} added to library.")
    typer.echo(f"Saved to: {saved_path}")


@patterns_app.command("generate")
def generate_pattern(
    description: Optional[str] = typer.Argument(None, help="Description for AI generation"),
    from_snapshot: Optional[str] = typer.Option(None, "--from-snapshot", help="Generate from snapshot"),
    instructions: Optional[str] = typer.Option(None, "--instructions", help="AI instructions"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    guardrails_list: Optional[str] = typer.Option(None, "--guardrails", help="Comma-separated guardrail names"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Generate a pattern using AI."""
    if description and from_snapshot:
        console.print("[red]Error:[/red] Provide description OR --from-snapshot, not both.")
        raise typer.Exit(code=1)

    if not description and not from_snapshot:
        console.print("[red]Error:[/red] Provide a description or --from-snapshot.")
        raise typer.Exit(code=1)

    try:
        import boto3

        bedrock_client = boto3.client("bedrock-runtime")
    except Exception:
        console.print("[red]Error:[/red] Bedrock credentials required for pattern generation.")
        raise typer.Exit(code=1)

    guardrail_names = None
    if guardrails_list:
        guardrail_names = [g.strip() for g in guardrails_list.split(",") if g.strip()]

    from ..patterns.generator import generate_from_description, generate_from_snapshot

    try:
        if from_snapshot:
            pattern = generate_from_snapshot(
                snapshot_name=from_snapshot,
                instructions=instructions,
                guardrail_names=guardrail_names,
                bedrock_client=bedrock_client,
            )
        else:
            pattern = generate_from_description(
                description=description,  # type: ignore[arg-type]
                instructions=instructions,
                bedrock_client=bedrock_client,
            )
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    pattern_yaml = yaml.dump(pattern.to_dict(), default_flow_style=False, sort_keys=False)

    if output:
        with open(output, "w") as f:
            f.write(pattern_yaml)
        console.print(f"Pattern written to {output}")
    else:
        typer.echo(pattern_yaml)


@patterns_app.command("list")
def list_patterns(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    resource_type: Optional[str] = typer.Option(None, "--type", help="Filter by resource type"),
    search: Optional[str] = typer.Option(None, "--search", help="Search name/description"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """List all patterns in the library."""
    lib_path = get_library_path(library)
    patterns = load_library(lib_path)

    if tag:
        patterns = [p for p in patterns if tag in p.tags]
    if resource_type:
        patterns = [p for p in patterns if any(r.type == resource_type for r in p.resources)]
    if search:
        search_lower = search.lower()
        patterns = [p for p in patterns if search_lower in p.name.lower() or search_lower in p.description.lower()]

    output = format_pattern_list(patterns, as_json=json_output)
    typer.echo(output)


@patterns_app.command("show")
def show_pattern(
    name: str = typer.Argument(..., help="Pattern name"),
    version: Optional[int] = typer.Option(None, "--version", help="Specific version"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Show detailed information about a pattern."""
    lib_path = get_library_path(library)
    patterns = load_library(lib_path)

    matches = [p for p in patterns if p.name == name]
    if not matches:
        console.print(f"[red]Error:[/red] Pattern '{name}' not found.")
        raise typer.Exit(code=1)

    if version is not None:
        matches = [p for p in matches if p.version == version]
        if not matches:
            console.print(f"[red]Error:[/red] Pattern '{name}' v{version} not found.")
            raise typer.Exit(code=1)

    target = max(matches, key=lambda p: p.version)

    versions = list_pattern_versions(name, lib_path)
    output = format_pattern_detail(target, as_json=json_output)
    typer.echo(output)

    if not json_output and len(versions) > 1:
        typer.echo(f"\nVersions available: {', '.join(f'v{v}' for v in versions)}")


@patterns_app.command("compare")
def compare_patterns(
    snapshot: str = typer.Option(..., "--snapshot", envvar="AWSINV_SNAPSHOT_ID", help="Snapshot to compare"),
    pattern_name: Optional[str] = typer.Option(None, "--pattern", help="Target single pattern"),
    threshold: float = typer.Option(0.25, "--threshold", help="Minimum score threshold"),
    output: Optional[str] = typer.Option(None, "--output", help="Export results to file"),
    format_type: Optional[str] = typer.Option(None, "--format", help="Export format (json/yaml)"),
    no_guidance: bool = typer.Option(False, "--no-guidance", help="Skip AI guidance generation"),
    guardrails_policy: Optional[str] = typer.Option(None, "--guardrails-policy", help="Custom guardrails policy"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Compare a snapshot against the pattern library."""
    import json as json_mod

    from ..patterns.comparator import compare_snapshot

    lib_path = get_library_path(library)

    try:
        report = compare_snapshot(
            snapshot_name=snapshot,
            library_path=lib_path,
            threshold=threshold,
            target_pattern=pattern_name,
            guardrails_policy_path=guardrails_policy,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if not no_guidance and report.matches:
        try:
            import boto3

            bedrock_client = boto3.client("bedrock-runtime")
            from ..patterns.generator import generate_guidance

            for match in report.matches:
                guidance = generate_guidance(report, bedrock_client=bedrock_client)
                if guidance:
                    match.guidance = guidance
                    break
        except Exception:
            pass

    if output:
        report_dict = format_json_report(report)
        with open(output, "w") as f:
            if format_type == "yaml":
                yaml.dump(report_dict, f, default_flow_style=False, sort_keys=False)
            else:
                json_mod.dump(report_dict, f, indent=2)
        console.print(f"Results exported to {output}")
    else:
        typer.echo(format_terminal_report(report))


@patterns_app.command("generate-iac")
def generate_iac(
    pattern_name: str = typer.Argument(..., help="Pattern name or YAML file path"),
    format_type: str = typer.Option(
        "terraform", "--format", "-f", help="Output format: terraform, cdk-typescript, cdk-python"
    ),
    output_dir: str = typer.Option("./output", "--output-dir", help="Output directory"),
    version: Optional[int] = typer.Option(None, "--version", help="Pattern version"),
    guardrails: bool = typer.Option(False, "--guardrails", help="Enable guardrails"),
    guardrails_policy: Optional[str] = typer.Option(None, "--guardrails-policy", help="Custom guardrails policy"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Generate IaC (Terraform/CDK) from a pattern."""
    from ..patterns.iac_bridge import generate_iac_from_pattern

    lib_path = get_library_path(library)
    patterns = load_library(lib_path)

    matches = [p for p in patterns if p.name == pattern_name]
    if not matches:
        try:
            target = load_pattern(pattern_name)
        except (ValueError, FileNotFoundError, OSError) as exc:
            console.print(
                f"[red]Error:[/red] Pattern '{pattern_name}' not found in library and not a valid file: {exc}"
            )
            raise typer.Exit(code=1)
    else:
        if version is not None:
            matches = [p for p in matches if p.version == version]
            if not matches:
                console.print(f"[red]Error:[/red] Pattern '{pattern_name}' v{version} not found.")
                raise typer.Exit(code=1)
        target = max(matches, key=lambda p: p.version)

    try:
        result = generate_iac_from_pattern(
            pattern=target,
            output_format=format_type,
            output_dir=output_dir,
            guardrails_enabled=guardrails,
            guardrails_policy_path=guardrails_policy,
        )
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] Generation failed: {exc}")
        raise typer.Exit(code=1)

    if result.success:
        console.print(f"IaC generated successfully in {output_dir}")
        if hasattr(result, "generated_files") and result.generated_files:
            for f in result.generated_files:
                typer.echo(f"  {f}")
    else:
        console.print("[red]Error:[/red] Generation failed.")
        if hasattr(result, "errors") and result.errors:
            for err in result.errors:
                console.print(f"  - {err}")
        raise typer.Exit(code=1)


@patterns_app.command("compliance")
def compliance(
    snapshots: List[str] = typer.Option(
        [], "--snapshot", envvar="AWSINV_SNAPSHOT_ID", help="Snapshot names (repeat for multiple)"
    ),
    pattern_name: Optional[str] = typer.Option(None, "--pattern", help="Target single pattern"),
    threshold: float = typer.Option(0.25, "--threshold", help="Minimum score threshold"),
    output: Optional[str] = typer.Option(None, "--output", help="Export results to file"),
    format_type: Optional[str] = typer.Option(None, "--format", help="Export format (json/yaml)"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Run compliance report across multiple snapshots."""
    import json as json_mod

    from ..patterns.comparator import compliance_report as _compliance_report

    if not snapshots:
        console.print("[red]Error:[/red] At least one --snapshot is required.")
        raise typer.Exit(code=1)

    lib_path = get_library_path(library)

    data = _compliance_report(
        snapshot_names=snapshots,
        library_path=lib_path,
        threshold=threshold,
        target_pattern=pattern_name,
    )

    if output:
        with open(output, "w") as f:
            if format_type == "yaml":
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            else:
                json_mod.dump(data, f, indent=2)
        console.print(f"Compliance report exported to {output}")
    else:
        typer.echo(format_compliance_report(data))


@patterns_app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Pattern name"),
    version: Optional[int] = typer.Option(None, "--version", help="Specific version"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Delete a pattern from the library."""
    lib_path = get_library_path(library)

    deleted = _delete_pattern(name, lib_path, version=version)
    if deleted:
        if version is not None:
            console.print(f"Deleted pattern '{name}' v{version}.")
        else:
            console.print(f"Deleted all versions of pattern '{name}'.")
    else:
        console.print(f"[red]Error:[/red] Pattern '{name}' not found.")
        raise typer.Exit(code=1)


@patterns_app.command("export")
def export_pattern(
    name: str = typer.Argument(..., help="Pattern name"),
    version: Optional[int] = typer.Option(None, "--version", help="Specific version"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    format_type: str = typer.Option("yaml", "--format", "-f", help="Export format (json/yaml)"),
    library: Optional[str] = typer.Option(None, "--library", help="Override library location"),
) -> None:
    """Export a pattern to a file."""
    import json as json_mod

    lib_path = get_library_path(library)
    patterns = load_library(lib_path)

    matches = [p for p in patterns if p.name == name]
    if not matches:
        console.print(f"[red]Error:[/red] Pattern '{name}' not found.")
        raise typer.Exit(code=1)

    if version is not None:
        matches = [p for p in matches if p.version == version]
        if not matches:
            console.print(f"[red]Error:[/red] Pattern '{name}' v{version} not found.")
            raise typer.Exit(code=1)

    target = max(matches, key=lambda p: p.version)
    data = target.to_dict()

    with open(output, "w") as f:
        if format_type == "json":
            json_mod.dump(data, f, indent=2)
        else:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    console.print(f"Pattern '{name}' v{target.version} exported to {output}")
