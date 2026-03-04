from __future__ import annotations

import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

SNAPSHOT_TTL_SECONDS = 4 * 365 * 24 * 3600
SNAPSHOT_DB_PATH = Path(__file__).resolve().parent / "data" / "snapshots.sqlite"


class SnapshotExpiredError(KeyError):
    pass


def _connect() -> sqlite3.Connection:
    SNAPSHOT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SNAPSHOT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS program_snapshots (
              token TEXT PRIMARY KEY,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              catalog_year TEXT NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def create_snapshot(payload: Dict[str, Any], catalog_year: str) -> Dict[str, int | str]:
    init_db()
    created_at = int(time.time())
    expires_at = created_at + SNAPSHOT_TTL_SECONDS
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    with _connect() as conn:
        for _ in range(5):
            token = secrets.token_urlsafe(16)
            try:
                conn.execute(
                    """
                    INSERT INTO program_snapshots (token, created_at, expires_at, catalog_year, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (token, created_at, expires_at, catalog_year, payload_json),
                )
                conn.commit()
                return {
                    "token": token,
                    "created_at": created_at,
                    "expires_at": expires_at,
                }
            except sqlite3.IntegrityError:
                continue

    raise RuntimeError("Failed to create a unique snapshot token.")


def get_snapshot(token: str) -> Dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT token, created_at, expires_at, catalog_year, payload_json
            FROM program_snapshots
            WHERE token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            raise KeyError(token)

        expires_at = int(row["expires_at"])
        now = int(time.time())
        if now > expires_at:
            conn.execute("DELETE FROM program_snapshots WHERE token = ?", (token,))
            conn.commit()
            raise SnapshotExpiredError(token)

        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}

        return {
            "token": row["token"],
            "created_at": int(row["created_at"]),
            "expires_at": expires_at,
            "catalog_year": row["catalog_year"],
            "payload": payload,
        }
