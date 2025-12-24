"""Database schema exploration for collecting comprehensive metadata."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from collections.abc import Generator

from utils.logging import logger

if TYPE_CHECKING:
    from database.service import DatabaseService

from database.client import validate_identifier


@dataclass
class ColumnInfo:
    """Information about a table column."""

    name: str
    data_type: str
    is_nullable: bool
    column_key: str  # PRI, UNI, MUL, or empty
    default: Optional[str]
    extra: str  # auto_increment, etc.
    comment: Optional[str]


@dataclass
class IndexInfo:
    """Information about a table index."""

    name: str
    columns: list[str]
    is_unique: bool
    index_type: str  # BTREE, HASH, FULLTEXT, etc.


@dataclass
class ForeignKeyInfo:
    """Information about a foreign key relationship."""

    constraint_name: str
    table_name: str
    column_name: str
    referenced_table: str
    referenced_column: str


@dataclass
class TableInfo:
    """Comprehensive information about a single table."""

    name: str
    comment: Optional[str]
    engine: str
    row_count_estimate: int
    data_size_bytes: int
    index_size_bytes: int
    columns: list[ColumnInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    primary_key_columns: list[str] = field(default_factory=list)


@dataclass
class DatabaseStatistics:
    """Overall database statistics."""

    total_tables: int
    total_rows_estimate: int
    total_data_size_bytes: int
    total_index_size_bytes: int


@dataclass
class DatabaseSchemaSnapshot:
    """Complete snapshot of database schema.

    Contains all metadata collected from exploring a database.
    """

    database_name: str
    host: str
    port: int
    tables: list[TableInfo]
    foreign_keys: list[ForeignKeyInfo]
    statistics: DatabaseStatistics
    collected_at: datetime
    schema_hash: str

    def get_tables_by_row_count(self, descending: bool = True) -> list[TableInfo]:
        """Get tables sorted by estimated row count."""
        return sorted(self.tables, key=lambda t: t.row_count_estimate, reverse=descending)

    @staticmethod
    def compute_schema_hash(tables: list[TableInfo]) -> str:
        """Compute a hash of the schema for change detection.

        The hash is based on table names and column definitions.
        """
        schema_str_parts = []
        for table in sorted(tables, key=lambda t: t.name):
            cols_str = ",".join(f"{c.name}:{c.data_type}:{c.column_key}" for c in table.columns)
            schema_str_parts.append(f"{table.name}({cols_str})")

        schema_str = "|".join(schema_str_parts)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


@dataclass
class TableExploreProgress:
    """Progress information for table exploration."""

    current: int
    total: int
    table_name: str
    table_info: Optional[TableInfo] = None
    error: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.table_info is not None or self.error is not None


class DatabaseExplorer:
    """Explore database schema and collect comprehensive metadata.

    This class provides methods to explore a MySQL database and collect
    information about tables, columns, indexes, and foreign keys.

    Usage:
        explorer = DatabaseExplorer(db_service)
        snapshot = explorer.explore()
    """

    def __init__(self, db_service: DatabaseService):
        """Initialize explorer with a database service.

        Args:
            db_service: Connected database service instance
        """
        self._db_service = db_service

    def _execute_query(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a query and return (columns, rows).

        Returns:
            Tuple of (column_names, rows)
        """
        result = self._db_service.execute_query(sql)
        if not result.success:
            logger.warning(f"Query failed: {result.error}")
            return [], []
        return result.columns or [], result.rows

    def explore(self) -> DatabaseSchemaSnapshot:
        """Explore the current database and return a complete schema snapshot.

        Returns:
            DatabaseSchemaSnapshot with all collected metadata

        Raises:
            ValueError: If not connected to a database
        """
        # Use the generator version but consume it immediately
        tables = []
        snapshot = None
        for progress in self.explore_iter():
            if progress.table_info:
                tables.append(progress.table_info)
            if isinstance(progress, DatabaseSchemaSnapshot):
                snapshot = progress

        # The last yield should be the snapshot
        if snapshot is None:
            raise ValueError("Failed to explore database")
        return snapshot

    def explore_iter(
        self, table_filter: Optional[list[str]] = None
    ) -> Generator[TableExploreProgress | DatabaseSchemaSnapshot, None, None]:
        """Explore the database with progress updates.

        Args:
            table_filter: Optional list of table names to filter. If provided, only these
                         tables will be explored. If None, all tables are explored.

        Yields TableExploreProgress for each table, then the final DatabaseSchemaSnapshot.

        Usage:
            for progress in explorer.explore_iter():
                if isinstance(progress, TableExploreProgress):
                    print(f"[{progress.current}/{progress.total}] {progress.table_name}")
                else:
                    # Final snapshot
                    snapshot = progress

        Yields:
            TableExploreProgress for each table being explored
            DatabaseSchemaSnapshot as the final yield
        """
        conn_info = self._db_service.get_connection_info()
        if not conn_info.get("connected"):
            raise ValueError("Not connected to a database")

        database_name = conn_info.get("database")
        if not database_name:
            raise ValueError("No database selected")

        host = conn_info.get("host", "localhost")
        port = conn_info.get("port", 3306)

        # First, get table list and foreign keys (with filtering if specified)
        tables = self._collect_tables(database_name, table_filter)
        foreign_keys = self._collect_foreign_keys(database_name, table_filter)

        total = len(tables)
        completed_tables: list[TableInfo] = []

        # Explore each table with progress updates
        for i, table in enumerate(tables, 1):
            # Yield progress before starting
            yield TableExploreProgress(
                current=i,
                total=total,
                table_name=table.name,
            )

            try:
                # Collect detailed info for this table
                table.columns = self._collect_columns(database_name, table.name)
                table.indexes = self._collect_indexes(table.name)
                table.primary_key_columns = [col.name for col in table.columns if col.column_key == "PRI"]
                completed_tables.append(table)

            except Exception as e:
                logger.warning(f"Failed to explore table {table.name}: {e}")
                # Still add the table but with minimal info
                completed_tables.append(table)

        # Calculate statistics
        statistics = DatabaseStatistics(
            total_tables=len(completed_tables),
            total_rows_estimate=sum(t.row_count_estimate for t in completed_tables),
            total_data_size_bytes=sum(t.data_size_bytes for t in completed_tables),
            total_index_size_bytes=sum(t.index_size_bytes for t in completed_tables),
        )

        # Generate schema hash for change detection
        schema_hash = DatabaseSchemaSnapshot.compute_schema_hash(completed_tables)

        # Yield the final snapshot
        yield DatabaseSchemaSnapshot(
            database_name=database_name,
            host=host,
            port=port,
            tables=completed_tables,
            foreign_keys=foreign_keys,
            statistics=statistics,
            collected_at=datetime.now(),
            schema_hash=schema_hash,
        )

    def _collect_tables(self, database_name: str, table_filter: Optional[list[str]] = None) -> list[TableInfo]:
        """Collect basic table information from information_schema.

        Args:
            database_name: Name of the database to query
            table_filter: Optional list of table names to filter. If provided, only these
                         tables will be returned. If None, all tables are returned.

        Returns:
            List of TableInfo objects for matching tables
        """
        # Build WHERE clause with optional table filter
        where_clause = f"TABLE_SCHEMA = '{database_name}' AND TABLE_TYPE = 'BASE TABLE'"
        if table_filter:
            # Validate and escape table names, then build IN clause
            validated_tables = []
            for name in table_filter:
                try:
                    validated_name = validate_identifier(name)
                    # Escape single quotes for SQL string literal
                    escaped_name = validated_name.replace("'", "''")
                    validated_tables.append(f"'{escaped_name}'")
                except ValueError as e:
                    logger.warning(f"Invalid table name '{name}' in filter, skipping: {e}")
                    continue
            if validated_tables:
                where_clause += f" AND TABLE_NAME IN ({', '.join(validated_tables)})"
            else:
                # No valid tables in filter, return empty list
                return []

        sql = f"""
            SELECT
                TABLE_NAME,
                TABLE_COMMENT,
                ENGINE,
                TABLE_ROWS,
                DATA_LENGTH,
                INDEX_LENGTH
            FROM information_schema.TABLES
            WHERE {where_clause}
            ORDER BY TABLE_NAME
        """
        columns, rows = self._execute_query(sql)

        tables = []
        for row in rows:
            tables.append(
                TableInfo(
                    name=row[0],
                    comment=row[1] if row[1] else None,
                    engine=row[2] or "InnoDB",
                    row_count_estimate=row[3] or 0,
                    data_size_bytes=row[4] or 0,
                    index_size_bytes=row[5] or 0,
                )
            )

        return tables

    def _collect_columns(self, database_name: str, table_name: str) -> list[ColumnInfo]:
        """Collect column information for a specific table."""
        sql = f"""
            SELECT
                COLUMN_NAME,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_DEFAULT,
                EXTRA,
                COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = '{database_name}'
              AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """
        columns, rows = self._execute_query(sql)

        result = []
        for row in rows:
            result.append(
                ColumnInfo(
                    name=row[0],
                    data_type=row[1],
                    is_nullable=(row[2] == "YES"),
                    column_key=row[3] or "",
                    default=row[4],
                    extra=row[5] or "",
                    comment=row[6] if row[6] else None,
                )
            )

        return result

    def _collect_indexes(self, table_name: str) -> list[IndexInfo]:
        """Collect index information for a specific table."""
        sql = f"SHOW INDEX FROM `{table_name}`"
        columns, rows = self._execute_query(sql)

        # Group by index name
        index_map: dict[str, IndexInfo] = {}
        for row in rows:
            # SHOW INDEX columns: Table, Non_unique, Key_name, Seq_in_index,
            # Column_name, Collation, Cardinality, Sub_part, Packed, Null,
            # Index_type, Comment, Index_comment
            key_name = row[2]
            non_unique = row[1]
            column_name = row[4]
            index_type = row[10] if len(row) > 10 else "BTREE"

            if key_name not in index_map:
                index_map[key_name] = IndexInfo(
                    name=key_name,
                    columns=[],
                    is_unique=(non_unique == 0),
                    index_type=index_type,
                )
            # Only append non-None column names
            if column_name:
                index_map[key_name].columns.append(column_name)

        return list(index_map.values())

    def _collect_foreign_keys(
        self, database_name: str, table_filter: Optional[list[str]] = None
    ) -> list[ForeignKeyInfo]:
        """Collect foreign key relationships.

        Args:
            database_name: Name of the database to query
            table_filter: Optional list of table names to filter. If provided, only foreign
                         keys involving these tables (either as source or target) will be
                         returned. If None, all foreign keys are returned.

        Returns:
            List of ForeignKeyInfo objects for matching foreign keys
        """
        # Build WHERE clause with optional table filter
        where_clause = f"kcu.TABLE_SCHEMA = '{database_name}' AND kcu.REFERENCED_TABLE_NAME IS NOT NULL"
        if table_filter:
            # Validate and escape table names, then build filter condition
            validated_tables = []
            for name in table_filter:
                try:
                    validated_name = validate_identifier(name)
                    # Escape single quotes for SQL string literal
                    escaped_name = validated_name.replace("'", "''")
                    validated_tables.append(f"'{escaped_name}'")
                except ValueError as e:
                    logger.warning(f"Invalid table name '{name}' in filter, skipping: {e}")
                    continue
            if validated_tables:
                table_list = ", ".join(validated_tables)
                where_clause += (
                    f" AND (kcu.TABLE_NAME IN ({table_list}) OR kcu.REFERENCED_TABLE_NAME IN ({table_list}))"
                )
            else:
                # No valid tables in filter, return empty list
                return []

        sql = f"""
            SELECT
                kcu.CONSTRAINT_NAME,
                kcu.TABLE_NAME,
                kcu.COLUMN_NAME,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE kcu
            WHERE {where_clause}
            ORDER BY kcu.TABLE_NAME, kcu.CONSTRAINT_NAME
        """
        columns, rows = self._execute_query(sql)

        fks = []
        for row in rows:
            fks.append(
                ForeignKeyInfo(
                    constraint_name=row[0],
                    table_name=row[1],
                    column_name=row[2],
                    referenced_table=row[3],
                    referenced_column=row[4],
                )
            )

        return fks


