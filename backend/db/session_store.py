"""
Supabase session persistence for WoundScan V2.

Storage strategy (schema-safe):
- wound_sessions: core geometry metrics (all columns exist in schema)
- clinical_assessments: BWAT scores + full AI report packed as JSON into
  'dressing_recommendation' TEXT column (avoids needing patient_message /
  clinician_report columns which may not exist in live Supabase).
- wound_media: image storage URLs
"""
from __future__ import annotations
import json, os, uuid
from datetime import datetime


def _supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or url == "your_supabase_url_here":
        raise ValueError("SUPABASE_URL not configured.")
    from supabase import create_client
    return create_client(url, key)


def _get_uuid(pid: str) -> str:
    try:
        uuid.UUID(pid)
        return pid
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, pid))


def _upload_to_storage(sb, file_bytes: bytes, filename: str) -> str | None:
    try:
        sb.storage.from_("wound-images").upload(
            filename, file_bytes, {"content-type": "image/jpeg"}
        )
        return sb.storage.from_("wound-images").get_public_url(filename)
    except Exception as e:
        print(f"[Storage] Upload failed: {e}")
        return None


def save_session(
    patient_id: str,
    session_data: dict,
    original_image_bytes: bytes = None,
) -> str:
    """
    Persist a wound session. AI report is packed into dressing_recommendation
    as JSON to avoid dependency on columns that may not exist in live Supabase.
    """
    session_id = str(uuid.uuid4())
    db_pid = _get_uuid(patient_id)
    sb = _supabase()

    # 1. Ensure patient row exists (ignore duplicate errors)
    try:
        sb.table("patients").insert({"id": db_pid, "user_id": patient_id}).execute()
    except Exception:
        pass

    # 2. Core wound session (only columns guaranteed by schema)
    sb.table("wound_sessions").insert({
        "id":                          session_id,
        "patient_id":                  db_pid,
        "session_date":                datetime.utcnow().isoformat(),
        "session_number":              session_data.get("session_number", 1),
        "wound_type":                  session_data.get("wound_type"),
        "area_cm2":                    session_data.get("area_cm2"),
        "perimeter_cm":                session_data.get("perimeter_cm"),
        "longest_axis_cm":             session_data.get("longest_axis_cm"),
        "shortest_axis_cm":            session_data.get("shortest_axis_cm"),
        "gilman_parameter_cm_per_week": session_data.get("gilman_parameter_cm_per_week"),
        "granulation_pct":             session_data.get("granulation_pct"),
        "slough_pct":                  session_data.get("slough_pct"),
        "necrotic_pct":                session_data.get("necrotic_pct"),
        "epithelial_pct":              session_data.get("epithelial_pct"),
        "dominant_tissue":             session_data.get("dominant_tissue"),
        "healing_trajectory":          session_data.get("healing_trajectory"),
    }).execute()

    # 3. Clinical assessment — pack EVERYTHING into dressing_recommendation JSON
    #    so we never depend on optional columns (patient_message, clinician_report)
    report_json  = session_data.get("clinical_report_json", {}) or {}
    care_plan    = report_json.get("care_plan", {}) or {}
    bwat_items   = (session_data.get("bwat_json", {}) or {}).get("bwat", {}) or {}

    # This blob is the single source of truth for the AI report
    ai_blob = json.dumps({
        "patient_message":  session_data.get("patient_message"),
        "clinician_report": session_data.get("clinician_report"),
        "care_plan":        care_plan,
        "TIME":             report_json.get("TIME", {}),
        "bwat_total":       session_data.get("bwat_total"),
        "bwat_severity":    session_data.get("bwat_severity"),
        "infection_risk":   session_data.get("infection_risk"),
        "est_closure_days": session_data.get("est_closure_days"),
        "push_score":       session_data.get("push_score"),
        "nerds_score":      session_data.get("nerds_score"),
        "stones_score":     session_data.get("stones_score"),
        "healing_trajectory": session_data.get("healing_trajectory"),
    }, ensure_ascii=False)

    # Insert only the columns that definitely exist in the schema
    try:
        sb.table("clinical_assessments").insert({
            "session_id":              session_id,
            "bwat_total":              session_data.get("bwat_total"),
            "bwat_severity":           session_data.get("bwat_severity"),
            "bwat_depth":              bwat_items.get("depth", {}).get("finding"),
            "bwat_edges":              bwat_items.get("edges", {}).get("finding"),
            "time_t_tissue":           report_json.get("TIME", {}).get("T"),
            "time_i_infection":        report_json.get("TIME", {}).get("I"),
            "time_m_moisture":         report_json.get("TIME", {}).get("M"),
            "time_e_edge":             report_json.get("TIME", {}).get("E"),
            "nerds_score":             session_data.get("nerds_score"),
            "stones_score":            session_data.get("stones_score"),
            "infection_risk":          session_data.get("infection_risk"),
            "push_score":              session_data.get("push_score"),
            "est_closure_days":        session_data.get("est_closure_days"),
            # dressing_recommendation stores the full AI report blob as JSON
            "dressing_recommendation": ai_blob,
        }).execute()
    except Exception as e:
        # Try minimal insert — only absolutely guaranteed columns
        print(f"[DB] clinical_assessments full insert failed ({e}), trying minimal…")
        try:
            sb.table("clinical_assessments").insert({
                "session_id":              session_id,
                "dressing_recommendation": ai_blob,
            }).execute()
        except Exception as e2:
            print(f"[DB] clinical_assessments minimal insert also failed: {e2}")

    # 4. Upload original image to Supabase Storage
    if original_image_bytes:
        filename   = f"{db_pid}/{session_id}_original.jpg"
        public_url = _upload_to_storage(sb, original_image_bytes, filename)
        if public_url:
            try:
                sb.table("wound_media").insert({
                    "session_id":  session_id,
                    "media_type":  "original",
                    "storage_url": public_url,
                }).execute()
            except Exception as e:
                print(f"[DB] wound_media insert failed: {e}")

    return session_id


