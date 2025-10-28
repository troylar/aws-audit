"""Delta report formatting and display."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models.delta_report import DeltaReport


class DeltaReporter:
    """Format and display delta reports."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize delta reporter.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()

    def display(self, report: DeltaReport, show_details: bool = False) -> None:
        """Display delta report to console.

        Args:
            report: DeltaReport to display
            show_details: Whether to show detailed resource information
        """
        # Header
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Resource Delta Report[/bold]\n"
                f"Reference Snapshot: {report.baseline_snapshot_name}\n"
                f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                style="cyan",
            )
        )
        self.console.print()

        # Check if there are any changes
        if not report.has_changes:
            self.console.print(
                "[green]✓ No changes detected - environment matches reference snapshot[/green]", style="bold"
            )
            self.console.print()
            self.console.print(f"Total resources: {report.baseline_resource_count}")
            return

        # Summary statistics
        self._display_summary(report)

        # Group changes by service
        grouped = report.group_by_service()

        # Display changes by service
        for service_type in sorted(grouped.keys()):
            changes = grouped[service_type]
            if any(changes.values()):
                self._display_service_changes(service_type, changes, show_details)

    def _display_summary(self, report: DeltaReport) -> None:
        """Display summary statistics."""
        table = Table(title="Summary", show_header=True, header_style="bold magenta")
        table.add_column("Change Type", style="cyan", width=15)
        table.add_column("Count", justify="right", style="yellow", width=10)

        added_count = len(report.added_resources)
        deleted_count = len(report.deleted_resources)
        modified_count = len(report.modified_resources)
        unchanged_count = report.unchanged_count

        if added_count > 0:
            table.add_row("➕ Added", f"[green]{added_count}[/green]")
        if deleted_count > 0:
            table.add_row("➖ Deleted", f"[red]{deleted_count}[/red]")
        if modified_count > 0:
            table.add_row("🔄 Modified", f"[yellow]{modified_count}[/yellow]")
        if unchanged_count > 0:
            table.add_row("✓ Unchanged", str(unchanged_count))

        table.add_row("━" * 15, "━" * 10, style="dim")
        table.add_row("[bold]Total Changes", f"[bold]{report.total_changes}")

        self.console.print(table)
        self.console.print()

    def _display_service_changes(self, service_type: str, changes: dict, show_details: bool) -> None:
        """Display changes for a specific service type.

        Args:
            service_type: AWS resource type (e.g., 'AWS::EC2::Instance')
            changes: Dictionary with 'added', 'deleted', 'modified' lists
            show_details: Whether to show detailed information
        """
        # Count total changes for this service
        total = len(changes["added"]) + len(changes["deleted"]) + len(changes["modified"])
        if total == 0:
            return

        self.console.print(f"[bold cyan]{service_type}[/bold cyan] ({total} changes)")

        # Create table for this service
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Change", width=8)
        table.add_column("Name", style="white")
        table.add_column("Region", width=15)
        table.add_column("ARN" if show_details else "Tags", style="dim")

        # Added resources
        for resource in changes["added"]:
            tags_str = self._format_tags(resource.tags)
            arn_or_tags = resource.arn if show_details else tags_str
            table.add_row("[green]➕ Add[/green]", resource.name, resource.region, arn_or_tags)

        # Deleted resources
        for resource in changes["deleted"]:
            tags_str = self._format_tags(resource.tags)
            arn_or_tags = resource.arn if show_details else tags_str
            table.add_row("[red]➖ Del[/red]", resource.name, resource.region, arn_or_tags)

        # Modified resources
        for change in changes["modified"]:
            tags_str = self._format_tags(change.resource.tags)
            arn_or_tags = change.resource.arn if show_details else tags_str
            table.add_row("[yellow]🔄 Mod[/yellow]", change.resource.name, change.resource.region, arn_or_tags)

        self.console.print(table)
        self.console.print()

    def _format_tags(self, tags: dict) -> str:
        """Format tags dictionary as a string.

        Args:
            tags: Dictionary of tag key-value pairs

        Returns:
            Formatted string like "Env=prod, App=web"
        """
        if not tags:
            return "-"

        # Show up to 3 most important tags
        important_keys = ["Name", "Environment", "Project", "Team", "Application"]
        selected_tags = []

        # First add important tags if present
        for key in important_keys:
            if key in tags:
                selected_tags.append(f"{key}={tags[key]}")

        # Add other tags up to limit
        for key, value in tags.items():
            if key not in important_keys and len(selected_tags) < 3:
                selected_tags.append(f"{key}={value}")

        return ", ".join(selected_tags[:3])

    def export_json(self, report: DeltaReport, filepath: str) -> None:
        """Export delta report to JSON file.

        Args:
            report: DeltaReport to export
            filepath: Destination file path
        """
        from ..utils.export import export_to_json

        export_to_json(report.to_dict(), filepath)
        self.console.print(f"[green]✓ Delta report exported to {filepath}[/green]")

    def export_csv(self, report: DeltaReport, filepath: str) -> None:
        """Export delta report to CSV file.

        Args:
            report: DeltaReport to export
            filepath: Destination file path
        """
        from ..utils.export import export_to_csv

        # Flatten the report into rows
        rows = []

        for resource in report.added_resources:
            rows.append(
                {
                    "change_type": "added",
                    "resource_type": resource.resource_type,
                    "name": resource.name,
                    "arn": resource.arn,
                    "region": resource.region,
                    "tags": str(resource.tags),
                    "created_at": resource.created_at.isoformat() if resource.created_at else None,
                }
            )

        for resource in report.deleted_resources:
            rows.append(
                {
                    "change_type": "deleted",
                    "resource_type": resource.resource_type,
                    "name": resource.name,
                    "arn": resource.arn,
                    "region": resource.region,
                    "tags": str(resource.tags),
                    "created_at": resource.created_at.isoformat() if resource.created_at else None,
                }
            )

        for change in report.modified_resources:
            rows.append(
                {
                    "change_type": "modified",
                    "resource_type": change.resource.resource_type,
                    "name": change.resource.name,
                    "arn": change.resource.arn,
                    "region": change.resource.region,
                    "tags": str(change.resource.tags),
                    "old_hash": change.old_config_hash,
                    "new_hash": change.new_config_hash,
                }
            )

        export_to_csv(rows, filepath)
        self.console.print(f"[green]✓ Delta report exported to {filepath}[/green]")
