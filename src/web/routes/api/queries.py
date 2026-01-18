"""Saved queries API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...dependencies import get_database, get_resource_store

router = APIRouter(prefix="/queries")


class SavedQuery(BaseModel):
    """Saved query model."""

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    sql_text: str
    category: str = "custom"
    is_favorite: bool = False


class QueryResult(BaseModel):
    """Query execution result."""

    columns: List[str]
    rows: List[dict]
    row_count: int
    execution_time_ms: float


@router.get("")
async def list_saved_queries(
    category: Optional[str] = Query(None, description="Filter by category"),
    favorites_only: bool = Query(False, description="Show only favorites"),
):
    """List saved queries."""
    db = get_database()

    sql = "SELECT * FROM saved_queries WHERE 1=1"
    params: List = []

    if category:
        sql += " AND category = ?"
        params.append(category)

    if favorites_only:
        sql += " AND is_favorite = 1"

    sql += " ORDER BY is_favorite DESC, last_run_at DESC NULLS LAST, name"

    rows = db.fetchall(sql, tuple(params))
    return {"queries": [dict(r) for r in rows]}


@router.post("")
async def create_saved_query(query: SavedQuery):
    """Save a new query."""
    db = get_database()

    try:
        cursor = db.execute(
            """
            INSERT INTO saved_queries (name, description, sql_text, category, is_favorite, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query.name,
                query.description,
                query.sql_text,
                query.category,
                query.is_favorite,
                datetime.utcnow().isoformat(),
            ),
        )
        db.commit()
        return {"id": cursor.lastrowid, "message": "Query saved"}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail=f"Query with name '{query.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{query_id}")
async def get_saved_query(query_id: int):
    """Get a saved query by ID."""
    db = get_database()
    row = db.fetchone("SELECT * FROM saved_queries WHERE id = ?", (query_id,))

    if not row:
        raise HTTPException(status_code=404, detail="Query not found")

    return dict(row)


@router.put("/{query_id}")
async def update_saved_query(query_id: int, query: SavedQuery):
    """Update a saved query."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_queries WHERE id = ?", (query_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Query not found")

    db.execute(
        """
        UPDATE saved_queries
        SET name = ?, description = ?, sql_text = ?, category = ?, is_favorite = ?
        WHERE id = ?
        """,
        (query.name, query.description, query.sql_text, query.category, query.is_favorite, query_id),
    )
    db.commit()
    return {"message": "Query updated"}


@router.delete("/{query_id}")
async def delete_saved_query(query_id: int):
    """Delete a saved query."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_queries WHERE id = ?", (query_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Query not found")

    db.execute("DELETE FROM saved_queries WHERE id = ?", (query_id,))
    db.commit()
    return {"message": "Query deleted"}


@router.post("/{query_id}/run")
async def run_saved_query(
    query_id: int,
    limit: int = Query(100, le=1000),
):
    """Execute a saved query."""
    db = get_database()

    row = db.fetchone("SELECT * FROM saved_queries WHERE id = ?", (query_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")

    sql_text = row["sql_text"]

    # Update last_run_at and run_count
    db.execute(
        """
        UPDATE saved_queries
        SET last_run_at = ?, run_count = run_count + 1
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(), query_id),
    )
    db.commit()

    # Execute the query
    return await _execute_sql(sql_text, limit)


@router.post("/execute")
async def execute_sql(
    sql: str,
    limit: int = Query(100, le=1000),
):
    """Execute an ad-hoc SQL query."""
    return await _execute_sql(sql, limit)


async def _execute_sql(sql: str, limit: int) -> dict:
    """Execute SQL and return results."""
    import time

    store = get_resource_store()

    # Add limit if not present
    sql_lower = sql.lower().strip()
    if "limit" not in sql_lower:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"

    start = time.time()

    try:
        results = store.query_raw(sql)
        elapsed = (time.time() - start) * 1000

        if results:
            columns = list(results[0].keys())
        else:
            columns = []

        return {
            "columns": columns,
            "rows": results,
            "row_count": len(results),
            "execution_time_ms": round(elapsed, 2),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
