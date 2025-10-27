"""Main CLI entry point using Typer."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from datetime import datetime
import sys

from .config import Config
from ..utils.logging import setup_logging
from ..snapshot.storage import SnapshotStorage
from ..aws.credentials import validate_credentials, CredentialValidationError

# Create Typer app
app = typer.Typer(
    name="aws-baseline",
    help="AWS Baseline Snapshot & Delta Tracking CLI tool",
    add_completion=False,
)

# Create Rich console for output
console = Console()

# Global config
config: Optional[Config] = None


@app.callback()
def main(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except errors"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
):
    """AWS Baseline Snapshot & Delta Tracking CLI tool."""
    global config

    # Load configuration
    config = Config.load()

    # Override with CLI options
    if profile:
        config.aws_profile = profile

    # Setup logging
    log_level = "ERROR" if quiet else ("DEBUG" if verbose else config.log_level)
    setup_logging(level=log_level)

    # Disable colors if requested
    if no_color:
        console.no_color = True


@app.command()
def version():
    """Show version information."""
    from .. import __version__
    import boto3
    import sys

    console.print(f"aws-baseline-snapshot version {__version__}")
    console.print(f"Python {sys.version.split()[0]}")
    console.print(f"boto3 {boto3.__version__}")


# Snapshot commands group
snapshot_app = typer.Typer(help="Snapshot management commands")
app.add_typer(snapshot_app, name="snapshot")


@snapshot_app.command("create")
def snapshot_create(
    name: Optional[str] = typer.Argument(None, help="Snapshot name (auto-generated if not provided)"),
    regions: Optional[str] = typer.Option(None, "--regions", help="Comma-separated list of regions (default: us-east-1)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name to use"),
    set_active: bool = typer.Option(True, "--set-active/--no-set-active", help="Set as active baseline"),
    compress: bool = typer.Option(False, "--compress", help="Compress snapshot with gzip"),
    before_date: Optional[str] = typer.Option(None, "--before-date", help="Include only resources created before date (YYYY-MM-DD)"),
    after_date: Optional[str] = typer.Option(None, "--after-date", help="Include only resources created on/after date (YYYY-MM-DD)"),
    filter_tags: Optional[str] = typer.Option(None, "--filter-tags", help="DEPRECATED: use --include-tags instead"),
    include_tags: Optional[str] = typer.Option(None, "--include-tags", help="Include only resources with ALL these tags (Key=Value,Key2=Value2)"),
    exclude_tags: Optional[str] = typer.Option(None, "--exclude-tags", help="Exclude resources with ANY of these tags (Key=Value,Key2=Value2)"),
):
    """Create a new baseline snapshot of AWS resources.

    Captures resources from 25 AWS services:
    - IAM: Roles, Users, Groups, Policies
    - Lambda: Functions, Layers
    - S3: Buckets
    - EC2: Instances, Volumes, VPCs, Security Groups, Subnets, VPC Endpoints
    - RDS: DB Instances, DB Clusters (including Aurora)
    - CloudWatch: Alarms, Log Groups
    - SNS: Topics
    - SQS: Queues
    - DynamoDB: Tables
    - ELB: Load Balancers (Classic, ALB, NLB, GWLB)
    - CloudFormation: Stacks
    - API Gateway: REST APIs, HTTP APIs, WebSocket APIs
    - EventBridge: Event Buses, Rules
    - Secrets Manager: Secrets
    - KMS: Customer-Managed Keys
    - Systems Manager: Parameters, Documents
    - Route53: Hosted Zones
    - ECS: Clusters, Services, Task Definitions
    - EKS: Clusters, Node Groups, Fargate Profiles
    - Step Functions: State Machines
    - WAF: Web ACLs (Regional & CloudFront)
    - CodePipeline: Pipelines
    - CodeBuild: Projects
    - Backup: Backup Plans, Backup Vaults

    Historical Baselines & Filtering:
    Use --before-date, --after-date, --include-tags, and/or --exclude-tags to create
    snapshots representing resources as they existed at specific points in time or with
    specific characteristics.

    Examples:
    - Production only: --include-tags Environment=production
    - Exclude test/dev: --exclude-tags Environment=test,Environment=dev
    - Multiple filters: --include-tags Team=platform,Environment=prod --exclude-tags Status=archived
    """
    try:
        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials
        console.print("🔐 Validating AWS credentials...")
        identity = validate_credentials(aws_profile)
        console.print(f"✓ Authenticated as: {identity['arn']}\n", style="green")

        # Generate snapshot name if not provided
        if not name:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            name = f"baseline-{timestamp}"

        # Parse regions - default to us-east-1
        region_list = []
        if regions:
            region_list = [r.strip() for r in regions.split(',')]
        elif config.regions:
            region_list = config.regions
        else:
            # Default to us-east-1
            region_list = ['us-east-1']

        console.print(f"📸 Creating snapshot: [bold]{name}[/bold]")
        console.print(f"Regions: {', '.join(region_list)}\n")

        # Parse filters
        resource_filter = None
        if before_date or after_date or filter_tags or include_tags or exclude_tags:
            from ..snapshot.filter import ResourceFilter
            from datetime import datetime as dt

            # Parse dates
            before_dt = None
            after_dt = None

            if before_date:
                try:
                    before_dt = dt.strptime(before_date, '%Y-%m-%d')
                except ValueError:
                    console.print(f"✗ Invalid --before-date format. Use YYYY-MM-DD", style="bold red")
                    raise typer.Exit(code=1)

            if after_date:
                try:
                    after_dt = dt.strptime(after_date, '%Y-%m-%d')
                except ValueError:
                    console.print(f"✗ Invalid --after-date format. Use YYYY-MM-DD", style="bold red")
                    raise typer.Exit(code=1)

            # Helper function to parse tag strings
            def parse_tags(tag_string: str) -> Dict[str, str]:
                """Parse comma-separated Key=Value pairs into dict."""
                tags = {}
                for tag_pair in tag_string.split(','):
                    if '=' not in tag_pair:
                        console.print(f"✗ Invalid tag format. Use Key=Value", style="bold red")
                        raise typer.Exit(code=1)
                    key, value = tag_pair.split('=', 1)
                    tags[key.strip()] = value.strip()
                return tags

            # Parse include tags (supports both --filter-tags and --include-tags)
            include_tags_dict = {}
            if filter_tags:
                console.print("⚠️  Note: --filter-tags is deprecated, use --include-tags", style="yellow")
                try:
                    include_tags_dict = parse_tags(filter_tags)
                except Exception as e:
                    console.print(f"✗ Error parsing filter-tags: {e}", style="bold red")
                    raise typer.Exit(code=1)

            if include_tags:
                try:
                    include_tags_dict.update(parse_tags(include_tags))
                except Exception as e:
                    console.print(f"✗ Error parsing include-tags: {e}", style="bold red")
                    raise typer.Exit(code=1)

            # Parse exclude tags
            exclude_tags_dict = {}
            if exclude_tags:
                try:
                    exclude_tags_dict = parse_tags(exclude_tags)
                except Exception as e:
                    console.print(f"✗ Error parsing exclude-tags: {e}", style="bold red")
                    raise typer.Exit(code=1)

            # Create filter
            resource_filter = ResourceFilter(
                before_date=before_dt,
                after_date=after_dt,
                include_tags=include_tags_dict if include_tags_dict else None,
                exclude_tags=exclude_tags_dict if exclude_tags_dict else None,
            )

            console.print(f"{resource_filter.get_filter_summary()}\n")

        # Import snapshot creation
        from ..snapshot.capturer import create_snapshot

        snapshot = create_snapshot(
            name=name,
            regions=region_list,
            account_id=identity['account_id'],
            profile_name=aws_profile,
            set_active=set_active,
            resource_filter=resource_filter,
        )

        # Save snapshot
        storage = SnapshotStorage(config.snapshot_dir)
        filepath = storage.save_snapshot(snapshot, compress=compress)

        # Display summary
        console.print("\n✓ Snapshot complete!", style="bold green")
        console.print(f"\nSummary:")
        console.print(f"  Name: {snapshot.name}")
        console.print(f"  Resources: {snapshot.resource_count}")
        console.print(f"  File: {filepath}")
        console.print(f"  Active: {'Yes' if snapshot.is_active else 'No'}")

        # Show collection errors if any
        collection_errors = snapshot.metadata.get('collection_errors', [])
        if collection_errors:
            console.print(f"\n⚠️  Note: {len(collection_errors)} service(s) were unavailable", style="yellow")
            if verbose:
                console.print("  Run with --verbose for details")

        # Show filtering stats if filters were applied
        if snapshot.filters_applied:
            stats = snapshot.filters_applied.get('statistics', {})
            console.print(f"\nFiltering:")
            console.print(f"  Collected: {stats.get('total_collected', 0)}")
            console.print(f"  Matched filters: {stats.get('final_count', 0)}")
            console.print(f"  Filtered out: {stats.get('total_collected', 0) - stats.get('final_count', 0)}")

        # Show service breakdown
        if snapshot.service_counts:
            console.print("\nResources by service:")
            table = Table(show_header=True)
            table.add_column("Service", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for service, count in sorted(snapshot.service_counts.items()):
                table.add_row(service, str(count))

            console.print(table)

    except CredentialValidationError as e:
        console.print(f"✗ Error: {e}", style="bold red")
        raise typer.Exit(code=3)
    except Exception as e:
        console.print(f"✗ Error creating snapshot: {e}", style="bold red")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=2)


@snapshot_app.command("list")
def snapshot_list():
    """List all available snapshots."""
    try:
        storage = SnapshotStorage(config.snapshot_dir)
        snapshots = storage.list_snapshots()

        if not snapshots:
            console.print("No snapshots found.", style="yellow")
            return

        # Create table
        table = Table(show_header=True, title="Available Snapshots")
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Size (MB)", justify="right")
        table.add_column("Active", justify="center")

        for snap in snapshots:
            active_marker = "✓" if snap['is_active'] else ""
            table.add_row(
                snap['name'],
                snap['modified'].strftime("%Y-%m-%d %H:%M"),
                f"{snap['size_mb']:.2f}",
                active_marker,
            )

        console.print(table)
        console.print(f"\nTotal snapshots: {len(snapshots)}")

    except Exception as e:
        console.print(f"✗ Error listing snapshots: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("show")
def snapshot_show(name: str = typer.Argument(..., help="Snapshot name to display")):
    """Display detailed information about a snapshot."""
    try:
        storage = SnapshotStorage(config.snapshot_dir)
        snapshot = storage.load_snapshot(name)

        console.print(f"\n[bold]Snapshot: {snapshot.name}[/bold]")
        console.print(f"Created: {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print(f"Account: {snapshot.account_id}")
        console.print(f"Regions: {', '.join(snapshot.regions)}")
        console.print(f"Status: {'Active baseline' if snapshot.is_active else 'Inactive'}")
        console.print(f"Total resources: {snapshot.resource_count}\n")

        # Show filters if applied
        if snapshot.filters_applied:
            console.print("Filters applied:")
            date_filters = snapshot.filters_applied.get('date_filters', {})
            if date_filters.get('before_date'):
                console.print(f"  Before: {date_filters['before_date']}")
            if date_filters.get('after_date'):
                console.print(f"  After: {date_filters['after_date']}")
            tag_filters = snapshot.filters_applied.get('tag_filters', {})
            if tag_filters:
                console.print(f"  Tags: {tag_filters}")
            console.print()

        # Service breakdown
        if snapshot.service_counts:
            console.print("Resources by service:")
            table = Table(show_header=True)
            table.add_column("Service", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Percent", justify="right")

            for service, count in sorted(snapshot.service_counts.items(), key=lambda x: x[1], reverse=True):
                percent = (count / snapshot.resource_count * 100) if snapshot.resource_count > 0 else 0
                table.add_row(service, str(count), f"{percent:.1f}%")

            console.print(table)

    except FileNotFoundError:
        console.print(f"✗ Snapshot '{name}' not found", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error loading snapshot: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("set-active")
def snapshot_set_active(name: str = typer.Argument(..., help="Snapshot name to set as active")):
    """Set a snapshot as the active baseline.

    The active baseline is used by default for delta and cost analysis.
    """
    try:
        storage = SnapshotStorage(config.snapshot_dir)
        storage.set_active_snapshot(name)

        console.print(f"✓ Set [bold]{name}[/bold] as active baseline", style="green")

    except FileNotFoundError:
        console.print(f"✗ Snapshot '{name}' not found", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error setting active snapshot: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("delete")
def snapshot_delete(
    name: str = typer.Argument(..., help="Snapshot name to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a snapshot.

    Cannot delete the active baseline - set another snapshot as active first.
    """
    try:
        storage = SnapshotStorage(config.snapshot_dir)

        # Load snapshot to show info
        snapshot = storage.load_snapshot(name)

        # Confirm deletion
        if not yes:
            console.print(f"\n[yellow]⚠️  About to delete snapshot:[/yellow]")
            console.print(f"  Name: {snapshot.name}")
            console.print(f"  Created: {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            console.print(f"  Resources: {snapshot.resource_count}")
            console.print(f"  Active: {'Yes' if snapshot.is_active else 'No'}\n")

            confirm = typer.confirm("Are you sure you want to delete this snapshot?")
            if not confirm:
                console.print("Cancelled")
                raise typer.Exit(code=0)

        # Delete snapshot
        storage.delete_snapshot(name)

        console.print(f"✓ Deleted snapshot [bold]{name}[/bold]", style="green")

    except FileNotFoundError:
        console.print(f"✗ Snapshot '{name}' not found", style="bold red")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"✗ {e}", style="bold red")
        console.print("\nTip: Set another snapshot as active first:")
        console.print(f"  aws-baseline snapshot set-active <other-snapshot-name>")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error deleting snapshot: {e}", style="bold red")
        raise typer.Exit(code=1)


