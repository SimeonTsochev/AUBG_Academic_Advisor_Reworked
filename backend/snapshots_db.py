from __future__ import annotations

import os
import secrets
import time
from typing import Any, Dict

from supabase import Client, create_client

SNAPSHOT_TTL_SECONDS = 4 * 365 * 24 * 3600
SNAPSHOT_TABLE = "program_snapshots"

_supabase_client: Client | None = None


class SnapshotExpiredError(KeyError):
    pass


def snapshot_storage_enabled() -> bool:
    return bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def _now_ts() -> int:
    return int(time.time())


def _generate_token() -> str:
    return secrets.token_urlsafe(16)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(
        f"{name} is not configured for program snapshot storage."
    )


def _get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = _require_env("SUPABASE_URL")
    service_role_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    try:
        _supabase_client = create_client(url, service_role_key)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialize Supabase snapshot storage: {exc}"
        ) from exc
    return _supabase_client


def _cleanup_expired_snapshot(token: str) -> None:
    try:
        _get_supabase().table(SNAPSHOT_TABLE).delete().eq("token", token).execute()
    except Exception:
        # Expired rows are best-effort cleanup only.
        return


def _is_duplicate_token_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == "23505":
        return True
    message = str(exc).lower()
    return "duplicate key" in message or "already exists" in message


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def init_db() -> None:
    try:
        _get_supabase().table(SNAPSHOT_TABLE).select("token").limit(1).execute()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to access Supabase snapshot table '{SNAPSHOT_TABLE}': {exc}"
        ) from exc


def create_snapshot(payload: Dict[str, Any], catalog_year: str) -> Dict[str, Any]:
    now = _now_ts()
    expires_at = now + SNAPSHOT_TTL_SECONDS
    row = {
        "catalog_year": catalog_year,
        "payload": payload,
        "expires_at": expires_at,
    }

    for _ in range(5):
        token = _generate_token()
        try:
            _get_supabase().table(SNAPSHOT_TABLE).insert(
                {**row, "token": token}
            ).execute()
        except Exception as exc:
            if _is_duplicate_token_error(exc):
                continue
            raise RuntimeError(f"Failed to create program snapshot: {exc}") from exc

        return {
            "token": token,
            "catalog_year": catalog_year,
            "payload": payload,
            "expires_at": expires_at,
        }

    raise RuntimeError("Failed to create a unique snapshot token.")


def get_snapshot(token: str) -> Dict[str, Any]:
    try:
        response = (
            _get_supabase()
            .table(SNAPSHOT_TABLE)
            .select("token, catalog_year, payload, expires_at")
            .eq("token", token)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load program snapshot: {exc}") from exc

    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        raise KeyError(token)

    row = rows[0] if isinstance(rows[0], dict) else {}
    expires_at = _coerce_int(row.get("expires_at"))
    if _now_ts() > expires_at:
        _cleanup_expired_snapshot(token)
        raise SnapshotExpiredError(token)

    payload = row.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    catalog_year = row.get("catalog_year")
    if not isinstance(catalog_year, str):
        catalog_year = ""

    return {
        "token": str(row.get("token", token)),
        "catalog_year": catalog_year,
        "payload": payload,
        "expires_at": expires_at,
    }
