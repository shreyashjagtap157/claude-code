"""Session lifecycle management."""

import uuid
from datetime import datetime
from typing import Optional

from prysm.state.database import DatabaseManager
from prysm.config.paths import get_state_db_path


class Session:
    """Represents a single PRYSM session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        model_id: str = "",
        runtime_id: str = "auto",
        name: Optional[str] = None,
    ):
        self.session_id = session_id or f"ses_{uuid.uuid4().hex[:12]}"
        self.name = name
        self.model_id = model_id
        self.runtime_id = runtime_id
        self.message_count = 0
        self.token_count = 0
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self._db = DatabaseManager(get_state_db_path())

    def save(self) -> None:
        """Persist this session to the database."""
        conn = self._db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (id, name, model_id, runtime_id, created_at, updated_at, message_count, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.session_id, self.name, self.model_id, self.runtime_id,
                self.created_at, self.updated_at, self.message_count, self.token_count,
            ),
        )
        conn.commit()

    def add_message(self, role: str, content: str, tokens: int = 0) -> None:
        """Record a message in this session."""
        conn = self._db.connect()
        conn.execute(
            """INSERT INTO messages (session_id, role, content, tokens)
               VALUES (?, ?, ?, ?)""",
            (self.session_id, role, content, tokens),
        )
        self.message_count += 1
        self.token_count += tokens
        self.updated_at = datetime.now().isoformat()
        conn.execute(
            "UPDATE sessions SET message_count=?, token_count=?, updated_at=? WHERE id=?",
            (self.message_count, self.token_count, self.updated_at, self.session_id),
        )
        conn.commit()

    def record_usage(
        self,
        model_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record token usage for this session."""
        conn = self._db.connect()
        conn.execute(
            """INSERT INTO usage (session_id, model_id, prompt_tokens, completion_tokens, cost_usd)
               VALUES (?, ?, ?, ?, ?)""",
            (self.session_id, model_id, prompt_tokens, completion_tokens, cost_usd),
        )
        conn.commit()

    def get_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get messages for this session, newest first."""
        conn = self._db.connect()
        cursor = conn.execute(
            """SELECT role, content, tool_calls, tokens, created_at
               FROM messages WHERE session_id = ?
               ORDER BY id ASC LIMIT ? OFFSET ?""",
            (self.session_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete(self) -> None:
        """Delete this session and all associated data."""
        conn = self._db.connect()
        conn.execute("DELETE FROM sessions WHERE id = ?", (self.session_id,))
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._db.close()


class SessionManager:
    """Manages active sessions."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        model_id: str = "",
        runtime_id: str = "auto",
        name: Optional[str] = None,
    ) -> Session:
        """Create and register a new session."""
        session = Session(model_id=model_id, runtime_id=runtime_id, name=name)
        session.save()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Get an active session."""
        return self._sessions.get(session_id)

    def close_all(self) -> None:
        """Close all active sessions."""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