@app.command()
def delta(
    snapshot: Optional[str] = typer.Option(None, "--snapshot", help="Baseline snapshot name (default: active)"),
    resource_type: Optional[str] = typer.Option(None, "--resource-type", help="Filter by resource type"),
    region: Optional[str] = typer.Option(None, "--region", help="Filter by region"),
    show_details: bool = typer.Option(False, "--show-details", help="Show detailed resource information"),
    export: Optional[str] = typer.Option(None, "--export", help="Export to file (JSON or CSV based on extension)"),
):
    """View resource changes since baseline snapshot.

    Compares current AWS state to the baseline snapshot and shows added, deleted,
    and modified resources.
    """
    try:
        # Load baseline snapshot
        storage = SnapshotStorage(config.snapshot_dir)

        if snapshot:
            baseline_snapshot = storage.load_snapshot(snapshot)
        else:
            # Use active snapshot
            active_name = storage.get_active_snapshot_name()
            if not active_name:
                console.print("✗ No active baseline snapshot found", style="bold red")
                console.print("Create a snapshot first: aws-baseline snapshot create")
                raise typer.Exit(code=1)
            baseline_snapshot = storage.load_snapshot(active_name)

        console.print(f"🔍 Comparing to baseline: [bold]{baseline_snapshot.name}[/bold]")
        console.print(f"   Created: {baseline_snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

        # Prepare filters
        resource_type_filter = [resource_type] if resource_type else None
        region_filter = [region] if region else None

        # Calculate delta
        from ..delta.calculator import compare_to_current_state

        delta_report = compare_to_current_state(
            baseline_snapshot=baseline_snapshot,
            profile_name=config.aws_profile,
            regions=None,  # Use baseline regions
            resource_type_filter=resource_type_filter,
            region_filter=region_filter,
        )

        # Display delta
        from ..delta.reporter import DeltaReporter

        reporter = DeltaReporter(console)
        reporter.display(delta_report, show_details=show_details)

        # Export if requested
        if export:
            if export.endswith('.json'):
                reporter.export_json(delta_report, export)
            elif export.endswith('.csv'):
                reporter.export_csv(delta_report, export)
            else:
                console.print(f"✗ Unsupported export format. Use .json or .csv", style="bold red")
                raise typer.Exit(code=1)

        # Exit with code 0 if no changes (for scripting)
        if not delta_report.has_changes:
            raise typer.Exit(code=0)

    except FileNotFoundError as e:
        console.print(f"✗ Snapshot not found: {e}", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error calculating delta: {e}", style="bold red")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=2)


@app.command()
def cost(
    snapshot: Optional[str] = typer.Option(None, "--snapshot", help="Baseline snapshot name (default: active)"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Start date (YYYY-MM-DD, default: snapshot date)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (YYYY-MM-DD, default: today)"),
    granularity: str = typer.Option("MONTHLY", "--granularity", help="Cost granularity: DAILY or MONTHLY"),
    show_services: bool = typer.Option(True, "--show-services/--no-services", help="Show service breakdown"),
    export: Optional[str] = typer.Option(None, "--export", help="Export to file (JSON or CSV based on extension)"),
):
    """Analyze cost breakdown between baseline and non-baseline resources.

    Shows "dial tone" baseline costs vs project costs for proper cost allocation
    and chargeback.
    """
    try:
        # Load baseline snapshot
        storage = SnapshotStorage(config.snapshot_dir)

        if snapshot:
            baseline_snapshot = storage.load_snapshot(snapshot)
        else:
            # Use active snapshot
            active_name = storage.get_active_snapshot_name()
            if not active_name:
                console.print("✗ No active baseline snapshot found", style="bold red")
                console.print("Create a snapshot first: aws-baseline snapshot create")
                raise typer.Exit(code=1)
            baseline_snapshot = storage.load_snapshot(active_name)

        console.print(f"💰 Analyzing costs for baseline: [bold]{baseline_snapshot.name}[/bold]\n")

        # Parse dates
        from datetime import datetime as dt

        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = dt.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                console.print(f"✗ Invalid start date format. Use YYYY-MM-DD", style="bold red")
                raise typer.Exit(code=1)

        if end_date:
            try:
                end_dt = dt.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                console.print(f"✗ Invalid end date format. Use YYYY-MM-DD", style="bold red")
                raise typer.Exit(code=1)

        # Validate granularity
        if granularity not in ['DAILY', 'MONTHLY']:
            console.print(f"✗ Invalid granularity. Use DAILY or MONTHLY", style="bold red")
            raise typer.Exit(code=1)

        # Analyze costs
        from ..cost.explorer import CostExplorerClient, CostExplorerError
        from ..cost.analyzer import CostAnalyzer

        try:
            cost_explorer = CostExplorerClient(profile_name=config.aws_profile)
            analyzer = CostAnalyzer(cost_explorer)

            cost_report = analyzer.analyze(
                baseline_snapshot=baseline_snapshot,
                start_date=start_dt,
                end_date=end_dt,
                granularity=granularity,
            )

            # Display cost report
            from ..cost.reporter import CostReporter

            reporter = CostReporter(console)
            reporter.display(cost_report, show_services=show_services)

            # Export if requested
            if export:
                if export.endswith('.json'):
                    reporter.export_json(cost_report, export)
                elif export.endswith('.csv'):
                    reporter.export_csv(cost_report, export)
                else:
                    console.print(f"✗ Unsupported export format. Use .json or .csv", style="bold red")
                    raise typer.Exit(code=1)

        except CostExplorerError as e:
            console.print(f"✗ Cost Explorer error: {e}", style="bold red")
            console.print("\nTroubleshooting:")
            console.print("  1. Ensure Cost Explorer is enabled in your AWS account")
            console.print("  2. Check IAM permissions: ce:GetCostAndUsage")
            console.print("  3. Cost data typically has a 24-48 hour lag")
            raise typer.Exit(code=3)

    except FileNotFoundError as e:
        console.print(f"✗ Snapshot not found: {e}", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error analyzing costs: {e}", style="bold red")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=2)


def cli_main():
    """Entry point for console script."""
    app()


if __name__ == "__main__":
    cli_main()
