"""
FastAPI — WoundScan daily tracking pipeline.

Full pipeline per session:
  1. Quality gate (OpenCV)
  2. Gemini Flash Role A — photo QA + wound localization + type
  3. Calibration (coin → px/mm)
  4. SAM2/MedSAM segmentation using Gemini bbox
  5. Geometry (area, perimeter, axes, circularity)
  6. Periwound inflammation (Wannous erythema)
  7. SegFormer tissue classification
  8. Gemini Flash Role B — BWAT 12-item visual assessment
  9. Gemini Flash Role C — tissue validation + blend
  10. Load session history (Supabase / local JSON)
  11. Gemini Flash Role D — full clinical synthesis
  12. Save session
  13. Return full structured response + annotated images

Set MOCK_MODE=true to bypass model weights (development).
"""

from __future__ import annotations
import base64, io, os, traceback, uuid
from datetime import date, datetime
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from cv.quality_gate import check_image_quality
from cv.calibration import get_px_per_mm, COIN_LABELS
from cv.geometry import compute_geometry, generate_annotated_overlay
from cv.periwound import compute_inflammation_index, generate_inflammation_heatmap
from scoring.engine import ClinicalScoringEngine
from db.session_store import save_session, get_session_history, get_session_count

load_dotenv()

MOCK_MODE: bool = os.getenv("MOCK_MODE", "false").lower() == "true"

app = FastAPI(title="WoundScan API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Model singletons ──────────────────────────────────────────────────────────
_segmenter  = None
_tissue_clf = None
_scorer     = ClinicalScoringEngine()


@app.on_event("startup")
async def load_models():
    global _segmenter, _tissue_clf

    if MOCK_MODE:
        from cv.mock_segmenter import MockWoundSegmenter
        from cv.mock_tissue_classifier import MockTissueClassifier
        _segmenter  = MockWoundSegmenter()
        _tissue_clf = MockTissueClassifier()
        print("[startup] ⚠  MOCK_MODE — synthetic models loaded")
        return

    medsam_path    = os.getenv("MEDSAM_WEIGHTS_PATH",  "models/medsam_vit_b.pth")
    segformer_path = os.getenv("SEGFORMER_MODEL_PATH", "models/segformer_wound")

    try:
        from cv.segmenter import WoundSegmenter
        _segmenter = WoundSegmenter(weights_path=medsam_path)
        print(f"[startup] ✓ MedSAM loaded")
    except Exception as e:
        print(f"[startup] ✗ MedSAM failed: {e}")

    try:
        from cv.tissue_classifier import TissueClassifier
        _tissue_clf = TissueClassifier(model_path=segformer_path)
        print(f"[startup] ✓ SegFormer loaded")
    except Exception as e:
        print(f"[startup] ✗ SegFormer failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _np_to_b64(img_rgb: np.ndarray) -> str:
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf.tobytes()).decode()


def _load_image(upload: UploadFile):
    raw = upload.file.read()
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    rgb = np.array(pil)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return pil, rgb, bgr


def _safe_gemini(fn, *args, fallback=None, label="gemini"):
    try:
        return fn(*args)
    except Exception as e:
        print(f"[{label}] failed: {e}")
        return fallback if fallback is not None else {}


# ── Utility endpoints ─────────────────────────────────────────────────────────
@app.get("/coins")
def list_coins():
    return [{"key": k, "label": v} for k, v in COIN_LABELS.items()]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mock_mode": MOCK_MODE,
        "medsam_loaded":    _segmenter  is not None,
        "segformer_loaded": _tissue_clf is not None,
    }


@app.get("/history/{patient_id}")
def get_patient_history(patient_id: str, limit: int = 20):
    """Return all sessions for a patient — used by the dashboard chart."""
    sessions = get_session_history(patient_id, limit=limit)
    return {"patient_id": patient_id, "sessions": sessions, "count": len(sessions)}