def get_session_history(patient_id: str, limit: int = 10) -> list[dict]:
    """Return fully-joined session history, flattened for frontend consumption."""
    sb   = _supabase()
    dbid = _get_uuid(patient_id)

    resp = (
        sb.table("wound_sessions")
        .select("*, clinical_assessments(*), wound_media(storage_url)")
        .eq("patient_id", dbid)
        .order("session_date", desc=True)
        .limit(limit)
        .execute()
    )
    if not resp.data:
        return []

    out = []
    for row in resp.data:
        ca        = row.get("clinical_assessments") or {}
        media     = row.get("wound_media") or []
        image_url = media[0].get("storage_url") if media else None

        # Decode the AI blob from dressing_recommendation
        blob: dict = {}
        raw = ca.get("dressing_recommendation") if ca else None
        if raw:
            try:
                blob = json.loads(raw)
            except Exception:
                # Legacy: plain text dressing type stored here
                blob = {"care_plan": {"dressing_type": raw}}

        # Merge: blob values take priority for AI fields;
        # direct CA columns are used as fallback for BWAT/infection
        flat = {
            **row,
            # AI report fields (from blob)
            "patient_message":  blob.get("patient_message"),
            "clinician_report": blob.get("clinician_report"),
            "care_plan":        blob.get("care_plan") or {},
            "clinical_report_json": {"care_plan": blob.get("care_plan") or {}},
            "TIME": blob.get("TIME") or {
                "T": ca.get("time_t_tissue")  if ca else None,
                "I": ca.get("time_i_infection") if ca else None,
                "M": ca.get("time_m_moisture") if ca else None,
                "E": ca.get("time_e_edge")     if ca else None,
            },
            # Score fields — prefer blob (always fresh), fall back to CA columns
            "bwat_total":     blob.get("bwat_total")     or (ca.get("bwat_total")    if ca else None),
            "bwat_severity":  blob.get("bwat_severity")  or (ca.get("bwat_severity") if ca else None),
            "infection_risk": blob.get("infection_risk") or (ca.get("infection_risk") if ca else None),
            "est_closure_days": blob.get("est_closure_days") or (ca.get("est_closure_days") if ca else None),
            "image_url": image_url,
        }
        flat.pop("clinical_assessments", None)
        flat.pop("wound_media", None)
        out.append(flat)

    return out


def get_session_count(patient_id: str) -> int:
    try:
        return len(get_session_history(patient_id, limit=200))
    except Exception:
        return 0
