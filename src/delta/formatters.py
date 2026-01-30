"""Drift formatter for color-coded terminal output of configuration changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models.config_diff import ChangeCategory
from .models import DriftReport

if TYPE_CHECKING:
    from ..models.config_diff import ConfigDiff


class DriftFormatter:
    """Format and display configuration drift with color coding.

    Color scheme:
    - Red: Removed fields
    - Green: Added fields
    - Yellow: Security-critical changes
    - Cyan: Configuration changes
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize drift formatter.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()

    def display(
        self,
        report: DriftReport,
        group_by: str = "category",
        resource_type_filter: Optional[str] = None,
        region_filter: Optional[str] = None,
    ) -> None:
        """Display drift report to console with color coding.

        Args:
            report: DriftReport to display
            group_by: How to group changes ("category" or "resource")
            resource_type_filter: Optional resource type filter (e.g., "ec2")
            region_filter: Optional region filter (e.g., "us-east-1")
        """
        # Apply filters
        diffs = report.get_all_diffs()

        if resource_type_filter:
            diffs = [d for d in diffs if resource_type_filter.lower() in d.resource_arn.lower()]

        if region_filter:
            diffs = [d for d in diffs if region_filter in d.resource_arn]

        # Check if there are any changes after filtering
        if not diffs:
            self.console.print()
            self.console.print(
                Panel(
                    "[bold green]No configuration changes detected[/bold green]",
                    style="green",
                )
            )
            self.console.print()
            return

        # Display header
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Configuration Drift Details[/bold]\nTotal Changes: {len(diffs)}",
                style="cyan",
            )
        )
        self.console.print()

        # Display summary statistics
        self._display_summary(diffs)

        # Group and display changes
        if group_by == "resource":
            self._display_by_resource(diffs)
        else:
            self._display_by_category(diffs)

    def _display_summary(self, diffs: list) -> None:
        """Display summary statistics for drift.

        Args:
            diffs: List of ConfigDiff objects
        """
        # Count by category
        tags_count = sum(1 for d in diffs if d.category == ChangeCategory.TAGS)
        config_count = sum(1 for d in diffs if d.category == ChangeCategory.CONFIGURATION)
        security_count = sum(1 for d in diffs if d.category == ChangeCategory.SECURITY)
        permissions_count = sum(1 for d in diffs if d.category == ChangeCategory.PERMISSIONS)

        # Create summary table
        table = Table(title="Summary", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan", width=20)
        table.add_column("Count", justify="right", style="yellow", width=10)

        if tags_count > 0:
            table.add_row("Tags", str(tags_count))
        if config_count > 0:
            table.add_row("Configuration", str(config_count))
        if security_count > 0:
            table.add_row("[yellow]Security[/yellow]", f"[yellow]{security_count}[/yellow]")
        if permissions_count > 0:
            table.add_row("Permissions", str(permissions_count))

        self.console.print(table)
        self.console.print()

    def _display_by_category(self, diffs: list) -> None:
        """Display diffs grouped by category.

        Args:
            diffs: List of ConfigDiff objects
        """
        # Group by category
        from typing import Dict, List

        categories: Dict[ChangeCategory, List] = {
            ChangeCategory.TAGS: [],
            ChangeCategory.CONFIGURATION: [],
            ChangeCategory.SECURITY: [],
            ChangeCategory.PERMISSIONS: [],
        }

        for diff in diffs:
            categories[diff.category].append(diff)

        # Display each category
        category_names = {
            ChangeCategory.TAGS: "Tags",
            ChangeCategory.CONFIGURATION: "Configuration",
            ChangeCategory.SECURITY: "Security",
            ChangeCategory.PERMISSIONS: "Permissions",
        }

        for category, category_diffs in categories.items():
            if not category_diffs:
                continue

            self.console.print(f"[bold]{category_names[category]} Changes:[/bold]")
            table = Table(show_header=True, box=None, padding=(0, 2))
            table.add_column("Resource", style="dim", width=50)
            table.add_column("Field", style="cyan", width=30)
            table.add_column("Change", width=40)

            for diff in category_diffs:
                # Extract resource name/ID from ARN
                resource_display = self._format_resource_name(diff.resource_arn)

                # Format the change with color coding
                change_display = self._format_change(diff)

                table.add_row(resource_display, diff.field_path, change_display)

            self.console.print(table)
            self.console.print()

    def _display_by_resource(self, diffs: list) -> None:
        """Display diffs grouped by resource ARN.

        Args:
            diffs: List of ConfigDiff objects
        """
        # Group by resource
        by_resource: dict[str, list] = {}
        for diff in diffs:
            if diff.resource_arn not in by_resource:
                by_resource[diff.resource_arn] = []
            by_resource[diff.resource_arn].append(diff)

        # Display each resource's changes
        for resource_arn, resource_diffs in by_resource.items():
            resource_display = self._format_resource_name(resource_arn)
            self.console.print(f"[bold cyan]{resource_display}[/bold cyan]")

            table = Table(show_header=True, box=None, padding=(0, 2))
            table.add_column("Field", style="cyan", width=35)
            table.add_column("Change", width=50)
            table.add_column("Category", width=15)

            for diff in resource_diffs:
                change_display = self._format_change(diff)
                category_display = diff.category.value.capitalize()

                table.add_row(diff.field_path, change_display, category_display)

            self.console.print(table)
            self.console.print()

    def _format_resource_name(self, arn: str) -> str:
        """Extract a readable resource name from ARN.

        Args:
            arn: Resource ARN

        Returns:
            Formatted resource name
        """
        # Extract the resource ID/name from ARN
        # ARN format: arn:aws:service:region:account:resourceType/resourceId
        parts = arn.split(":")
        if len(parts) >= 6:
            resource_part = parts[5]
            if "/" in resource_part:
                return resource_part.split("/", 1)[1]
            return resource_part
        return arn

    def _format_change(self, diff: ConfigDiff) -> str:
        """Format a change with color coding and arrow notation.

        Args:
            diff: ConfigDiff object

        Returns:
            Rich-formatted change string
        """
        old_str = self._format_value(diff.old_value)
        new_str = self._format_value(diff.new_value)

        # Color code based on change type
        if diff.old_value is None:
            # Field added
            return f"[green]+[/green] {new_str}"
        elif diff.new_value is None:
            # Field removed
            return f"[red]-[/red] {old_str}"
        else:
            # Field modified
            if diff.is_security_critical():
                # Security-critical change - yellow
                return f"[yellow]{old_str} → {new_str}[/yellow]"
            else:
                # Regular change - cyan
                return f"{old_str} → {new_str}"

    def _format_value(self, value: Any) -> str:
        """Format a configuration value for display.

        Args:
            value: Configuration value

        Returns:
            Formatted string representation
        """
        if value is None:
            return "[dim](none)[/dim]"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (dict, list)):
            # Truncate complex values
            str_value = str(value)
            if len(str_value) > 50:
                return str_value[:47] + "..."
            return str_value
        else:
            str_value = str(value)
            # Truncate very long values
            if len(str_value) > 100:
                return str_value[:97] + "..."
            return str_value
