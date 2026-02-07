# Web UI

The Resource Explorer provides a web-based interface for browsing and analyzing your inventory.

## Getting Started

```bash
# Install web dependencies
pip install aws-inventory-manager[web]

# Launch the server
awsinv serve
```

This opens a browser automatically at `http://localhost:8000`.

## Features

- **Dashboard**: KPI cards and charts showing resource distribution by type/region
- **Snapshot Browser**: View, compare, and manage snapshots
- **Resource Explorer**: Search, filter, and browse all resources with a data-dense table
- **Diff Viewer**: Side-by-side snapshot comparison with added/removed/modified resources
- **SQL Query Editor**: Run custom SQL queries with syntax highlighting
- **Cleanup UI**: Preview and execute cleanup operations with audit logs

## Resource Explorer

The main table supports:

- **Column customization**: Show/hide columns, reorder, freeze columns
- **Advanced filters**: Build complex AND/OR filter conditions
- **Saved views**: Save and restore column layouts and filter configurations
- **Saved filters**: Reuse frequently used filter combinations
- **Tag columns**: Individual tag keys as separate columns
- **Creator columns**: Created By, Creator Type, Creation Time (from CloudTrail enrichment)
- **Export**: CSV and YAML export of filtered data

## Options

```bash
# Custom port
awsinv serve --port 3000

# Custom host
awsinv serve --host 0.0.0.0

# Custom storage path
awsinv serve --storage-path /path/to/inventory
```