def format_snapshot_for_research(snapshot: DatabaseSchemaSnapshot) -> str:
    """Format DatabaseSchemaSnapshot as text for the research agent.

    This function converts a DatabaseSchemaSnapshot into a formatted markdown
    text that can be used as context for research agents analyzing database schemas.

    Args:
        snapshot: The collected database schema snapshot.

    Returns:
        Formatted markdown text describing the schema.
    """
    lines: list[str] = []

    # Database Overview
    lines.append("# Database Schema")
    lines.append(f"- Database: {snapshot.database_name}")
    lines.append(f"- Host: {snapshot.host}:{snapshot.port}")
    lines.append(f"- Total Tables: {snapshot.statistics.total_tables}")
    lines.append(f"- Total Rows (estimate): {snapshot.statistics.total_rows_estimate:,}")
    lines.append(f"- Data Size: {_format_bytes(snapshot.statistics.total_data_size_bytes)}")
    lines.append(f"- Index Size: {_format_bytes(snapshot.statistics.total_index_size_bytes)}")
    lines.append("")

    # Engine distribution
    engine_counts: dict[str, int] = {}
    for table in snapshot.tables:
        engine_counts[table.engine] = engine_counts.get(table.engine, 0) + 1
    if engine_counts:
        engine_str = ", ".join(f"{engine}: {count}" for engine, count in sorted(engine_counts.items()))
        lines.append(f"- Engines: {engine_str}")
        lines.append("")

    # Tables
    lines.append("# Tables")
    lines.append("")

    for table in snapshot.tables:
        lines.append(f"## {table.name}")

        # Table metadata
        meta_parts = [f"Engine: {table.engine}"]
        meta_parts.append(f"Rows: ~{table.row_count_estimate:,}")
        meta_parts.append(f"Size: {_format_bytes(table.data_size_bytes)}")
        if table.comment:
            meta_parts.append(f"Comment: {table.comment}")
        lines.append(f"- {' | '.join(meta_parts)}")

        # Primary key
        if table.primary_key_columns:
            lines.append(f"- Primary Key: {', '.join(table.primary_key_columns)}")
        else:
            lines.append("- Primary Key: **NONE**")

        # Columns
        lines.append("")
        lines.append("### Columns")
        lines.append("| Column | Type | Nullable | Key | Extra | Comment |")
        lines.append("|--------|------|----------|-----|-------|---------|")

        for col in table.columns:
            nullable = "YES" if col.is_nullable else "NO"
            key = col.column_key or "-"
            extra = col.extra or "-"
            comment = col.comment or "-"
            # Escape pipe characters in values
            col_type = col.data_type.replace("|", "\\|")
            comment = comment.replace("|", "\\|")
            lines.append(f"| {col.name} | {col_type} | {nullable} | {key} | {extra} | {comment} |")

        # Indexes
        if table.indexes:
            lines.append("")
            lines.append("### Indexes")
            lines.append("| Index Name | Columns | Unique | Type |")
            lines.append("|------------|---------|--------|------|")

            for idx in table.indexes:
                unique = "YES" if idx.is_unique else "NO"
                columns = ", ".join(idx.columns)
                lines.append(f"| {idx.name} | {columns} | {unique} | {idx.index_type} |")

        lines.append("")

    # Foreign Keys
    if snapshot.foreign_keys:
        lines.append("# Foreign Key Relationships")
        lines.append("")
        lines.append("| Constraint | Table.Column | References |")
        lines.append("|------------|--------------|------------|")

        for fk in snapshot.foreign_keys:
            from_col = f"{fk.table_name}.{fk.column_name}"
            to_col = f"{fk.referenced_table}.{fk.referenced_column}"
            lines.append(f"| {fk.constraint_name} | {from_col} | {to_col} |")

        lines.append("")

    return "\n".join(lines)


def _format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (B, KB, MB, GB).
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
