"""SQLite-backed replacement for the Firestore stores.

Preserves the same Job dataclass and the method signatures used by app.py
and job_processor.py so the switch is a one-line import change at the call
sites.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    user_id: str
    username: str
    prompt: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    progress: int = 0
    progress_message: str = "Queued"
    model: str = "llama3.2"
    react_mode: bool = False
    react_turn_count: int = 0
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class _Base:
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        raise NotImplementedError


class SqliteJobStore(_Base):
    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    progress INTEGER DEFAULT 0,
                    progress_message TEXT DEFAULT 'Queued',
                    model TEXT DEFAULT 'llama3.2',
                    react_mode INTEGER DEFAULT 0,
                    react_turn_count INTEGER DEFAULT 0,
                    session_id TEXT,
                    system_prompt TEXT
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);")

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            job_id=row["job_id"],
            user_id=row["user_id"],
            username=row["username"],
            prompt=row["prompt"],
            status=JobStatus(row["status"]),
            created_at=_parse_dt(row["created_at"]),
            started_at=_parse_dt(row["started_at"]),
            completed_at=_parse_dt(row["completed_at"]),
            result=json.loads(row["result"]) if row["result"] else None,
            progress=row["progress"] or 0,
            progress_message=row["progress_message"] or "Queued",
            model=row["model"] or "llama3.2",
            react_mode=bool(row["react_mode"]),
            react_turn_count=row["react_turn_count"] or 0,
            session_id=row["session_id"],
            system_prompt=row["system_prompt"],
        )

    def create_job(self, job: Job) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO jobs
                (job_id, user_id, username, prompt, status, created_at, started_at,
                 completed_at, result, progress, progress_message, model, react_mode,
                 react_turn_count, session_id, system_prompt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.user_id,
                    job.username,
                    job.prompt,
                    job.status.value,
                    _iso(job.created_at),
                    _iso(job.started_at),
                    _iso(job.completed_at),
                    json.dumps(job.result) if job.result else None,
                    job.progress,
                    job.progress_message,
                    getattr(job, "model", "llama3.2"),
                    1 if getattr(job, "react_mode", False) else 0,
                    getattr(job, "react_turn_count", 0),
                    getattr(job, "session_id", None),
                    getattr(job, "system_prompt", None),
                ),
            )

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def update_job(self, job_id: str, **fields) -> None:
        if not fields:
            return
        if "status" in fields and isinstance(fields["status"], JobStatus):
            fields["status"] = fields["status"].value
        for dt_key in ("started_at", "completed_at"):
            if dt_key in fields and isinstance(fields[dt_key], datetime):
                fields[dt_key] = _iso(fields[dt_key])
        if "result" in fields and fields["result"] is not None and not isinstance(fields["result"], str):
            fields["result"] = json.dumps(fields["result"])
        if "react_mode" in fields:
            fields["react_mode"] = 1 if fields["react_mode"] else 0

        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE job_id = ?", values)

    def list_jobs_for_user(self, user_id: str) -> List[Job]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [self._row_to_job(r) for r in rows]


class SqliteMCPStore(_Base):
    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS triggered_mcp_servers (
                    user_id TEXT PRIMARY KEY,
                    used_servers TEXT NOT NULL
                )
                """
            )

    def update_mcp_triggered(self, user_id: str, used_servers: List[Dict[str, str]]) -> None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT used_servers FROM triggered_mcp_servers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            existing: Dict[str, List[str]] = json.loads(row["used_servers"]) if row else {}

            for entry in used_servers:
                server = entry["server"]
                tool = entry["tool"]
                existing.setdefault(server, [])
                if tool not in existing[server]:
                    existing[server].append(tool)

            c.execute(
                "INSERT OR REPLACE INTO triggered_mcp_servers (user_id, used_servers) VALUES (?, ?)",
                (user_id, json.dumps(existing)),
            )

    def get_used_servers(self, user_id: str) -> Dict[str, List[str]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT used_servers FROM triggered_mcp_servers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return json.loads(row["used_servers"]) if row else {}
