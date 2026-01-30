"""
Report output formatting using Rich for terminal UI.

This module contains the ReportFormatter class responsible for rendering
reports to the terminal with Rich tables, progress bars, and formatted output.
"""

from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.panel import Panel

from src.models.report import DetailedResource, ResourceSummary, SnapshotMetadata
from src.utils.pagination import paginate_resources


class ReportFormatter:
    """
    Formats and renders reports using Rich terminal UI.

    Handles rendering of headers, summaries, tables, and progress bars
    for snapshot resource reports.
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        """
        Initialize formatter with Rich Console.

        Args:
            console: Rich Console instance (creates default if not provided)
        """
        self.console = console or Console()

    def format_summary(
        self,
        metadata: SnapshotMetadata,
        summary: ResourceSummary,
        has_filters: bool = False,
    ) -> None:
        """
        Format and display complete summary report.

        Orchestrates all render methods to display header, service breakdown,
        region breakdown, and type breakdown.

        Args:
            metadata: Snapshot metadata for header
            summary: Resource summary with aggregated counts
            has_filters: Whether filters were applied (shows "Filtered" indicator)
        """
        # Render header
        self._render_header(metadata, has_filters)

        # Add spacing
        self.console.print()

        # Render summary sections
        self.console.print("📊 [bold]Resource Summary[/bold]\n")
        self.console.print(f"Total Resources: [bold cyan]{summary.total_count:,}[/bold cyan]\n")

        if summary.total_count > 0:
            # Render service breakdown
            self._render_service_breakdown(summary)

            # Render region breakdown
            self._render_region_breakdown(summary)

            # Render type breakdown (top 10)
            self._render_type_breakdown(summary)

    def _render_header(self, metadata: SnapshotMetadata, has_filters: bool = False) -> None:
        """
        Render report header with snapshot metadata.

        Args:
            metadata: Snapshot metadata
            has_filters: Whether to show "Filtered" indicator
        """
        title = f"Snapshot Report: {metadata.name}"
        if has_filters:
            title += " (Filtered)"

        # Create header panel
        header_content = f"""[bold]Inventory:[/bold]     {metadata.inventory_name}
[bold]Account ID:[/bold]    {metadata.account_id}
[bold]Created:[/bold]       {metadata.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}
[bold]Regions:[/bold]       {metadata.region_summary}"""

        panel = Panel(
            header_content,
            title=title,
            border_style="blue",
            expand=False,
        )

        self.console.print(panel)

    def _render_service_breakdown(self, summary: ResourceSummary) -> None:
        """
        Render service breakdown with progress bars.

        Args:
            summary: Resource summary with service counts
        """
        if not summary.by_service:
            return

        self.console.print("[bold]By Service:[/bold]")

        # Get top services (sorted by count)
        top_services = summary.top_services(limit=10)

        for service, count in top_services:
            percentage = (count / summary.total_count) * 100
            bar_length = int((count / summary.total_count) * 30)
            bar = "█" * bar_length + "░" * (30 - bar_length)

            self.console.print(f"  {service:15} {count:5}  {bar}  ({percentage:.1f}%)")

        self.console.print()

    def _render_region_breakdown(self, summary: ResourceSummary) -> None:
        """
        Render region breakdown with progress bars.

        Args:
            summary: Resource summary with region counts
        """
        if not summary.by_region:
            return

        self.console.print("[bold]By Region:[/bold]")

        # Get top regions (sorted by count)
        top_regions = summary.top_regions(limit=10)

        for region, count in top_regions:
            percentage = (count / summary.total_count) * 100
            bar_length = int((count / summary.total_count) * 30)
            bar = "█" * bar_length + "░" * (30 - bar_length)

            self.console.print(f"  {region:15} {count:5}  {bar}  ({percentage:.1f}%)")

        self.console.print()

    def _render_type_breakdown(self, summary: ResourceSummary) -> None:
        """
        Render resource type breakdown showing top 10 types.

        Args:
            summary: Resource summary with type counts
        """
        if not summary.by_type:
            return

        self.console.print("[bold]Top 10 Resource Types:[/bold]")

        # Get top 10 resource types
        sorted_types = sorted(
            summary.by_type.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        for resource_type, count in sorted_types:
            percentage = (count / summary.total_count) * 100
            self.console.print(f"  {resource_type:45} {count:5}  ({percentage:.1f}%)")

        self.console.print()

    def format_detailed(
        self,
        metadata: SnapshotMetadata,
        resources: List[DetailedResource],
        page_size: int = 100,
    ) -> None:
        """
        Format and display detailed resource view with pagination.

        Args:
            metadata: Snapshot metadata for header
            resources: List of detailed resources to display
            page_size: Number of resources per page (default: 100)
        """
        # Render header
        self._render_header(metadata, has_filters=False)
        self.console.print()

        total_resources = len(resources)
        self.console.print(f"Total Resources: [bold cyan]{total_resources:,}[/bold cyan]\n")

        if total_resources == 0:
            return

        # Paginate resources
        pages = list(paginate_resources(resources, page_size=page_size))
        total_pages = len(pages)

        # Display pages
        for page_num, page in enumerate(pages, start=1):
            for idx, resource in enumerate(page, start=1):
                global_idx = (page_num - 1) * page_size + idx
                self._render_detailed_resource(resource, global_idx, total_resources)

            # Show pagination info (but no prompts - non-interactive for now)
            if page_num < total_pages:
                self.console.print(f"\n[dim]─── Page {page_num} of {total_pages} ───[/dim]\n")

    def _render_detailed_resource(
        self,
        resource: DetailedResource,
        index: int,
        total: int,
    ) -> None:
        """
        Render a single detailed resource.

        Args:
            resource: DetailedResource to display
            index: Resource index (1-based)
            total: Total number of resources
        """
        self.console.print("─" * 65)
        self.console.print(f"[bold]Resource {index}/{total}[/bold]\n")

        self.console.print(f"[bold]ARN:[/bold]          {resource.arn}")
        self.console.print(f"[bold]Type:[/bold]         {resource.resource_type}")
        self.console.print(f"[bold]Name:[/bold]         {resource.name}")
        self.console.print(f"[bold]Region:[/bold]       {resource.region}")

        # Show creation date if available
        if resource.created_at:
            age_str = ""
            if resource.age_days is not None:
                age_str = f" ({resource.age_days} days ago)"
            created_str = resource.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            self.console.print(f"[bold]Created:[/bold]      {created_str}{age_str}")

        # Show tags
        self.console.print()
        if resource.tags:
            self.console.print("[bold]Tags:[/bold]")
            for key, value in resource.tags.items():
                self.console.print(f"  {key:20} {value}")
        else:
            self.console.print("[dim]No tags[/dim]")

        self.console.print()
