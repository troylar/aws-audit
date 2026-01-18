"""SQLite database connection and management for AWS Inventory Manager."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from ..utils.paths import get_snapshot_storage_path
from .schema import INDEXES_SQL, SCHEMA_SQL, SCHEMA_VERSION, get_migrations

logger = logging.getLogger(__name__)


class Database:
    """SQLite database connection manager.

    Handles connection pooling, schema setup, and auto-migration from YAML.
    """

    def __init__(self, db_path: Optional[Path] = None, storage_path: Optional[Path] = None):
        """Initialize database manager.

        Args:
            db_path: Direct path to database file (overrides storage_path)
            storage_path: Storage directory (database will be inventory.db inside)
        """
        if db_path:
            self.db_path = Path(db_path)
        elif storage_path:
            self.db_path = Path(storage_path) / "inventory.db"
        else:
            self.db_path = get_snapshot_storage_path() / "inventory.db"

        self.storage_path = self.db_path.parent
        self._connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection with optimal settings.

        Returns:
            SQLite connection configured for optimal performance
        """
        if self._connection is None:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self._connection = sqlite3.connect(str(self.db_path))
            # Use Row factory for dict-like access
            self._connection.row_factory = sqlite3.Row

            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")

            # Use WAL mode for better concurrent performance
            self._connection.execute("PRAGMA journal_mode = WAL")

            # Optimize for performance
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._connection.execute("PRAGMA cache_size = -64000")  # 64MB cache
            self._connection.execute("PRAGMA temp_store = MEMORY")  # Temp tables in memory
            self._connection.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O

            logger.debug(f"Connected to database: {self.db_path}")

        return self._connection

    def ensure_schema(self) -> None:
        """Create database schema if not exists and run migrations."""
        if self._initialized:
            return

        conn = self.connect()
        cursor = conn.cursor()

        try:
            # Get current schema version before creating tables
            current_version = self._get_raw_schema_version(cursor)

            # Create tables
            cursor.executescript(SCHEMA_SQL)

            # Run migrations BEFORE creating indexes (migrations may add columns that indexes depend on)
            if current_version and current_version != SCHEMA_VERSION:
                self._run_migrations(cursor, current_version)

            # Create indexes (after migrations so new columns exist)
            cursor.executescript(INDEXES_SQL)

            # Set schema version
            cursor.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )

            conn.commit()
            self._initialized = True
            logger.debug(f"Database schema initialized (version {SCHEMA_VERSION})")

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def _get_raw_schema_version(self, cursor: sqlite3.Cursor) -> Optional[str]:
        """Get schema version without ensuring schema exists.

        Args:
            cursor: Database cursor

        Returns:
            Schema version string or None if not set
        """
        try:
            cursor.execute("SELECT value FROM schema_info WHERE key = ?", ("schema_version",))
            row = cursor.fetchone()
            return row["value"] if row else None
        except sqlite3.OperationalError:
            return None

    def _run_migrations(self, cursor: sqlite3.Cursor, from_version: str) -> None:
        """Run schema migrations from a given version.

        Args:
            cursor: Database cursor
            from_version: Version to migrate from
        """
        migrations = get_migrations()

        # Simple version comparison - assumes semantic versioning
        for version, statements in sorted(migrations.items()):
            if version > from_version:
                logger.info(f"Running migration to version {version}")
                for sql in statements:
                    try:
                        cursor.execute(sql)
                        logger.debug(f"Migration SQL executed: {sql[:50]}...")
                    except sqlite3.OperationalError as e:
                        # Column may already exist if migration was partially applied
                        if "duplicate column name" in str(e).lower():
                            logger.debug(f"Column already exists, skipping: {e}")
                        else:
                            raise

    def get_schema_version(self) -> Optional[str]:
        """Get current schema version from database.

        Returns:
            Schema version string or None if not set
        """
        conn = self.connect()
        try:
            cursor = conn.execute("SELECT value FROM schema_info WHERE key = ?", ("schema_version",))
            row = cursor.fetchone()
            return row["value"] if row else None
        except sqlite3.OperationalError:
            return None

    def is_empty(self) -> bool:
        """Check if database has no snapshots.

        Returns:
            True if no snapshots exist
        """
        conn = self.connect()
        self.ensure_schema()
        cursor = conn.execute("SELECT COUNT(*) as count FROM snapshots")
        row = cursor.fetchone()
        return row["count"] == 0

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database transactions.

        Yields:
            Database cursor

        Example:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO ...")
        """
        conn = self.connect()
        self.ensure_schema()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement.

        Args:
            sql: SQL statement
            params: Query parameters

        Returns:
            Cursor with results
        """
        conn = self.connect()
        self.ensure_schema()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement with placeholders
            params_list: List of parameter tuples

        Returns:
            Cursor
        """
        conn = self.connect()
        self.ensure_schema()
        return conn.executemany(sql, params_list)

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and fetch all results as dicts.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and fetch single result as dict.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            Result dictionary or None
        """
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def commit(self) -> None:
        """Commit the current transaction."""
        if self._connection:
            self._connection.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self._initialized = False
            logger.debug("Database connection closed")

    def __enter__(self) -> "Database":
        """Context manager entry."""
        self.connect()
        self.ensure_schema()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# JSON serialization helpers for SQLite
def json_serialize(obj: Any) -> Optional[str]:
    """Serialize object to JSON string for SQLite storage.

    Args:
        obj: Object to serialize

    Returns:
        JSON string or None if obj is None
    """
    if obj is None:
        return None
    return json.dumps(obj, default=str)


def json_deserialize(json_str: Optional[str]) -> Any:
    """Deserialize JSON string from SQLite.

    Args:
        json_str: JSON string

    Returns:
        Deserialized object or None
    """
    if json_str is None:
        return None
    return json.loads(json_str)
