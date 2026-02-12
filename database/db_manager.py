"""
Database Manager for Slack Leave Bot Analytics
Handles SQLite connection, initialization, and query execution with WAL mode for concurrent access
"""

import sqlite3
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database connections and operations"""

    def __init__(self, db_path: str):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._initialized = False
        self._lock = threading.Lock()

    def init_db(self) -> bool:
        """
        Initialize database schema and enable WAL mode

        Returns:
            True if initialization successful, False otherwise
        """
        with self._lock:
            if self._initialized:
                logger.debug("Database already initialized")
                return True

            try:
                # Create database directory if it doesn't exist
                db_dir = Path(self.db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)

                # Read schema file from database module directory
                module_dir = Path(__file__).parent
                schema_path = module_dir / "schema.sql"
                if not schema_path.exists():
                    logger.error(f"Schema file not found: {schema_path}")
                    return False

                with open(schema_path, 'r') as f:
                    schema_sql = f.read()

                # Initialize database
                conn = sqlite3.connect(self.db_path)
                try:
                    # Enable WAL mode for concurrent reads
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
                    conn.execute("PRAGMA temp_store=MEMORY")

                    # Execute schema
                    conn.executescript(schema_sql)
                    conn.commit()

                    logger.info(f"Database initialized successfully at {self.db_path}")
                    self._initialized = True
                    return True

                finally:
                    conn.close()

            except Exception as e:
                logger.error(f"Failed to initialize database: {e}", exc_info=True)
                return False

    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """
        Get thread-local database connection as context manager

        Args:
            timeout: Database lock timeout in seconds

        Yields:
            sqlite3.Connection: Database connection
        """
        # Get or create thread-local connection
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            try:
                self._local.conn = sqlite3.connect(
                    self.db_path,
                    timeout=timeout,
                    check_same_thread=False
                )
                # Set row factory for dict-like access
                self._local.conn.row_factory = sqlite3.Row
            except Exception as e:
                logger.error(f"Failed to create database connection: {e}")
                raise

        try:
            yield self._local.conn
        except Exception as e:
            self._local.conn.rollback()
            raise

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        fetch: str = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a database query

        Args:
            query: SQL query string
            params: Query parameters (tuple)
            fetch: Fetch mode - 'one', 'all', or None for no fetch

        Returns:
            Query results as list of dicts, or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # Handle fetch
                if fetch == 'one':
                    row = cursor.fetchone()
                    result = [dict(row)] if row else None
                elif fetch == 'all':
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows] if rows else []
                else:
                    result = None

                # Commit if write operation
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()

                return result

        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return None

    def execute_many(self, query: str, params_list: List[Tuple]) -> bool:
        """
        Execute query with multiple parameter sets (batch insert)

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                logger.debug(f"Batch executed {len(params_list)} operations")
                return True

        except Exception as e:
            logger.error(f"Batch execution failed: {e}", exc_info=True)
            return False

    def get_table_count(self, table_name: str) -> int:
        """
        Get row count for a table

        Args:
            table_name: Name of the table

        Returns:
            Number of rows, or -1 on error
        """
        try:
            result = self.execute_query(
                f"SELECT COUNT(*) as count FROM {table_name}",
                fetch='one'
            )
            return result[0]['count'] if result else -1

        except Exception as e:
            logger.error(f"Failed to get table count: {e}")
            return -1

    def vacuum(self) -> bool:
        """
        Run VACUUM to optimize database

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
                return True

        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            return False

    def close(self):
        """Close thread-local connection if exists"""
        if hasattr(self._local, 'conn') and self._local.conn:
            try:
                self._local.conn.close()
                self._local.conn = None
            except Exception as e:
                logger.error(f"Failed to close connection: {e}")


# Global database manager instance (initialized by main.py)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> Optional[DatabaseManager]:
    """Get global database manager instance"""
    return _db_manager


def set_db_manager(db_manager: DatabaseManager):
    """Set global database manager instance"""
    global _db_manager
    _db_manager = db_manager
