"""
Supabase session persistence for wound tracking.
Falls back to local JSON file if Supabase not configured.
"""
from __future__ import annotations
import json, os, uuid
from datetime import datetime
from pathlib import Path

_LOCAL_STORE = Path("data/sessions.json")

def _supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or url == "your_supabase_url_here":
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def save_session(patient_id: str, session_data: dict) -> str:
    """Save a wound session. Returns session_id."""
    session_id = str(uuid.uuid4())
    record = {
        "id":           session_id,
        "patient_id":   patient_id,
        "session_date": datetime.utcnow().isoformat(),
        **session_data,   # session_number comes from caller
    }

    sb = _supabase()
    if sb:
        sb.table("wound_sessions").insert(record).execute()
    else:
        _local_save(record)

    return session_id


def get_session_history(patient_id: str, limit: int = 10) -> list[dict]:
    """Return up to `limit` most recent sessions for a patient."""
    sb = _supabase()
    if sb:
        resp = (
            sb.table("wound_sessions")
            .select("*")
            .eq("patient_id", patient_id)
            .order("session_date", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    return _local_load(patient_id, limit)


def get_session_count(patient_id: str) -> int:
    return len(get_session_history(patient_id, limit=200))


# ── Local JSON fallback ───────────────────────────────────────────────────────
def _local_save(record: dict):
    _LOCAL_STORE.parent.mkdir(exist_ok=True)
    data = {}
    if _LOCAL_STORE.exists():
        data = json.loads(_LOCAL_STORE.read_text())
    pid = record["patient_id"]
    data.setdefault(pid, []).append(record)
    _LOCAL_STORE.write_text(json.dumps(data, indent=2, default=str))


def _local_load(patient_id: str, limit: int) -> list[dict]:
    if not _LOCAL_STORE.exists():
        return []
    data = json.loads(_LOCAL_STORE.read_text())
    sessions = data.get(patient_id, [])
    return sorted(sessions, key=lambda s: s.get("session_date",""), reverse=True)[:limit]
