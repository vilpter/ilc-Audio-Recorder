#!/usr/bin/env python3
"""
Database Utilities
Provides safe database connection management with automatic cleanup
"""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Callable, Any

logger = logging.getLogger('db_utils')


@contextmanager
def get_db_connection(db_path, timeout=10.0, row_factory=None):
    """
    Context manager for safe database connections.
    Ensures connection is always closed, even if exceptions occur.

    Args:
        db_path: Path to SQLite database file
        timeout: Connection timeout in seconds (default: 10.0)
        row_factory: Optional row factory (e.g., sqlite3.Row)

    Yields:
        sqlite3.Connection: Database connection object

    Example:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
            conn.commit()
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=timeout)
        if row_factory:
            conn.row_factory = row_factory
        yield conn
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logger.error(f"Error closing database connection: {close_error}")


def execute_query(db_path, query, params=None, commit=False, row_factory=None, timeout=10.0):
    """
    Execute a single query with automatic connection management.

    Args:
        db_path: Path to SQLite database file
        query: SQL query string
        params: Query parameters (tuple or dict)
        commit: Whether to commit the transaction
        row_factory: Optional row factory (e.g., sqlite3.Row)
        timeout: Connection timeout in seconds

    Returns:
        List of rows for SELECT queries, None for other queries

    Example:
        # SELECT query
        rows = execute_query(DB_PATH, "SELECT * FROM users WHERE id = ?", (1,))

        # INSERT query
        execute_query(DB_PATH, "INSERT INTO users VALUES (?, ?)", (1, 'admin'), commit=True)
    """
    with get_db_connection(db_path, timeout=timeout, row_factory=row_factory) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if commit:
            conn.commit()

        # Return results for SELECT queries
        if query.strip().upper().startswith('SELECT'):
            return cursor.fetchall()

        return None


def execute_many(db_path, query, params_list, timeout=10.0):
    """
    Execute multiple queries with the same statement (batch insert/update).

    Args:
        db_path: Path to SQLite database file
        query: SQL query string
        params_list: List of parameter tuples
        timeout: Connection timeout in seconds

    Example:
        execute_many(DB_PATH, "INSERT INTO users VALUES (?, ?)",
                    [(1, 'admin'), (2, 'user')])
    """
    with get_db_connection(db_path, timeout=timeout) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()


def execute_transaction(db_path, transaction_func, timeout=10.0):
    """
    Execute multiple operations in a single transaction.
    Automatically commits on success, rolls back on error.

    Args:
        db_path: Path to SQLite database file
        transaction_func: Function that takes (conn, cursor) and performs operations
        timeout: Connection timeout in seconds

    Returns:
        Return value from transaction_func

    Example:
        def my_transaction(conn, cursor):
            cursor.execute("INSERT INTO users VALUES (?, ?)", (1, 'admin'))
            cursor.execute("INSERT INTO logs VALUES (?)", ('user created',))
            return cursor.lastrowid

        user_id = execute_transaction(DB_PATH, my_transaction)
    """
    with get_db_connection(db_path, timeout=timeout) as conn:
        cursor = conn.cursor()
        result = transaction_func(conn, cursor)
        conn.commit()
        return result


def fetch_one(db_path, query, params=None, row_factory=None, timeout=10.0):
    """
    Fetch a single row from the database.

    Args:
        db_path: Path to SQLite database file
        query: SQL query string
        params: Query parameters
        row_factory: Optional row factory (e.g., sqlite3.Row)
        timeout: Connection timeout in seconds

    Returns:
        Single row or None if no results
    """
    with get_db_connection(db_path, timeout=timeout, row_factory=row_factory) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()


def fetch_all(db_path, query, params=None, row_factory=None, timeout=10.0):
    """
    Fetch all rows from the database.

    Args:
        db_path: Path to SQLite database file
        query: SQL query string
        params: Query parameters
        row_factory: Optional row factory (e.g., sqlite3.Row)
        timeout: Connection timeout in seconds

    Returns:
        List of rows
    """
    with get_db_connection(db_path, timeout=timeout, row_factory=row_factory) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
