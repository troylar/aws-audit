# Data Storage

## Where Snapshots Are Stored

By default, all data is stored locally in a SQLite database:

```
~/.snapshots/
+-- inventory.db              # SQLite database (snapshots, resources, tags)
+-- audit-logs/
    +-- cleanup/              # Cleanup operation audit logs
        +-- 2026-01-15_cleanup.yaml
```

The SQLite database provides:

- **Fast queries**: Search across all snapshots with SQL
- **Tag analysis**: Normalized tags table for efficient filtering
- **Cross-snapshot history**: Track resources across multiple snapshots

## Changing Storage Location

```bash
# Via environment variable
export AWS_INVENTORY_STORAGE_PATH=/path/to/storage
awsinv snapshot create my-snapshot

# Via CLI flag
awsinv snapshot create my-snapshot --storage-path /path/to/storage
```

## Team Sharing

The SQLite database is a single portable file. To share across a team:

- Store `inventory.db` in a shared filesystem
- Sync via S3 or other cloud storage
- Use separate databases per environment/team

## Database Schema

For advanced usage including the full SQLite schema and SQL queries, see the [Database Reference](../reference/database.md).
