"""Main CLI entry point using Typer."""

import logging
import sys
from datetime import datetime
from typing import List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ..aws.credentials import CredentialValidationError, validate_credentials
from ..snapshot.storage import SnapshotStorage
from ..utils.logging import setup_logging
from .config import Config

logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    name="awsinv",
    help="AWS Inventory Manager - Resource Snapshot & Delta Tracking CLI tool",
    add_completion=False,
)

# Create Rich console for output
console = Console()

# Global config
config: Optional[Config] = None


def show_quickstart():
    """Display quickstart guide for new users."""
    quickstart_content = """
# AWS Inventory Manager - Quick Start

Welcome to AWS Inventory Manager! This tool helps you track AWS resources, create snapshots, and analyze costs.

## Complete Walkthrough

Follow these steps to get started. All commands use the same inventory and snapshot names
for continuity - you can run them in sequence!

### 1. Create an Inventory
An inventory is a named collection of snapshots for tracking resource changes over time.

```bash
awsinv inventory create prod-baseline --description "Production baseline resources"
```

### 2. Take Your First Snapshot
Capture the current state of AWS resources in your region(s).

```bash
awsinv snapshot create initial --regions us-east-1 --inventory prod-baseline
```

This creates a snapshot named "initial" in the "prod-baseline" inventory.

### 3. (Optional) Make Some Changes
Make changes to your AWS environment - deploy resources, update configurations, etc.
Then take another snapshot to see what changed.

```bash
awsinv snapshot create current --regions us-east-1 --inventory prod-baseline
```

### 4. Compare Snapshots (Delta Analysis)
See exactly what resources were added, removed, or changed since your snapshot.

```bash
awsinv delta --snapshot initial --inventory prod-baseline
```

### 5. Analyze Costs
Get cost breakdown for the resources in your snapshot.

```bash
# Costs since snapshot was created
awsinv cost --snapshot initial --inventory prod-baseline

# Costs for specific date range
awsinv cost --snapshot initial --inventory prod-baseline \
  --start-date 2025-01-01 --end-date 2025-01-31
```

## Common Commands

Using the inventory and snapshots from above:

### List Resources
```bash
# List all inventories
awsinv inventory list

# List snapshots in your inventory
awsinv snapshot list --inventory prod-baseline

# Show snapshot details
awsinv snapshot show initial --inventory prod-baseline
```

### Advanced Filtering
```bash
# Create inventory with tag filters (production resources only)
awsinv inventory create production \\
  --description "Production resources only" \\
  --include-tags Environment=production

# Snapshot only resources created after a specific date
awsinv snapshot create recent --regions us-east-1 \\
  --inventory prod-baseline --after-date 2025-01-01
```

## Getting Help

```bash
# General help
awsinv --help

# Help for specific command
awsinv inventory --help
awsinv snapshot create --help
awsinv cost --help

# Show version
awsinv version
```

## Next Steps

**Ready to get started?** Follow the walkthrough above, starting with:

```bash
awsinv inventory create prod-baseline --description "Production baseline resources"
```

Then continue with the remaining steps to take snapshots, compare changes, and analyze costs.

For detailed help on any command, use `--help`:

```bash
awsinv snapshot create --help
awsinv cost --help
```
"""

    console.print(
        Panel(
            Markdown(quickstart_content),
            title="[bold cyan]🚀 AWS Inventory Manager[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


@app.callback()
def main(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    storage_path: Optional[str] = typer.Option(
        None,
        "--storage-path",
        help="Custom path for snapshot storage (default: ~/.snapshots or $AWS_INVENTORY_STORAGE_PATH)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except errors"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
):
    """AWS Inventory Manager - Resource Snapshot & Delta Tracking CLI tool."""
    global config

    # Load configuration
    config = Config.load()

    # Override with CLI options
    if profile:
        config.aws_profile = profile

    # Store storage path in config for use by commands
    if storage_path:
        config.storage_path = storage_path
    else:
        config.storage_path = None

    # Setup logging
    log_level = "ERROR" if quiet else ("DEBUG" if verbose else config.log_level)
    setup_logging(level=log_level, verbose=verbose)

    # Disable colors if requested
    if no_color:
        console.no_color = True


@app.command()
def version():
    """Show version information."""
    import boto3

    from .. import __version__

    console.print(f"aws-inventory-manager version {__version__}")
    console.print(f"Python {sys.version.split()[0]}")
    console.print(f"boto3 {boto3.__version__}")


# Inventory commands group
inventory_app = typer.Typer(help="Inventory management commands")
app.add_typer(inventory_app, name="inventory")


# Helper function to parse tag strings (shared by snapshot and inventory commands)
def parse_tags(tag_string: str) -> dict:
    """Parse comma-separated Key=Value pairs into dict."""
    tags = {}
    for tag_pair in tag_string.split(","):
        if "=" not in tag_pair:
            console.print("✗ Invalid tag format. Use Key=Value", style="bold red")
            raise typer.Exit(code=1)
        key, value = tag_pair.split("=", 1)
        tags[key.strip()] = value.strip()
    return tags


@inventory_app.command("create")
def inventory_create(
    name: str = typer.Argument(..., help="Inventory name (alphanumeric, hyphens, underscores only)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Human-readable description"),
    include_tags: Optional[str] = typer.Option(
        None, "--include-tags", help="Include only resources with ALL these tags (Key=Value,Key2=Value2)"
    ),
    exclude_tags: Optional[str] = typer.Option(
        None, "--exclude-tags", help="Exclude resources with ANY of these tags (Key=Value,Key2=Value2)"
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name to use"),
):
    """Create a new inventory for organizing snapshots.

    Inventories allow you to organize snapshots by purpose (e.g., baseline, team-a-resources)
    with optional tag-based filters that automatically apply to all snapshots in that inventory.

    Examples:
        # Create basic inventory with no filters
        aws-baseline inventory create baseline --description "Production baseline resources"

        # Create filtered inventory for team resources
        aws-baseline inventory create team-a-resources \\
            --description "Team Alpha project resources" \\
            --include-tags "team=alpha,env=prod" \\
            --exclude-tags "managed-by=terraform"
    """
    try:
        from datetime import datetime, timezone

        from ..aws.credentials import get_account_id
        from ..models.inventory import Inventory
        from ..snapshot.inventory_storage import InventoryStorage

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials and get account ID
        console.print("🔐 Validating AWS credentials...")
        account_id = get_account_id(aws_profile)
        console.print(f"✓ Authenticated for account: {account_id}\n", style="green")

        # Validate inventory name format
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            console.print("✗ Error: Invalid inventory name", style="bold red")
            console.print("Name must contain only alphanumeric characters, hyphens, and underscores\n")
            raise typer.Exit(code=1)

        if len(name) > 50:
            console.print("✗ Error: Inventory name too long", style="bold red")
            console.print("Name must be 50 characters or less\n")
            raise typer.Exit(code=1)

        # Check for duplicate
        storage = InventoryStorage(config.storage_path)
        if storage.exists(name, account_id):
            console.print(f"✗ Error: Inventory '{name}' already exists for account {account_id}", style="bold red")
            console.print("\nUse a different name or delete the existing inventory first:")
            console.print(f"  aws-baseline inventory delete {name}\n")
            raise typer.Exit(code=1)

        # Parse tags if provided
        include_tag_dict = {}
        exclude_tag_dict = {}

        if include_tags:
            include_tag_dict = parse_tags(include_tags)

        if exclude_tags:
            exclude_tag_dict = parse_tags(exclude_tags)

        # Create inventory
        inventory = Inventory(
            name=name,
            account_id=account_id,
            description=description or "",
            include_tags=include_tag_dict,
            exclude_tags=exclude_tag_dict,
            snapshots=[],
            active_snapshot=None,
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        # Save inventory
        storage.save(inventory)

        # T042: Audit logging for create operation
        logger.info(
            f"Created inventory '{name}' for account {account_id} with "
            f"{len(include_tag_dict)} include filters and {len(exclude_tag_dict)} exclude filters"
        )

        # Display success message
        console.print(f"✓ Created inventory '[bold]{name}[/bold]' for account {account_id}", style="green")
        console.print()
        console.print("[bold]Inventory Details:[/bold]")
        console.print(f"  Name: {name}")
        console.print(f"  Account: {account_id}")
        console.print(f"  Description: {description or '(none)'}")

        # Display filters
        if include_tag_dict or exclude_tag_dict:
            console.print("  Filters:")
            if include_tag_dict:
                tag_str = ", ".join(f"{k}={v}" for k, v in include_tag_dict.items())
                console.print(f"    Include Tags: {tag_str} (resources must have ALL)")
            if exclude_tag_dict:
                tag_str = ", ".join(f"{k}={v}" for k, v in exclude_tag_dict.items())
                console.print(f"    Exclude Tags: {tag_str} (resources must NOT have ANY)")
        else:
            console.print("  Filters: None")

        console.print("  Snapshots: 0")
        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error creating inventory: {e}", style="bold red")
        raise typer.Exit(code=2)


@inventory_app.command("list")
def inventory_list(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name to use"),
):
    """List all inventories for the current AWS account.

    Displays a table showing all inventories with their snapshot counts,
    filter settings, and descriptions.
    """
    try:
        from ..aws.credentials import get_account_id
        from ..snapshot.inventory_storage import InventoryStorage

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Get account ID
        account_id = get_account_id(aws_profile)

        # Load inventories
        storage = InventoryStorage(config.storage_path)
        inventories = storage.load_by_account(account_id)

        if not inventories:
            console.print(f"No inventories found for account {account_id}", style="yellow")
            console.print("\nCreate one with: aws-baseline inventory create <name>")
            return

        # Create table
        table = Table(title=f"Inventories for Account {account_id}", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", width=25)
        table.add_column("Snapshots", justify="center", width=12)
        table.add_column("Filters", width=15)
        table.add_column("Description", width=40)

        for inv in inventories:
            # Determine filter summary
            if inv.include_tags or inv.exclude_tags:
                inc_count = len(inv.include_tags)
                exc_count = len(inv.exclude_tags)
                filter_text = f"Yes ({inc_count}/{exc_count})"
            else:
                filter_text = "None"

            table.add_row(inv.name, str(len(inv.snapshots)), filter_text, inv.description or "(no description)")

        console.print()
        console.print(table)
        console.print()
        console.print(f"Total Inventories: {len(inventories)}")
        console.print()

    except Exception as e:
        console.print(f"✗ Error listing inventories: {e}", style="bold red")
        raise typer.Exit(code=2)


@inventory_app.command("show")
def inventory_show(
    name: str = typer.Argument(..., help="Inventory name to display"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name to use"),
):
    """Show detailed information for a specific inventory.

    Displays full details including filters, snapshots, and timestamps.
    """
    try:
        from ..aws.credentials import get_account_id
        from ..snapshot.inventory_storage import InventoryNotFoundError, InventoryStorage

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Get account ID
        account_id = get_account_id(aws_profile)

        # Load inventory
        storage = InventoryStorage(config.storage_path)
        try:
            inventory = storage.get_by_name(name, account_id)
        except InventoryNotFoundError:
            console.print(f"✗ Error: Inventory '{name}' not found for account {account_id}", style="bold red")
            console.print("\nList available inventories with: aws-baseline inventory list")
            raise typer.Exit(code=1)

        # Display inventory details
        console.print()
        console.print(f"[bold]Inventory: {inventory.name}[/bold]")
        console.print(f"Account: {inventory.account_id}")
        console.print(f"Description: {inventory.description or '(none)'}")
        console.print(f"Created: {inventory.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print(f"Last Updated: {inventory.last_updated.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        console.print()

        # Display filters
        if inventory.include_tags or inventory.exclude_tags:
            console.print("[bold]Filters:[/bold]")
            if inventory.include_tags:
                console.print("  Include Tags (must have ALL):")
                for key, value in inventory.include_tags.items():
                    console.print(f"    • {key} = {value}")
            if inventory.exclude_tags:
                console.print("  Exclude Tags (must NOT have ANY):")
                for key, value in inventory.exclude_tags.items():
                    console.print(f"    • {key} = {value}")
            console.print()

        # Display snapshots
        console.print(f"[bold]Snapshots: {len(inventory.snapshots)}[/bold]")
        if inventory.snapshots:
            for snapshot_file in inventory.snapshots:
                active_marker = " [green](active)[/green]" if snapshot_file == inventory.active_snapshot else ""
                console.print(f"  • {snapshot_file}{active_marker}")
        else:
            console.print("  (No snapshots taken yet)")
        console.print()

        # Display active snapshot
        if inventory.active_snapshot:
            console.print(f"[bold]Active Baseline:[/bold] {inventory.active_snapshot}")
        else:
            console.print("[bold]Active Baseline:[/bold] None")
        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error showing inventory: {e}", style="bold red")
        raise typer.Exit(code=2)


@inventory_app.command("migrate")
def inventory_migrate(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name to use"),
):
    """Migrate legacy snapshots to inventory structure.

    Scans for snapshots without inventory assignment and adds them to the 'default' inventory.
    """
    try:
        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials
        identity = validate_credentials(aws_profile)

        console.print("🔄 Scanning for legacy snapshots...\n")

        # T035: Scan .snapshots/ directory for snapshot files
        storage = SnapshotStorage(config.storage_path)
        from pathlib import Path
        from typing import List

        snapshots_dir = storage.storage_dir
        snapshot_files: List[Path] = []

        # Find all .yaml and .yaml.gz files
        for pattern in ["*.yaml", "*.yaml.gz"]:
            snapshot_files.extend(snapshots_dir.glob(pattern))

        if not snapshot_files:
            # T037: No snapshots found
            console.print("✓ No legacy snapshots found. Nothing to migrate.", style="green")
            raise typer.Exit(code=0)

        # Load inventory storage
        from ..snapshot.inventory_storage import InventoryStorage

        inventory_storage = InventoryStorage(config.storage_path)

        # Get or create default inventory
        default_inventory = inventory_storage.get_or_create_default(identity["account_id"])

        # T035: Check each snapshot for inventory assignment
        legacy_count = 0
        added_count = 0

        for snapshot_file in snapshot_files:
            snapshot_filename = snapshot_file.name
            snapshot_name = snapshot_filename.replace(".yaml.gz", "").replace(".yaml", "")

            # Skip if already in default inventory
            if snapshot_filename in default_inventory.snapshots:
                continue

            try:
                # Load snapshot to check if it has inventory_name
                snapshot = storage.load_snapshot(snapshot_name)

                # Check if snapshot belongs to this account
                if snapshot.account_id != identity["account_id"]:
                    continue

                # If inventory_name is 'default', it's a legacy snapshot
                if snapshot.inventory_name == "default":
                    legacy_count += 1

                    # Add to default inventory
                    default_inventory.add_snapshot(snapshot_filename, set_active=False)
                    added_count += 1

            except Exception as e:
                # T037: Handle corrupted snapshot files
                console.print(f"⚠️  Skipping {snapshot_filename}: {e}", style="yellow")
                continue

        # T035: Save updated default inventory
        if added_count > 0:
            inventory_storage.save(default_inventory)

        # T036: Display progress feedback
        console.print(f"✓ Found {legacy_count} snapshot(s) without inventory assignment", style="green")
        if added_count > 0:
            console.print(f"✓ Added {added_count} snapshot(s) to 'default' inventory", style="green")
            console.print("\n✓ Migration complete!", style="bold green")
        else:
            console.print("\n✓ All snapshots already assigned to inventories", style="green")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error during migration: {e}", style="bold red")
        logger.exception("Error in inventory migrate command")
        raise typer.Exit(code=2)


@inventory_app.command("delete")
def inventory_delete(
    name: str = typer.Argument(..., help="Inventory name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name to use"),
):
    """Delete an inventory, optionally deleting its snapshot files.

    WARNING: This will remove the inventory metadata. Snapshot files can be preserved or deleted.
    """
    try:
        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials
        identity = validate_credentials(aws_profile)

        # Load inventory storage
        from ..snapshot.inventory_storage import InventoryNotFoundError, InventoryStorage

        storage = InventoryStorage(config.storage_path)

        # T027, T032: Load inventory or error if doesn't exist
        try:
            inventory = storage.get_by_name(name, identity["account_id"])
        except InventoryNotFoundError:
            console.print(f"✗ Inventory '{name}' not found for account {identity['account_id']}", style="bold red")
            console.print("  Use 'aws-baseline inventory list' to see available inventories", style="yellow")
            raise typer.Exit(code=1)

        # T032: Check if this would leave account with zero inventories
        all_inventories = storage.load_by_account(identity["account_id"])
        if len(all_inventories) == 1:
            console.print(f"✗ Cannot delete '{name}' - it is the only inventory for this account", style="bold red")
            console.print("  At least one inventory must exist per account", style="yellow")
            raise typer.Exit(code=1)

        # T028: Display inventory details for confirmation
        console.print(f"\n📦 Inventory: [bold]{inventory.name}[/bold]")
        if inventory.description:
            console.print(f"   {inventory.description}")
        console.print(f"   Snapshots: {len(inventory.snapshots)}")

        # T029: Warn if this is the active snapshot
        if inventory.active_snapshot:
            console.print("\n⚠️  Warning: This inventory has an active snapshot snapshot!", style="bold yellow")
            console.print("   Deleting it will prevent cost/delta analysis for this inventory.", style="yellow")

        # T028: Confirmation prompt
        if not force:
            console.print()
            confirm = typer.confirm(f"Delete inventory '{name}'?", default=False)
            if not confirm:
                console.print("Cancelled.")
                raise typer.Exit(code=0)

        # T030: Ask about snapshot file deletion
        delete_snapshots = False
        if inventory.snapshots and not force:
            console.print()
            delete_snapshots = typer.confirm(f"Delete {len(inventory.snapshots)} snapshot file(s) too?", default=False)
        elif inventory.snapshots and force:
            # With --force, don't delete snapshots by default (safer)
            delete_snapshots = False

        # T031, T032: Delete inventory (already implemented in InventoryStorage)
        try:
            deleted_count = storage.delete(name, identity["account_id"], delete_snapshots=delete_snapshots)
        except Exception as e:
            console.print(f"✗ Error deleting inventory: {e}", style="bold red")
            raise typer.Exit(code=2)

        # T042: Audit logging for delete operation
        logger.info(
            f"Deleted inventory '{name}' for account {identity['account_id']}, "
            f"deleted {deleted_count} snapshot files, snapshots_deleted={delete_snapshots}"
        )

        # T033: Display completion messages
        console.print(f"\n✓ Inventory '[bold]{name}[/bold]' deleted", style="green")
        if delete_snapshots and deleted_count > 0:
            console.print(f"✓ {deleted_count} snapshot file(s) deleted", style="green")
        elif inventory.snapshots and not delete_snapshots:
            console.print(f"  {len(inventory.snapshots)} snapshot file(s) preserved", style="cyan")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error deleting inventory: {e}", style="bold red")
        logger.exception("Error in inventory delete command")
        raise typer.Exit(code=2)


# Snapshot commands group
snapshot_app = typer.Typer(help="Snapshot management commands")
app.add_typer(snapshot_app, name="snapshot")


@snapshot_app.command("create")
def snapshot_create(
    name: Optional[str] = typer.Argument(None, help="Snapshot name (auto-generated if not provided)"),
    regions: Optional[str] = typer.Option(
        None, "--regions", help="Comma-separated list of regions (default: us-east-1)"
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name to use"),
    inventory: Optional[str] = typer.Option(
        None, "--inventory", help="Inventory name to use for filters (conflicts with --include-tags/--exclude-tags)"
    ),
    set_active: bool = typer.Option(True, "--set-active/--no-set-active", help="Set as active snapshot"),
    compress: bool = typer.Option(False, "--compress", help="Compress snapshot with gzip"),
    before_date: Optional[str] = typer.Option(
        None, "--before-date", help="Include only resources created before date (YYYY-MM-DD)"
    ),
    after_date: Optional[str] = typer.Option(
        None, "--after-date", help="Include only resources created on/after date (YYYY-MM-DD)"
    ),
    filter_tags: Optional[str] = typer.Option(None, "--filter-tags", help="DEPRECATED: use --include-tags instead"),
    include_tags: Optional[str] = typer.Option(
        None, "--include-tags", help="Include only resources with ALL these tags (Key=Value,Key2=Value2)"
    ),
    exclude_tags: Optional[str] = typer.Option(
        None, "--exclude-tags", help="Exclude resources with ANY of these tags (Key=Value,Key2=Value2)"
    ),
):
    """Create a new snapshot of AWS resources.

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

        # T012: Validate filter conflict - inventory vs inline tags
        if inventory and (include_tags or exclude_tags):
            console.print(
                "✗ Error: Cannot use --inventory with --include-tags or --exclude-tags\n"
                "  Filters are defined in the inventory. Either:\n"
                "  1. Use --inventory to apply inventory's filters, OR\n"
                "  2. Use --include-tags/--exclude-tags for ad-hoc filtering",
                style="bold red",
            )
            raise typer.Exit(code=1)

        # T013: Load inventory and apply its filters
        from ..snapshot.inventory_storage import InventoryStorage

        inventory_storage = InventoryStorage(config.storage_path)
        active_inventory = None
        inventory_name = "default"

        if inventory:
            # Load specified inventory
            try:
                active_inventory = inventory_storage.get_by_name(inventory, identity["account_id"])
                inventory_name = inventory
                console.print(f"📦 Using inventory: [bold]{inventory}[/bold]", style="cyan")
                if active_inventory.description:
                    console.print(f"   {active_inventory.description}")
            except Exception:
                # T018: Handle nonexistent inventory
                console.print(
                    f"✗ Inventory '{inventory}' not found for account {identity['account_id']}", style="bold red"
                )
                console.print("  Use 'aws-baseline inventory list' to see available inventories", style="yellow")
                raise typer.Exit(code=1)
        else:
            # Get or create default inventory (lazy creation)
            active_inventory = inventory_storage.get_or_create_default(identity["account_id"])
            inventory_name = "default"

        # Generate snapshot name if not provided (T014: use inventory in naming)
        if not name:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            name = f"{identity['account_id']}-{inventory_name}-{timestamp}"

        # Parse regions - default to us-east-1
        region_list = []
        if regions:
            region_list = [r.strip() for r in regions.split(",")]
        elif config.regions:
            region_list = config.regions
        else:
            # Default to us-east-1
            region_list = ["us-east-1"]

        console.print(f"📸 Creating snapshot: [bold]{name}[/bold]")
        console.print(f"Regions: {', '.join(region_list)}\n")

        # Parse filters - use inventory filters if inventory specified, else inline filters
        resource_filter = None

        # T013: Determine which filters to use
        if inventory:
            # Use inventory's filters
            include_tags_dict = active_inventory.include_tags if active_inventory.include_tags else None
            exclude_tags_dict = active_inventory.exclude_tags if active_inventory.exclude_tags else None
        else:
            # Use inline filters from command-line
            include_tags_dict = {}
            exclude_tags_dict = {}

            # Parse include tags (supports both --filter-tags and --include-tags)
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
            if exclude_tags:
                try:
                    exclude_tags_dict = parse_tags(exclude_tags)
                except Exception as e:
                    console.print(f"✗ Error parsing exclude-tags: {e}", style="bold red")
                    raise typer.Exit(code=1)

            # Convert to None if empty
            include_tags_dict = include_tags_dict if include_tags_dict else None
            exclude_tags_dict = exclude_tags_dict if exclude_tags_dict else None

        # Create filter if any filters or dates are specified
        if before_date or after_date or include_tags_dict or exclude_tags_dict:
            from datetime import datetime as dt

            from ..snapshot.filter import ResourceFilter

            # Parse dates
            before_dt = None
            after_dt = None

            if before_date:
                try:
                    # Parse as UTC timezone-aware
                    from datetime import timezone

                    before_dt = dt.strptime(before_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    console.print("✗ Invalid --before-date format. Use YYYY-MM-DD (UTC)", style="bold red")
                    raise typer.Exit(code=1)

            if after_date:
                try:
                    # Parse as UTC timezone-aware
                    from datetime import timezone

                    after_dt = dt.strptime(after_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    console.print("✗ Invalid --after-date format. Use YYYY-MM-DD (UTC)", style="bold red")
                    raise typer.Exit(code=1)

            # Create filter
            resource_filter = ResourceFilter(
                before_date=before_dt,
                after_date=after_dt,
                include_tags=include_tags_dict,
                exclude_tags=exclude_tags_dict,
            )

            console.print(f"{resource_filter.get_filter_summary()}\n")

        # Import snapshot creation
        from ..snapshot.capturer import create_snapshot

        # T015: Pass inventory_name to create_snapshot
        snapshot = create_snapshot(
            name=name,
            regions=region_list,
            account_id=identity["account_id"],
            profile_name=aws_profile,
            set_active=set_active,
            resource_filter=resource_filter,
            inventory_name=inventory_name,
        )

        # T018: Check for zero resources after filtering
        if snapshot.resource_count == 0:
            console.print("⚠️  Warning: Snapshot contains 0 resources after filtering", style="bold yellow")
            if resource_filter:
                console.print(
                    "  Your filters may be too restrictive. Consider:\n"
                    "  - Adjusting tag filters\n"
                    "  - Checking date ranges\n"
                    "  - Verifying resources exist in the specified regions",
                    style="yellow",
                )
            console.print("\nSnapshot was not saved.\n")
            raise typer.Exit(code=0)

        # Save snapshot
        storage = SnapshotStorage(config.storage_path)
        filepath = storage.save_snapshot(snapshot, compress=compress)

        # T016: Register snapshot with inventory
        snapshot_filename = filepath.name
        active_inventory.add_snapshot(snapshot_filename, set_active=set_active)
        inventory_storage.save(active_inventory)

        # T017: User feedback about inventory
        console.print(f"\n✓ Added to inventory '[bold]{inventory_name}[/bold]'", style="green")
        if set_active:
            console.print("  Marked as active snapshot for this inventory", style="green")

        # Display summary
        console.print("\n✓ Snapshot complete!", style="bold green")
        console.print("\nSummary:")
        console.print(f"  Name: {snapshot.name}")
        console.print(f"  Resources: {snapshot.resource_count}")
        console.print(f"  File: {filepath}")
        console.print(f"  Active: {'Yes' if snapshot.is_active else 'No'}")

        # Show collection errors if any
        collection_errors = snapshot.metadata.get("collection_errors", [])
        if collection_errors:
            console.print(f"\n⚠️  Note: {len(collection_errors)} service(s) were unavailable", style="yellow")

        # Show filtering stats if filters were applied
        if snapshot.filters_applied:
            stats = snapshot.filters_applied.get("statistics", {})
            console.print("\nFiltering:")
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

    except typer.Exit:
        # Re-raise Exit exceptions (normal exit codes)
        raise
    except CredentialValidationError as e:
        console.print(f"✗ Error: {e}", style="bold red")
        raise typer.Exit(code=3)
    except Exception as e:
        console.print(f"✗ Error creating snapshot: {e}", style="bold red")
        logger.exception("Error in snapshot create command")
        raise typer.Exit(code=2)


@snapshot_app.command("list")
def snapshot_list(profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name")):
    """List all available snapshots."""
    try:
        storage = SnapshotStorage(config.storage_path)
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
            active_marker = "✓" if snap["is_active"] else ""
            table.add_row(
                snap["name"],
                snap["modified"].strftime("%Y-%m-%d %H:%M"),
                f"{snap['size_mb']:.2f}",
                active_marker,
            )

        console.print(table)
        console.print(f"\nTotal snapshots: {len(snapshots)}")

    except Exception as e:
        console.print(f"✗ Error listing snapshots: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("show")
def snapshot_show(
    name: str = typer.Argument(..., help="Snapshot name to display"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Display detailed information about a snapshot."""
    try:
        storage = SnapshotStorage(config.storage_path)
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
            date_filters = snapshot.filters_applied.get("date_filters", {})
            if date_filters.get("before_date"):
                console.print(f"  Before: {date_filters['before_date']}")
            if date_filters.get("after_date"):
                console.print(f"  After: {date_filters['after_date']}")
            tag_filters = snapshot.filters_applied.get("tag_filters", {})
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
def snapshot_set_active(
    name: str = typer.Argument(..., help="Snapshot name to set as active"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Set a snapshot as the active snapshot.

    The active snapshot is used by default for delta and cost analysis.
    """
    try:
        storage = SnapshotStorage(config.storage_path)
        storage.set_active_snapshot(name)

        console.print(f"✓ Set [bold]{name}[/bold] as active snapshot", style="green")

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
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Delete a snapshot.

    Cannot delete the active snapshot - set another snapshot as active first.
    """
    try:
        storage = SnapshotStorage(config.storage_path)

        # Load snapshot to show info
        snapshot = storage.load_snapshot(name)

        # Confirm deletion
        if not yes:
            console.print("\n[yellow]⚠️  About to delete snapshot:[/yellow]")
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
        console.print("  aws-snapshot set-active <other-snapshot-name>")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error deleting snapshot: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("report")
def snapshot_report(
    snapshot_name: Optional[str] = typer.Argument(None, help="Snapshot name (default: active snapshot)"),
    inventory: Optional[str] = typer.Option(None, "--inventory", help="Inventory name (required if multiple exist)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    storage_path: Optional[str] = typer.Option(None, "--storage-path", help="Override storage location"),
    resource_type: Optional[List[str]] = typer.Option(
        None, "--resource-type", help="Filter by resource type (can specify multiple)"
    ),
    region: Optional[List[str]] = typer.Option(None, "--region", help="Filter by region (can specify multiple)"),
    detailed: bool = typer.Option(
        False, "--detailed", help="Show detailed resource information (ARN, tags, creation date)"
    ),
    page_size: int = typer.Option(100, "--page-size", help="Resources per page in detailed view (default: 100)"),
    export: Optional[str] = typer.Option(
        None, "--export", help="Export report to file (format detected from extension: .json, .csv, .txt)"
    ),
):
    """Display resource summary report for a snapshot.

    Shows aggregated resource counts by service, region, and type with
    visual progress bars and formatted output. Can export to JSON, CSV, or TXT formats.

    Snapshot Selection (in order of precedence):
      1. Explicit snapshot name argument
      2. Most recent snapshot from specified --inventory
      3. Active snapshot (set via 'awsinv snapshot set-active')

    Examples:
        awsinv snapshot report                          # Report on active snapshot
        awsinv snapshot report baseline-2025-01         # Report on specific snapshot
        awsinv snapshot report --inventory prod         # Most recent snapshot from 'prod' inventory
        awsinv snapshot report --resource-type ec2      # Filter by resource type
        awsinv snapshot report --region us-east-1       # Filter by region
        awsinv snapshot report --resource-type ec2 --resource-type lambda  # Multiple filters
        awsinv snapshot report --export report.json     # Export full report to JSON
        awsinv snapshot report --export resources.csv   # Export resources to CSV
        awsinv snapshot report --export summary.txt     # Export summary to TXT
        awsinv snapshot report --detailed --export details.json  # Export detailed view
    """
    from ..models.report import FilterCriteria
    from ..snapshot.report_formatter import ReportFormatter
    from ..snapshot.reporter import SnapshotReporter
    from ..utils.export import detect_format, export_report_csv, export_report_json, export_report_txt

    try:
        # Use provided storage path or default from config
        storage = SnapshotStorage(storage_path or config.storage_path)

        # Determine which snapshot to load
        target_snapshot_name: str
        if snapshot_name:
            # Explicit snapshot name provided
            target_snapshot_name = snapshot_name
        elif inventory:
            # Inventory specified - find most recent snapshot from that inventory
            from datetime import datetime as dt
            from typing import TypedDict

            class InventorySnapshot(TypedDict):
                name: str
                created_at: dt

            all_snapshots = storage.list_snapshots()
            inventory_snapshots: List[InventorySnapshot] = []

            for snap_meta in all_snapshots:
                try:
                    snap = storage.load_snapshot(snap_meta["name"])
                    if snap.inventory_name == inventory:
                        inventory_snapshots.append(
                            InventorySnapshot(
                                name=snap.name,
                                created_at=snap.created_at,
                            )
                        )
                except Exception:
                    continue

            if not inventory_snapshots:
                console.print(f"✗ No snapshots found for inventory '{inventory}'", style="bold red")
                console.print("\nCreate a snapshot first:")
                console.print(f"  awsinv snapshot create --inventory {inventory}")
                raise typer.Exit(code=1)

            # Sort by created_at and pick most recent
            inventory_snapshots.sort(key=lambda x: x["created_at"], reverse=True)
            target_snapshot_name = inventory_snapshots[0]["name"]
            console.print(
                f"ℹ Using most recent snapshot from inventory '{inventory}': {target_snapshot_name}", style="dim"
            )
        else:
            # Try to get active snapshot
            active_name = storage.get_active_snapshot_name()
            if not active_name:
                console.print("✗ No active snapshot found", style="bold red")
                console.print("\nSet an active snapshot with:")
                console.print("  awsinv snapshot set-active <name>")
                console.print("\nOr specify a snapshot explicitly:")
                console.print("  awsinv snapshot report <snapshot-name>")
                console.print("\nOr specify an inventory to use the most recent snapshot:")
                console.print("  awsinv snapshot report --inventory <inventory-name>")
                raise typer.Exit(code=1)
            target_snapshot_name = active_name

        # Load the snapshot
        try:
            snapshot = storage.load_snapshot(target_snapshot_name)
        except FileNotFoundError:
            console.print(f"✗ Snapshot '{target_snapshot_name}' not found", style="bold red")

            # Show available snapshots
            try:
                all_snapshots = storage.list_snapshots()
                if all_snapshots:
                    console.print("\nAvailable snapshots:")
                    for snap_name in all_snapshots[:5]:
                        console.print(f"  • {snap_name}")
                    if len(all_snapshots) > 5:
                        console.print(f"  ... and {len(all_snapshots) - 5} more")
                    console.print("\nRun 'awsinv snapshot list' to see all snapshots.")
            except Exception:
                pass

            raise typer.Exit(code=1)

        # Handle empty snapshot
        if snapshot.resource_count == 0:
            console.print(f"⚠️  Warning: Snapshot '{snapshot.name}' contains 0 resources", style="yellow")
            console.print("\nNo report to generate.")
            raise typer.Exit(code=0)

        # Create filter criteria if filters provided
        has_filters = bool(resource_type or region)
        criteria = None
        if has_filters:
            criteria = FilterCriteria(
                resource_types=resource_type if resource_type else None,
                regions=region if region else None,
            )

        # Generate report
        reporter = SnapshotReporter(snapshot)
        metadata = reporter._extract_metadata()

        # Detailed view vs Summary view
        if detailed:
            # Get detailed resources (with optional filtering)
            detailed_resources = list(reporter.get_detailed_resources(criteria))

            # Export mode
            if export:
                try:
                    # Detect format from file extension
                    export_format = detect_format(export)

                    # Export based on format
                    if export_format == "json":
                        # For JSON, export full report structure with detailed resources
                        summary = (
                            reporter.generate_filtered_summary(criteria) if criteria else reporter.generate_summary()
                        )
                        export_path = export_report_json(export, metadata, summary, detailed_resources)
                        console.print(
                            f"✓ Exported {len(detailed_resources):,} resources to JSON: {export_path}",
                            style="bold green",
                        )
                    elif export_format == "csv":
                        # For CSV, export detailed resources
                        export_path = export_report_csv(export, detailed_resources)
                        console.print(
                            f"✓ Exported {len(detailed_resources):,} resources to CSV: {export_path}",
                            style="bold green",
                        )
                    elif export_format == "txt":
                        # For TXT, export summary (detailed view doesn't make sense for plain text)
                        summary = (
                            reporter.generate_filtered_summary(criteria) if criteria else reporter.generate_summary()
                        )
                        export_path = export_report_txt(export, metadata, summary)
                        console.print(f"✓ Exported summary to TXT: {export_path}", style="bold green")
                except FileExistsError as e:
                    console.print(f"✗ {e}", style="bold red")
                    console.print("\nUse a different filename or delete the existing file.", style="yellow")
                    raise typer.Exit(code=1)
                except FileNotFoundError as e:
                    console.print(f"✗ {e}", style="bold red")
                    raise typer.Exit(code=1)
                except ValueError as e:
                    console.print(f"✗ {e}", style="bold red")
                    raise typer.Exit(code=1)
            else:
                # Display mode - show filter information if applied
                if criteria:
                    console.print("\n[bold cyan]Filters Applied:[/bold cyan]")
                    if resource_type:
                        console.print(f"  • Resource Types: {', '.join(resource_type)}")
                    if region:
                        console.print(f"  • Regions: {', '.join(region)}")
                    console.print(
                        f"  • Matching Resources: {len(detailed_resources):,} (of {snapshot.resource_count:,} total)\n"
                    )

                # Format and display detailed view
                formatter = ReportFormatter(console)
                formatter.format_detailed(metadata, detailed_resources, page_size=page_size)
        else:
            # Generate summary (filtered or full)
            if criteria:
                summary = reporter.generate_filtered_summary(criteria)
            else:
                summary = reporter.generate_summary()

            # Export mode
            if export:
                try:
                    # Detect format from file extension
                    export_format = detect_format(export)

                    # Export based on format
                    if export_format == "json":
                        # For JSON, export full report structure
                        # Get all resources for complete export
                        all_resources = list(reporter.get_detailed_resources(criteria))
                        export_path = export_report_json(export, metadata, summary, all_resources)
                        console.print(
                            f"✓ Exported {summary.total_count:,} resources to JSON: {export_path}", style="bold green"
                        )
                    elif export_format == "csv":
                        # For CSV, export resources
                        all_resources = list(reporter.get_detailed_resources(criteria))
                        export_path = export_report_csv(export, all_resources)
                        console.print(
                            f"✓ Exported {len(all_resources):,} resources to CSV: {export_path}", style="bold green"
                        )
                    elif export_format == "txt":
                        # For TXT, export summary only
                        export_path = export_report_txt(export, metadata, summary)
                        console.print(f"✓ Exported summary to TXT: {export_path}", style="bold green")
                except FileExistsError as e:
                    console.print(f"✗ {e}", style="bold red")
                    console.print("\nUse a different filename or delete the existing file.", style="yellow")
                    raise typer.Exit(code=1)
                except FileNotFoundError as e:
                    console.print(f"✗ {e}", style="bold red")
                    raise typer.Exit(code=1)
                except ValueError as e:
                    console.print(f"✗ {e}", style="bold red")
                    raise typer.Exit(code=1)
            else:
                # Display mode - show filter information
                if criteria:
                    console.print("\n[bold cyan]Filters Applied:[/bold cyan]")
                    if resource_type:
                        console.print(f"  • Resource Types: {', '.join(resource_type)}")
                    if region:
                        console.print(f"  • Regions: {', '.join(region)}")
                    console.print(
                        f"  • Matching Resources: {summary.total_count:,} (of {snapshot.resource_count:,} total)\n"
                    )

                # Format and display summary report
                formatter = ReportFormatter(console)
                formatter.format_summary(metadata, summary, has_filters=has_filters)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error generating report: {e}", style="bold red")
        logger.exception("Error in snapshot report command")
        raise typer.Exit(code=2)


@app.command()
def delta(
    snapshot: Optional[str] = typer.Option(
        None, "--snapshot", help="Baseline snapshot name (default: active from inventory)"
    ),
    inventory: Optional[str] = typer.Option(None, "--inventory", help="Inventory name (default: 'default')"),
    resource_type: Optional[str] = typer.Option(None, "--resource-type", help="Filter by resource type"),
    region: Optional[str] = typer.Option(None, "--region", help="Filter by region"),
    show_details: bool = typer.Option(False, "--show-details", help="Show detailed resource information"),
    show_diff: bool = typer.Option(False, "--show-diff", help="Show field-level configuration differences"),
    export: Optional[str] = typer.Option(None, "--export", help="Export to file (JSON or CSV based on extension)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """View resource changes since snapshot.

    Compares current AWS state to the snapshot and shows added, deleted,
    and modified resources. Use --show-diff to see field-level configuration changes.
    """
    try:
        # T021: Get inventory and use its active snapshot
        from ..aws.credentials import validate_credentials
        from ..snapshot.inventory_storage import InventoryStorage

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials to get account ID
        identity = validate_credentials(aws_profile)

        # Load inventory
        inventory_storage = InventoryStorage(config.storage_path)
        inventory_name = inventory if inventory else "default"

        if inventory:
            try:
                active_inventory = inventory_storage.get_by_name(inventory, identity["account_id"])
            except Exception:
                # T024: Inventory doesn't exist
                console.print(
                    f"✗ Inventory '{inventory}' not found for account {identity['account_id']}", style="bold red"
                )
                console.print("  Use 'aws-baseline inventory list' to see available inventories", style="yellow")
                raise typer.Exit(code=1)
        else:
            # Get or create default inventory
            active_inventory = inventory_storage.get_or_create_default(identity["account_id"])
            inventory_name = "default"

        # T026: User feedback about inventory
        console.print(f"📦 Using inventory: [bold]{inventory_name}[/bold]", style="cyan")

        # T024, T025: Validate inventory has snapshots and active snapshot
        if not active_inventory.snapshots:
            console.print(f"✗ No snapshots exist in inventory '{inventory_name}'", style="bold red")
            console.print(f"  Take a snapshot first: aws-snapshot create --inventory {inventory_name}", style="yellow")
            raise typer.Exit(code=1)

        # Load snapshot
        storage = SnapshotStorage(config.storage_path)

        if snapshot:
            # User specified a snapshot explicitly
            reference_snapshot = storage.load_snapshot(snapshot)
        else:
            # Use inventory's active snapshot
            if not active_inventory.active_snapshot:
                console.print(f"✗ No active snapshot in inventory '{inventory_name}'", style="bold red")
                console.print(
                    f"  Take a snapshot or set one as active: " f"aws-snapshot create --inventory {inventory_name}",
                    style="yellow",
                )
                raise typer.Exit(code=1)

            # Load the active snapshot (strip .yaml extension if present)
            snapshot_name = active_inventory.active_snapshot.replace(".yaml.gz", "").replace(".yaml", "")
            reference_snapshot = storage.load_snapshot(snapshot_name)

        console.print(f"🔍 Comparing to baseline: [bold]{reference_snapshot.name}[/bold]")
        console.print(f"   Created: {reference_snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

        # Prepare filters
        resource_type_filter = [resource_type] if resource_type else None
        region_filter = [region] if region else None

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Calculate delta
        from ..delta.calculator import compare_to_current_state

        delta_report = compare_to_current_state(
            reference_snapshot,
            profile_name=aws_profile,
            regions=None,  # Use reference snapshot regions
            resource_type_filter=resource_type_filter,
            region_filter=region_filter,
            include_drift_details=show_diff,
        )

        # Display delta
        from ..delta.reporter import DeltaReporter

        reporter = DeltaReporter(console)
        reporter.display(delta_report, show_details=show_details)

        # Export if requested
        if export:
            if export.endswith(".json"):
                reporter.export_json(delta_report, export)
            elif export.endswith(".csv"):
                reporter.export_csv(delta_report, export)
            else:
                console.print("✗ Unsupported export format. Use .json or .csv", style="bold red")
                raise typer.Exit(code=1)

        # Exit with code 0 if no changes (for scripting)
        if not delta_report.has_changes:
            raise typer.Exit(code=0)

    except typer.Exit:
        # Re-raise Exit exceptions (normal exit codes)
        raise
    except FileNotFoundError as e:
        console.print(f"✗ Snapshot not found: {e}", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error calculating delta: {e}", style="bold red")
        logger.exception("Error in delta command")
        raise typer.Exit(code=2)


@app.command()
def cost(
    snapshot: Optional[str] = typer.Option(
        None, "--snapshot", help="Baseline snapshot name (default: active from inventory)"
    ),
    inventory: Optional[str] = typer.Option(None, "--inventory", help="Inventory name (default: 'default')"),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", help="Start date (YYYY-MM-DD, default: snapshot date)"
    ),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (YYYY-MM-DD, default: today)"),
    granularity: str = typer.Option("MONTHLY", "--granularity", help="Cost granularity: DAILY or MONTHLY"),
    show_services: bool = typer.Option(True, "--show-services/--no-services", help="Show service breakdown"),
    export: Optional[str] = typer.Option(None, "--export", help="Export to file (JSON or CSV based on extension)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Analyze costs for resources in a specific inventory.

    Shows costs for resources captured in the inventory's active snapshot,
    enabling per-team, per-environment, or per-project cost tracking.
    """
    try:
        # T020: Get inventory and use its active snapshot
        from ..aws.credentials import validate_credentials
        from ..snapshot.inventory_storage import InventoryStorage

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Validate credentials to get account ID
        identity = validate_credentials(aws_profile)

        # Load inventory
        inventory_storage = InventoryStorage(config.storage_path)
        inventory_name = inventory if inventory else "default"

        if inventory:
            try:
                active_inventory = inventory_storage.get_by_name(inventory, identity["account_id"])
            except Exception:
                # T022: Inventory doesn't exist
                console.print(
                    f"✗ Inventory '{inventory}' not found for account {identity['account_id']}", style="bold red"
                )
                console.print("  Use 'aws-baseline inventory list' to see available inventories", style="yellow")
                raise typer.Exit(code=1)
        else:
            # Get or create default inventory
            active_inventory = inventory_storage.get_or_create_default(identity["account_id"])
            inventory_name = "default"

        # T026: User feedback about inventory
        console.print(f"📦 Using inventory: [bold]{inventory_name}[/bold]", style="cyan")

        # T022, T023: Validate inventory has snapshots and active snapshot
        if not active_inventory.snapshots:
            console.print(f"✗ No snapshots exist in inventory '{inventory_name}'", style="bold red")
            console.print(f"  Take a snapshot first: aws-snapshot create --inventory {inventory_name}", style="yellow")
            raise typer.Exit(code=1)

        # Load snapshot
        storage = SnapshotStorage(config.storage_path)

        if snapshot:
            # User specified a snapshot explicitly
            reference_snapshot = storage.load_snapshot(snapshot)
        else:
            # Use inventory's active snapshot
            if not active_inventory.active_snapshot:
                console.print(f"✗ No active snapshot in inventory '{inventory_name}'", style="bold red")
                console.print(
                    f"  Take a snapshot or set one as active: " f"aws-snapshot create --inventory {inventory_name}",
                    style="yellow",
                )
                raise typer.Exit(code=1)

            # Load the active snapshot (strip .yaml extension if present)
            snapshot_name = active_inventory.active_snapshot.replace(".yaml.gz", "").replace(".yaml", "")
            reference_snapshot = storage.load_snapshot(snapshot_name)

        console.print(f"💰 Analyzing costs for snapshot: [bold]{reference_snapshot.name}[/bold]\n")

        # Parse dates
        from datetime import datetime as dt

        start_dt = None
        end_dt = None

        if start_date:
            try:
                # Parse as UTC timezone-aware
                from datetime import timezone

                start_dt = dt.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                console.print("✗ Invalid start date format. Use YYYY-MM-DD (UTC)", style="bold red")
                raise typer.Exit(code=1)

        if end_date:
            try:
                # Parse as UTC timezone-aware
                from datetime import timezone

                end_dt = dt.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                console.print("✗ Invalid end date format. Use YYYY-MM-DD (UTC)", style="bold red")
                raise typer.Exit(code=1)

        # Validate granularity
        if granularity not in ["DAILY", "MONTHLY"]:
            console.print("✗ Invalid granularity. Use DAILY or MONTHLY", style="bold red")
            raise typer.Exit(code=1)

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # First, check if there are any deltas (new resources)
        console.print("🔍 Checking for resource changes since snapshot...\n")
        from ..delta.calculator import compare_to_current_state

        delta_report = compare_to_current_state(
            reference_snapshot,
            profile_name=aws_profile,
            regions=None,
        )

        # Analyze costs
        from ..cost.analyzer import CostAnalyzer
        from ..cost.explorer import CostExplorerClient, CostExplorerError

        try:
            cost_explorer = CostExplorerClient(profile_name=aws_profile)
            analyzer = CostAnalyzer(cost_explorer)

            # If no changes, only show baseline costs (no splitting)
            has_deltas = delta_report.has_changes

            cost_report = analyzer.analyze(
                reference_snapshot,
                start_date=start_dt,
                end_date=end_dt,
                granularity=granularity,
                has_deltas=has_deltas,
                delta_report=delta_report,
            )

            # Display cost report
            from ..cost.reporter import CostReporter

            reporter = CostReporter(console)
            reporter.display(cost_report, show_services=show_services, has_deltas=has_deltas)

            # Export if requested
            if export:
                if export.endswith(".json"):
                    reporter.export_json(cost_report, export)
                elif export.endswith(".csv"):
                    reporter.export_csv(cost_report, export)
                else:
                    console.print("✗ Unsupported export format. Use .json or .csv", style="bold red")
                    raise typer.Exit(code=1)

        except CostExplorerError as e:
            console.print(f"✗ Cost Explorer error: {e}", style="bold red")
            console.print("\nTroubleshooting:")
            console.print("  1. Ensure Cost Explorer is enabled in your AWS account")
            console.print("  2. Check IAM permissions: ce:GetCostAndUsage")
            console.print("  3. Cost data typically has a 24-48 hour lag")
            raise typer.Exit(code=3)

    except typer.Exit:
        # Re-raise Exit exceptions (normal exit codes)
        raise
    except FileNotFoundError as e:
        console.print(f"✗ Snapshot not found: {e}", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error analyzing costs: {e}", style="bold red")
        logger.exception("Error in cost command")
        raise typer.Exit(code=2)


# ============================================================================
# Security Commands
# ============================================================================

security_app = typer.Typer(help="Security scanning and compliance checking commands")


@security_app.command(name="scan")
def security_scan(
    snapshot: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Snapshot name to scan"),
    inventory: Optional[str] = typer.Option(None, "--inventory", "-i", help="Inventory name (uses active snapshot)"),
    storage_dir: Optional[str] = typer.Option(None, "--storage-dir", help="Snapshot storage directory"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity: critical, high, medium, low"),
    export: Optional[str] = typer.Option(None, "--export", help="Export findings to file"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json or csv"),
    cis_only: bool = typer.Option(False, "--cis-only", help="Show only findings with CIS Benchmark mappings"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Scan a snapshot for security misconfigurations and compliance issues.

    Performs comprehensive security checks including:
    - Public S3 buckets
    - Open security groups (SSH, RDP, databases)
    - Publicly accessible RDS instances
    - EC2 instances with IMDSv1 enabled
    - IAM credentials older than 90 days
    - Secrets Manager secrets not rotated in 90+ days

    Examples:
        # Scan a specific snapshot
        awsinv security scan --snapshot my-snapshot

        # Scan with severity filter
        awsinv security scan --snapshot my-snapshot --severity critical

        # Export findings to JSON
        awsinv security scan --snapshot my-snapshot --export findings.json

        # Export to CSV
        awsinv security scan --snapshot my-snapshot --export findings.csv --format csv

        # Show only CIS-mapped findings
        awsinv security scan --snapshot my-snapshot --cis-only
    """
    from ..security.cis_mapper import CISMapper
    from ..security.reporter import SecurityReporter
    from ..security.scanner import SecurityScanner
    from ..snapshot.inventory_storage import InventoryStorage

    try:
        # Determine which snapshot to scan
        if not snapshot and not inventory:
            console.print("✗ Error: Must specify either --snapshot or --inventory", style="bold red")
            raise typer.Exit(code=1)

        # Use profile parameter if provided, otherwise use config
        aws_profile = profile if profile else config.aws_profile

        # Load snapshot
        storage = SnapshotStorage(storage_dir or config.storage_path)

        if inventory:
            # Load active snapshot from inventory
            # Need AWS credentials to get account ID
            identity = validate_credentials(aws_profile)
            inv_storage = InventoryStorage(storage_dir or config.storage_path)
            inv = inv_storage.get_by_name(inventory, identity["account_id"])
            if not inv.active_snapshot:
                console.print(
                    f"✗ Error: Inventory '{inventory}' has no active snapshot. "
                    f"Use 'awsinv snapshot set-active' to set one.",
                    style="bold red",
                )
                raise typer.Exit(code=1)
            # Strip .yaml or .yaml.gz extension if present
            snapshot_name = inv.active_snapshot.replace(".yaml.gz", "").replace(".yaml", "")
            snapshot_obj = storage.load_snapshot(snapshot_name)
        else:
            snapshot_obj = storage.load_snapshot(snapshot)  # type: ignore

        console.print(f"\n🔍 Scanning snapshot: [bold cyan]{snapshot_obj.name}[/bold cyan]\n")

        # Parse severity filter
        severity_filter = None
        if severity:
            from ..models.security_finding import Severity

            severity_map = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "medium": Severity.MEDIUM,
                "low": Severity.LOW,
            }
            severity_filter = severity_map.get(severity.lower())
            if not severity_filter:
                console.print(f"✗ Invalid severity: {severity}. Must be: critical, high, medium, low", style="bold red")
                raise typer.Exit(code=1)

        # Run security scan
        scanner = SecurityScanner()
        result = scanner.scan(snapshot_obj, severity_filter=severity_filter)

        # Filter CIS-only if requested
        findings_to_report = result.findings
        if cis_only:
            findings_to_report = [f for f in result.findings if f.cis_control is not None]

        # Display results
        reporter = SecurityReporter()

        if len(findings_to_report) == 0:
            console.print("✓ [bold green]No security issues found![/bold green]\n")
            if severity_filter:
                console.print(f"  (Filtered by severity: {severity})")
            if cis_only:
                console.print("  (Showing only CIS-mapped findings)")
        else:
            # Generate summary
            summary = reporter.generate_summary(findings_to_report)

            console.print(f"[bold red]✗ Found {summary['total_findings']} security issue(s)[/bold red]\n")
            console.print(
                f"  Critical: {summary['critical_count']}  "
                f"High: {summary['high_count']}  "
                f"Medium: {summary['medium_count']}  "
                f"Low: {summary['low_count']}\n"
            )

            # Display findings
            output = reporter.format_terminal(findings_to_report)
            console.print(output)

            # Show CIS summary
            cis_mapper = CISMapper()
            cis_summary = cis_mapper.get_summary(findings_to_report)

            if cis_summary["total_controls_checked"] > 0:
                console.print("\n[bold]CIS Benchmark Summary:[/bold]")
                console.print(
                    f"  Controls checked: {cis_summary['total_controls_checked']}  "
                    f"Failed: {cis_summary['controls_failed']}  "
                    f"Passed: {cis_summary['controls_passed']}"
                )

        # Export if requested
        if export:
            if format.lower() == "json":
                reporter.export_json(findings_to_report, export)
                console.print(f"\n✓ Exported findings to: [cyan]{export}[/cyan] (JSON)")
            elif format.lower() == "csv":
                reporter.export_csv(findings_to_report, export)
                console.print(f"\n✓ Exported findings to: [cyan]{export}[/cyan] (CSV)")
            else:
                console.print(f"✗ Invalid format: {format}. Must be 'json' or 'csv'", style="bold red")
                raise typer.Exit(code=1)

    except typer.Exit:
        # Re-raise Typer exit codes (for early returns like missing params)
        raise
    except FileNotFoundError as e:
        console.print(f"✗ Snapshot not found: {e}", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error during security scan: {e}", style="bold red")
        logger.exception("Error in security scan command")
        raise typer.Exit(code=2)


app.add_typer(security_app, name="security")


# Restore commands
restore_app = typer.Typer(help="Resource cleanup and restoration commands")


@restore_app.command("preview")
def restore_preview(
    baseline_snapshot: str = typer.Argument(..., help="Snapshot name to restore to (can be any snapshot)"),
    account_id: str = typer.Option(None, "--account-id", help="AWS account ID (auto-detected if not provided)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    resource_types: Optional[List[str]] = typer.Option(
        None, "--type", help="Filter by resource types (e.g., AWS::EC2::Instance)"
    ),
    regions: Optional[List[str]] = typer.Option(None, "--region", help="Filter by AWS regions"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json, yaml"),
):
    """Preview resources that would be deleted to restore to a snapshot.

    Shows what resources have been created since the snapshot without
    performing any deletions. This is a safe dry-run operation.

    Examples:
        # Preview resources since a baseline snapshot
        awsinv restore preview prod-baseline

        # Preview with ephemeral test snapshot
        awsinv restore preview clean-state

        # Preview only EC2 instances in us-east-1
        awsinv restore preview my-snapshot --type AWS::EC2::Instance --region us-east-1

        # Preview with specific AWS profile
        awsinv restore preview my-snapshot --profile production
    """
    from ..aws.credentials import get_account_id
    from ..restore.audit import AuditStorage
    from ..restore.cleaner import ResourceCleaner
    from ..restore.safety import SafetyChecker

    try:
        console.print("\n[bold cyan]🔍 Previewing Resource Cleanup[/bold cyan]\n")

        # Auto-detect account ID if not provided
        if not account_id:
            try:
                account_id = get_account_id(profile_name=profile)
                console.print(f"[dim]Detected account ID: {account_id}[/dim]")
            except Exception as e:
                console.print(f"[red]Error detecting account ID: {e}[/red]")
                console.print("[yellow]Please provide --account-id explicitly[/yellow]")
                raise typer.Exit(code=1)

        # Initialize components
        snapshot_storage = SnapshotStorage()
        safety_checker = SafetyChecker(rules=[])  # Load rules from config
        audit_storage = AuditStorage()

        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        # Run preview
        with console.status("[bold green]Analyzing resources..."):
            operation = cleaner.preview(
                baseline_snapshot=baseline_snapshot,
                account_id=account_id,
                aws_profile=profile,
                resource_types=resource_types,
                regions=regions,
            )

        # Display results
        console.print("\n[bold green]✓ Preview Complete[/bold green]\n")

        # Summary panel
        summary_text = f"""
[bold]Operation ID:[/bold] {operation.operation_id}
[bold]Baseline Snapshot:[/bold] {operation.baseline_snapshot}
[bold]Account ID:[/bold] {operation.account_id}
[bold]Mode:[/bold] DRY-RUN (preview only)
[bold]Status:[/bold] {operation.status.value.upper()}

[bold cyan]Resources Identified:[/bold cyan]
• Total: {operation.total_resources}
• Would be deleted: {operation.total_resources - operation.skipped_count}
• Protected (skipped): {operation.skipped_count}
        """

        if operation.filters:
            filter_text = "\n[bold]Filters Applied:[/bold]"
            if operation.filters.get("resource_types"):
                filter_text += f"\n• Types: {', '.join(operation.filters['resource_types'])}"
            if operation.filters.get("regions"):
                filter_text += f"\n• Regions: {', '.join(operation.filters['regions'])}"
            summary_text += filter_text

        console.print(Panel(summary_text.strip(), title="[bold]Preview Summary[/bold]", border_style="cyan"))

        # Warning if resources would be deleted
        if operation.total_resources > operation.skipped_count:
            deletable_count = operation.total_resources - operation.skipped_count
            console.print(
                f"\n[yellow]⚠️  {deletable_count} resource(s) would be DELETED if you run 'restore execute'[/yellow]"
            )
            console.print("[dim]Use 'awsinv restore execute' with --confirm to actually delete resources[/dim]\n")
        else:
            console.print("\n[green]✓ No resources would be deleted - environment matches baseline[/green]\n")

    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]\n")
        logger.exception("Error in restore preview command")
        raise typer.Exit(code=2)


@restore_app.command("execute")
def restore_execute(
    baseline_snapshot: str = typer.Argument(..., help="Snapshot name to restore to (can be any snapshot)"),
    account_id: str = typer.Option(None, "--account-id", help="AWS account ID (auto-detected if not provided)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    resource_types: Optional[List[str]] = typer.Option(None, "--type", help="Filter by resource types"),
    regions: Optional[List[str]] = typer.Option(None, "--region", help="Filter by AWS regions"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm deletion (REQUIRED for execution)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation prompt"),
):
    """Execute resource deletion to restore environment to a snapshot.

    DESTRUCTIVE OPERATION: This will permanently delete AWS resources!

    Deletes resources that were created after the snapshot, restoring
    your AWS environment to that point in time. Protected resources are skipped.

    Examples:
        # Restore to a baseline snapshot
        awsinv restore execute prod-baseline --confirm

        # Clean up ephemeral test environment
        awsinv restore execute clean-state --confirm

        # Execute with filters and skip prompt
        awsinv restore execute my-snapshot --confirm --yes --type AWS::EC2::Instance

        # Execute in specific region with profile
        awsinv restore execute my-snapshot --confirm --region us-east-1 --profile prod
    """
    from ..aws.credentials import get_account_id
    from ..restore.audit import AuditStorage
    from ..restore.cleaner import ResourceCleaner
    from ..restore.safety import SafetyChecker

    try:
        # Require --confirm flag
        if not confirm:
            console.print("\n[red]ERROR: --confirm flag is required for deletion operations[/red]")
            console.print("[yellow]This is a safety measure to prevent accidental deletions[/yellow]")
            console.print("\n[dim]Run with: awsinv restore execute <snapshot> --confirm[/dim]\n")
            raise typer.Exit(code=1)

        console.print("\n[bold red]⚠️  DESTRUCTIVE OPERATION[/bold red]\n")

        # Auto-detect account ID if not provided
        if not account_id:
            try:
                account_id = get_account_id(profile_name=profile)
                console.print(f"[dim]Detected account ID: {account_id}[/dim]")
            except Exception as e:
                console.print(f"[red]Error detecting account ID: {e}[/red]")
                console.print("[yellow]Please provide --account-id explicitly[/yellow]")
                raise typer.Exit(code=1)

        # Initialize components
        snapshot_storage = SnapshotStorage()
        safety_checker = SafetyChecker(rules=[])
        audit_storage = AuditStorage()

        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        # First, run preview to show what will be deleted
        console.print("[bold]Preview - Analyzing resources...[/bold]")
        with console.status("[bold green]Analyzing..."):
            preview_op = cleaner.preview(
                baseline_snapshot=baseline_snapshot,
                account_id=account_id,
                aws_profile=profile,
                resource_types=resource_types,
                regions=regions,
            )

        deletable_count = preview_op.total_resources - preview_op.skipped_count

        if deletable_count == 0:
            console.print("\n[green]✓ No resources to delete - environment matches baseline[/green]\n")
            raise typer.Exit(code=0)

        # Show what will be deleted
        console.print("\n[bold yellow]The following will be PERMANENTLY DELETED:[/bold yellow]")
        console.print(f"• {deletable_count} resource(s) will be deleted")
        console.print(f"• {preview_op.skipped_count} resource(s) will be skipped (protected)")
        console.print(f"• Account: {account_id}")
        console.print(f"• Baseline: {baseline_snapshot}")

        if preview_op.filters:
            if preview_op.filters.get("resource_types"):
                console.print(f"• Types: {', '.join(preview_op.filters['resource_types'])}")
            if preview_op.filters.get("regions"):
                console.print(f"• Regions: {', '.join(preview_op.filters['regions'])}")

        # Interactive confirmation (unless --yes flag)
        if not yes:
            console.print()
            proceed = typer.confirm(
                "⚠️  Are you absolutely sure you want to DELETE these resources?",
                default=False,
            )
            if not proceed:
                console.print("\n[yellow]Aborted - no resources were deleted[/yellow]\n")
                raise typer.Exit(code=0)

        # Execute deletion
        console.print("\n[bold red]Executing deletion...[/bold red]")
        with console.status("[bold red]Deleting resources..."):
            operation = cleaner.execute(
                baseline_snapshot=baseline_snapshot,
                account_id=account_id,
                confirmed=True,
                aws_profile=profile,
                resource_types=resource_types,
                regions=regions,
            )

        # Display results
        console.print("\n[bold]Deletion Complete[/bold]\n")

        # Results summary
        status_color = (
            "green"
            if operation.status.value == "completed"
            else "yellow" if operation.status.value == "partial" else "red"
        )

        summary_text = f"""
[bold]Operation ID:[/bold] {operation.operation_id}
[bold]Status:[/bold] [{status_color}]{operation.status.value.upper()}[/{status_color}]

[bold]Results:[/bold]
• Succeeded: {operation.succeeded_count}
• Failed: {operation.failed_count}
• Skipped: {operation.skipped_count}
• Total: {operation.total_resources}
        """

        console.print(Panel(summary_text.strip(), title="[bold]Execution Summary[/bold]", border_style=status_color))

        # Show audit log location
        console.print("\n[dim]📝 Full audit log saved to: ~/.snapshots/audit-logs/[/dim]\n")

        # Exit with appropriate code
        if operation.failed_count > 0:
            raise typer.Exit(code=1)

    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]\n")
        logger.exception("Error in restore execute command")
        raise typer.Exit(code=2)


app.add_typer(restore_app, name="restore")


def cli_main():
    """Entry point for console script."""
    app()


if __name__ == "__main__":
    cli_main()
