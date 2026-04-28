import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class MeetingLogger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meeting_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    sequence_id TEXT,
                    round INTEGER,
                    expert_id TEXT,
                    expert_type TEXT,
                    content TEXT,
                    suggestions TEXT,
                    created_at TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS version_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    version_hash TEXT,
                    content TEXT,
                    message TEXT,
                    created_at TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rag_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    query TEXT,
                    results TEXT,
                    scores TEXT,
                    created_at TEXT
                )
            """)

    def log_meeting(
        self,
        project_id: str,
        expert_id: str,
        expert_type: str,
        content: str,
        suggestions: list[str] = None,
        sequence_id: str = None,
        round: int = 0
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO meeting_logs 
                (project_id, sequence_id, round, expert_id, expert_type, content, suggestions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    sequence_id,
                    round,
                    expert_id,
                    expert_type,
                    content,
                    json.dumps(suggestions or [], ensure_ascii=False),
                    datetime.now().isoformat()
                )
            )

    def log_version(
        self,
        project_id: str,
        layer: str,
        content: dict,
        message: str = "",
        version_hash: str = None
    ):
        if version_hash is None:
            import hashlib
            content_str = json.dumps(content, ensure_ascii=False)
            version_hash = hashlib.sha256(content_str.encode()).hexdigest()[:12]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO version_history
                (project_id, layer, version_hash, content, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    layer,
                    version_hash,
                    json.dumps(content, ensure_ascii=False),
                    message,
                    datetime.now().isoformat()
                )
            )
        return version_hash

    def log_rag_query(
        self,
        project_id: str,
        query: str,
        results: list[dict],
        scores: list[float]
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO rag_logs (project_id, query, results, scores, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    query,
                    json.dumps(results, ensure_ascii=False),
                    json.dumps(scores),
                    datetime.now().isoformat()
                )
            )

    def get_meeting_logs(self, project_id: str, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM meeting_logs 
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_version_history(self, project_id: str, layer: str = None) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if layer:
                cursor = conn.execute(
                    """
                    SELECT * FROM version_history
                    WHERE project_id = ? AND layer = ?
                    ORDER BY created_at DESC
                    """,
                    (project_id, layer)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM version_history
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                    """,
                    (project_id,)
                )
            return [dict(row) for row in cursor.fetchall()]


def get_meeting_logger(project_id: str) -> MeetingLogger:
    from backend.services.project_manager import get_project_manager
    pm = get_project_manager()
    project = pm.get_project(project_id)
    if project:
        db_path = project.project_path / "logs" / "meeting.db"
        return MeetingLogger(db_path)
    return None
