"""SQLite schema definitions for AWS Inventory Manager."""

SCHEMA_VERSION = "1.2.0"

# Schema creation SQL
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Core snapshots table
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    account_id TEXT NOT NULL,
    regions TEXT NOT NULL,
    resource_count INTEGER DEFAULT 0,
    total_resources_before_filter INTEGER,
    service_counts TEXT,
    metadata TEXT,
    filters_applied TEXT,
    schema_version TEXT DEFAULT '1.1',
    inventory_name TEXT DEFAULT 'default',
    is_active BOOLEAN DEFAULT 0
);

-- Resources table
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    arn TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    raw_config TEXT,
    created_at TIMESTAMP,
    source TEXT DEFAULT 'direct_api',
    canonical_name TEXT,
    normalized_name TEXT,
    extracted_patterns TEXT,
    normalization_method TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE,
    UNIQUE(snapshot_id, arn)
);

-- Normalized tags for efficient querying
CREATE TABLE IF NOT EXISTS resource_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);

-- Inventories table
CREATE TABLE IF NOT EXISTS inventories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_id TEXT NOT NULL,
    description TEXT DEFAULT '',
    include_tags TEXT,
    exclude_tags TEXT,
    active_snapshot_id INTEGER,
    created_at TIMESTAMP NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    FOREIGN KEY (active_snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL,
    UNIQUE(name, account_id)
);

-- Link table for inventory snapshots (many-to-many)
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    inventory_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    PRIMARY KEY (inventory_id, snapshot_id),
    FOREIGN KEY (inventory_id) REFERENCES inventories(id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

-- Audit operations table
CREATE TABLE IF NOT EXISTS audit_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT UNIQUE NOT NULL,
    baseline_snapshot TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    aws_profile TEXT,
    account_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    total_resources INTEGER,
    succeeded_count INTEGER,
    failed_count INTEGER,
    skipped_count INTEGER,
    duration_seconds REAL,
    filters TEXT
);

-- Audit records table
CREATE TABLE IF NOT EXISTS audit_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    resource_arn TEXT NOT NULL,
    resource_id TEXT,
    resource_type TEXT NOT NULL,
    region TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    protection_reason TEXT,
    deletion_tier TEXT,
    tags TEXT,
    estimated_monthly_cost REAL,
    FOREIGN KEY (operation_id) REFERENCES audit_operations(operation_id) ON DELETE CASCADE
);

-- Saved queries table (for web UI)
CREATE TABLE IF NOT EXISTS saved_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    sql_text TEXT NOT NULL,
    category TEXT DEFAULT 'custom',
    is_favorite BOOLEAN DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    last_run_at TIMESTAMP,
    run_count INTEGER DEFAULT 0
);

-- Saved filters table (for resource explorer)
CREATE TABLE IF NOT EXISTS saved_filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    filter_config TEXT NOT NULL,
    is_favorite BOOLEAN DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP,
    use_count INTEGER DEFAULT 0
);

-- Saved views table (for customizable resource views)
CREATE TABLE IF NOT EXISTS saved_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    view_config TEXT NOT NULL,
    is_default BOOLEAN DEFAULT 0,
    is_favorite BOOLEAN DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP,
    use_count INTEGER DEFAULT 0
);

-- Resource groups table (for baseline comparison)
CREATE TABLE IF NOT EXISTS resource_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    source_snapshot TEXT,
    resource_count INTEGER DEFAULT 0,
    is_favorite BOOLEAN DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    last_updated TIMESTAMP NOT NULL
);