# ── Main analysis endpoint ────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze_wound(
    image:      UploadFile       = File(...),
    coin_type:  str              = Form(...),
    patient_id: Optional[str]   = Form(None),
    # Legacy / fallback click coords (used if Gemini bbox not available)
    click_x:    Optional[int]   = Form(None),
    click_y:    Optional[int]   = Form(None),
    # Legacy temporal fields (kept for backward compat)
    prev_area_cm2:           Optional[float] = Form(None),
    prev_perimeter_cm:       Optional[float] = Form(None),
    prev_composite_score:    Optional[float] = Form(None),
    prev_date:               Optional[str]   = Form(None),
    initial_area_cm2:        Optional[float] = Form(None),
    initial_perimeter_cm:    Optional[float] = Form(None),
):
    if _segmenter is None or _tissue_clf is None:
        raise HTTPException(503, "Models not loaded. Check logs or set MOCK_MODE=true.")

    # ── Load image ────────────────────────────────────────────────────────────
    try:
        pil_image, image_rgb, image_bgr = _load_image(image)
    except Exception:
        raise HTTPException(400, "Cannot decode image. Send JPEG or PNG.")

    # Auto-generate patient_id if not provided (device-session based)
    if not patient_id:
        patient_id = f"anon_{uuid.uuid4().hex[:12]}"

    # ── Step 1: OpenCV quality gate ───────────────────────────────────────────
    quality = check_image_quality(image_bgr)

    # ── Step 2: Gemini Flash — photo QA + wound localization ─────────────────
    from ai.gemini_vision import localize_wound
    localization = _safe_gemini(
        localize_wound, pil_image,
        fallback={"wound_found": True, "wound_type": "unknown",
                  "wound_type_confidence": 0.0, "photo_quality": {"pass": True}},
        label="localize",
    )

    # Photo quality gate — Gemini takes precedence over OpenCV
    gemini_quality = localization.get("photo_quality", {})
    if not gemini_quality.get("pass", True) and not quality.get("pass", True):
        return {
            "status": "quality_failed",
            "issues":  quality.get("issues", []),
            "gemini_advice": gemini_quality.get("advice"),
            "quality": quality,
        }

    if not localization.get("wound_found", True):
        return {
            "status": "wound_not_found",
            "detail": "No wound detected in image. Ensure wound is clearly visible.",
            "gemini_advice": gemini_quality.get("advice"),
        }

    # ── Step 3: Calibration ───────────────────────────────────────────────────
    px_per_mm, cal_ok, cal_debug = get_px_per_mm(image_bgr, coin_type)
    if not cal_ok or px_per_mm is None:
        return {
            "status": "calibration_failed",
            "detail": cal_debug.get("error", "Coin not detected"),
            "tip": "Place the coin flat and ensure it is fully visible with clear contrast.",
        }

    # ── Step 4: Segmentation ──────────────────────────────────────────────────
    # Use Gemini bbox_px if available, else fall back to click coords
    bbox_px = localization.get("bbox_px")
    try:
        if bbox_px and not MOCK_MODE:
            wound_mask = _segmenter.segment_with_box(
                image_rgb,
                bbox_px["x1"], bbox_px["y1"],
                bbox_px["x2"], bbox_px["y2"],
            )
        elif click_x is not None and click_y is not None:
            if MOCK_MODE:
                wound_mask = _segmenter.segment(image_rgb, click_x, click_y, px_per_mm=px_per_mm)
            else:
                wound_mask = _segmenter.segment(image_rgb, click_x, click_y)
        else:
            # Fallback: use Gemini bbox midpoint as click
            if bbox_px:
                cx = (bbox_px["x1"] + bbox_px["x2"]) // 2
                cy = (bbox_px["y1"] + bbox_px["y2"]) // 2
                if MOCK_MODE:
                    wound_mask = _segmenter.segment(image_rgb, cx, cy, px_per_mm=px_per_mm)
                else:
                    wound_mask = _segmenter.segment(image_rgb, cx, cy)
            else:
                raise HTTPException(400, "No click coords or wound bbox available.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Segmentation failed: {e}")

    if wound_mask.sum() < 50:
        return {
            "status": "segmentation_failed",
            "detail": "Wound region too small or could not be isolated. Try clicking directly on the wound.",
        }

    # ── Step 5: Geometry ──────────────────────────────────────────────────────
    geometry = compute_geometry(wound_mask, px_per_mm)

    # ── Step 6: Inflammation ──────────────────────────────────────────────────
    inflammation = compute_inflammation_index(image_bgr, wound_mask)

    # ── Step 7: SegFormer tissue classification ───────────────────────────────
    tissue_raw = _tissue_clf.classify(image_rgb, wound_mask)
    seg_map    = tissue_raw.pop("seg_map", None)
    tissue_raw.pop("confidence_map", None)

    # ── Step 8: Gemini Flash — BWAT 12-item ──────────────────────────────────
    from ai.gemini_vision import assess_bwat
    bwat = _safe_gemini(assess_bwat, pil_image, fallback={
        "bwat_total": 0, "bwat_severity": "unknown",
        "bwat": {}, "TIME": {}, "healing_phase": "unknown",
        "biofilm_suspected": False, "moisture_balance": "unknown",
        "infection_signs_visual": [], "overall_concern": "unknown",
    }, label="bwat")

    # ── Step 9: Gemini Flash — tissue validation + blend ─────────────────────
    from ai.gemini_vision import validate_tissue, blend_tissue
    validation = _safe_gemini(validate_tissue, pil_image, tissue_raw,
                              fallback={"overall_agreement": 1.0}, label="validate")
    tissue = blend_tissue(tissue_raw, validation)

    # ── Step 10: Load session history ─────────────────────────────────────────
    session_number  = get_session_count(patient_id) + 1
    session_history = get_session_history(patient_id, limit=10)

    # ── Step 11: Gemini Flash — clinical synthesis ────────────────────────────
    from ai.gemini_vision import clinical_report as gemini_clinical
    assessment = _safe_gemini(
        gemini_clinical,
        pil_image,
        localization,
        geometry,
        tissue,
        bwat,
        inflammation,
        session_number,
        session_history,
        fallback={"error": "Clinical synthesis unavailable"},
        label="clinical",
    )

    # ── Legacy scoring (backward compat / fallback) ───────────────────────────
    composite = _scorer.composite_score(
        tissue_pct=tissue,
        inflammation_index=inflammation.get("inflammation_index", 0),
        circularity=geometry.get("circularity", 0),
    )

    # ── Step 12: Save session ─────────────────────────────────────────────────
    session_record = {
        "session_number":      session_number,
        "wound_type":          localization.get("wound_type", "unknown"),
        "wound_type_confidence": localization.get("wound_type_confidence", 0),
        "area_cm2":            geometry.get("area_cm2", 0),
        "perimeter_cm":        geometry.get("perimeter_cm", 0),
        "circularity":         geometry.get("circularity", 0),
        "longest_axis_cm":     geometry.get("longest_axis_cm", 0),
        "inflammation_index":  inflammation.get("inflammation_index", 0),
        "granulation_pct":     tissue.get("granulation_pct", 0),
        "slough_pct":          tissue.get("slough_pct", 0),
        "necrotic_pct":        tissue.get("necrotic_pct", 0),
        "epithelial_pct":      tissue.get("epithelial_pct", 0),
        "dominant_tissue":     tissue.get("dominant_tissue", "unknown"),
        "tissue_source":       tissue.get("tissue_source", "cv_model"),
        "gemini_agreement":    tissue.get("gemini_agreement", 1.0),
        "bwat_total":          bwat.get("bwat_total", 0),
        "bwat_severity":       bwat.get("bwat_severity", "unknown"),
        "bwat_json":           bwat,
        "healing_phase":       bwat.get("healing_phase", "unknown"),
        "moisture_balance":    bwat.get("moisture_balance", "unknown"),
        "biofilm_suspected":   bwat.get("biofilm_suspected", False),
        "push_score":          assessment.get("primary_score", {}).get("value") if assessment.get("primary_score", {}).get("name") == "PUSH" else None,
        "resvech_score":       assessment.get("primary_score", {}).get("value") if assessment.get("primary_score", {}).get("name") == "RESVECH" else None,
        "nerds_score":         assessment.get("nerds", {}).get("score"),
        "stones_score":        assessment.get("stones", {}).get("score"),
        "infection_risk":      assessment.get("infection_risk", "UNKNOWN"),
        "healing_trajectory":  assessment.get("healing_trajectory", "FIRST_SESSION"),
        "est_closure_days":    assessment.get("estimated_closure_days"),
        "composite_score":     composite,
        "clinical_report_json": assessment,
    }
    try:
        session_id = save_session(patient_id, session_record)
    except Exception as e:
        session_id = None
        print(f"[session] save failed: {e}")

    # ── Step 13: Annotated images ─────────────────────────────────────────────
    annotated_rgb = generate_annotated_overlay(image_rgb, wound_mask, seg_map)
    heatmap_rgb   = generate_inflammation_heatmap(image_bgr, wound_mask)

    # ── Build alerts ──────────────────────────────────────────────────────────
    alerts = _build_alerts(assessment, geometry, session_number, session_history)

    return {
        "status":        "success",
        "session_id":    session_id,
        "session_number": session_number,
        "patient_id":    patient_id,

        "localization": {
            "wound_type":            localization.get("wound_type"),
            "wound_type_confidence": localization.get("wound_type_confidence"),
            "wound_type_reasoning":  localization.get("wound_type_reasoning"),
            "auto_detected":         bbox_px is not None,
        },

        "calibration": {
            "px_per_mm": round(px_per_mm, 4),
            "method":    cal_debug.get("method"),
        },

        "quality":     quality,
        "geometry":    geometry,
        "tissue":      tissue,
        "inflammation": inflammation,
        "bwat":        bwat,

        "clinical_assessment": assessment,

        "scores": {
            "composite_score": composite,
            "healing_trajectory": assessment.get("healing_trajectory", "FIRST_SESSION"),
            "infection_risk":    assessment.get("infection_risk", "UNKNOWN"),
            "primary_score":     assessment.get("primary_score"),
            "nerds":             assessment.get("nerds"),
            "stones":            assessment.get("stones"),
            "estimated_closure_days": assessment.get("estimated_closure_days"),
            "forty_percent_rule":     assessment.get("forty_percent_rule"),
        },

        "care_plan":   assessment.get("care_plan", {}),
        "red_flags":   assessment.get("red_flags", []),
        "alerts":      alerts,

        "patient_message":  assessment.get("patient_message", ""),
        "clinician_report": assessment.get("clinician_report", ""),

        "images": {
            "annotated_b64": _np_to_b64(annotated_rgb),
            "heatmap_b64":   _np_to_b64(heatmap_rgb),
        },

        # Trend data for frontend charts
        "trend": _build_trend(session_history, session_record),
    }


