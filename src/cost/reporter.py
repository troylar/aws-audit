"""Cost report formatting and display."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models.cost_report import CostReport


class CostReporter:
    """Format and display cost reports."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize cost reporter.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()

    def display(self, report: CostReport, show_services: bool = True, has_deltas: bool = False) -> None:
        """Display cost report to console.

        Args:
            report: CostReport to display
            show_services: Whether to show service-level breakdown
            has_deltas: Whether there are resource changes (deltas)
        """
        # Header
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Cost Analysis Report[/bold]\n"
                f"Snapshot: {report.baseline_snapshot_name}\n"
                f"Period: {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}\n"
                f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                style="cyan",
            )
        )
        self.console.print()

        # Data completeness warning
        if not report.data_complete and report.data_through:
            self.console.print(
                f"⚠️  [yellow]Note: Cost data has {report.lag_days} day lag. "
                f"Data available through {report.data_through.strftime('%Y-%m-%d')}[/yellow]\n"
            )

        # If no deltas, show simplified view
        if not has_deltas:
            self.console.print(
                "✓ [green]No resource changes detected - all costs are from snapshot resources[/green]\n"
            )
            self._display_snapshot_costs(report)
        else:
            # Summary table with baseline/non-baseline split
            self._display_summary(report)

        # Service breakdown
        if show_services and report.baseline_costs.by_service:
            self.console.print()
            self._display_service_breakdown(report, has_deltas)

    def _display_snapshot_costs(self, report: CostReport) -> None:
        """Display snapshot costs (no splitting since there are no changes)."""
        table = Table(title="Snapshot Costs", show_header=True, header_style="bold cyan")
        table.add_column("Total Cost", justify="right", style="bold green", width=20)
        table.add_row(f"${report.baseline_costs.total:,.2f}")
        self.console.print(table)

    def _display_summary(self, report: CostReport) -> None:
        """Display cost summary."""
        table = Table(title="Cost Summary", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan", width=25)
        table.add_column("Amount (USD)", justify="right", style="green", width=15)
        table.add_column("Percentage", justify="right", width=12)
        table.add_column("Visual", width=30)

        # Baseline costs
        baseline_bar = self._create_progress_bar(report.baseline_percentage, color="blue")
        table.add_row(
            '💰 Baseline ("Dial Tone")',
            f"${report.baseline_costs.total:,.2f}",
            f"{report.baseline_percentage:.1f}%",
            baseline_bar,
        )

        # Non-baseline costs
        non_baseline_bar = self._create_progress_bar(report.non_baseline_percentage, color="yellow")
        table.add_row(
            "📊 Non-Baseline (Projects)",
            f"${report.non_baseline_costs.total:,.2f}",
            f"{report.non_baseline_percentage:.1f}%",
            non_baseline_bar,
        )

        # Separator
        table.add_row("━" * 25, "━" * 15, "━" * 12, "━" * 30, style="dim")

        # Total
        table.add_row("[bold]Total", f"[bold]${report.total_cost:,.2f}", "[bold]100.0%", "")

        self.console.print(table)

    def _display_service_breakdown(self, report: CostReport, has_deltas: bool = False) -> None:
        """Display service-level cost breakdown."""
        # Get top services
        top_baseline = report.get_top_services(limit=10, baseline=True)

        if top_baseline:
            title = "Costs by Service" if not has_deltas else "Top Baseline Services"
            self.console.print(f"[bold cyan]{title}:[/bold cyan]")
            baseline_table = Table(show_header=True, box=None, padding=(0, 2))
            baseline_table.add_column("Service", style="white")
            baseline_table.add_column("Cost", justify="right", style="green")
            baseline_table.add_column("% of Total", justify="right", style="dim")

            for service, cost in top_baseline.items():
                pct = (cost / report.baseline_costs.total * 100) if report.baseline_costs.total > 0 else 0
                baseline_table.add_row(self._shorten_service_name(service), f"${cost:,.2f}", f"{pct:.1f}%")

            self.console.print(baseline_table)
            self.console.print()

        # Only show non-baseline section if there are actual deltas
        if has_deltas:
            top_non_baseline = report.get_top_services(limit=5, baseline=False)
            if top_non_baseline:
                self.console.print("[bold yellow]Top Non-Baseline Services:[/bold yellow]")
                non_baseline_table = Table(show_header=True, box=None, padding=(0, 2))
                non_baseline_table.add_column("Service", style="white")
                non_baseline_table.add_column("Cost", justify="right", style="green")
                non_baseline_table.add_column("% of Non-Baseline", justify="right", style="dim")

                for service, cost in top_non_baseline.items():
                    pct = (cost / report.non_baseline_costs.total * 100) if report.non_baseline_costs.total > 0 else 0
                    non_baseline_table.add_row(self._shorten_service_name(service), f"${cost:,.2f}", f"{pct:.1f}%")

                self.console.print(non_baseline_table)

    def _create_progress_bar(self, percentage: float, color: str = "green") -> str:
        """Create a text-based progress bar.

        Args:
            percentage: Percentage value (0-100)
            color: Color for the bar

        Returns:
            Formatted progress bar string
        """
        width = 20
        filled = int((percentage / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{color}]{bar}[/{color}]"

    def _shorten_service_name(self, service_name: str) -> str:
        """Shorten AWS service names for display.

        Args:
            service_name: Full AWS service name

        Returns:
            Shortened service name
        """
        # Common abbreviations
        replacements = {
            "Amazon Elastic Compute Cloud - Compute": "EC2",
            "Amazon Simple Storage Service": "S3",
            "AWS Lambda": "Lambda",
            "Amazon Relational Database Service": "RDS",
            "AWS Identity and Access Management": "IAM",
            "Amazon Virtual Private Cloud": "VPC",
            "Amazon CloudWatch": "CloudWatch",
            "Amazon Simple Notification Service": "SNS",
            "Amazon Simple Queue Service": "SQS",
            "Amazon DynamoDB": "DynamoDB",
        }

        return replacements.get(service_name, service_name)

    def export_json(self, report: CostReport, filepath: str) -> None:
        """Export cost report to JSON file.

        Args:
            report: CostReport to export
            filepath: Destination file path
        """
        from ..utils.export import export_to_json

        export_to_json(report.to_dict(), filepath)
        self.console.print(f"[green]✓ Cost report exported to {filepath}[/green]")

    def export_csv(self, report: CostReport, filepath: str) -> None:
        """Export cost report to CSV file.

        Args:
            report: CostReport to export
            filepath: Destination file path
        """
        from ..utils.export import export_to_csv

        # Flatten into rows - one row per service
        rows = []

        # Baseline services
        for service, cost in report.baseline_costs.by_service.items():
            pct = (cost / report.baseline_costs.total * 100) if report.baseline_costs.total > 0 else 0
            rows.append(
                {
                    "category": "baseline",
                    "service": service,
                    "cost": cost,
                    "percentage_of_category": pct,
                    "percentage_of_total": (cost / report.total_cost * 100) if report.total_cost > 0 else 0,
                }
            )

        # Non-baseline services
        for service, cost in report.non_baseline_costs.by_service.items():
            pct = (cost / report.non_baseline_costs.total * 100) if report.non_baseline_costs.total > 0 else 0
            rows.append(
                {
                    "category": "non_baseline",
                    "service": service,
                    "cost": cost,
                    "percentage_of_category": pct,
                    "percentage_of_total": (cost / report.total_cost * 100) if report.total_cost > 0 else 0,
                }
            )

        if rows:
            export_to_csv(rows, filepath)
            self.console.print(f"[green]✓ Cost report exported to {filepath}[/green]")
        else:
            self.console.print("[yellow]⚠ No cost data to export[/yellow]")
