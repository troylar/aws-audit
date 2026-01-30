"""Real-time deletion progress display with dependency tree view.

Provides a visual display showing deletion progress organized by dependency tier,
with real-time status updates as each resource is deleted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text


class ResourceStatus(Enum):
    """Status of a resource during deletion."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"  # Already deleted / not found
    FAILED = "failed"


@dataclass
class TrackedResource:
    """Track state of a resource during deletion."""

    resource: Any  # Resource model
    tier: int
    status: ResourceStatus = ResourceStatus.PENDING
    error: Optional[str] = None


class DeletionProgressDisplay:
    """Manages real-time deletion progress with dependency tree view.

    Displays resources grouped by deletion tier with real-time status updates.
    Supports two display modes:
    - Detailed: Shows all resources with status icons (< 50 resources)
    - Compact: Shows tier summaries with progress bars (>= 50 resources)
    """

    TIER_NAMES: Dict[int, str] = {
        1: "Application Layer",
        2: "Compute Layer",
        3: "Load Balancers",
        4: "Networking Accessories",
        5: "Security Groups",
        6: "Subnets & Route Tables",
        7: "Internet Gateways",
        8: "VPCs",
        9: "Standalone Resources",
        10: "IAM Resources",
    }

    TIER_EMOJIS: Dict[int, str] = {
        1: "🚀",  # Application Layer - rockets/apps
        2: "💻",  # Compute Layer - computers
        3: "⚖️",  # Load Balancers - balance scales
        4: "🔌",  # Networking Accessories - plugs
        5: "🛡️",  # Security Groups - shields
        6: "🛤️",  # Subnets & Route Tables - railway tracks
        7: "🌐",  # Internet Gateways - globe
        8: "🏠",  # VPCs - houses/networks
        9: "📦",  # Standalone Resources - packages
        10: "🔑",  # IAM Resources - keys
    }

    # Threshold for switching to compact mode
    COMPACT_THRESHOLD = 50

    # Status icons and colors
    STATUS_ICONS: Dict[ResourceStatus, str] = {
        ResourceStatus.PENDING: "○",
        ResourceStatus.IN_PROGRESS: "⋯",
        ResourceStatus.SUCCEEDED: "✓",
        ResourceStatus.SKIPPED: "⏭",
        ResourceStatus.FAILED: "✗",
    }

    STATUS_COLORS: Dict[ResourceStatus, str] = {
        ResourceStatus.PENDING: "dim",
        ResourceStatus.IN_PROGRESS: "yellow",
        ResourceStatus.SUCCEEDED: "green",
        ResourceStatus.SKIPPED: "cyan",
        ResourceStatus.FAILED: "red",
    }

    def __init__(self, resources: List[Any], console: Console) -> None:
        """Initialize the deletion progress display.

        Args:
            resources: List of Resource objects to be deleted (already sorted by tier)
            console: Rich Console instance for output
        """
        self.console = console
        self.resources_by_tier: Dict[int, List[TrackedResource]] = {}
        self.resource_map: Dict[str, TrackedResource] = {}  # ARN -> TrackedResource
        self.total = len(resources)
        self.succeeded = 0
        self.skipped = 0
        self.failed = 0
        self.current: Optional[TrackedResource] = None
        self.live: Optional[Live] = None
        self.start_time: float = 0.0
        self._init_resources(resources)

    def _init_resources(self, resources: List[Any]) -> None:
        """Group resources by tier and create tracking state.

        Args:
            resources: List of Resource objects
        """
        from ..restore.dependency import get_deletion_tier

        for resource in resources:
            tier = get_deletion_tier(resource.resource_type)
            tracked = TrackedResource(resource=resource, tier=tier)

            if tier not in self.resources_by_tier:
                self.resources_by_tier[tier] = []
            self.resources_by_tier[tier].append(tracked)
            self.resource_map[resource.arn] = tracked

    def _get_resource_label(self, tracked: TrackedResource) -> str:
        """Get a short label for a resource.

        Args:
            tracked: TrackedResource to get label for

        Returns:
            Short label like "Lambda: my-function (us-east-1)"
        """
        resource = tracked.resource
        # Extract just the resource type name (e.g., "Instance" from "AWS::EC2::Instance")
        res_type = resource.resource_type
        type_short = res_type.split("::")[-1] if "::" in res_type else res_type
        return f"{type_short}: {resource.name} ({resource.region})"

    def _build_detailed_display(self) -> RenderableType:
        """Build detailed tree view showing all resources.

        Returns:
            Rich renderable with detailed resource list
        """
        lines: List[Text] = []

        # Header with overall progress
        completed = self.succeeded + self.failed
        pct = (completed / self.total * 100) if self.total > 0 else 0
        elapsed = time.time() - self.start_time if self.start_time else 0

        header = Text()
        header.append("Deletion Progress: ", style="bold")
        header.append(f"{completed}/{self.total}", style="cyan")
        header.append(f" ({pct:.0f}%)  ", style="dim")
        header.append(self._make_progress_bar(completed, self.total), style="cyan")
        header.append(f"  {elapsed:.0f}s", style="dim")
        lines.append(header)
        lines.append(Text())

        # Resources grouped by tier
        for tier in sorted(self.resources_by_tier.keys()):
            tier_resources = self.resources_by_tier[tier]
            tier_name = self.TIER_NAMES.get(tier, f"Tier {tier}")

            # Count completed in this tier
            tier_done = sum(
                1
                for r in tier_resources
                if r.status in (ResourceStatus.SUCCEEDED, ResourceStatus.SKIPPED, ResourceStatus.FAILED)
            )
            tier_failed = sum(1 for r in tier_resources if r.status == ResourceStatus.FAILED)
            tier_skipped = sum(1 for r in tier_resources if r.status == ResourceStatus.SKIPPED)

            # Tier header
            tier_header = Text()
            tier_header.append(f"Tier {tier}: {tier_name}", style="bold")
            tier_header.append(f" ({tier_done}/{len(tier_resources)})", style="dim")
            if tier_skipped > 0:
                tier_header.append(f" - {tier_skipped} skipped", style="cyan")
            if tier_failed > 0:
                tier_header.append(f" - {tier_failed} failed", style="red")
            lines.append(tier_header)

            # Individual resources
            for tracked in tier_resources:
                icon = self.STATUS_ICONS[tracked.status]
                color = self.STATUS_COLORS[tracked.status]
                label = self._get_resource_label(tracked)

                resource_line = Text()
                resource_line.append("  ")
                resource_line.append(icon, style=color)
                resource_line.append(" ")
                resource_line.append(label, style=color if tracked.status != ResourceStatus.PENDING else "")

                if tracked.status == ResourceStatus.IN_PROGRESS:
                    resource_line.append("  ← deleting", style="yellow italic")
                elif tracked.status == ResourceStatus.SKIPPED:
                    resource_line.append("  (already gone)", style="cyan italic")
                elif tracked.status == ResourceStatus.FAILED and tracked.error:
                    resource_line.append(f" - {tracked.error[:50]}", style="red dim")

                lines.append(resource_line)

            lines.append(Text())

        # Legend
        legend = Text()
        legend.append("Legend: ", style="dim")
        legend.append("✓", style="green")
        legend.append(" Deleted  ", style="dim")
        legend.append("⏭", style="cyan")
        legend.append(" Skipped  ", style="dim")
        legend.append("⋯", style="yellow")
        legend.append(" In Progress  ", style="dim")
        legend.append("○", style="dim")
        legend.append(" Pending  ", style="dim")
        legend.append("✗", style="red")
        legend.append(" Failed", style="dim")
        lines.append(legend)

        return Group(*lines)

    def _build_compact_display(self) -> RenderableType:
        """Build compact view with tier progress bars.

        Returns:
            Rich renderable with compact tier summaries
        """
        lines: List[Text] = []

        # Header with overall progress
        completed = self.succeeded + self.failed
        pct = (completed / self.total * 100) if self.total > 0 else 0
        elapsed = time.time() - self.start_time if self.start_time else 0

        header = Text()
        header.append("Deletion Progress: ", style="bold")
        header.append(f"{completed}/{self.total}", style="cyan")
        header.append(f" ({pct:.0f}%)  ", style="dim")
        header.append(self._make_progress_bar(completed, self.total, width=30), style="cyan")
        header.append(f"  {elapsed:.0f}s", style="dim")
        lines.append(header)
        lines.append(Text())

        # Tier summaries
        for tier in sorted(self.resources_by_tier.keys()):
            tier_resources = self.resources_by_tier[tier]
            tier_name = self.TIER_NAMES.get(tier, f"Tier {tier}")
            tier_total = len(tier_resources)

            # Count statuses
            tier_succeeded = sum(1 for r in tier_resources if r.status == ResourceStatus.SUCCEEDED)
            tier_failed = sum(1 for r in tier_resources if r.status == ResourceStatus.FAILED)
            tier_done = tier_succeeded + tier_failed
            tier_in_progress = sum(1 for r in tier_resources if r.status == ResourceStatus.IN_PROGRESS)

            # Build tier line
            tier_line = Text()
            tier_line.append(f"Tier {tier}: {tier_name:<24}", style="bold" if tier_in_progress else "")
            tier_line.append(self._make_progress_bar(tier_done, tier_total, width=20))
            tier_line.append(f"  {tier_done}/{tier_total}  ")

            if tier_done == tier_total and tier_total > 0:
                if tier_failed > 0:
                    tier_line.append(f"✗ {tier_failed} failed", style="red")
                else:
                    tier_line.append("✓", style="green")
            elif tier_in_progress:
                # Show current resource being deleted
                current_in_tier = next((r for r in tier_resources if r.status == ResourceStatus.IN_PROGRESS), None)
                if current_in_tier:
                    name = current_in_tier.resource.name
                    if len(name) > 20:
                        name = name[:17] + "..."
                    tier_line.append(f"⋯ {name}", style="yellow")

            lines.append(tier_line)

        lines.append(Text())

        # Legend
        legend = Text()
        legend.append("Legend: ", style="dim")
        legend.append("✓", style="green")
        legend.append(" Complete  ", style="dim")
        legend.append("⋯", style="yellow")
        legend.append(" In Progress  ", style="dim")
        legend.append("✗", style="red")
        legend.append(" Failed", style="dim")
        lines.append(legend)

        return Group(*lines)

    def _make_progress_bar(self, completed: int, total: int, width: int = 20) -> str:
        """Create a text-based progress bar.

        Args:
            completed: Number of completed items
            total: Total number of items
            width: Width of the bar in characters

        Returns:
            Progress bar string like "━━━━━━━━━━○○○○○○○○○○"
        """
        if total == 0:
            return "━" * width

        filled = int((completed / total) * width)
        empty = width - filled

        return "━" * filled + "○" * empty

    def _build_display(self) -> RenderableType:
        """Build the Rich renderable for current state.

        Chooses between detailed and compact mode based on total resource count.

        Returns:
            Rich renderable for the live display
        """
        if self.total >= self.COMPACT_THRESHOLD:
            return self._build_compact_display()
        else:
            return self._build_detailed_display()

    def start(self) -> None:
        """Start the live display."""
        self.start_time = time.time()
        self.live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,  # Keep final state visible
        )
        self.live.start()

    def mark_in_progress(self, resource: Any) -> None:
        """Mark resource as currently being deleted.

        Args:
            resource: Resource object being deleted
        """
        tracked = self.resource_map.get(resource.arn)
        if tracked:
            tracked.status = ResourceStatus.IN_PROGRESS
            self.current = tracked
            self._refresh()

    def mark_succeeded(self, resource: Any) -> None:
        """Mark resource as successfully deleted.

        Args:
            resource: Resource object that was deleted
        """
        tracked = self.resource_map.get(resource.arn)
        if tracked:
            tracked.status = ResourceStatus.SUCCEEDED
            self.succeeded += 1
            self.current = None
            self._refresh()

    def mark_skipped(self, resource: Any) -> None:
        """Mark resource as skipped (already deleted / not found).

        Args:
            resource: Resource object that was already deleted
        """
        tracked = self.resource_map.get(resource.arn)
        if tracked:
            tracked.status = ResourceStatus.SKIPPED
            self.skipped += 1
            self.current = None
            self._refresh()

    def mark_failed(self, resource: Any, error: str) -> None:
        """Mark resource as failed to delete.

        Args:
            resource: Resource object that failed to delete
            error: Error message describing the failure
        """
        tracked = self.resource_map.get(resource.arn)
        if tracked:
            tracked.status = ResourceStatus.FAILED
            tracked.error = error
            self.failed += 1
            self.current = None
            self._refresh()

    def _refresh(self) -> None:
        """Refresh the live display with current state."""
        if self.live:
            self.live.update(self._build_display())

    def stop(self) -> None:
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None

    def print_final_summary(self) -> None:
        """Print a final summary report of all deletions organized by tier."""
        from rich.table import Table

        self.console.print()

        # Calculate totals first for the header
        total_deleted = 0
        total_skipped = 0
        total_failed = 0
        for tier_resources in self.resources_by_tier.values():
            total_deleted += sum(1 for r in tier_resources if r.status == ResourceStatus.SUCCEEDED)
            total_skipped += sum(1 for r in tier_resources if r.status == ResourceStatus.SKIPPED)
            total_failed += sum(1 for r in tier_resources if r.status == ResourceStatus.FAILED)

        # Determine overall status emoji
        if total_failed == 0 and (total_deleted > 0 or total_skipped > 0):
            status_emoji = "✨"
            if total_skipped > 0:
                status_text = f"Complete! {total_deleted} deleted, {total_skipped} already gone"
            else:
                status_text = "All resources deleted successfully!"
            status_style = "bold green"
        elif total_failed > 0 and (total_deleted > 0 or total_skipped > 0):
            status_emoji = "⚠️"
            status_text = f"{total_deleted} deleted, {total_skipped} skipped, {total_failed} failed"
            status_style = "bold yellow"
        elif total_failed > 0:
            status_emoji = "❌"
            status_text = "Deletion encountered errors"
            status_style = "bold red"
        else:
            status_emoji = "📋"
            status_text = "No resources to delete"
            status_style = "dim"

        # Print header
        self.console.print()
        self.console.print(f"  {status_emoji}  [{status_style}]{status_text}[/{status_style}]")
        self.console.print()

        # Build summary table
        table = Table(
            title="🗑️  Deletion Summary by Tier",
            show_header=True,
            header_style="bold white on dark_blue",
            border_style="blue",
            title_style="bold cyan",
            row_styles=["", "dim"],
        )
        table.add_column("", width=3, justify="center")  # Emoji column
        table.add_column("Tier", style="cyan", width=4, justify="center")
        table.add_column("Layer", width=22)
        table.add_column("✅ Deleted", style="green", justify="right", width=9)
        table.add_column("⏭️ Skipped", style="cyan", justify="right", width=9)
        table.add_column("❌ Failed", style="red", justify="right", width=9)
        table.add_column("📊 Total", justify="right", width=8)

        for tier in sorted(self.resources_by_tier.keys()):
            tier_resources = self.resources_by_tier[tier]
            tier_name = self.TIER_NAMES.get(tier, f"Tier {tier}")
            tier_emoji = self.TIER_EMOJIS.get(tier, "📦")

            deleted_count = sum(1 for r in tier_resources if r.status == ResourceStatus.SUCCEEDED)
            skipped_count = sum(1 for r in tier_resources if r.status == ResourceStatus.SKIPPED)
            failed_count = sum(1 for r in tier_resources if r.status == ResourceStatus.FAILED)
            tier_total = len(tier_resources)

            # Only show tiers that have resources
            if tier_total > 0:
                table.add_row(
                    tier_emoji,
                    str(tier),
                    tier_name,
                    f"[green]{deleted_count}[/green]" if deleted_count > 0 else "[dim]-[/dim]",
                    f"[cyan]{skipped_count}[/cyan]" if skipped_count > 0 else "[dim]-[/dim]",
                    f"[red]{failed_count}[/red]" if failed_count > 0 else "[dim]-[/dim]",
                    str(tier_total),
                )

        # Add totals row
        table.add_section()
        table.add_row(
            "🎯",
            "",
            "[bold]TOTAL[/bold]",
            f"[bold green]{total_deleted}[/bold green]",
            f"[bold cyan]{total_skipped}[/bold cyan]" if total_skipped > 0 else "[dim]-[/dim]",
            f"[bold red]{total_failed}[/bold red]" if total_failed > 0 else "[dim]-[/dim]",
            f"[bold]{self.total}[/bold]",
        )

        self.console.print(table)

        # Show failed resources detail if any
        if total_failed > 0:
            self.console.print()
            self.console.print("  ❌  [bold red]Failed Resources[/bold red]")
            self.console.print("  " + "─" * 50)

            for tier in sorted(self.resources_by_tier.keys()):
                tier_resources = self.resources_by_tier[tier]
                failed_in_tier = [r for r in tier_resources if r.status == ResourceStatus.FAILED]

                if failed_in_tier:
                    tier_name = self.TIER_NAMES.get(tier, f"Tier {tier}")
                    tier_emoji = self.TIER_EMOJIS.get(tier, "📦")
                    self.console.print(f"\n  {tier_emoji}  [bold]Tier {tier}: {tier_name}[/bold]")

                    for tracked in failed_in_tier:
                        label = self._get_resource_label(tracked)
                        error_msg = tracked.error or "Unknown error"
                        # Truncate long errors
                        if len(error_msg) > 60:
                            error_msg = error_msg[:57] + "..."
                        self.console.print(f"      [red]✗[/red] {label}")
                        self.console.print(f"        [dim italic]{error_msg}[/dim italic]")

            self.console.print()
        else:
            self.console.print()
            self.console.print("  🎉  [green]All resources cleaned up successfully![/green]")
            self.console.print()
