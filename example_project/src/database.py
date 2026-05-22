"""
Database module - SQLite connection and queries.
"""

import sqlite3
import os
from pathlib import Path
from models import Task, User

DB_PATH = os.environ.get("DATABASE_PATH", "tasks.db")

_connection = None


def get_db():
    """Get database connection (singleton)."""
    global _connection
    if _connection is None:
        _connection = Database(DB_PATH)
    return _connection


def init_db():
    """Initialize database schema."""
    db = get_db()
    db._execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """)
    db._execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            completed INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def _execute(self, query: str, params=None):
        cursor = self.conn.cursor()
        cursor.execute(query, params or [])
        self.conn.commit()
        return cursor

    def find_user_by_email(self, email: str) -> User | None:
        cursor = self._execute("SELECT * FROM users WHERE email = ?", [email])
        row = cursor.fetchone()
        return User.from_row(row) if row else None

    def find_user_by_id(self, user_id: int) -> User | None:
        cursor = self._execute("SELECT * FROM users WHERE id = ?", [user_id])
        row = cursor.fetchone()
        return User.from_row(row) if row else None

    def get_tasks_by_user(self, user_id: int) -> list[Task]:
        cursor = self._execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            [user_id]
        )
        return [Task.from_row(row) for row in cursor.fetchall()]

    def get_task(self, task_id: int) -> Task | None:
        cursor = self._execute("SELECT * FROM tasks WHERE id = ?", [task_id])
        row = cursor.fetchone()
        return Task.from_row(row) if row else None

    def save_task(self, task: Task) -> Task:
        if task.id:
            self._execute(
                """UPDATE tasks SET title=?, description=?, priority=?, 
                   completed=?, updated_at=strftime('%s','now') WHERE id=?""",
                [task.title, task.description, task.priority, task.completed, task.id]
            )
        else:
            cursor = self._execute(
                "INSERT INTO tasks (user_id, title, description, priority) VALUES (?, ?, ?, ?)",
                [task.user_id, task.title, task.description, task.priority]
            )
            task.id = cursor.lastrowid
        return task

    def delete_task(self, task_id: int):
        self._execute("DELETE FROM tasks WHERE id = ?", [task_id])