-- Resource group members table (normalized for efficient querying)
CREATE TABLE IF NOT EXISTS resource_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    resource_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    original_arn TEXT,
    match_strategy TEXT DEFAULT 'physical_name',
    FOREIGN KEY (group_id) REFERENCES resource_groups(id) ON DELETE CASCADE,
    UNIQUE (group_id, resource_name, resource_type)
);
"""

# Indexes for common queries (created separately for better error handling)
# SQLite performance tips applied:
# - Indexes on foreign keys for faster JOINs
# - Composite indexes for common query patterns
# - Covering indexes where possible
INDEXES_SQL = """
-- Resources indexes
CREATE INDEX IF NOT EXISTS idx_resources_arn ON resources(arn);
CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_resources_region ON resources(region);
CREATE INDEX IF NOT EXISTS idx_resources_created ON resources(created_at);
CREATE INDEX IF NOT EXISTS idx_resources_snapshot ON resources(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_resources_type_region ON resources(resource_type, region);
CREATE INDEX IF NOT EXISTS idx_resources_canonical_name_type ON resources(canonical_name, resource_type);
CREATE INDEX IF NOT EXISTS idx_resources_normalized_name_type ON resources(normalized_name, resource_type);

-- Tags indexes (for efficient tag queries)
CREATE INDEX IF NOT EXISTS idx_tags_resource ON resource_tags(resource_id);
CREATE INDEX IF NOT EXISTS idx_tags_key ON resource_tags(key);
CREATE INDEX IF NOT EXISTS idx_tags_value ON resource_tags(value);
CREATE INDEX IF NOT EXISTS idx_tags_kv ON resource_tags(key, value);

-- Snapshots indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_account ON snapshots(account_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_created ON snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_name ON snapshots(name);
CREATE INDEX IF NOT EXISTS idx_snapshots_account_created ON snapshots(account_id, created_at DESC);

-- Inventories indexes
CREATE INDEX IF NOT EXISTS idx_inventories_account ON inventories(account_id);
CREATE INDEX IF NOT EXISTS idx_inventories_name_account ON inventories(name, account_id);

-- Audit indexes (for history queries and filtering)
CREATE INDEX IF NOT EXISTS idx_audit_ops_timestamp ON audit_operations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_ops_account ON audit_operations(account_id);
CREATE INDEX IF NOT EXISTS idx_audit_ops_account_timestamp ON audit_operations(account_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_records_operation ON audit_records(operation_id);
CREATE INDEX IF NOT EXISTS idx_audit_records_arn ON audit_records(resource_arn);
CREATE INDEX IF NOT EXISTS idx_audit_records_type ON audit_records(resource_type);
CREATE INDEX IF NOT EXISTS idx_audit_records_region ON audit_records(region);
CREATE INDEX IF NOT EXISTS idx_audit_records_status ON audit_records(status);

-- Saved queries indexes
CREATE INDEX IF NOT EXISTS idx_queries_category ON saved_queries(category);
CREATE INDEX IF NOT EXISTS idx_queries_favorite ON saved_queries(is_favorite);
CREATE INDEX IF NOT EXISTS idx_queries_last_run ON saved_queries(last_run_at DESC);

-- Saved filters indexes
CREATE INDEX IF NOT EXISTS idx_filters_favorite ON saved_filters(is_favorite);
CREATE INDEX IF NOT EXISTS idx_filters_last_used ON saved_filters(last_used_at DESC);

-- Saved views indexes
CREATE INDEX IF NOT EXISTS idx_views_default ON saved_views(is_default);
CREATE INDEX IF NOT EXISTS idx_views_favorite ON saved_views(is_favorite);
CREATE INDEX IF NOT EXISTS idx_views_last_used ON saved_views(last_used_at DESC);

-- Resource groups indexes
CREATE INDEX IF NOT EXISTS idx_groups_name ON resource_groups(name);
CREATE INDEX IF NOT EXISTS idx_groups_favorite ON resource_groups(is_favorite);
CREATE INDEX IF NOT EXISTS idx_groups_created ON resource_groups(created_at DESC);

-- Resource group members indexes
CREATE INDEX IF NOT EXISTS idx_group_members_group ON resource_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_name_type ON resource_group_members(resource_name, resource_type);
CREATE INDEX IF NOT EXISTS idx_group_members_strategy ON resource_group_members(match_strategy);
"""


MIGRATIONS = {
    "1.1.0": [
        # Add canonical_name column to resources table
        "ALTER TABLE resources ADD COLUMN canonical_name TEXT",
        # Add match_strategy column to resource_group_members table
        "ALTER TABLE resource_group_members ADD COLUMN match_strategy TEXT DEFAULT 'physical_name'",
        # Backfill canonical_name from CloudFormation logical-id tag
        """
        UPDATE resources
        SET canonical_name = (
            SELECT value FROM resource_tags
            WHERE resource_tags.resource_id = resources.id
            AND key = 'aws:cloudformation:logical-id'
        )
        WHERE canonical_name IS NULL
        """,
        # Fallback to physical name for resources without CloudFormation tag
        """
        UPDATE resources
        SET canonical_name = COALESCE(name, arn)
        WHERE canonical_name IS NULL
        """,
    ],
    "1.2.0": [
        # Add normalized_name column for pattern-stripped names
        "ALTER TABLE resources ADD COLUMN normalized_name TEXT",
        # Add extracted_patterns column for storing what was stripped (JSON)
        "ALTER TABLE resources ADD COLUMN extracted_patterns TEXT",
        # Add normalization_method column for tracking how normalization was done
        "ALTER TABLE resources ADD COLUMN normalization_method TEXT",
        # Backfill normalized_name from CloudFormation logical-id tag
        """
        UPDATE resources
        SET normalized_name = (
            SELECT value FROM resource_tags
            WHERE resource_tags.resource_id = resources.id
            AND key = 'aws:cloudformation:logical-id'
        ),
        normalization_method = 'tag:logical-id'
        WHERE normalized_name IS NULL
        AND EXISTS (
            SELECT 1 FROM resource_tags
            WHERE resource_tags.resource_id = resources.id
            AND key = 'aws:cloudformation:logical-id'
        )
        """,
        # Backfill from Name tag
        """
        UPDATE resources
        SET normalized_name = (
            SELECT value FROM resource_tags
            WHERE resource_tags.resource_id = resources.id
            AND key = 'Name'
        ),
        normalization_method = 'tag:Name'
        WHERE normalized_name IS NULL
        AND EXISTS (
            SELECT 1 FROM resource_tags
            WHERE resource_tags.resource_id = resources.id
            AND key = 'Name'
        )
        """,
        # Fallback to physical name (pattern extraction needs Python, done on re-snapshot)
        """
        UPDATE resources
        SET normalized_name = COALESCE(name, arn),
            normalization_method = 'none'
        WHERE normalized_name IS NULL
        """,
    ],
}


def get_schema_sql() -> str:
    """Get the full schema SQL."""
    return SCHEMA_SQL


def get_indexes_sql() -> str:
    """Get the indexes SQL."""
    return INDEXES_SQL


def get_migrations() -> dict:
    """Get the migrations dictionary.

    Returns:
        Dict mapping version strings to lists of SQL statements
    """
    return MIGRATIONS
