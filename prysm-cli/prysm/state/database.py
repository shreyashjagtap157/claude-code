"""SQLite database management for session state and metadata."""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from prysm.config.paths import get_state_db_path, ensure_dirs


SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    model_id TEXT NOT NULL,
    runtime_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_model ON sessions(model_id);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool_result', 'system')),
    content TEXT,
    tool_calls TEXT,
    tokens INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(session_id, role);

-- Token usage tracking
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    provider TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cache_hit_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_usage_session ON usage(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage(model_id);
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp DESC);

-- Plugin state
CREATE TABLE IF NOT EXISTS plugin_state (
    plugin_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (plugin_id, session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Cross-session learnings
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('preference', 'rules', 'workspace', 'general')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
"""


class DatabaseManager:
    """Manages the SQLite database connection and schema."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_state_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Open (or return existing) database connection with WAL mode."""
        if self._conn is not None:
            return self._conn

        ensure_dirs()
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the active connection (raises if not connected)."""
        if self._conn is None:
            return self.connect()
        return self._conn

    def _migrate(self) -> None:
        """Run schema migrations."""
        cursor = self.conn.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = cursor.fetchone()
        current_version = row[0] if row and row[0] else 0

        if current_version < SCHEMA_VERSION:
            self._backup()
            self.conn.executescript(SCHEMA_SQL)
            self.conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, description) VALUES (?, ?)",
                (SCHEMA_VERSION, "Initial schema"),
            )
            self.conn.commit()

    def _backup(self) -> None:
        """Create a timestamped backup before schema changes."""
        if self.db_path.exists():
            backup_path = self.db_path.parent / f"state.{datetime.now():%Y%m%d_%H%M%S}.db"
            shutil.copy2(self.db_path, backup_path)

    def vacuum(self) -> None:
        """VACUUM the database to reclaim space."""
        self.conn.execute("VACUUM")
