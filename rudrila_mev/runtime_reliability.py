from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeStateStore:
    """Durable-ish runtime state with atomic file fallback and optional Postgres.

    The file backend survives ordinary process restarts when the filesystem is
    preserved. When POSTBUY_DATABASE_URL/DATABASE_URL is configured, Postgres
    becomes the authoritative cross-instance backend and the file remains a
    local fallback/cache.
    """

    def __init__(
        self,
        *,
        service_key: str,
        file_path: str,
        database_url: str | None = None,
        event_log_path: str | None = None,
    ) -> None:
        self.service_key = str(service_key)
        self.file_path = Path(file_path)
        self.database_url = (database_url or "").strip() or None
        self.event_log_path = Path(event_log_path) if event_log_path else None
        self._lock = threading.Lock()
        self._pg_ready = False
        self._pg_error: str | None = None

    @property
    def backend(self) -> str:
        if self.database_url and self._pg_ready:
            return "postgres+file"
        if self.database_url:
            return "file(postgres-unavailable)"
        return "file"

    @property
    def postgres_error(self) -> str | None:
        return self._pg_error

    def _connect(self):
        if not self.database_url:
            raise RuntimeError("database URL not configured")
        try:
            import psycopg  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._pg_error = f"{type(exc).__name__}: {exc}"
            raise
        return psycopg.connect(self.database_url, connect_timeout=5)

    def initialize(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if self.event_log_path:
            self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            return
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS rudrila_runtime_state (
                            service_key TEXT PRIMARY KEY,
                            payload JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS rudrila_runtime_events (
                            id BIGSERIAL PRIMARY KEY,
                            service_key TEXT NOT NULL,
                            event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            payload JSONB NOT NULL
                        )
                        """
                    )
                conn.commit()
            self._pg_ready = True
            self._pg_error = None
        except Exception as exc:
            self._pg_ready = False
            self._pg_error = f"{type(exc).__name__}: {exc}"

    def _load_file(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.file_path.read_text())
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _save_file(self, payload: dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.file_path.name + ".",
            suffix=".tmp",
            dir=str(self.file_path.parent),
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, separators=(",", ":"), default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, self.file_path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except Exception:
                pass

    def load(self) -> dict[str, Any] | None:
        with self._lock:
            if self.database_url and not self._pg_ready:
                self.initialize()
            if self._pg_ready:
                try:
                    with self._connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT payload FROM rudrila_runtime_state WHERE service_key=%s",
                                (self.service_key,),
                            )
                            row = cur.fetchone()
                    if row and isinstance(row[0], dict):
                        self._pg_error = None
                        return dict(row[0])
                except Exception as exc:
                    self._pg_ready = False
                    self._pg_error = f"{type(exc).__name__}: {exc}"
            return self._load_file()

    def save(self, payload: dict[str, Any]) -> None:
        row = dict(payload)
        row["checkpoint_saved_at"] = utc_now()
        with self._lock:
            self._save_file(row)
            if self.database_url and not self._pg_ready:
                self.initialize()
            if self._pg_ready:
                try:
                    with self._connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO rudrila_runtime_state(service_key,payload,updated_at)
                                VALUES (%s,%s::jsonb,NOW())
                                ON CONFLICT(service_key) DO UPDATE SET
                                  payload=EXCLUDED.payload,
                                  updated_at=NOW()
                                """,
                                (
                                    self.service_key,
                                    json.dumps(row, separators=(",", ":"), default=str),
                                ),
                            )
                        conn.commit()
                    self._pg_error = None
                except Exception as exc:
                    self._pg_ready = False
                    self._pg_error = f"{type(exc).__name__}: {exc}"

    def append_event(self, event: dict[str, Any]) -> None:
        row = dict(event)
        line = json.dumps(row, separators=(",", ":"), default=str)
        with self._lock:
            if self.event_log_path:
                self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.event_log_path.open("a") as f:
                    f.write(line + "\n")
                    f.flush()
            if self.database_url and not self._pg_ready:
                self.initialize()
            if self._pg_ready:
                try:
                    with self._connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO rudrila_runtime_events(service_key,payload)
                                VALUES (%s,%s::jsonb)
                                """,
                                (self.service_key, line),
                            )
                        conn.commit()
                    self._pg_error = None
                except Exception as exc:
                    self._pg_ready = False
                    self._pg_error = f"{type(exc).__name__}: {exc}"