# ── Alert builder ─────────────────────────────────────────────────────────────
def _build_alerts(assessment: dict, geometry: dict,
                  session_number: int, history: list) -> list[dict]:
    alerts = []

    # Propagate red flags from Gemini
    for flag in assessment.get("red_flags", []):
        alerts.append({"type": "red_flag", "severity": "urgent", "message": flag})

    # Infection alert
    risk = assessment.get("infection_risk", "LOW")
    if risk == "CRITICAL":
        alerts.append({
            "type": "infection",
            "severity": "urgent",
            "message": "Critical infection indicators — seek immediate medical care.",
            "action": "Go to emergency or call your doctor today.",
        })
    elif risk == "HIGH":
        alerts.append({
            "type": "infection",
            "severity": "warning",
            "message": "High infection risk detected (STONES criteria met).",
            "action": "Contact clinician within 24 hours. Systemic antibiotics may be needed.",
        })

    # 40% rule
    rule = assessment.get("forty_percent_rule", {})
    if rule.get("applicable") and rule.get("status") == "BELOW_TARGET":
        alerts.append({
            "type": "non_healing",
            "severity": "warning",
            "message": f"Wound has only reduced {rule.get('current_reduction_pct',0):.0f}% "
                       f"(target: 40% at 4 weeks — Sheehan 2003).",
            "action": rule.get("action", "Reassess treatment plan."),
        })

    # Area increase
    if history and session_number > 1:
        prev_area = history[0].get("area_cm2", 0) if history else 0
        curr_area = geometry.get("area_cm2", 0)
        if prev_area > 0 and curr_area > prev_area * 1.15:
            alerts.append({
                "type": "deteriorating",
                "severity": "warning",
                "message": f"Wound area increased >15% since last session "
                           f"({prev_area:.2f} → {curr_area:.2f} cm²).",
                "action": "Review dressing, infection status, and underlying condition.",
            })

    # Healing milestone
    if history:
        baseline = history[-1].get("area_cm2", 0) if history else 0
        curr = geometry.get("area_cm2", 0)
        if baseline > 0 and curr <= baseline * 0.5:
            alerts.append({
                "type": "milestone",
                "severity": "info",
                "message": "Wound has healed more than 50% from baseline — great progress!",
                "action": "Continue current management.",
            })

    return alerts


# ── Trend builder for frontend charts ─────────────────────────────────────────
def _build_trend(history: list, current: dict) -> dict:
    all_sessions = list(reversed(history)) + [current]

    return {
        "area_cm2":       [s.get("area_cm2", 0)        for s in all_sessions],
        "bwat_total":     [s.get("bwat_total", 0)       for s in all_sessions],
        "granulation_pct":[s.get("granulation_pct", 0)  for s in all_sessions],
        "slough_pct":     [s.get("slough_pct", 0)       for s in all_sessions],
        "necrotic_pct":   [s.get("necrotic_pct", 0)     for s in all_sessions],
        "epithelial_pct": [s.get("epithelial_pct", 0)   for s in all_sessions],
        "inflammation":   [s.get("inflammation_index", 0) for s in all_sessions],
        "session_dates":  [s.get("session_date", "")[:10] for s in all_sessions],
        "session_numbers":[s.get("session_number", 0)   for s in all_sessions],
    }
