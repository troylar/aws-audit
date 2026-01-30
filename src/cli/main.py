"""Main CLI entry point using Typer."""

import base64
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ..aws.credentials import CredentialValidationError, validate_credentials
from ..snapshot.storage import SnapshotStorage
from ..utils.logging import setup_logging
from .config import Config
from .deletion_progress import DeletionProgressDisplay

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
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
    storage_path: Optional[str] = typer.Option(
        None,
        "--storage-path",
        help="Custom path for snapshot storage (default: ~/.snapshots or $AWS_INVENTORY_STORAGE_PATH)",
        envvar=["AWSINV_STORAGE_PATH", "AWS_INVENTORY_STORAGE_PATH"],
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
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
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
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
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
    name: str = typer.Argument(..., help="Inventory name to display", envvar="AWSINV_INVENTORY_ID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
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
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
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
    name: str = typer.Argument(..., help="Inventory name to delete", envvar="AWSINV_INVENTORY_ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
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

# Config commands group
config_app = typer.Typer(help="AWS Config integration commands")
app.add_typer(config_app, name="config")


@config_app.command("check")
def config_check(
    regions: Optional[str] = typer.Option(
        None,
        "--regions",
        help="Comma-separated list of regions (default: us-east-1)",
        envvar=["AWSINV_REGION", "AWS_REGION"],
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="AWS profile name", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed resource type support"),
):
    """Check AWS Config availability and status.

    Shows whether AWS Config is enabled in each region and what resource types
    are being recorded. This helps understand which collection method will be used.

    Examples:
        awsinv config check
        awsinv config check --regions us-east-1,us-west-2
        awsinv config check --verbose
    """
    import boto3

    from ..config_service.detector import detect_config_availability
    from ..config_service.resource_type_mapping import COLLECTOR_TO_CONFIG_TYPES, CONFIG_SUPPORTED_TYPES

    region_list = (regions or "us-east-1").split(",")

    # Create session
    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)

    # Header
    console.print()
    console.print("[bold]AWS Config Status Check[/bold]")
    console.print()

    # Check each region
    for region in region_list:
        availability = detect_config_availability(session, region, profile)

        if availability.is_enabled:
            status = "[green]✓ ENABLED[/green]"
            recorder_info = f"Recorder: {availability.recorder_name}"
            if availability.recording_group_all_supported:
                types_info = f"Recording: [cyan]All supported types[/cyan] ({len(CONFIG_SUPPORTED_TYPES)} types)"
            else:
                types_info = f"Recording: [yellow]{len(availability.resource_types_recorded)} specific types[/yellow]"
        else:
            status = "[red]✗ NOT ENABLED[/red]"
            recorder_info = f"Reason: {availability.error_message or 'Unknown'}"
            types_info = ""

        console.print(f"[bold]{region}[/bold]: {status}")
        console.print(f"  {recorder_info}")
        if types_info:
            console.print(f"  {types_info}")

        if verbose and availability.is_enabled:
            # Show which services will use Config vs Direct API
            console.print()
            console.print("  [dim]Collection method by service:[/dim]")

            service_table = Table(show_header=True, header_style="dim", box=None, padding=(0, 2))
            service_table.add_column("Service", style="cyan")
            service_table.add_column("Method", style="white")
            service_table.add_column("Resource Types", style="dim")

            for service, config_types in sorted(COLLECTOR_TO_CONFIG_TYPES.items()):
                supported_types = [t for t in config_types if availability.supports_resource_type(t)]
                if supported_types:
                    method = "[green]Config[/green]"
                    types_str = ", ".join(t.split("::")[-1] for t in supported_types[:3])
                    if len(supported_types) > 3:
                        types_str += f" (+{len(supported_types) - 3} more)"
                else:
                    method = "[yellow]Direct API[/yellow]"
                    types_str = "Config not recording these types"

                service_table.add_row(service.upper(), method, types_str)

            console.print(service_table)

        console.print()

    # Summary
    enabled_regions = [r for r in region_list if detect_config_availability(session, r, profile).is_enabled]
    if enabled_regions:
        console.print(f"[green]Config enabled in {len(enabled_regions)}/{len(region_list)} regions[/green]")
        console.print("[dim]Snapshots will use Config for faster collection where available.[/dim]")
    else:
        console.print("[yellow]Config not enabled in any checked regions[/yellow]")
        console.print("[dim]Snapshots will use direct API calls (slower).[/dim]")
        console.print()
        console.print(
            "[dim]To enable AWS Config: https://docs.aws.amazon.com/config/latest/developerguide/gs-console.html[/dim]"
        )


@snapshot_app.command("create")
def snapshot_create(
    name: Optional[str] = typer.Argument(
        None, help="Snapshot name (auto-generated if not provided)", envvar="AWSINV_SNAPSHOT_ID"
    ),
    regions: Optional[str] = typer.Option(
        None,
        "--regions",
        help="Comma-separated list of regions (default: us-east-1)",
        envvar=["AWSINV_REGION", "AWS_REGION"],
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="AWS profile name to use", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
    inventory: Optional[str] = typer.Option(
        None,
        "--inventory",
        help="Inventory name to use for filters (conflicts with --include-tags/--exclude-tags)",
        envvar="AWSINV_INVENTORY_ID",
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
    created_by_role: Optional[str] = typer.Option(
        None,
        "--created-by-role",
        help="Tag resources created by this IAM role with _created_by_role (queries CloudTrail, 90-day limit)",
    ),
    track_creators: bool = typer.Option(
        False,
        "--track-creators",
        help="Query CloudTrail to tag ALL resources with their creator (_created_by, _created_by_type)",
    ),
    use_config: bool = typer.Option(
        False, "--config", help="Use AWS Config for collection when available (default: disabled, use direct API)"
    ),
    config_aggregator: Optional[str] = typer.Option(
        None, "--config-aggregator", help="AWS Config Aggregator name for multi-account collection"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed collection method breakdown"),
    lambda_code_max_size: Optional[int] = typer.Option(
        None,
        "--lambda-code-max-size",
        help="Max Lambda code size (MB) to store inline. Larger packages stored to files. "
        "Default: 10. Use 0 for external-only, -1 for unlimited inline.",
    ),
):
    """Create a new snapshot of AWS resources.

    Captures resources from 26 AWS services:
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
    - Glue: Databases, Tables, Crawlers, Jobs, Connections

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
        # Show Config status
        if use_config:
            console.print(
                "🔧 AWS Config collection: [bold green]enabled[/bold green] (fallback to direct API if unavailable)"
            )
            if config_aggregator:
                console.print(f"   Using aggregator: {config_aggregator}")
        else:
            console.print("🔧 AWS Config collection: [bold yellow]disabled[/bold yellow] (using direct API)")

        # Convert lambda code max size from MB to bytes (handle special values)
        lambda_code_max_size_bytes = None
        if lambda_code_max_size is not None:
            if lambda_code_max_size == -1:
                lambda_code_max_size_bytes = -1  # Unlimited
            elif lambda_code_max_size == 0:
                lambda_code_max_size_bytes = 0  # External only
            else:
                lambda_code_max_size_bytes = lambda_code_max_size * 1024 * 1024

            # Show Lambda code storage setting
            if lambda_code_max_size == -1:
                console.print("📦 Lambda code storage: [bold green]unlimited inline[/bold green]")
            elif lambda_code_max_size == 0:
                console.print("📦 Lambda code storage: [bold cyan]external files only[/bold cyan]")
            else:
                console.print(
                    f"📦 Lambda code storage: inline up to [bold]{lambda_code_max_size}MB[/bold], larger to files"
                )

        snapshot = create_snapshot(
            name=name,
            regions=region_list,
            account_id=identity["account_id"],
            profile_name=aws_profile,
            set_active=set_active,
            resource_filter=resource_filter,
            inventory_name=inventory_name,
            use_config=use_config,
            config_aggregator=config_aggregator,
            lambda_code_max_size=lambda_code_max_size_bytes,
        )

        # Tag resources created by role if specified (uses CloudTrail)
        if created_by_role:
            from ..cloudtrail import CloudTrailQuery

            console.print(f"\n🔍 Checking creator role: [bold]{created_by_role}[/bold]")
            console.print("   Querying CloudTrail (this may take a moment)...")

            ct_query = CloudTrailQuery(profile_name=aws_profile, regions=region_list)
            created_resources = ct_query.get_created_resource_names(
                role_arn=created_by_role,
                days_back=90,
                regions=region_list,
            )

            # Build a set of (name, type) tuples for matching
            created_set = set()
            for resource_type, names in created_resources.items():
                for name in names:
                    created_set.add((name, resource_type))

            # Tag resources that were created by this role (add to tags dict)
            matched_count = 0
            for resource in snapshot.resources:
                is_match = False
                # Match by name and type
                if (resource.name, resource.resource_type) in created_set:
                    is_match = True
                # Also try matching by ARN components
                elif resource.arn:
                    arn_name = resource.arn.split("/")[-1].split(":")[-1]
                    if (arn_name, resource.resource_type) in created_set:
                        is_match = True

                if is_match:
                    matched_count += 1
                    # Add created-by tag to resource (internal tracking, not AWS tag)
                    if resource.tags is None:
                        resource.tags = {}
                    resource.tags["_created_by_role"] = created_by_role

            console.print(f"   Found {len(created_resources)} resource types in CloudTrail")
            console.print(f"   Tagged {matched_count}/{len(snapshot.resources)} resources as created by this role")
            console.print("   [dim](Resources older than 90 days won't appear in CloudTrail)[/dim]")

        # Track creators for ALL resources if --track-creators specified
        if track_creators:
            from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

            from ..cloudtrail import CloudTrailQuery
            from ..cloudtrail.query import EVENT_TO_RESOURCE_TYPE, MULTI_SERVICE_EVENTS

            console.print("\n🔍 Tracking resource creators from CloudTrail...")

            ct_query = CloudTrailQuery(profile_name=aws_profile, regions=region_list)

            # Count total event types to query
            event_types = list(EVENT_TO_RESOURCE_TYPE.keys()) + list(MULTI_SERVICE_EVENTS.keys())
            total_queries = len(event_types) * len(region_list)
            completed_queries = 0
            total_events_found = 0

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"[cyan]Querying {len(event_types)} event types...", total=total_queries)

                def progress_callback(event_name: str, events_found: int):
                    nonlocal completed_queries, total_events_found
                    completed_queries += 1
                    total_events_found += events_found
                    progress.update(task, advance=1, description=f"[cyan]{event_name}: {events_found} events")

                creators = ct_query.get_resource_creators(
                    days_back=90,
                    regions=region_list,
                    progress_callback=progress_callback,
                )

            # Match resources to their creators
            matched_count = 0
            for resource in snapshot.resources:
                # Try to find creator by resource type and name
                key = f"{resource.resource_type}:{resource.name}"
                creator_info = creators.get(key)

                # Also try matching by ARN name components
                if not creator_info and resource.arn:
                    arn_name = resource.arn.split("/")[-1].split(":")[-1]
                    key = f"{resource.resource_type}:{arn_name}"
                    creator_info = creators.get(key)

                if creator_info:
                    matched_count += 1
                    if resource.tags is None:
                        resource.tags = {}
                    resource.tags["_created_by"] = creator_info["created_by"]
                    resource.tags["_created_by_type"] = creator_info["created_by_type"]
                    resource.tags["_created_at"] = creator_info["created_at"]

            console.print(f"   Found {len(creators)} creation events in CloudTrail")
            console.print(f"   Tagged {matched_count}/{len(snapshot.resources)} resources with creator info")
            console.print("   [dim](Resources older than 90 days won't appear in CloudTrail)[/dim]")

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

        # Show collection method summary (Config vs Direct API)
        collection_sources = snapshot.metadata.get("collection_sources", {})
        config_enabled_regions = snapshot.metadata.get("config_enabled_regions", [])

        if collection_sources:
            # Count unique sources by method
            config_types = [t for t, s in collection_sources.items() if s == "config"]
            direct_types = [t for t, s in collection_sources.items() if s == "direct_api"]

            console.print("\nCollection Method:")
            if config_enabled_regions:
                console.print(f"  AWS Config: [green]Enabled[/green] in {', '.join(config_enabled_regions)}")
                console.print(f"  [green]Config[/green]: {len(config_types)} resource type(s)")
                console.print(f"  [yellow]Direct API[/yellow]: {len(direct_types)} resource type(s)")
            else:
                console.print("  AWS Config: [yellow]Not enabled[/yellow] (using direct API)")
                console.print(f"  Direct API: {len(direct_types)} resource type(s)")

            # Show detailed table only with --verbose
            if verbose and (config_types or direct_types):
                console.print()
                method_table = Table(show_header=True, title="Collection Sources by Resource Type")
                method_table.add_column("Resource Type", style="cyan")
                method_table.add_column("Method", style="green")
                method_table.add_column("Reason", style="dim")

                for resource_type in sorted(collection_sources.keys()):
                    method = collection_sources[resource_type]
                    if method == "config":
                        reason = "Config enabled & type recorded"
                        method_display = "[green]Config[/green]"
                    else:
                        # Determine reason for direct API
                        if not config_enabled_regions:
                            reason = "Config not enabled"
                        else:
                            reason = "Type not recorded by Config"
                        method_display = "[yellow]Direct API[/yellow]"
                    method_table.add_row(resource_type, method_display, reason)

                console.print(method_table)
            elif not verbose and (config_types or direct_types):
                console.print("\n  [dim]Use --verbose to see detailed breakdown by resource type[/dim]")
        elif not use_config:
            console.print("\nCollection Method:")
            console.print("  All resources collected via Direct API (use --config to enable AWS Config)")

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


@snapshot_app.command("enrich-creators")
def snapshot_enrich_creators(
    name: Optional[str] = typer.Argument(None, help="Snapshot name (defaults to active snapshot)"),
    regions: Optional[str] = typer.Option(
        None, "--regions", help="Comma-separated list of regions to query CloudTrail"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile name", envvar=["AWSINV_PROFILE", "AWS_PROFILE"]
    ),
    days_back: int = typer.Option(90, "--days", "-d", help="Days to look back in CloudTrail (max 90)"),
):
    """Enrich an existing snapshot with creator information from CloudTrail.

    Queries CloudTrail for resource creation events and tags resources with:
    - _created_by: ARN of the creator (role/user)
    - _created_by_type: Type of creator (AssumedRole, IAMUser, etc.)
    - _created_at: When the resource was created

    Example:
        awsinv snapshot enrich-creators my-snapshot --regions us-east-1,us-west-2
        awsinv snapshot enrich-creators  # uses active snapshot
    """
    try:
        from ..cloudtrail import CloudTrailQuery

        # Validate credentials
        aws_profile = profile if profile else config.aws_profile
        console.print("🔐 Validating AWS credentials...")
        identity = validate_credentials(aws_profile)
        console.print(f"✓ Authenticated as: {identity['arn']}\n", style="green")

        # Load snapshot
        storage = SnapshotStorage(config.storage_path)

        if name:
            snapshot = storage.load_snapshot(name)
        else:
            # Get active snapshot
            active_name = storage.get_active_snapshot_name()
            if not active_name:
                console.print("✗ No active snapshot found. Specify a snapshot name.", style="bold red")
                raise typer.Exit(code=1)
            snapshot = storage.load_snapshot(active_name)
            name = active_name

        console.print(f"📸 Enriching snapshot: [bold]{name}[/bold]")
        console.print(f"   Resources: {snapshot.resource_count}")

        # Parse regions
        if regions:
            region_list = [r.strip() for r in regions.split(",")]
        else:
            # Use regions from snapshot metadata if available
            region_list = snapshot.metadata.get("regions", ["us-east-1"])

        console.print(f"   Regions: {', '.join(region_list)}\n")

        # Query CloudTrail for creators with progress
        from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

        from ..cloudtrail.query import EVENT_TO_RESOURCE_TYPE, MULTI_SERVICE_EVENTS

        console.print("🔍 Querying CloudTrail for resource creators...")
        console.print(f"   Looking back {days_back} days...")

        # Extract unique resource types from snapshot to filter queries (big speedup!)
        snapshot_resource_types = {r.resource_type for r in snapshot.resources}

        # Filter event types to only those that create resources in the snapshot
        relevant_event_types = [
            event_name for event_name, res_type in EVENT_TO_RESOURCE_TYPE.items() if res_type in snapshot_resource_types
        ]
        # Also include multi-service events if any of their resource types match
        for event_name, source_mapping in MULTI_SERVICE_EVENTS.items():
            for res_type in source_mapping.values():
                if res_type in snapshot_resource_types and event_name not in relevant_event_types:
                    relevant_event_types.append(event_name)

        # If no matching event types, fall back to all (don't filter)
        all_event_count = len(EVENT_TO_RESOURCE_TYPE) + len(MULTI_SERVICE_EVENTS)
        if relevant_event_types:
            console.print(f"   Filtering to {len(relevant_event_types)} event types (matching snapshot resources)")
            event_count = len(relevant_event_types)
        else:
            console.print(
                f"   [yellow]No matching event types for snapshot resources, "
                f"querying all {all_event_count} event types[/yellow]"
            )
            snapshot_resource_types = None  # Don't filter
            event_count = all_event_count

        ct_query = CloudTrailQuery(profile_name=aws_profile, regions=region_list)

        # Count total event types to query
        total_queries = event_count * len(region_list)
        completed_queries = 0
        total_events_found = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Querying {event_count} event types...", total=total_queries)

            def progress_callback(event_name: str, events_found: int):
                nonlocal completed_queries, total_events_found
                completed_queries += 1
                total_events_found += events_found
                progress.update(task, advance=1, description=f"[cyan]{event_name}: {events_found} events")

            creators = ct_query.get_resource_creators(
                days_back=min(days_back, 90),
                regions=region_list,
                progress_callback=progress_callback,
                resource_types=snapshot_resource_types,
            )

        console.print(f"   Found {len(creators)} unique resource creators\n")

        # Match resources to their creators
        matched_count = 0
        for resource in snapshot.resources:
            # Try to find creator by resource type and name
            key = f"{resource.resource_type}:{resource.name}"
            creator_info = creators.get(key)

            # Also try matching by ARN name components
            if not creator_info and resource.arn:
                arn_name = resource.arn.split("/")[-1].split(":")[-1]
                key = f"{resource.resource_type}:{arn_name}"
                creator_info = creators.get(key)

            if creator_info:
                matched_count += 1
                if resource.tags is None:
                    resource.tags = {}
                resource.tags["_created_by"] = creator_info["created_by"]
                resource.tags["_created_by_type"] = creator_info["created_by_type"]
                resource.tags["_created_at"] = creator_info["created_at"]

        # Save updated snapshot by deleting old and re-saving
        # Need to use snapshot store directly since save_snapshot creates new
        from ..storage import SnapshotStore

        snapshot_store = SnapshotStore(storage.db)

        # Delete old snapshot and save updated one
        snapshot_store.delete(name)
        snapshot_store.save(snapshot)

        console.print("✓ Enrichment complete!", style="bold green")
        console.print(f"\n   Tagged {matched_count}/{snapshot.resource_count} resources with creator info")
        console.print(f"\n   [dim](Resources older than {days_back} days won't appear in CloudTrail)[/dim]")

        # Show sample of creators found
        if matched_count > 0:
            console.print("\n📋 Sample of creators found:")
            shown = 0
            for resource in snapshot.resources:
                if resource.tags and "_created_by" in resource.tags:
                    creator = resource.tags["_created_by"]
                    # Shorten long ARNs
                    if len(creator) > 60:
                        creator = "..." + creator[-57:]
                    console.print(f"   {resource.name}: {creator}")
                    shown += 1
                    if shown >= 5:
                        if matched_count > 5:
                            console.print(f"   ... and {matched_count - 5} more")
                        break

    except FileNotFoundError:
        console.print(f"✗ Snapshot '{name}' not found", style="bold red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"✗ Error enriching snapshot: {e}", style="bold red")
        raise typer.Exit(code=1)


@snapshot_app.command("rename")
def snapshot_rename(
    old_name: str = typer.Argument(..., help="Current snapshot name"),
    new_name: str = typer.Argument(..., help="New snapshot name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
):
    """Rename a snapshot.

    Example:
        awsinv snapshot rename old-snapshot-name new-snapshot-name
    """
    try:
        storage = SnapshotStorage(config.storage_path)

        # Check if source exists
        if not storage.exists(old_name):
            console.print(f"✗ Snapshot '{old_name}' not found", style="bold red")
            raise typer.Exit(code=1)

        # Check if target already exists
        if storage.exists(new_name):
            console.print(f"✗ Snapshot '{new_name}' already exists", style="bold red")
            raise typer.Exit(code=1)

        # Rename
        storage.rename_snapshot(old_name, new_name)

        console.print(f"✓ Renamed snapshot [bold]{old_name}[/bold] to [bold]{new_name}[/bold]", style="green")

    except Exception as e:
        console.print(f"✗ Error renaming snapshot: {e}", style="bold red")
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


@snapshot_app.command("creators")
def snapshot_creators(
    snapshot_name: Optional[str] = typer.Argument(None, help="Snapshot name (default: active snapshot)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    storage_path: Optional[str] = typer.Option(None, "--storage-path", help="Override storage location"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show individual resources for each creator"),
    export: Optional[str] = typer.Option(
        None, "--export", help="Export to file (format detected from extension: .json, .csv)"
    ),
):
    """List all resource creators for a snapshot.

    Shows a summary of who created resources in the snapshot, including resource
    counts by creator and resource type breakdown. Requires snapshots to have
    creator information (use --track-creators when creating or enrich-creators).

    Examples:
        awsinv snapshot creators                    # Creators for active snapshot
        awsinv snapshot creators baseline-2025      # Creators for specific snapshot
        awsinv snapshot creators --detailed         # Show individual resources
        awsinv snapshot creators --export out.json  # Export to JSON
        awsinv snapshot creators --export out.csv   # Export to CSV
    """
    from rich.table import Table

    from ..storage.database import Database
    from ..storage.resource_store import ResourceStore

    try:
        # Use provided storage path or default from config
        storage = SnapshotStorage(storage_path or config.storage_path)

        # Determine which snapshot to use
        target_snapshot_name: str
        if snapshot_name:
            target_snapshot_name = snapshot_name
        else:
            active_name = storage.get_active_snapshot_name()
            if not active_name:
                console.print("✗ No active snapshot found", style="bold red")
                console.print("\nSet an active snapshot with:")
                console.print("  awsinv snapshot set-active <name>")
                console.print("\nOr specify a snapshot explicitly:")
                console.print("  awsinv snapshot creators <snapshot-name>")
                raise typer.Exit(code=1)
            target_snapshot_name = active_name

        # Verify snapshot exists
        try:
            snapshot = storage.load_snapshot(target_snapshot_name)
        except FileNotFoundError:
            console.print(f"✗ Snapshot '{target_snapshot_name}' not found", style="bold red")
            raise typer.Exit(code=1)

        # Initialize database and resource store
        db = Database(storage_path or config.storage_path)
        resource_store = ResourceStore(db)

        # Get creators summary
        creators_summary = resource_store.get_creators_summary(target_snapshot_name)
        resources_without_creator = resource_store.get_resources_without_creator(target_snapshot_name)

        # Export mode
        if export:
            import json
            from pathlib import Path

            export_path = Path(export)
            ext = export_path.suffix.lower()

            if ext == ".json":
                export_data = {
                    "snapshot_name": target_snapshot_name,
                    "snapshot_created_at": snapshot.created_at.isoformat(),
                    "total_creators": len(creators_summary),
                    "resources_without_creator": resources_without_creator,
                    "creators": creators_summary,
                }
                with open(export_path, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)
                console.print(f"✓ Exported {len(creators_summary)} creators to JSON: {export_path}", style="bold green")

            elif ext == ".csv":
                import csv

                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    if detailed:
                        # Detailed CSV with one row per resource
                        writer.writerow(
                            ["creator", "creator_type", "resource_arn", "resource_type", "name", "region", "created_at"]
                        )
                        for creator_info in creators_summary:
                            for resource in creator_info["resources"]:
                                writer.writerow(
                                    [
                                        creator_info["creator"],
                                        creator_info["creator_type"],
                                        resource["arn"],
                                        resource["resource_type"],
                                        resource["name"],
                                        resource["region"],
                                        resource.get("created_at", ""),
                                    ]
                                )
                    else:
                        # Summary CSV with one row per creator
                        writer.writerow(["creator", "creator_type", "resource_count", "resource_types"])
                        for creator_info in creators_summary:
                            types_str = ", ".join(f"{k}:{v}" for k, v in creator_info["resource_types"].items())
                            writer.writerow(
                                [
                                    creator_info["creator"],
                                    creator_info["creator_type"],
                                    creator_info["resource_count"],
                                    types_str,
                                ]
                            )
                console.print(f"✓ Exported creators to CSV: {export_path}", style="bold green")

            else:
                console.print(f"✗ Unsupported export format: {ext}", style="bold red")
                console.print("  Supported formats: .json, .csv")
                raise typer.Exit(code=1)

            raise typer.Exit(code=0)

        # Display mode
        console.print(f"\n[bold cyan]Resource Creators for Snapshot: {target_snapshot_name}[/bold cyan]")
        console.print(f"[dim]Created: {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")

        if not creators_summary:
            console.print("⚠️  No creator information found in this snapshot.", style="yellow")
            console.print("\nTo add creator information, use one of:")
            console.print("  • awsinv snapshot create --track-creators")
            console.print("  • awsinv snapshot enrich-creators <snapshot-name>")
            raise typer.Exit(code=0)

        # Summary stats
        total_tracked = sum(c["resource_count"] for c in creators_summary)
        console.print("[bold]Summary:[/bold]")
        console.print(f"  • Unique creators: {len(creators_summary)}")
        console.print(f"  • Resources with creator info: {total_tracked:,}")
        if resources_without_creator > 0:
            console.print(f"  • Resources without creator info: {resources_without_creator:,}", style="yellow")
        console.print()

        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Creator", style="cyan", no_wrap=False)
        table.add_column("Type", style="dim")
        table.add_column("Resources", justify="right")
        table.add_column("Top Resource Types", no_wrap=False)

        for creator_info in creators_summary:
            # Extract just the name from ARN for display
            creator_arn = creator_info["creator"]
            if "/" in creator_arn:
                creator_display = creator_arn.split("/")[-1]
            elif ":" in creator_arn:
                creator_display = creator_arn.split(":")[-1]
            else:
                creator_display = creator_arn

            # Get top 3 resource types
            sorted_types = sorted(creator_info["resource_types"].items(), key=lambda x: x[1], reverse=True)[:3]
            types_display = ", ".join(f"{t.split('::')[-1]}({c})" for t, c in sorted_types)

            table.add_row(
                creator_display,
                creator_info["creator_type"],
                str(creator_info["resource_count"]),
                types_display,
            )

        console.print(table)

        # Detailed view
        if detailed:
            console.print("\n[bold cyan]Detailed Resources by Creator:[/bold cyan]\n")

            for creator_info in creators_summary:
                creator_arn = creator_info["creator"]
                if "/" in creator_arn:
                    creator_display = creator_arn.split("/")[-1]
                else:
                    creator_display = creator_arn

                console.print(f"[bold]{creator_display}[/bold] ({creator_info['resource_count']} resources)")
                console.print(f"  [dim]Full ARN: {creator_arn}[/dim]")
                console.print(f"  [dim]Type: {creator_info['creator_type']}[/dim]\n")

                # Show resources grouped by type
                resources_by_type: Dict[str, List[Dict]] = {}
                for resource in creator_info["resources"]:
                    rtype = resource["resource_type"]
                    if rtype not in resources_by_type:
                        resources_by_type[rtype] = []
                    resources_by_type[rtype].append(resource)

                for rtype, resources in sorted(resources_by_type.items()):
                    type_short = rtype.split("::")[-1] if "::" in rtype else rtype
                    console.print(f"  [cyan]{type_short}[/cyan] ({len(resources)})")
                    for resource in resources[:5]:  # Show max 5 per type
                        console.print(f"    • {resource['name'] or resource['arn']}")
                        if resource.get("region"):
                            console.print(f"      [dim]Region: {resource['region']}[/dim]")
                    if len(resources) > 5:
                        console.print(f"    [dim]... and {len(resources) - 5} more[/dim]")
                    console.print()

                console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"✗ Error listing creators: {e}", style="bold red")
        logger.exception("Error in snapshot creators command")
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
                    f"  Take a snapshot or set one as active: aws-snapshot create --inventory {inventory_name}",
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
                    f"  Take a snapshot or set one as active: aws-snapshot create --inventory {inventory_name}",
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


# Cleanup commands (destructive operations)
cleanup_app = typer.Typer(help="Delete resources - returns environment to baseline or removes unprotected resources")


@cleanup_app.command("preview")
def cleanup_preview(
    baseline_snapshot: str = typer.Argument(
        ..., help="Baseline snapshot - resources created after this will be deleted"
    ),
    account_id: str = typer.Option(None, "--account-id", help="AWS account ID (auto-detected if not provided)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    resource_types: Optional[List[str]] = typer.Option(
        None, "--type", help="Filter by resource types (e.g., AWS::EC2::Instance)"
    ),
    regions: Optional[List[str]] = typer.Option(None, "--region", help="Filter by AWS regions"),
    protect_tags: Optional[List[str]] = typer.Option(
        None, "--protect-tag", help="Protect resources with tag (format: key=value, can repeat)"
    ),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to protection rules config file"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json, yaml"),
):
    """Preview resources that would be DELETED to return to a baseline snapshot.

    Shows what resources have been created since the snapshot without
    performing any deletions. This is a safe dry-run operation.

    Examples:
        # Preview resources created since a baseline snapshot
        awsinv cleanup preview prod-baseline

        # Preview with tag-based protection
        awsinv cleanup preview my-snapshot --protect-tag "project=baseline"

        # Preview with multiple protection tags
        awsinv cleanup preview my-snapshot --protect-tag "project=baseline" --protect-tag "env=prod"

        # Preview with config file
        awsinv cleanup preview my-snapshot --config .awsinv-cleanup.yaml

        # Preview only EC2 instances in us-east-1
        awsinv cleanup preview my-snapshot --type AWS::EC2::Instance --region us-east-1
    """
    from ..aws.credentials import get_account_id
    from ..restore.audit import AuditStorage
    from ..restore.cleaner import ResourceCleaner
    from ..restore.config import build_protection_rules, load_config_file
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

        # Load config and build protection rules
        config = load_config_file(config_file)
        protection_rules = build_protection_rules(config, protect_tags)

        if protection_rules:
            console.print(f"[dim]Loaded {len(protection_rules)} protection rule(s)[/dim]")

        # Initialize components
        snapshot_storage = SnapshotStorage()
        safety_checker = SafetyChecker(rules=protection_rules)
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
                f"\n[yellow]⚠️  {deletable_count} resource(s) would be DELETED if you run 'cleanup execute'[/yellow]"
            )
            console.print("[dim]Use 'awsinv cleanup execute' with --confirm to actually delete resources[/dim]\n")
        else:
            console.print("\n[green]✓ No resources would be deleted - environment matches baseline[/green]\n")

    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]\n")
        logger.exception("Error in cleanup preview command")
        raise typer.Exit(code=2)


@cleanup_app.command("execute")
def cleanup_execute(
    baseline_snapshot: str = typer.Argument(
        ..., help="Baseline snapshot - resources created after this will be deleted"
    ),
    account_id: str = typer.Option(None, "--account-id", help="AWS account ID (auto-detected if not provided)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    resource_types: Optional[List[str]] = typer.Option(None, "--type", help="Filter by resource types"),
    regions: Optional[List[str]] = typer.Option(None, "--region", help="Filter by AWS regions"),
    protect_tags: Optional[List[str]] = typer.Option(
        None, "--protect-tag", help="Protect resources with tag (format: key=value, can repeat)"
    ),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to protection rules config file"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm deletion (REQUIRED for execution)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation prompt"),
):
    """DELETE resources created after a baseline snapshot.

    ⚠️  DESTRUCTIVE OPERATION: This will permanently delete AWS resources!

    Deletes resources that were created after the snapshot, returning
    your AWS environment to that baseline state. Protected resources are skipped.

    Examples:
        # Delete resources created after baseline, protecting tagged resources
        awsinv cleanup execute my-snapshot --protect-tag "project=baseline" --confirm

        # Use config file for protection rules
        awsinv cleanup execute my-snapshot --config .awsinv-cleanup.yaml --confirm

        # Delete only EC2 instances, skip prompt
        awsinv cleanup execute my-snapshot --confirm --yes --type AWS::EC2::Instance

        # Delete in specific region with profile
        awsinv cleanup execute my-snapshot --confirm --region us-east-1 --profile prod
    """
    from ..aws.credentials import get_account_id
    from ..restore.audit import AuditStorage
    from ..restore.cleaner import ResourceCleaner
    from ..restore.config import build_protection_rules, load_config_file
    from ..restore.safety import SafetyChecker

    try:
        # Require --confirm flag
        if not confirm:
            console.print("\n[red]ERROR: --confirm flag is required for deletion operations[/red]")
            console.print("[yellow]This is a safety measure to prevent accidental deletions[/yellow]")
            console.print("\n[dim]Run with: awsinv cleanup execute <snapshot> --confirm[/dim]\n")
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

        # Load config and build protection rules
        config = load_config_file(config_file)
        protection_rules = build_protection_rules(config, protect_tags)

        if protection_rules:
            console.print(f"[dim]Loaded {len(protection_rules)} protection rule(s)[/dim]")

        # Initialize components
        snapshot_storage = SnapshotStorage()
        safety_checker = SafetyChecker(rules=protection_rules)
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
            operation, deletion_records = cleaner.execute(
                baseline_snapshot=baseline_snapshot,
                account_id=account_id,
                confirmed=True,
                aws_profile=profile,
                resource_types=resource_types,
                regions=regions,
            )

        # Display results
        console.print("\n[bold]Deletion Complete[/bold]\n")

        # Show failure details if any
        failed_records = [r for r in deletion_records if r.status.value == "failed"]
        if failed_records:
            console.print("[bold red]Failed Deletions:[/bold red]\n")
            for record in failed_records:
                # Extract just the resource type name (e.g., "Instance" from "AWS::EC2::Instance")
                type_short = (
                    record.resource_type.split("::")[-1] if "::" in record.resource_type else record.resource_type
                )
                console.print(f"  [red]✗[/red] [bold]{type_short}[/bold]: {record.resource_id}")
                console.print(f"    [dim]Region:[/dim] {record.region}")
                console.print(f"    [dim]ARN:[/dim] {record.resource_arn}")
                console.print(f"    [dim]Error:[/dim] [yellow]{record.error_message}[/yellow]")
                console.print()

        # Results summary
        status_color = (
            "green"
            if operation.status.value == "completed"
            else "yellow"
            if operation.status.value == "partial"
            else "red"
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
        logger.exception("Error in cleanup execute command")
        raise typer.Exit(code=2)


def _matches_wildcard_pattern(value: str, pattern: str) -> bool:
    """Check if value matches a wildcard pattern.

    Supports * (any characters) and ? (single character) wildcards.
    Case-insensitive matching.

    Args:
        value: The string to check
        pattern: The pattern with optional wildcards

    Returns:
        True if value matches pattern
    """
    import fnmatch

    return fnmatch.fnmatch(value.lower(), pattern.lower())


def _resource_matches_exclusion(
    resource_name: str,
    resource_tags: Dict[str, str],
    exclude_names: Optional[List[str]],
    exclude_tags: Optional[List[str]],
) -> tuple:
    """Check if a resource should be excluded from deletion.

    Args:
        resource_name: The resource name
        resource_tags: The resource tags
        exclude_names: List of name patterns to exclude (supports wildcards)
        exclude_tags: List of tag patterns to exclude (format: key=value, supports wildcards)

    Returns:
        Tuple of (is_excluded, reason) where reason explains why excluded
    """
    # Check name exclusions
    if exclude_names:
        for pattern in exclude_names:
            if _matches_wildcard_pattern(resource_name or "", pattern):
                return True, f"name matches exclusion pattern '{pattern}'"

    # Check tag exclusions
    if exclude_tags and resource_tags:
        for tag_pattern in exclude_tags:
            if "=" in tag_pattern:
                key_pattern, value_pattern = tag_pattern.split("=", 1)
            else:
                # If no =, match any value for this key
                key_pattern = tag_pattern
                value_pattern = "*"

            for tag_key, tag_value in resource_tags.items():
                if _matches_wildcard_pattern(tag_key, key_pattern) and _matches_wildcard_pattern(
                    tag_value, value_pattern
                ):
                    return True, f"tag '{tag_key}={tag_value}' matches exclusion pattern '{tag_pattern}'"

    return False, ""


@cleanup_app.command("purge")
def cleanup_purge(
    account_id: str = typer.Option(None, "--account-id", help="AWS account ID (auto-detected if not provided)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile name"),
    resource_types: Optional[List[str]] = typer.Option(None, "--type", help="Filter by resource types"),
    regions: Optional[List[str]] = typer.Option(None, "--region", help="Filter by AWS regions"),
    protect_tags: Optional[List[str]] = typer.Option(
        None, "--protect-tag", help="Protect resources with tag (format: key=value, can repeat)"
    ),
    exclude_names: Optional[List[str]] = typer.Option(
        None, "--exclude-name", "-x", help="Exclude resources by name pattern (supports * and ? wildcards, can repeat)"
    ),
    exclude_tags: Optional[List[str]] = typer.Option(
        None, "--exclude-tag", help="Exclude resources by tag (format: key=value, supports wildcards, can repeat)"
    ),
    config_file: Optional[str] = typer.Option(None, "--config", help="Path to protection rules config file"),
    from_snapshot: Optional[str] = typer.Option(
        None,
        "--from-snapshot",
        "-s",
        help="Use resources from an enriched snapshot (required for --created-by filters)",
    ),
    created_by: Optional[str] = typer.Option(
        None, "--created-by", help="Only delete resources created by this user/role (substring match on creator ARN)"
    ),
    created_after: Optional[str] = typer.Option(
        None,
        "--created-after",
        help="Only delete resources created after this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    created_before: Optional[str] = typer.Option(
        None,
        "--created-before",
        help="Only delete resources created before this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    preview: bool = typer.Option(False, "--preview", help="Preview mode - show what would be deleted without deleting"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm deletion (REQUIRED for execution)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation prompt"),
):
    """DELETE all resources EXCEPT those matching protection rules or exclusions.

    ⚠️  DESTRUCTIVE OPERATION: This will permanently delete AWS resources!

    Unlike 'cleanup execute', this does NOT compare to a snapshot. It deletes
    ALL resources that don't match protection rules (tags, types, etc.).

    Use this for lab/sandbox cleanup where baseline resources are tagged.

    Exclusion Filters:
        Use --exclude-name and --exclude-tag to protect specific resources from deletion.
        Supports wildcards: * (any characters) and ? (single character).
        Can specify multiple exclusions (OR logic - excluded if ANY match).

    Creator/Date Filters:
        Use --from-snapshot with an enriched snapshot to filter by creator.
        First run: awsinv snapshot enrich-creators <snapshot-name>

    Examples:
        # Preview what would be deleted (safe)
        awsinv cleanup purge --protect-tag "project=baseline" --preview

        # Delete everything except baseline-tagged resources
        awsinv cleanup purge --protect-tag "project=baseline" --confirm

        # Multiple protection tags (OR logic - protected if ANY match)
        awsinv cleanup purge --protect-tag "project=baseline" --protect-tag "env=prod" --confirm

        # Exclude specific resources by name pattern (wildcards supported)
        awsinv cleanup purge --protect-tag "env=dev" --exclude-name "*-prod-*" --preview
        awsinv cleanup purge --protect-tag "env=dev" --exclude-name "my-critical-function" --preview

        # Exclude multiple resources by name (can repeat option)
        awsinv cleanup purge --protect-tag "env=dev" -x "*-prod-*" -x "*-staging-*" -x "critical-*" --preview

        # Exclude resources by tag pattern (wildcards on key and value)
        awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "Name=*production*" --preview
        awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "critical=true" --preview

        # Exclude by tag key only (any value)
        awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "do-not-delete=*" --preview

        # Combine name and tag exclusions
        awsinv cleanup purge --protect-tag "env=dev" --exclude-name "*-prod-*" --exclude-tag "protected=yes" --preview

        # Use config file for protection rules
        awsinv cleanup purge --config .awsinv-cleanup.yaml --confirm

        # Purge only specific resource types
        awsinv cleanup purge --protect-tag "project=baseline" --type AWS::EC2::Instance --confirm

        # Purge in specific region
        awsinv cleanup purge --protect-tag "project=baseline" --region us-east-1 --confirm

        # Delete resources created by a specific user (requires enriched snapshot)
        awsinv cleanup purge --from-snapshot my-snapshot --created-by "john.doe" --preview

        # Delete resources created by a specific role
        awsinv cleanup purge --from-snapshot my-snapshot --created-by "AWSReservedSSO_Developer" --confirm

        # Delete resources created after a specific date
        awsinv cleanup purge --from-snapshot my-snapshot --created-after "2025-01-01" --preview

        # Delete resources created within a date range
        awsinv cleanup purge --from-snapshot my-snapshot \\
            --created-after "2025-01-01" --created-before "2025-01-15" --preview

        # Combine creator and date filters
        awsinv cleanup purge --from-snapshot my-snapshot \\
            --created-by "john" --created-after "2025-01-10" --preview
    """
    from collections import defaultdict
    from datetime import datetime as dt

    from ..aws.credentials import get_account_id
    from ..restore.audit import AuditStorage
    from ..restore.config import build_protection_rules, load_config_file
    from ..restore.deleter import ResourceDeleter
    from ..restore.dependency import get_deletion_tier, sort_resources_for_deletion
    from ..restore.safety import SafetyChecker
    from ..snapshot.capturer import create_snapshot

    try:
        # Validate creator/date filters require --from-snapshot
        if (created_by or created_after or created_before) and not from_snapshot:
            console.print(
                "\n[red]ERROR: --created-by, --created-after, and --created-before require --from-snapshot[/red]"
            )
            console.print("[yellow]First enrich a snapshot with creator info:[/yellow]")
            console.print("[dim]  awsinv snapshot enrich-creators <snapshot-name>[/dim]")
            console.print(
                "[dim]Then use: awsinv cleanup purge --from-snapshot <snapshot-name> --created-by <name>[/dim]\n"
            )
            raise typer.Exit(code=1)

        # Parse date filters
        created_after_dt = None
        created_before_dt = None
        if created_after:
            try:
                created_after_dt = dt.fromisoformat(created_after.replace("Z", "+00:00"))
            except ValueError:
                console.print(f"\n[red]ERROR: Invalid date format for --created-after: {created_after}[/red]")
                console.print("[yellow]Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[/yellow]\n")
                raise typer.Exit(code=1)
        if created_before:
            try:
                created_before_dt = dt.fromisoformat(created_before.replace("Z", "+00:00"))
            except ValueError:
                console.print(f"\n[red]ERROR: Invalid date format for --created-before: {created_before}[/red]")
                console.print("[yellow]Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[/yellow]\n")
                raise typer.Exit(code=1)

        # Load config and build protection rules
        config = load_config_file(config_file)
        protection_rules = build_protection_rules(config, protect_tags)

        if preview:
            console.print("\n[bold cyan]🔍 Purge Preview (dry-run)[/bold cyan]\n")
        else:
            if not confirm:
                console.print("\n[red]ERROR: --confirm flag is required for purge operations[/red]")
                console.print("[yellow]This is a safety measure to prevent accidental deletions[/yellow]")
                console.print("\n[dim]Run with: awsinv cleanup purge --confirm[/dim]\n")
                raise typer.Exit(code=1)
            console.print("\n[bold red]⚠️  PURGE OPERATION - DESTRUCTIVE[/bold red]\n")

        # Auto-detect account ID if not provided
        if not account_id:
            try:
                account_id = get_account_id(profile_name=profile)
                console.print(f"[dim]Detected account ID: {account_id}[/dim]")
            except Exception as e:
                console.print(f"[red]Error detecting account ID: {e}[/red]")
                console.print("[yellow]Please provide --account-id explicitly[/yellow]")
                raise typer.Exit(code=1)

        console.print(f"[dim]Loaded {len(protection_rules)} protection rule(s)[/dim]")
        for rule in protection_rules:
            console.print(f"[dim]  • {rule.description}[/dim]")

        # Initialize safety checker
        safety_checker = SafetyChecker(rules=protection_rules)

        # Collect resources - either from snapshot or live scan
        all_resources = []

        if from_snapshot:
            # Load from enriched snapshot
            console.print(f"\n[bold]Loading resources from snapshot: {from_snapshot}[/bold]")
            storage = SnapshotStorage()
            snapshot_data = storage.load_snapshot(from_snapshot)
            if not snapshot_data:
                console.print(f"[red]ERROR: Snapshot '{from_snapshot}' not found[/red]")
                raise typer.Exit(code=1)

            # snapshot_data.resources already contains Resource objects
            all_resources = list(snapshot_data.resources)
            console.print(f"[dim]Loaded {len(all_resources)} resources from snapshot[/dim]")

            # Check if snapshot has creator info
            has_creator_info = any(r.tags and "_created_by" in r.tags for r in all_resources[:100])  # Sample first 100
            if (created_by or created_after or created_before) and not has_creator_info:
                console.print("\n[yellow]WARNING: Snapshot may not have creator information[/yellow]")
                console.print("[dim]Run 'awsinv snapshot enrich-creators <snapshot>' first[/dim]\n")

            # Display active filters
            if created_by or created_after or created_before:
                console.print("[dim]Active filters:[/dim]")
                if created_by:
                    console.print(f"[dim]  • Created by: {created_by}[/dim]")
                if created_after_dt:
                    console.print(f"[dim]  • Created after: {created_after_dt}[/dim]")
                if created_before_dt:
                    console.print(f"[dim]  • Created before: {created_before_dt}[/dim]")

            # Apply creator/date filters
            filtered_resources = []
            for resource in all_resources:
                tags = resource.tags or {}

                # Filter by creator
                if created_by:
                    resource_creator = tags.get("_created_by", "")
                    if created_by.lower() not in resource_creator.lower():
                        continue

                # Filter by creation date
                resource_created_at = tags.get("_created_at")
                if resource_created_at and (created_after_dt or created_before_dt):
                    try:
                        resource_dt = dt.fromisoformat(resource_created_at.replace("Z", "+00:00"))
                        if created_after_dt and resource_dt < created_after_dt:
                            continue
                        if created_before_dt and resource_dt > created_before_dt:
                            continue
                    except ValueError:
                        # Skip resources with invalid dates when date filter is active
                        continue
                elif (created_after_dt or created_before_dt) and not resource_created_at:
                    # Skip resources without creation date when date filter is active
                    continue

                filtered_resources.append(resource)

            console.print(f"[dim]After creator/date filters: {len(filtered_resources)} resources[/dim]")
            all_resources = filtered_resources
        else:
            # Live scan using create_snapshot
            console.print("\n[bold]Scanning resources...[/bold]")
            target_regions = regions if regions else ["us-east-1"]  # Default to us-east-1 if not specified

            with console.status("[bold green]Collecting resources..."):
                try:
                    snapshot_data = create_snapshot(
                        name="purge-temp",
                        account_id=account_id,
                        regions=target_regions,
                        resource_types=resource_types,
                        profile_name=profile,
                    )
                    all_resources = list(snapshot_data.resources)
                except Exception as e:
                    console.print(f"[red]Error collecting resources: {e}[/red]")
                    logger.exception("Error in purge resource collection")
                    raise typer.Exit(code=1)

            console.print(f"[dim]Found {len(all_resources)} total resources[/dim]")

        # Apply type/region filters (for snapshot mode)
        if from_snapshot:
            if resource_types:
                all_resources = [r for r in all_resources if r.resource_type in resource_types]
                console.print(f"[dim]After type filter: {len(all_resources)} resources[/dim]")
            if regions:
                all_resources = [r for r in all_resources if r.region in regions]
                console.print(f"[dim]After region filter: {len(all_resources)} resources[/dim]")

        # Display exclusion filters if provided
        if exclude_names or exclude_tags:
            console.print("[dim]Exclusion filters:[/dim]")
            if exclude_names:
                for pattern in exclude_names:
                    console.print(f"[dim]  • Exclude name: {pattern}[/dim]")
            if exclude_tags:
                for pattern in exclude_tags:
                    console.print(f"[dim]  • Exclude tag: {pattern}[/dim]")

        # Apply protection rules and exclusions
        to_delete = []
        protected = []
        excluded = []

        for resource in all_resources:
            # First check exclusions (by name or tag pattern)
            is_excluded, exclude_reason = _resource_matches_exclusion(
                resource.name or "",
                resource.tags or {},
                exclude_names,
                exclude_tags,
            )

            if is_excluded:
                excluded.append((resource, exclude_reason))
                continue

            # Then check protection rules
            resource_dict = {
                "resource_id": resource.name,
                "resource_type": resource.resource_type,
                "region": resource.region,
                "arn": resource.arn,
                "tags": resource.tags or {},
            }

            is_protected, reason = safety_checker.is_protected(resource_dict)

            if is_protected:
                protected.append((resource, reason))
            else:
                to_delete.append(resource)

        # Sort resources by deletion order (dependency tree)
        to_delete = sort_resources_for_deletion(to_delete)

        # Display summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  • Total resources: {len(all_resources)}")
        console.print(f"  • Protected by rules (will keep): [green]{len(protected)}[/green]")
        if excluded:
            console.print(f"  • Excluded by pattern (will keep): [cyan]{len(excluded)}[/cyan]")
        console.print(f"  • Unprotected (will delete): [red]{len(to_delete)}[/red]")

        if preview:
            # Show what would be deleted, grouped by deletion tier
            if to_delete:
                console.print("\n[bold yellow]Resources that would be DELETED (in dependency order):[/bold yellow]")

                # Group resources by deletion tier
                resources_by_tier: Dict[int, List] = defaultdict(list)
                for resource in to_delete:
                    tier = get_deletion_tier(resource.resource_type)
                    resources_by_tier[tier].append(resource)

                # Display by tier (lower tiers deleted first)
                tier_names = {
                    1: "Application Layer (ECS Services, Lambda, API Gateway, etc.)",
                    2: "Compute Layer (EC2, RDS, EKS, etc.)",
                    3: "Load Balancers",
                    4: "Networking (NAT Gateways, ENIs, VPC Endpoints)",
                    5: "Security Groups",
                    6: "Subnets & Route Tables",
                    7: "Internet Gateways",
                    8: "VPCs",
                    9: "Standalone Resources (S3, DynamoDB, etc.)",
                    10: "IAM Resources",
                }

                for tier in sorted(resources_by_tier.keys()):
                    tier_resources = resources_by_tier[tier]
                    tier_name = tier_names.get(tier, f"Tier {tier}")
                    console.print(
                        f"\n  [bold magenta]Tier {tier}: {tier_name}[/bold magenta] ({len(tier_resources)} resources)"
                    )

                    for resource in tier_resources:
                        type_short = (
                            resource.resource_type.split("::")[-1]
                            if "::" in resource.resource_type
                            else resource.resource_type
                        )
                        console.print(f"    [red]✗[/red] {type_short}: {resource.name} ({resource.region})")

            if excluded:
                console.print("\n[bold cyan]Resources EXCLUDED by pattern (will keep):[/bold cyan]")
                for resource, reason in excluded:
                    console.print(f"  [cyan]○[/cyan] {resource.resource_type}: {resource.name} - {reason}")

            if protected:
                console.print("\n[bold green]Resources PROTECTED by rules (will keep):[/bold green]")
                for resource, reason in protected:
                    console.print(f"  [green]✓[/green] {resource.resource_type}: {resource.name} - {reason}")

            console.print("\n[dim]This was a preview. Use --confirm to actually delete resources.[/dim]\n")
            raise typer.Exit(code=0)

        # Execution mode
        if len(to_delete) == 0:
            console.print("\n[green]✓ No unprotected resources to delete[/green]\n")
            raise typer.Exit(code=0)

        # Interactive confirmation
        if not yes:
            console.print(f"\n[bold red]About to DELETE {len(to_delete)} resources![/bold red]")
            confirm_prompt = typer.confirm("Are you sure you want to proceed?")
            if not confirm_prompt:
                console.print("\n[yellow]Aborted - no resources were deleted[/yellow]\n")
                raise typer.Exit(code=0)

        # Execute deletion with real-time progress display
        console.print("\n[bold red]Executing deletion...[/bold red]\n")
        deleter = ResourceDeleter(aws_profile=profile)
        AuditStorage()

        succeeded = 0
        failed = 0
        failures = []  # Track failed resources with error details

        progress_display = DeletionProgressDisplay(to_delete, console)

        skipped = 0
        try:
            progress_display.start()

            for resource in to_delete:
                progress_display.mark_in_progress(resource)

                success, error, was_skipped = deleter.delete_resource(
                    resource_type=resource.resource_type,
                    resource_id=resource.name,
                    region=resource.region,
                    arn=resource.arn,
                )

                if success:
                    if was_skipped:
                        progress_display.mark_skipped(resource)
                        skipped += 1
                        logger.info(f"Skipped (already gone) {resource.resource_type}: {resource.name}")
                    else:
                        progress_display.mark_succeeded(resource)
                        succeeded += 1
                        logger.info(f"Deleted {resource.resource_type}: {resource.name}")
                else:
                    progress_display.mark_failed(resource, error)
                    failed += 1
                    failures.append((resource, error))
                    logger.warning(f"Failed to delete {resource.resource_type}: {resource.name} - {error}")
        finally:
            progress_display.stop()

        # Display final summary report by tier
        console.print("\n[bold]Purge Complete[/bold]")
        progress_display.print_final_summary()

        # Show overall summary panel
        status_color = "green" if failed == 0 else "yellow" if (succeeded > 0 or skipped > 0) else "red"

        excluded_line = f"\n• Excluded by pattern: {len(excluded)}" if excluded else ""
        skipped_line = f"\n• Skipped (already gone): [cyan]{skipped}[/cyan]" if skipped > 0 else ""
        summary_text = f"""
[bold]Results:[/bold]
• Deleted: [green]{succeeded}[/green]{skipped_line}
• Failed: [red]{failed}[/red]
• Protected by rules: {len(protected)}{excluded_line}
• Total scanned: {len(all_resources)}
        """

        console.print(Panel(summary_text.strip(), title="[bold]Purge Summary[/bold]", border_style=status_color))

        if failed > 0:
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]\n")
        logger.exception("Error in purge command")
        raise typer.Exit(code=2)


app.add_typer(cleanup_app, name="cleanup")


# ============================================================================
# QUERY COMMANDS - SQL queries across snapshots
# ============================================================================

query_app = typer.Typer(help="Query resources across snapshots using SQL")


@query_app.command("sql")
def query_sql(
    query: str = typer.Argument(..., help="SQL query to execute (SELECT only)"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum results to return"),
    snapshot: Optional[str] = typer.Option(
        None, "--snapshot", "-s", help="Filter by snapshot name", envvar="AWSINV_SNAPSHOT_ID"
    ),
):
    """Execute raw SQL query against the resource database.

    Only SELECT queries are allowed for safety. The database contains tables:
    - snapshots: Snapshot metadata
    - resources: Resource details (arn, type, name, region, config_hash)
    - resource_tags: Tags for each resource (resource_id, key, value)
    - inventories: Inventory definitions
    - audit_operations: Audit operation logs
    - audit_records: Individual resource audit records

    Examples:
        awsinv query sql "SELECT resource_type, COUNT(*) as count FROM resources GROUP BY resource_type"
        awsinv query sql "SELECT r.arn FROM resources r JOIN resource_tags t ON r.id = t.resource_id"
        # Use --snapshot to automatically filter by snapshot_id
        awsinv query sql "SELECT * FROM resources" --snapshot my-snapshot
    """
    import csv
    import json
    import re
    import sys

    from ..storage import Database, ResourceStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = ResourceStore(db)

        # Apply snapshot filter if provided
        if snapshot:
            # Look up snapshot ID
            rows = db.fetchall("SELECT id FROM snapshots WHERE name = ?", (snapshot,))
            if not rows:
                console.print(f"[red]Error: Snapshot '{snapshot}' not found[/red]")
                raise typer.Exit(code=1)

            snapshot_id = rows[0]["id"]

            # Inject WHERE clause logic
            # 1. Check for existing WHERE
            match_where = re.search(r"(?i)\bwhere\b", query)
            if match_where:
                # Insert AND after WHERE
                start, end = match_where.span()
                query = query[:end] + f" snapshot_id = {snapshot_id} AND" + query[end:]
            else:
                # 2. Check for clauses that must come AFTER WHERE (GROUP BY, HAVING, ORDER BY, LIMIT)
                match_clause = re.search(r"(?i)\b(group\s+by|having|order\s+by|limit)\b", query)
                if match_clause:
                    start, end = match_clause.span()
                    query = query[:start] + f" WHERE snapshot_id = {snapshot_id} " + query[start:]
                else:
                    # 3. Simple append
                    query = query.rstrip(";") + f" WHERE snapshot_id = {snapshot_id}"

            logger.debug(f"Modified query with snapshot filter: {query}")

        # Add LIMIT if not present
        query_upper = query.strip().upper()
        if "LIMIT" not in query_upper:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        results = store.query_raw(query)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        if format == "json":
            console.print(json.dumps(results, indent=2, default=str))
        elif format == "csv":
            if results:
                writer = csv.DictWriter(sys.stdout, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        else:  # table
            table = Table(show_header=True, header_style="bold cyan")
            for key in results[0].keys():
                table.add_column(key)
            for row in results:
                table.add_row(*[str(v) if v is not None else "" for v in row.values()])
            console.print(table)

        console.print(f"\n[dim]{len(results)} row(s) returned[/dim]")

    except ValueError as e:
        console.print(f"[red]Query error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Query failed")
        raise typer.Exit(code=1)


@query_app.command("resources")
def query_resources(
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type (e.g., 's3:bucket', 'ec2')"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Filter by region"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag (Key=Value)"),
    arn: Optional[str] = typer.Option(None, "--arn", help="Filter by ARN pattern (supports wildcards)"),
    snapshot: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Limit to specific snapshot"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum results to return"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Search resources with filters across all snapshots.

    Examples:
        awsinv query resources --type s3:bucket
        awsinv query resources --region us-east-1 --type ec2
        awsinv query resources --tag Environment=production
        awsinv query resources --arn "arn:aws:s3:::my-bucket*"
        awsinv query resources --snapshot baseline-2024 --type lambda
    """
    import json

    from ..storage import Database, ResourceStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = ResourceStore(db)

        # Parse tag filter
        tag_key = None
        tag_value = None
        if tag:
            if "=" in tag:
                tag_key, tag_value = tag.split("=", 1)
            else:
                tag_key = tag

        results = store.search(
            arn_pattern=arn,
            resource_type=type,
            region=region,
            tag_key=tag_key,
            tag_value=tag_value,
            snapshot_name=snapshot,
            limit=limit,
        )

        if not results:
            console.print("[yellow]No resources found matching filters[/yellow]")
            return

        if format == "json":
            console.print(json.dumps(results, indent=2, default=str))
        else:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("ARN", style="cyan", no_wrap=True)
            table.add_column("Type")
            table.add_column("Name")
            table.add_column("Region")
            table.add_column("Snapshot")

            for r in results:
                # Truncate ARN for display
                arn_display = r["arn"]
                if len(arn_display) > 60:
                    arn_display = "..." + arn_display[-57:]
                table.add_row(
                    arn_display,
                    r["resource_type"],
                    r["name"],
                    r["region"],
                    r["snapshot_name"],
                )
            console.print(table)

        console.print(f"\n[dim]{len(results)} resource(s) found[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Query failed")
        raise typer.Exit(code=1)


@query_app.command("history")
def query_history(
    arn: str = typer.Argument(..., help="Resource ARN to track across snapshots"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Show snapshot history for a specific resource.

    Tracks when a resource appeared in snapshots and whether its configuration changed.

    Example:
        awsinv query history "arn:aws:s3:::my-bucket"
    """
    import json

    from ..storage import Database, ResourceStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = ResourceStore(db)

        results = store.get_history(arn)

        if not results:
            console.print(f"[yellow]No history found for ARN: {arn}[/yellow]")
            return

        if format == "json":
            console.print(json.dumps(results, indent=2, default=str))
        else:
            console.print(f"\n[bold]History for:[/bold] {arn}\n")
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Snapshot")
            table.add_column("Snapshot Date")
            table.add_column("Config Hash")
            table.add_column("Source")

            prev_hash = None
            for r in results:
                config_hash = r["config_hash"][:12] if r["config_hash"] else "N/A"
                # Mark config changes
                if prev_hash and prev_hash != r["config_hash"]:
                    config_hash = f"[yellow]{config_hash}[/yellow] (changed)"
                prev_hash = r["config_hash"]

                table.add_row(
                    r["snapshot_name"],
                    str(r["snapshot_created_at"])[:19],
                    config_hash,
                    r["source"] or "direct_api",
                )
            console.print(table)

        console.print(f"\n[dim]Found in {len(results)} snapshot(s)[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Query failed")
        raise typer.Exit(code=1)


@query_app.command("stats")
def query_stats(
    snapshot: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Specific snapshot (default: all)"),
    group_by: str = typer.Option("type", "--group-by", "-g", help="Group by: type, region, service, snapshot"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Show resource statistics and counts.

    Examples:
        awsinv query stats
        awsinv query stats --group-by region
        awsinv query stats --snapshot baseline-2024 --group-by service
    """
    import json

    from ..storage import Database, ResourceStore, SnapshotStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        resource_store = ResourceStore(db)
        snapshot_store = SnapshotStore(db)

        # Get overall stats
        total_snapshots = snapshot_store.get_snapshot_count()
        total_resources = snapshot_store.get_resource_count()

        console.print("\n[bold]Database Statistics[/bold]")
        console.print(f"Total snapshots: [cyan]{total_snapshots}[/cyan]")
        console.print(f"Total resources: [cyan]{total_resources}[/cyan]")

        if snapshot:
            console.print(f"Filtering by snapshot: [cyan]{snapshot}[/cyan]")
        console.print()

        results = resource_store.get_stats(snapshot_name=snapshot, group_by=group_by)

        if not results:
            console.print("[yellow]No statistics available[/yellow]")
            return

        if format == "json":
            console.print(json.dumps(results, indent=2, default=str))
        else:
            group_label = {
                "type": "Resource Type",
                "region": "Region",
                "service": "Service",
                "snapshot": "Snapshot",
            }.get(group_by, "Group")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column(group_label)
            table.add_column("Count", justify="right")

            for r in results:
                table.add_row(r["group_key"] or "Unknown", str(r["count"]))
            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Query failed")
        raise typer.Exit(code=1)


@query_app.command("diff")
def query_diff(
    snapshot1: str = typer.Argument(..., help="First (older) snapshot name"),
    snapshot2: str = typer.Argument(..., help="Second (newer) snapshot name"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, summary"),
):
    """Compare resources between two snapshots.

    Shows resources that were added, removed, or modified between snapshots.

    Example:
        awsinv query diff baseline-2024 current-2024
        awsinv query diff snap1 snap2 --type s3:bucket
    """
    import json

    from ..storage import Database, ResourceStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = ResourceStore(db)

        result = store.compare_snapshots(snapshot1, snapshot2)

        # Filter by type if specified
        if type:
            result["added"] = [r for r in result["added"] if type.lower() in r["resource_type"].lower()]
            result["removed"] = [r for r in result["removed"] if type.lower() in r["resource_type"].lower()]
            result["modified"] = [r for r in result["modified"] if type.lower() in r["resource_type"].lower()]
            # Update counts
            result["summary"]["added_count"] = len(result["added"])
            result["summary"]["removed_count"] = len(result["removed"])
            result["summary"]["modified_count"] = len(result["modified"])

        summary = result["summary"]

        if format == "json":
            console.print(json.dumps(result, indent=2, default=str))
            return

        # Print summary
        console.print("\n[bold]Comparing Snapshots[/bold]")
        console.print(f"  {snapshot1} ({summary['snapshot1_count']} resources)")
        console.print(f"  {snapshot2} ({summary['snapshot2_count']} resources)")
        console.print()

        if format == "summary":
            console.print(f"[green]+ Added:[/green]    {summary['added_count']}")
            console.print(f"[red]- Removed:[/red]  {summary['removed_count']}")
            console.print(f"[yellow]~ Modified:[/yellow] {summary['modified_count']}")
            return

        # Show details
        if result["added"]:
            console.print(f"\n[green][bold]Added ({len(result['added'])})[/bold][/green]")
            table = Table(show_header=True, header_style="green")
            table.add_column("ARN")
            table.add_column("Type")
            table.add_column("Region")
            for r in result["added"][:20]:
                table.add_row(r["arn"][-60:], r["resource_type"], r["region"])
            console.print(table)
            if len(result["added"]) > 20:
                console.print(f"[dim]...and {len(result['added']) - 20} more[/dim]")

        if result["removed"]:
            console.print(f"\n[red][bold]Removed ({len(result['removed'])})[/bold][/red]")
            table = Table(show_header=True, header_style="red")
            table.add_column("ARN")
            table.add_column("Type")
            table.add_column("Region")
            for r in result["removed"][:20]:
                table.add_row(r["arn"][-60:], r["resource_type"], r["region"])
            console.print(table)
            if len(result["removed"]) > 20:
                console.print(f"[dim]...and {len(result['removed']) - 20} more[/dim]")

        if result["modified"]:
            console.print(f"\n[yellow][bold]Modified ({len(result['modified'])})[/bold][/yellow]")
            table = Table(show_header=True, header_style="yellow")
            table.add_column("ARN")
            table.add_column("Type")
            table.add_column("Old Hash")
            table.add_column("New Hash")
            for r in result["modified"][:20]:
                table.add_row(
                    r["arn"][-50:],
                    r["resource_type"],
                    r["old_hash"][:12],
                    r["new_hash"][:12],
                )
            console.print(table)
            if len(result["modified"]) > 20:
                console.print(f"[dim]...and {len(result['modified']) - 20} more[/dim]")

        if not result["added"] and not result["removed"] and not result["modified"]:
            console.print("[green]No differences found between snapshots[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Query failed")
        raise typer.Exit(code=1)


app.add_typer(query_app, name="query")


# =============================================================================
# Group Commands
# =============================================================================

group_app = typer.Typer(help="Manage resource groups for baseline comparison")


@group_app.command("create")
def group_create(
    name: str = typer.Argument(..., help="Name for the new group"),
    from_snapshot: Optional[str] = typer.Option(
        None, "--from-snapshot", "-s", help="Create group from resources in this snapshot"
    ),
    description: str = typer.Option("", "--description", "-d", help="Group description"),
    type_filter: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by resource type when creating from snapshot"
    ),
    region_filter: Optional[str] = typer.Option(
        None, "--region", "-r", help="Filter by region when creating from snapshot"
    ),
):
    """Create a new resource group.

    Groups define a set of resources (by name + type) that should exist in every account.
    Use --from-snapshot to populate the group from an existing snapshot.

    Examples:
        # Create empty group
        awsinv group create baseline --description "Production baseline resources"

        # Create from snapshot
        awsinv group create baseline --from-snapshot "empty-account-2026-01"

        # Create with filters
        awsinv group create iam-baseline --from-snapshot snap1 --type iam
    """
    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        if store.exists(name):
            console.print(f"[red]Error: Group '{name}' already exists[/red]")
            raise typer.Exit(code=1)

        if from_snapshot:
            # Create from snapshot
            count = store.create_from_snapshot(
                group_name=name,
                snapshot_name=from_snapshot,
                description=description,
                type_filter=type_filter,
                region_filter=region_filter,
            )
            console.print(
                f"[green]✓ Created group '{name}' with {count} resources from snapshot '{from_snapshot}'[/green]"
            )
        else:
            # Create empty group
            from ..models.group import ResourceGroup

            group = ResourceGroup(name=name, description=description)
            store.save(group)
            console.print(f"[green]✓ Created empty group '{name}'[/green]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Group creation failed")
        raise typer.Exit(code=1)


@group_app.command("list")
def group_list(
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """List all resource groups.

    Examples:
        awsinv group list
        awsinv group list --format json
    """
    import json

    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        groups = store.list_all()

        if not groups:
            console.print("[yellow]No groups found. Create one with 'awsinv group create'[/yellow]")
            return

        if format == "json":
            console.print(json.dumps(groups, indent=2, default=str))
        else:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Name", style="cyan")
            table.add_column("Description")
            table.add_column("Resources", justify="right")
            table.add_column("Source Snapshot")
            table.add_column("Favorite", justify="center")

            for g in groups:
                table.add_row(
                    g["name"],
                    g["description"][:40] + "..." if len(g["description"]) > 40 else g["description"],
                    str(g["resource_count"]),
                    g["source_snapshot"] or "-",
                    "★" if g["is_favorite"] else "",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to list groups")
        raise typer.Exit(code=1)


@group_app.command("show")
def group_show(
    name: str = typer.Argument(..., help="Group name"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum members to display"),
):
    """Show details of a resource group including its members.

    Examples:
        awsinv group show baseline
        awsinv group show baseline --limit 100
    """
    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        group = store.load(name)
        if not group:
            console.print(f"[red]Error: Group '{name}' not found[/red]")
            raise typer.Exit(code=1)

        # Show group info
        console.print(
            Panel(
                f"[bold]{group.name}[/bold]\n\n"
                f"[dim]Description:[/dim] {group.description or '(none)'}\n"
                f"[dim]Source Snapshot:[/dim] {group.source_snapshot or '(none)'}\n"
                f"[dim]Resource Count:[/dim] {group.resource_count}\n"
                f"[dim]Created:[/dim] {group.created_at}\n"
                f"[dim]Last Updated:[/dim] {group.last_updated}",
                title="Group Details",
                border_style="blue",
            )
        )

        # Show members
        if group.members:
            console.print(
                f"\n[bold]Members[/bold] (showing first {min(limit, len(group.members))} of {len(group.members)}):"
            )
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Resource Name", style="cyan")
            table.add_column("Type")
            table.add_column("Original ARN", style="dim")

            for member in group.members[:limit]:
                table.add_row(
                    member.resource_name,
                    member.resource_type,
                    (
                        member.original_arn[:60] + "..."
                        if member.original_arn and len(member.original_arn) > 60
                        else (member.original_arn or "-")
                    ),
                )

            console.print(table)
        else:
            console.print("\n[yellow]Group has no members[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to show group")
        raise typer.Exit(code=1)


@group_app.command("delete")
def group_delete(
    name: str = typer.Argument(..., help="Group name to delete"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a resource group.

    Examples:
        awsinv group delete baseline
        awsinv group delete baseline --yes
    """
    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        if not store.exists(name):
            console.print(f"[red]Error: Group '{name}' not found[/red]")
            raise typer.Exit(code=1)

        if not confirm:
            confirm_input = typer.confirm(f"Are you sure you want to delete group '{name}'?")
            if not confirm_input:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(code=0)

        store.delete(name)
        console.print(f"[green]✓ Deleted group '{name}'[/green]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to delete group")
        raise typer.Exit(code=1)


@group_app.command("compare")
def group_compare(
    name: str = typer.Argument(..., help="Group name"),
    snapshot: str = typer.Option(..., "--snapshot", "-s", help="Snapshot to compare against"),
    format: str = typer.Option("summary", "--format", "-f", help="Output format: summary, table, json"),
    show_details: bool = typer.Option(False, "--details", "-d", help="Show individual resource details"),
):
    """Compare a snapshot against a resource group.

    Shows which resources from the group are present in the snapshot,
    which are missing, and which resources in the snapshot are not in the group.

    Examples:
        awsinv group compare baseline --snapshot prod-account-2026-01
        awsinv group compare baseline -s prod-account --format json
        awsinv group compare baseline -s prod-account --details
    """
    import json

    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        result = store.compare_snapshot(name, snapshot)

        if format == "json":
            console.print(json.dumps(result, indent=2, default=str))
            return

        # Summary output
        console.print(
            Panel(
                f"[bold]Comparing snapshot '{snapshot}' against group '{name}'[/bold]\n\n"
                f"[dim]Total in group:[/dim] {result['total_in_group']}\n"
                f"[dim]Total in snapshot:[/dim] {result['total_in_snapshot']}\n\n"
                f"[green]✓ Matched:[/green] {result['matched']}\n"
                f"[red]✗ Missing from snapshot:[/red] {result['missing_from_snapshot']}\n"
                f"[yellow]+ Not in group:[/yellow] {result['not_in_group']}",
                title="Comparison Results",
                border_style="blue",
            )
        )

        if show_details or format == "table":
            # Show missing resources
            if result["resources"]["missing"]:
                console.print("\n[red bold]Missing from snapshot:[/red bold]")
                table = Table(show_header=True, header_style="bold red")
                table.add_column("Resource Name")
                table.add_column("Type")
                for r in result["resources"]["missing"][:25]:
                    table.add_row(r["name"], r["resource_type"])
                console.print(table)
                if len(result["resources"]["missing"]) > 25:
                    console.print(f"[dim]... and {len(result['resources']['missing']) - 25} more[/dim]")

            # Show extra resources
            if result["resources"]["extra"]:
                console.print("\n[yellow bold]Not in group (extra):[/yellow bold]")
                table = Table(show_header=True, header_style="bold yellow")
                table.add_column("Resource Name")
                table.add_column("Type")
                table.add_column("ARN", style="dim")
                for r in result["resources"]["extra"][:25]:
                    table.add_row(
                        r["name"],
                        r["resource_type"],
                        r["arn"][:50] + "..." if len(r["arn"]) > 50 else r["arn"],
                    )
                console.print(table)
                if len(result["resources"]["extra"]) > 25:
                    console.print(f"[dim]... and {len(result['resources']['extra']) - 25} more[/dim]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Comparison failed")
        raise typer.Exit(code=1)


@group_app.command("add")
def group_add(
    name: str = typer.Argument(..., help="Group name"),
    resource: str = typer.Option(
        ..., "--resource", "-r", help="Resource to add as 'name:type' (e.g., 'my-bucket:s3:bucket')"
    ),
):
    """Add a resource to a group manually.

    Resources are specified as 'name:type' where type is the AWS resource type.

    Examples:
        awsinv group add baseline --resource "my-bucket:s3:bucket"
        awsinv group add iam-baseline --resource "AdminRole:iam:role"
    """
    from ..models.group import GroupMember
    from ..storage import Database, GroupStore

    setup_logging()

    try:
        # Parse resource string
        parts = resource.split(":", 1)
        if len(parts) != 2:
            console.print("[red]Error: Resource must be specified as 'name:type' (e.g., 'my-bucket:s3:bucket')[/red]")
            raise typer.Exit(code=1)

        resource_name, resource_type = parts

        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        if not store.exists(name):
            console.print(f"[red]Error: Group '{name}' not found[/red]")
            raise typer.Exit(code=1)

        member = GroupMember(resource_name=resource_name, resource_type=resource_type)
        added = store.add_members(name, [member])

        if added > 0:
            console.print(f"[green]✓ Added '{resource_name}' ({resource_type}) to group '{name}'[/green]")
        else:
            console.print("[yellow]Resource already exists in group[/yellow]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to add resource to group")
        raise typer.Exit(code=1)


@group_app.command("remove")
def group_remove(
    name: str = typer.Argument(..., help="Group name"),
    resource: str = typer.Option(..., "--resource", "-r", help="Resource to remove as 'name:type'"),
):
    """Remove a resource from a group.

    Examples:
        awsinv group remove baseline --resource "my-bucket:s3:bucket"
    """
    from ..storage import Database, GroupStore

    setup_logging()

    try:
        # Parse resource string
        parts = resource.split(":", 1)
        if len(parts) != 2:
            console.print("[red]Error: Resource must be specified as 'name:type'[/red]")
            raise typer.Exit(code=1)

        resource_name, resource_type = parts

        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        if not store.exists(name):
            console.print(f"[red]Error: Group '{name}' not found[/red]")
            raise typer.Exit(code=1)

        removed = store.remove_member(name, resource_name, resource_type)

        if removed:
            console.print(f"[green]✓ Removed '{resource_name}' ({resource_type}) from group '{name}'[/green]")
        else:
            console.print("[yellow]Resource not found in group[/yellow]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to remove resource from group")
        raise typer.Exit(code=1)


@group_app.command("export")
def group_export(
    name: str = typer.Argument(..., help="Group name"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format: yaml, csv, json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (stdout if not specified)"),
):
    """Export a group definition.

    Examples:
        awsinv group export baseline --format yaml
        awsinv group export baseline --format csv --output baseline.csv
    """
    import csv
    import json

    import yaml

    from ..storage import Database, GroupStore

    setup_logging()

    try:
        db = Database()
        db.ensure_schema()
        store = GroupStore(db)

        group = store.load(name)
        if not group:
            console.print(f"[red]Error: Group '{name}' not found[/red]")
            raise typer.Exit(code=1)

        # Prepare output
        if format == "json":
            content = json.dumps(group.to_dict(), indent=2, default=str)
        elif format == "csv":
            import io

            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["resource_name", "resource_type", "original_arn"])
            for member in group.members:
                writer.writerow([member.resource_name, member.resource_type, member.original_arn or ""])
            content = buffer.getvalue()
        else:  # yaml
            content = yaml.dump(group.to_dict(), default_flow_style=False, sort_keys=False)

        if output:
            with open(output, "w") as f:
                f.write(content)
            console.print(f"[green]✓ Exported group '{name}' to {output}[/green]")
        else:
            console.print(content)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Export failed")
        raise typer.Exit(code=1)


app.add_typer(group_app, name="group")


# =============================================================================
# Serve Command (Web UI)
# =============================================================================


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on startup"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
):
    """Launch web-based inventory browser.

    Starts a local web server with a beautiful UI for browsing snapshots,
    exploring resources, running queries, and managing cleanup operations.
    """
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Web dependencies not installed.[/red]\n"
            "Install with: [cyan]pip install aws-inventory-manager[web][/cyan]"
        )
        raise typer.Exit(code=1)

    from ..web.app import create_app

    # Load config for storage path
    global config
    if config is None:
        config = Config.load()

    console.print(
        Panel.fit(
            f"[cyan bold]AWS Inventory Browser[/cyan bold]\n\n"
            f"[green]Server:[/green] http://{host}:{port}\n"
            f"[dim]Press Ctrl+C to stop[/dim]",
            title="Starting Web Server",
            border_style="blue",
        )
    )

    if open_browser:
        import threading
        import time
        import webbrowser

        def open_delayed():
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=open_delayed, daemon=True).start()

    # Create app with storage path from config
    app_instance = create_app(config.storage_path)

    uvicorn.run(
        app_instance,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# =============================================================================
# Normalize Command (AI Normalization)
# =============================================================================


@app.command()
def normalize(
    snapshot: str = typer.Option(..., "--snapshot", "-s", help="Snapshot name to normalize"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview normalizations without saving"),
    use_ai: bool = typer.Option(True, "--ai/--no-ai", help="Use AI for ambiguous names (default: enabled)"),
):
    """Re-run AI normalization on an existing snapshot.

    This command updates the normalized_name column for all resources
    in the specified snapshot using AI-based name normalization.

    Use this to:
    - Backfill normalized names for snapshots created before AI normalization
    - Re-normalize with updated AI models or prompts
    - Preview normalizations with --dry-run before committing

    Example:
        awsinv normalize --snapshot my-snapshot-20260113
        awsinv normalize --snapshot my-snapshot --dry-run
        awsinv normalize --snapshot my-snapshot --no-ai
    """
    global config
    if config is None:
        config = Config.load()

    from ..storage import Database, SnapshotStore

    try:
        from ..matching import NormalizerConfig, ResourceNormalizer
    except ImportError:
        console.print(
            "[red]AI dependencies not installed.[/red]\n"
            "Install with: [cyan]pip install aws-inventory-manager[ai][/cyan]"
        )
        raise typer.Exit(code=1)

    # Initialize database
    db = Database(config.storage_path)
    snapshot_store = SnapshotStore(db)

    # Check snapshot exists
    if not snapshot_store.exists(snapshot):
        console.print(f"[red]✗ Snapshot '{snapshot}' not found[/red]")
        raise typer.Exit(code=1)

    # Load the snapshot
    console.print(f"[cyan]Loading snapshot '[bold]{snapshot}[/bold]'...[/cyan]")
    snapshot_obj = snapshot_store.load(snapshot)

    if not snapshot_obj or not snapshot_obj.resources:
        console.print(f"[yellow]⚠ Snapshot '{snapshot}' has no resources to normalize[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"  Found [bold]{len(snapshot_obj.resources)}[/bold] resources")

    # Initialize normalizer
    normalizer_config = NormalizerConfig.from_env()

    if use_ai and not normalizer_config.is_ai_enabled:
        console.print("[yellow]⚠ OPENAI_API_KEY not set - using rules-based normalization only[/yellow]")
        use_ai = False

    normalizer = ResourceNormalizer(normalizer_config)

    # Prepare resources for normalization
    resource_dicts = [
        {
            "arn": r.arn,
            "name": r.name,
            "resource_type": r.resource_type,
            "tags": r.tags,
        }
        for r in snapshot_obj.resources
    ]

    # Run normalization
    if use_ai:
        console.print("[cyan]Running AI-assisted normalization...[/cyan]")
    else:
        console.print("[cyan]Running rules-based normalization...[/cyan]")

    with console.status("[bold green]Normalizing resources..."):
        normalized_names = normalizer.normalize_resources(resource_dicts, use_ai=use_ai)

    console.print(f"  Normalized [bold]{len(normalized_names)}[/bold] resource names")

    if normalizer.tokens_used > 0:
        console.print(f"  AI tokens used: [dim]{normalizer.tokens_used}[/dim]")

    # Show preview in dry-run mode
    if dry_run:
        console.print("\n[yellow]DRY RUN - No changes saved[/yellow]\n")

        # Build a table of changes
        table = Table(title="Normalization Preview (first 20)")
        table.add_column("Resource Type", style="cyan")
        table.add_column("Original Name", style="white")
        table.add_column("Normalized Name", style="green")

        count = 0
        for r in snapshot_obj.resources:
            if count >= 20:
                break
            norm_name = normalized_names.get(r.arn, r.name)
            # Only show if different or meaningful
            table.add_row(
                r.resource_type.split("::")[-1] if r.resource_type else "Unknown",
                r.name or "(no name)",
                norm_name,
            )
            count += 1

        console.print(table)

        if len(snapshot_obj.resources) > 20:
            console.print(f"\n[dim]... and {len(snapshot_obj.resources) - 20} more resources[/dim]")

        console.print("\n[yellow]Run without --dry-run to save changes[/yellow]")
        raise typer.Exit(code=0)

    # Update database with normalized names
    console.print("[cyan]Updating database...[/cyan]")

    snapshot_id = snapshot_store.get_id(snapshot)
    if snapshot_id is None:
        console.print("[red]✗ Failed to get snapshot ID[/red]")
        raise typer.Exit(code=1)

    updated_count = 0
    with db.transaction() as cursor:
        for r in snapshot_obj.resources:
            norm_name = normalized_names.get(r.arn)
            if norm_name:
                cursor.execute(
                    """
                    UPDATE resources
                    SET normalized_name = ?
                    WHERE snapshot_id = ? AND arn = ?
                    """,
                    (norm_name, snapshot_id, r.arn),
                )
                updated_count += cursor.rowcount

    console.print(f"[green]✓ Updated {updated_count} resources with normalized names[/green]")


# =============================================================================
# Lambda Code Commands
# =============================================================================

lambda_app = typer.Typer(help="Extract, view, and diff Lambda function code from snapshots")
app.add_typer(lambda_app, name="lambda")


def _get_lambda_code_bytes(code_info: Dict[str, Any]) -> Optional[bytes]:
    """Get Lambda code bytes from either inline or external storage.

    Args:
        code_info: The _code dict from a Lambda resource's raw_config

    Returns:
        Raw bytes of the deployment package, or None if not available
    """
    if not code_info.get("code_stored"):
        return None

    storage_type = code_info.get("storage_type", "inline")

    if storage_type == "external":
        # Load from external file
        file_path = code_info.get("code_file_path")
        if not file_path:
            return None
        try:
            from pathlib import Path

            path = Path(file_path)
            if path.exists():
                with open(path, "rb") as f:
                    return f.read()
            else:
                return None
        except Exception:
            return None
    else:
        # Inline base64 encoded
        code_b64 = code_info.get("code_base64")
        if code_b64:
            return base64.b64decode(code_b64)
        return None


def _get_lambda_code_size(code_info: Dict[str, Any]) -> int:
    """Get Lambda code size in bytes.

    Args:
        code_info: The _code dict from a Lambda resource's raw_config

    Returns:
        Size in bytes, or 0 if not available
    """
    # First check if we have explicit size info
    if "code_size_bytes" in code_info:
        return code_info["code_size_bytes"]

    storage_type = code_info.get("storage_type", "inline")

    if storage_type == "external":
        file_path = code_info.get("code_file_path")
        if file_path:
            try:
                from pathlib import Path

                path = Path(file_path)
                if path.exists():
                    return path.stat().st_size
            except Exception:
                pass
        return 0
    else:
        code_b64 = code_info.get("code_base64", "")
        if code_b64:
            return len(base64.b64decode(code_b64))
        return 0


@lambda_app.command("list")
def lambda_list(
    snapshot_name: Optional[str] = typer.Argument(None, help="Snapshot name (defaults to active)"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all lambdas including those without code"),
):
    """List Lambda functions with code information.

    Shows which functions have code stored, their size, and hash.

    Example:
        awsinv lambda list my-snapshot
        awsinv lambda list --all
    """

    storage = SnapshotStorage()

    if snapshot_name:
        snapshot = storage.load_snapshot(snapshot_name)
    else:
        active_name = storage.get_active_snapshot_name()
        if not active_name:
            console.print("[red]No active snapshot. Specify a snapshot name.[/red]")
            raise typer.Exit(code=1)
        snapshot = storage.load_snapshot(active_name)
        snapshot_name = active_name

    console.print(f"\n[bold]🔍 Lambda Functions in snapshot: {snapshot_name}[/bold]\n")

    # Find all Lambda functions
    lambdas = [r for r in snapshot.resources if r.resource_type == "AWS::Lambda::Function"]

    if not lambdas:
        console.print("[yellow]No Lambda functions found in this snapshot.[/yellow]")
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Function Name", style="white")
    table.add_column("Runtime", style="dim")
    table.add_column("Code Stored", style="green")
    table.add_column("Size", justify="right")
    table.add_column("SHA256", style="dim")
    table.add_column("Source", style="yellow")

    stored_count = 0
    for fn in sorted(lambdas, key=lambda x: x.name or ""):
        code_info = fn.raw_config.get("_code", {}) if fn.raw_config else {}
        runtime = fn.raw_config.get("Runtime", "N/A") if fn.raw_config else "N/A"

        has_code = code_info.get("code_stored", False)
        storage_type = code_info.get("storage_type", "inline")

        if has_code:
            stored_count += 1
            size_bytes = _get_lambda_code_size(code_info)
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            elif size_bytes >= 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} B"
            sha = code_info.get("code_sha256", "")[:12] + "..." if code_info.get("code_sha256") else ""
            # Determine source display
            if code_info.get("s3_bucket"):
                source = "S3"
            elif storage_type == "external":
                source = "File"
            else:
                source = "Inline"
            table.add_row(fn.name or "unnamed", runtime, "✓", size_str, sha, source)
        elif show_all:
            sha = code_info.get("code_sha256", "")[:12] + "..." if code_info.get("code_sha256") else "—"
            table.add_row(fn.name or "unnamed", runtime, "[dim]✗ (>10MB)[/dim]", "—", sha, "—")

    console.print(table)
    console.print(f"\n[dim]{stored_count}/{len(lambdas)} functions have code stored[/dim]")


@lambda_app.command("extract")
def lambda_extract(
    function_name: str = typer.Argument(..., help="Lambda function name (or 'all' for all functions)"),
    snapshot_name: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Snapshot name (defaults to active)"),
    output_dir: str = typer.Option("./lambda_code", "--output", "-o", help="Output directory"),
    flatten: bool = typer.Option(False, "--flatten", "-f", help="Extract all to single directory (no subdirs)"),
):
    """Extract Lambda function code to disk.

    Extracts the deployment package (zip) and unpacks it.

    Examples:
        awsinv lambda extract my-function
        awsinv lambda extract all --output ./code
        awsinv lambda extract my-function -s my-snapshot -o ./extracted
    """
    import os
    import zipfile
    from io import BytesIO

    storage = SnapshotStorage()

    if snapshot_name:
        snapshot = storage.load_snapshot(snapshot_name)
    else:
        active_name = storage.get_active_snapshot_name()
        if not active_name:
            console.print("[red]No active snapshot. Use --snapshot to specify.[/red]")
            raise typer.Exit(code=1)
        snapshot = storage.load_snapshot(active_name)
        snapshot_name = active_name

    # Find Lambda functions
    lambdas = [r for r in snapshot.resources if r.resource_type == "AWS::Lambda::Function"]

    if function_name.lower() == "all":
        targets = [fn for fn in lambdas if fn.raw_config and fn.raw_config.get("_code", {}).get("code_stored")]
    else:
        targets = [fn for fn in lambdas if fn.name == function_name]
        if not targets:
            console.print(f"[red]Lambda function '{function_name}' not found in snapshot.[/red]")
            available = [fn.name for fn in lambdas[:10]]
            if available:
                console.print(f"[dim]Available: {', '.join(available)}{'...' if len(lambdas) > 10 else ''}[/dim]")
            raise typer.Exit(code=1)

    if not targets:
        console.print("[yellow]No Lambda functions with stored code found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]📦 Extracting {len(targets)} Lambda function(s)[/bold]\n")

    os.makedirs(output_dir, exist_ok=True)
    extracted_count = 0

    for fn in targets:
        code_info = fn.raw_config.get("_code", {}) if fn.raw_config else {}
        zip_bytes = _get_lambda_code_bytes(code_info)

        if not zip_bytes:
            console.print(f"[yellow]⚠ {fn.name}: No code stored[/yellow]")
            continue

        try:
            if flatten:
                extract_path = output_dir
            else:
                extract_path = os.path.join(output_dir, fn.name or "unnamed")
                os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                zf.extractall(extract_path)
                file_count = len(zf.namelist())

            console.print(f"[green]✓[/green] {fn.name}: {file_count} files → {extract_path}")
            extracted_count += 1

        except Exception as e:
            console.print(f"[red]✗ {fn.name}: {e}[/red]")

    console.print(f"\n[bold green]Extracted {extracted_count} function(s) to {output_dir}[/bold green]")


@lambda_app.command("show")
def lambda_show(
    function_name: str = typer.Argument(..., help="Lambda function name"),
    snapshot_name: Optional[str] = typer.Option(None, "--snapshot", "-s", help="Snapshot name (defaults to active)"),
    file_path: Optional[str] = typer.Option(None, "--file", "-f", help="Show specific file from package"),
    list_files: bool = typer.Option(False, "--list", "-l", help="List files in package"),
):
    """Show Lambda function code with syntax highlighting.

    View code directly in terminal without extracting to disk.

    Examples:
        awsinv lambda show my-function --list
        awsinv lambda show my-function --file index.js
        awsinv lambda show my-function --file handler.py
    """
    import zipfile
    from io import BytesIO

    from rich.syntax import Syntax

    storage = SnapshotStorage()

    if snapshot_name:
        snapshot = storage.load_snapshot(snapshot_name)
    else:
        active_name = storage.get_active_snapshot_name()
        if not active_name:
            console.print("[red]No active snapshot. Use --snapshot to specify.[/red]")
            raise typer.Exit(code=1)
        snapshot = storage.load_snapshot(active_name)

    # Find the function
    fn = next(
        (r for r in snapshot.resources if r.resource_type == "AWS::Lambda::Function" and r.name == function_name), None
    )

    if not fn:
        console.print(f"[red]Lambda function '{function_name}' not found.[/red]")
        raise typer.Exit(code=1)

    code_info = fn.raw_config.get("_code", {}) if fn.raw_config else {}
    zip_bytes = _get_lambda_code_bytes(code_info)

    if not zip_bytes:
        console.print(f"[yellow]No code stored for '{function_name}'[/yellow]")
        if code_info.get("code_sha256"):
            console.print(f"[dim]SHA256: {code_info['code_sha256']}[/dim]")
        raise typer.Exit(1)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        files = zf.namelist()

        if list_files:
            console.print(f"\n[bold]📁 Files in {function_name} ({len(files)} files)[/bold]\n")
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("File", style="white")
            table.add_column("Size", justify="right")

            for f in sorted(files):
                if not f.endswith("/"):
                    info = zf.getinfo(f)
                    size = info.file_size
                    if size >= 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size} B"
                    table.add_row(f, size_str)

            console.print(table)
            return

        # Determine which file to show
        if file_path:
            target_file = file_path
        else:
            # Auto-detect main handler file
            handler = fn.raw_config.get("Handler", "") if fn.raw_config else ""
            if "." in handler:
                module = handler.split(".")[0]
                # Try common extensions
                for ext in [".py", ".js", ".ts", ".mjs", ".rb", ".java", ".go"]:
                    candidate = f"{module}{ext}"
                    if candidate in files:
                        target_file = candidate
                        break
                else:
                    target_file = files[0] if files else None
            else:
                target_file = files[0] if files else None

        if not target_file or target_file not in files:
            console.print(f"[red]File '{target_file}' not found in package.[/red]")
            console.print(f"[dim]Available: {', '.join(files[:10])}{'...' if len(files) > 10 else ''}[/dim]")
            raise typer.Exit(1)

        # Read and display the file
        content = zf.read(target_file).decode("utf-8", errors="replace")

        # Detect language from extension
        ext = target_file.rsplit(".", 1)[-1] if "." in target_file else ""
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "mjs": "javascript",
            "rb": "ruby",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "xml": "xml",
            "html": "html",
            "css": "css",
            "sh": "bash",
            "bash": "bash",
            "md": "markdown",
        }
        lang = lang_map.get(ext, "text")

        console.print(f"\n[bold]📄 {function_name}/{target_file}[/bold]\n")
        syntax = Syntax(content, lang, theme="monokai", line_numbers=True)
        console.print(syntax)


@lambda_app.command("diff")
def lambda_diff(
    function_name: str = typer.Argument(..., help="Lambda function name"),
    snapshot1: str = typer.Argument(..., help="First snapshot (older)"),
    snapshot2: str = typer.Argument(..., help="Second snapshot (newer)"),
    file_path: Optional[str] = typer.Option(None, "--file", "-f", help="Diff specific file"),
):
    """Compare Lambda function code between two snapshots.

    Shows what changed in the code between snapshots.

    Examples:
        awsinv lambda diff my-function snapshot-v1 snapshot-v2
        awsinv lambda diff my-function old new --file handler.py
    """
    import difflib
    import zipfile
    from io import BytesIO

    from rich.syntax import Syntax

    storage = SnapshotStorage()

    snap1 = storage.load_snapshot(snapshot1)
    snap2 = storage.load_snapshot(snapshot2)

    if not snap1:
        console.print(f"[red]Snapshot '{snapshot1}' not found.[/red]")
        raise typer.Exit(code=1)
    if not snap2:
        console.print(f"[red]Snapshot '{snapshot2}' not found.[/red]")
        raise typer.Exit(code=1)

    # Find the function in both snapshots
    fn1 = next(
        (r for r in snap1.resources if r.resource_type == "AWS::Lambda::Function" and r.name == function_name), None
    )
    fn2 = next(
        (r for r in snap2.resources if r.resource_type == "AWS::Lambda::Function" and r.name == function_name), None
    )

    if not fn1:
        console.print(f"[red]Function '{function_name}' not found in {snapshot1}[/red]")
        raise typer.Exit(code=1)
    if not fn2:
        console.print(f"[red]Function '{function_name}' not found in {snapshot2}[/red]")
        raise typer.Exit(code=1)

    code1 = fn1.raw_config.get("_code", {}) if fn1.raw_config else {}
    code2 = fn2.raw_config.get("_code", {}) if fn2.raw_config else {}

    # Quick hash comparison
    hash1 = code1.get("code_sha256", "")
    hash2 = code2.get("code_sha256", "")

    if hash1 == hash2:
        console.print(f"\n[green]✓ No changes in {function_name} between snapshots[/green]")
        console.print(f"[dim]SHA256: {hash1[:16]}...[/dim]")
        return

    console.print(f"\n[bold yellow]⚡ Code changed in {function_name}[/bold yellow]")
    console.print(f"[dim]{snapshot1}: {hash1[:16]}...[/dim]")
    console.print(f"[dim]{snapshot2}: {hash2[:16]}...[/dim]\n")

    bytes1 = _get_lambda_code_bytes(code1)
    bytes2 = _get_lambda_code_bytes(code2)

    if not bytes1 or not bytes2:
        console.print("[yellow]Cannot show diff - one or both snapshots missing code[/yellow]")
        raise typer.Exit(0)

    zip1 = zipfile.ZipFile(BytesIO(bytes1))
    zip2 = zipfile.ZipFile(BytesIO(bytes2))

    files1 = set(zip1.namelist())
    files2 = set(zip2.namelist())

    added = files2 - files1
    removed = files1 - files2
    common = files1 & files2

    if added:
        console.print(f"[green]+ Added files: {', '.join(sorted(added))}[/green]")
    if removed:
        console.print(f"[red]- Removed files: {', '.join(sorted(removed))}[/red]")

    # Determine which file to diff
    if file_path:
        diff_files = [file_path] if file_path in common else []
        if not diff_files:
            if file_path in added:
                console.print(f"\n[green]New file in {snapshot2}:[/green]")
                content = zip2.read(file_path).decode("utf-8", errors="replace")
                ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "text"
                syntax = Syntax(content, ext, theme="monokai", line_numbers=True)
                console.print(syntax)
                return
            elif file_path in removed:
                console.print(f"\n[red]File removed in {snapshot2} (was in {snapshot1}):[/red]")
                content = zip1.read(file_path).decode("utf-8", errors="replace")
                ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "text"
                syntax = Syntax(content, ext, theme="monokai", line_numbers=True)
                console.print(syntax)
                return
            console.print(f"[red]File '{file_path}' not found in either snapshot[/red]")
            raise typer.Exit(1)
    else:
        # Auto-detect handler file
        handler = fn2.raw_config.get("Handler", "") if fn2.raw_config else ""
        if "." in handler:
            module = handler.split(".")[0]
            for ext in [".py", ".js", ".ts", ".mjs"]:
                candidate = f"{module}{ext}"
                if candidate in common:
                    diff_files = [candidate]
                    break
            else:
                diff_files = list(common)[:3]  # Show first 3 changed files
        else:
            diff_files = list(common)[:3]

    # Show diffs for changed files
    for diff_file in diff_files:
        if diff_file.endswith("/"):
            continue

        try:
            content1 = zip1.read(diff_file).decode("utf-8", errors="replace")
            content2 = zip2.read(diff_file).decode("utf-8", errors="replace")

            if content1 == content2:
                continue

            console.print(f"\n[bold]📝 {diff_file}[/bold]")

            diff = difflib.unified_diff(
                content1.splitlines(keepends=True),
                content2.splitlines(keepends=True),
                fromfile=f"{snapshot1}/{diff_file}",
                tofile=f"{snapshot2}/{diff_file}",
            )

            diff_text = "".join(diff)
            if diff_text:
                syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
                console.print(syntax)

        except Exception as e:
            console.print(f"[red]Error diffing {diff_file}: {e}[/red]")

    zip1.close()
    zip2.close()


@lambda_app.command("fetch")
def lambda_fetch(
    snapshot_name: str = typer.Argument(..., help="Snapshot name to fetch code for"),
    function_name: Optional[str] = typer.Option(
        None, "--function", "-f", help="Specific function name (default: all without code)"
    ),
    max_size: int = typer.Option(
        50, "--max-size", "-m", help="Max code size (MB) to store inline. Larger stored to files. -1 for unlimited."
    ),
    force: bool = typer.Option(False, "--force", help="Re-fetch code even if already stored"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    no_ssl_verify: bool = typer.Option(
        False, "--no-ssl-verify", help="Disable SSL certificate verification for S3 downloads"
    ),
):
    """Fetch Lambda code from AWS for an existing snapshot.

    Downloads deployment packages for Lambda functions that don't have code stored,
    or re-fetches all code with --force.

    Handles versioned functions - will fetch code for the specific version/alias
    if specified in the function ARN.

    Examples:
        awsinv lambda fetch my-snapshot
        awsinv lambda fetch my-snapshot --function my-func
        awsinv lambda fetch my-snapshot --max-size 100
        awsinv lambda fetch my-snapshot --force
        awsinv lambda fetch my-snapshot --no-ssl-verify
    """
    import hashlib

    import boto3
    import requests
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

    from ..snapshot.lambda_code_storage import LambdaCodeStorage
    from ..storage.database import Database
    from ..storage.snapshot_store import SnapshotStore
    from ..utils.hash import compute_config_hash

    # Suppress SSL warnings if verification is disabled
    if no_ssl_verify:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        console.print("[yellow]⚠ SSL certificate verification disabled[/yellow]")

    storage = SnapshotStorage()

    try:
        snapshot = storage.load_snapshot(snapshot_name)
    except FileNotFoundError:
        console.print(f"[red]Snapshot '{snapshot_name}' not found.[/red]")
        raise typer.Exit(code=1)

    # Find Lambda functions
    lambdas = [r for r in snapshot.resources if r.resource_type == "AWS::Lambda::Function"]

    if not lambdas:
        console.print("[yellow]No Lambda functions in this snapshot.[/yellow]")
        raise typer.Exit(0)

    # Filter to specific function if requested
    if function_name:
        lambdas = [fn for fn in lambdas if fn.name == function_name]
        if not lambdas:
            console.print(f"[red]Lambda function '{function_name}' not found in snapshot.[/red]")
            raise typer.Exit(code=1)

    # Filter to functions without code (unless --force)
    if not force:
        lambdas = [fn for fn in lambdas if not (fn.raw_config or {}).get("_code", {}).get("code_stored", False)]

    if not lambdas:
        console.print("[green]All Lambda functions already have code stored.[/green]")
        console.print("[dim]Use --force to re-fetch code.[/dim]")
        raise typer.Exit(0)

    console.print(f"\n[bold]📥 Fetching code for {len(lambdas)} Lambda function(s)[/bold]")
    if max_size == -1:
        console.print("[dim]Storage: unlimited inline[/dim]")
    else:
        console.print(f"[dim]Storage: inline up to {max_size}MB, larger to files[/dim]")

    # Convert max_size to bytes
    max_size_bytes = -1 if max_size == -1 else max_size * 1024 * 1024

    # Initialize code storage for external files
    code_storage = LambdaCodeStorage()

    # Create boto3 session
    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)

    # Get database for updates
    db = Database()
    snapshot_store = SnapshotStore(db)

    # Process each function
    success_count = 0
    skip_count = 0
    error_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching...", total=len(lambdas))

        for fn in lambdas:
            progress.update(task, description=f"📦 {fn.name}")

            try:
                # Extract region and function details from ARN
                # ARN format: arn:aws:lambda:region:account:function:name[:qualifier]
                arn_parts = fn.arn.split(":")
                region = arn_parts[3] if len(arn_parts) > 3 else fn.region

                # Get function name and qualifier from ARN
                func_name = fn.name
                qualifier = None
                if len(arn_parts) > 7:
                    qualifier = arn_parts[7]  # Version or alias

                # Create Lambda client for the function's region
                lambda_client = session.client("lambda", region_name=region)

                # Get function info including code location
                get_func_kwargs = {"FunctionName": func_name}
                if qualifier:
                    get_func_kwargs["Qualifier"] = qualifier

                try:
                    func_response = lambda_client.get_function(**get_func_kwargs)
                except Exception as e:
                    console.print(f"[yellow]⚠ {fn.name}: Function not found in AWS ({e})[/yellow]")
                    skip_count += 1
                    progress.advance(task)
                    continue

                code_location = func_response.get("Code", {}).get("Location")
                if not code_location:
                    console.print(f"[yellow]⚠ {fn.name}: No code location available[/yellow]")
                    skip_count += 1
                    progress.advance(task)
                    continue

                # Download the code
                response = requests.get(code_location, timeout=120, verify=not no_ssl_verify)
                response.raise_for_status()

                code_bytes = response.content
                code_size = len(code_bytes)
                code_hash = hashlib.sha256(code_bytes).hexdigest()

                # Get existing raw_config or create new one
                raw_config = dict(fn.raw_config) if fn.raw_config else {}

                # Build code data
                code_data = raw_config.get("_code", {})
                code_data["code_size_bytes"] = code_size
                code_data["code_sha256"] = code_hash

                # Preserve existing S3 info if present
                code_info = func_response.get("Code", {})
                if "S3Bucket" in code_info:
                    code_data["s3_bucket"] = code_info["S3Bucket"]
                if "S3Key" in code_info:
                    code_data["s3_key"] = code_info["S3Key"]

                # Store based on size
                if max_size_bytes == -1 or code_size <= max_size_bytes:
                    # Store inline
                    code_data["code_base64"] = base64.b64encode(code_bytes).decode("utf-8")
                    code_data["code_stored"] = True
                    code_data["storage_type"] = "inline"
                    if "code_file_path" in code_data:
                        del code_data["code_file_path"]
                    storage_type = "inline"
                else:
                    # Store externally
                    file_path, _ = code_storage.store_code(snapshot_name, fn.name, code_bytes)
                    code_data["code_stored"] = True
                    code_data["storage_type"] = "external"
                    code_data["code_file_path"] = file_path
                    if "code_base64" in code_data:
                        del code_data["code_base64"]
                    storage_type = "file"

                # Remove the too_large flag if it was set
                if "code_too_large" in code_data:
                    del code_data["code_too_large"]

                raw_config["_code"] = code_data

                # Update in database
                new_hash = compute_config_hash(raw_config)
                snapshot_store.update_resource_config(snapshot_name, fn.arn, raw_config, new_hash)

                size_str = (
                    f"{code_size / (1024 * 1024):.1f}MB" if code_size >= 1024 * 1024 else f"{code_size / 1024:.1f}KB"
                )
                console.print(f"[green]✓[/green] {fn.name}: {size_str} ({storage_type})")
                success_count += 1

            except requests.RequestException as e:
                console.print(f"[red]✗ {fn.name}: Download failed - {e}[/red]")
                error_count += 1
            except Exception as e:
                console.print(f"[red]✗ {fn.name}: {e}[/red]")
                error_count += 1

            progress.advance(task)

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    if success_count:
        console.print(f"  [green]✓ {success_count} fetched[/green]")
    if skip_count:
        console.print(f"  [yellow]⚠ {skip_count} skipped[/yellow]")
    if error_count:
        console.print(f"  [red]✗ {error_count} failed[/red]")


# =============================================================================
# Copilot Commands
# =============================================================================

copilot_app = typer.Typer(help="GitHub Copilot instructions and prompt management")
app.add_typer(copilot_app, name="copilot")


@copilot_app.command("install")
def copilot_install(
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target project directory (defaults to current directory)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """Install GitHub Copilot instructions and prompts.

    Installs the following files to .github/:
    - copilot-instructions.md: Base instructions with AWS schema context
    - prompts/generate-terraform.prompt.md: Single-pass Terraform generation
    - prompts/generate-cdk-typescript.prompt.md: CDK TypeScript prompt
    - prompts/generate-cdk-python.prompt.md: CDK Python prompt
    - prompts/plan-iac.prompt.md: Analyze inventory and create IaC checklist
    - prompts/generate-terraform-layer.prompt.md: Layer-by-layer Terraform generation
    - instructions/terraform.instructions.md: Terraform best practices (applyTo: *.tf)

    For large inventories (3000+ lines), use plan-iac first, then generate-terraform-layer.

    Existing files are backed up with .bak.{timestamp} suffix.
    Custom org instructions in copilot-custom.md are never touched.

    Example:
        awsinv copilot install
        awsinv copilot install --path /path/to/project
        awsinv copilot install --json
    """
    import json
    from pathlib import Path

    from ..copilot.installer import install_files

    target_path = Path(path) if path else Path.cwd()

    result = install_files(target_path)

    if json_output:
        output = {
            "success": result.success,
            "installed": [str(p) for p in result.installed],
            "backed_up": [[str(orig), str(backup)] for orig, backup in result.backed_up],
            "skipped": [str(p) for p in result.skipped],
            "errors": [[str(p), msg] for p, msg in result.errors],
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            console.print(f"[green]✓ Installed {len(result.installed)} files to {target_path}/.github/[/green]")

            if result.installed:
                console.print("\n[bold]Installed:[/bold]")
                for f in result.installed:
                    console.print(f"  • {f.name}")

            if result.backed_up:
                console.print("\n[bold]Backed up:[/bold]")
                for orig, backup in result.backed_up:
                    console.print(f"  • {orig.name} → {backup.name}")

            if result.skipped:
                console.print("\n[bold]Skipped (custom files preserved):[/bold]")
                for f in result.skipped:
                    console.print(f"  • {f.name}")
        else:
            console.print("[red]✗ Installation failed[/red]")
            for path_obj, error in result.errors:
                console.print(f"  Error: {error}")
            raise typer.Exit(code=1)


@copilot_app.command("uninstall")
def copilot_uninstall(
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target project directory (defaults to current directory)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """Remove installed GitHub Copilot files.

    Removes installed template files but preserves:
    - copilot-custom.md (custom org instructions)
    - Backup files (.bak.*)

    Example:
        awsinv copilot uninstall
        awsinv copilot uninstall --path /path/to/project
    """
    import json
    from pathlib import Path

    from ..copilot.installer import uninstall_files

    target_path = Path(path) if path else Path.cwd()

    result = uninstall_files(target_path)

    if json_output:
        output = {
            "success": result.success,
            "removed": [str(p) for p in result.removed],
            "not_found": [str(p) for p in result.not_found],
            "preserved": [str(p) for p in result.preserved],
            "errors": [[str(p), msg] for p, msg in result.errors],
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            if result.removed:
                console.print(f"[green]✓ Removed {len(result.removed)} files[/green]")
                console.print("\n[bold]Removed:[/bold]")
                for f in result.removed:
                    console.print(f"  • {f.name}")
            else:
                console.print("[yellow]No installed files found to remove[/yellow]")

            if result.preserved:
                console.print("\n[bold]Preserved (custom files):[/bold]")
                for f in result.preserved:
                    console.print(f"  • {f.name}")
        else:
            console.print("[red]✗ Uninstall failed[/red]")
            for path_obj, error in result.errors:
                console.print(f"  Error: {error}")
            raise typer.Exit(code=1)


@copilot_app.command("list")
def copilot_list(
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target project directory (defaults to current directory)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """List installed GitHub Copilot files.

    Shows installed files with version information from frontmatter:
    - Filename and type (instructions, prompt, custom)
    - Model version (e.g., gpt-4.1)
    - Last updated date

    Example:
        awsinv copilot list
        awsinv copilot list --path /path/to/project
        awsinv copilot list --json
    """
    import json
    from pathlib import Path

    from ..copilot.installer import list_installed_files

    target_path = Path(path) if path else Path.cwd()

    files = list_installed_files(target_path)

    if json_output:
        output = {
            "files": [
                {
                    "filename": f.filename,
                    "path": str(f.path),
                    "type": f.file_type.value,
                    "model": f.model,
                    "last_updated": str(f.last_updated) if f.last_updated else None,
                    "is_custom": f.is_custom,
                }
                for f in files
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        if not files:
            console.print("[yellow]No Copilot files installed[/yellow]")
            console.print(f"\nRun [bold]awsinv copilot install[/bold] to install files to {target_path}/.github/")
        else:
            console.print(f"[bold]Installed Copilot files ({len(files)}):[/bold]\n")

            table = Table(show_header=True, header_style="bold")
            table.add_column("File")
            table.add_column("Type")
            table.add_column("Model")
            table.add_column("Last Updated")

            for f in files:
                file_type = "[cyan]custom[/cyan]" if f.is_custom else f.file_type.value
                model = f.model or "-"
                updated = str(f.last_updated) if f.last_updated else "-"

                table.add_row(
                    f.filename,
                    file_type,
                    model,
                    updated,
                )

            console.print(table)


# =============================================================================
# Generate Command (IaC Generation)
# =============================================================================


@app.command()
def generate(
    format: str = typer.Argument(..., help="Output format: terraform, cdk-typescript, cdk-python"),
    snapshot_name: str = typer.Argument(..., help="Name of snapshot to generate from"),
    output: str = typer.Option("./terraform", "--output", "-o", help="Output directory"),
    model_id: Optional[str] = typer.Option(
        None, "--model-id", "-m", help="Bedrock model ID (default: from AWSINV_BEDROCK_MODEL_ID)"
    ),
    region: Optional[str] = typer.Option(
        None, "--region", "-r", help="AWS region for Bedrock (default: from AWSINV_BEDROCK_REGION)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated without creating files"),
) -> None:
    """Generate IaC (Terraform/CDK) from an inventory snapshot.

    Uses AWS Bedrock for AI-powered code generation.

    Examples:
        awsinv generate terraform my-snapshot
        awsinv generate terraform my-snapshot --output ./infra
        awsinv generate terraform my-snapshot --model-id anthropic.claude-sonnet-4-20250514-v1:0 --verbose
    """
    if format not in ["terraform", "cdk-typescript", "cdk-python"]:
        console.print(f"[red]Error:[/red] Unknown format '{format}'. Use: terraform, cdk-typescript, cdk-python")
        raise typer.Exit(1)

    if format != "terraform":
        console.print(f"[yellow]Note:[/yellow] {format} support coming soon. Only terraform is currently supported.")
        raise typer.Exit(1)

    # Import here to avoid loading langgraph unless needed
    try:
        from ..generate.terraform_generator import generate_terraform
    except ImportError as e:
        console.print("[red]Error:[/red] Generate dependencies not installed.")
        console.print("Install with: pip install aws-inventory-manager[generate]")
        console.print(f"Details: {e}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Generating Terraform from snapshot:[/bold] {snapshot_name}")
    console.print(f"[dim]Output directory: {output}[/dim]\n")

    if dry_run:
        console.print("[yellow]Dry run mode - no files will be created[/yellow]\n")
        # TODO: Implement dry run mode
        raise typer.Exit(0)

    # Run generation
    with console.status("[bold blue]Generating Terraform...[/bold blue]"):
        result = generate_terraform(
            snapshot_name=snapshot_name,
            output_dir=output,
            model_id=model_id,
            region=region,
        )

    # Display results
    if result.success:
        console.print("[bold green]Generation complete![/bold green]\n")

        summary = result.summary
        console.print(f"  Layers processed: {summary['completed_layers']}/{summary['total_layers']}")
        console.print(f"  Resources: {summary['total_resources']}")
        console.print(f"  Files generated: {summary['generated_files']}")
        console.print(f"\n  Output: [cyan]{result.output_dir}[/cyan]")

        if verbose and result.generated_files:
            console.print("\n  Generated files:")
            for f in result.generated_files:
                console.print(f"    - {f}")
    else:
        console.print("[bold red]Generation failed[/bold red]\n")

        for error in result.errors:
            console.print(f"  [red]Error:[/red] {error}")

        raise typer.Exit(1)


def cli_main():
    """Entry point for console script."""
    app()


if __name__ == "__main__":
    cli_main()
