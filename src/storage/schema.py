"""SQLite schema definitions for AWS Inventory Manager."""

SCHEMA_VERSION = "1.0.0"

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
"""


def get_schema_sql() -> str:
    """Get the full schema SQL."""
    return SCHEMA_SQL


def get_indexes_sql() -> str:
    """Get the indexes SQL."""
    return INDEXES_SQL
