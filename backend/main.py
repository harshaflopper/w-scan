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
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from cv.quality_gate import check_image_quality
from cv.calibration import get_px_per_mm, COIN_LABELS
from cv.geometry import compute_geometry, generate_annotated_overlay
from cv.periwound import compute_inflammation_index, generate_inflammation_heatmap
from cv.colorimetry import lab_tissue_analysis, three_way_tissue_blend, crop_to_box
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


from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def _call_with_retry(fn, *args, **kwargs):
    return fn(*args, **kwargs)

def _safe_gemini(fn, *args, fallback=None, label="gemini", **kwargs):
    try:
        return _call_with_retry(fn, *args, **kwargs)
    except Exception as e:
        print(f"[{label}] failed after retries: {e}")
        return fallback if fallback is not None else {}


def _segment_with_box(image_rgb: np.ndarray, box: dict, segmenter, mock_mode: bool) -> np.ndarray:
    """
    Segment wound using confirmed box prompt.
    For small wounds (box < 2% image area): crop + upscale → segment → downscale back.
    """
    import cv2
    h, w = image_rgb.shape[:2]
    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
    box_area = (x2 - x1) * (y2 - y1)
    image_area = h * w

    if mock_mode or box_area >= 0.02 * image_area:
        # Standard: run box prompt on full image
        return segmenter.segment_with_box(image_rgb, x1, y1, x2, y2)

    # Small wound path: crop + upscale for MedSAM
    pad_x = max(10, int((x2 - x1) * 0.25))
    pad_y = max(10, int((y2 - y1) * 0.25))
    cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)

    crop = image_rgb[cy1:cy2, cx1:cx2]
    ch, cw = crop.shape[:2]

    # Upscale so min dimension ≥ 512
    scale = max(512 / cw, 512 / ch, 1.0)
    nw, nh = int(cw * scale), int(ch * scale)
    upscaled = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

    # Box coords in upscaled space
    ux1 = int((x1 - cx1) * scale)
    uy1 = int((y1 - cy1) * scale)
    ux2 = int((x2 - cx1) * scale)
    uy2 = int((y2 - cy1) * scale)

    small_mask = segmenter.segment_with_box(upscaled, ux1, uy1, ux2, uy2)

    # Downscale mask back to crop size
    mask_crop = cv2.resize(
        small_mask.astype(np.uint8), (cw, ch),
        interpolation=cv2.INTER_NEAREST,
    ).astype(bool)

    # Place in full image canvas
    full_mask = np.zeros((h, w), dtype=bool)
    full_mask[cy1:cy2, cx1:cx2] = mask_crop
    return full_mask


# ── /suggest-box — fast Gemini wound localization ────────────────────────────
@app.post("/suggest-box")
async def suggest_box(image: UploadFile = File(...)):
    """
    Called immediately after photo upload (before user does anything).
    Returns Gemini's suggested bounding box + wound type in ~1.5s.
    """
    try:
        raw = await image.read()
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        from ai.gemini_vision import localize_wound
        result = localize_wound(pil)
        bbox = result.get("bbox_px")
        if bbox:
            w, h = pil.size
            bbox = {
                "x1": max(0, bbox["x1"]), "y1": max(0, bbox["y1"]),
                "x2": min(w, bbox["x2"]), "y2": min(h, bbox["y2"]),
            }
        return {
            "wound_found":            result.get("wound_found", False),
            "wound_type":             result.get("wound_type", "unknown"),
            "wound_type_confidence":  result.get("wound_type_confidence", 0),
            "wound_type_reasoning":   result.get("wound_type_reasoning", ""),
            "bbox_px":                bbox,
            "photo_quality":          result.get("photo_quality", {"pass": True, "issues": []}),
            "gemini_ok":              "error" not in result,
        }
    except Exception as e:
        return {
            "wound_found": False, "gemini_ok": False,
            "bbox_px": None, "wound_type": "unknown",
            "wound_type_confidence": 0, "wound_type_reasoning": "",
            "photo_quality": {"pass": True, "issues": []},
            "fallback_message": f"AI detection failed — draw box manually. ({e})",
        }


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


@app.get("/test-db")
def test_db_connection():
    from db.session_store import _supabase, save_session, get_session_history
    import traceback
    try:
        sb = _supabase()
        if not sb:
            return {"status": "error", "message": "Supabase client not initialized. Check your .env file."}
        
        test_data = {
            "session_number": 999,
            "wound_type": "db_test",
            "area_cm2": 3.14,
            "patient_message": "Test successful",
            "this_field_goes_to_raw_json": True
        }
        
        session_id = save_session("test_user_123", test_data)
        
        history = get_session_history("test_user_123")
        
        return {
            "status": "success",
            "message": "Supabase insert and select worked perfectly!",
            "session_id": session_id,
            "history_length": len(history),
            "recovered_raw_json_field": history[0].get("this_field_goes_to_raw_json") if history else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}


# ── Main analysis endpoint ────────────────────────────────────────────────────
# ── Main analysis endpoint ────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze_wound(
    image:      UploadFile       = File(...),
    coin_type:  str              = Form(...),
    patient_id: Optional[str]   = Form(None),
    wound_type: Optional[str]   = Form(None),
    # Confirmed wound bounding box in original image pixels (from BoxDrawCanvas)
    box_x1:    int               = Form(...),
    box_y1:    int               = Form(...),
    box_x2:    int               = Form(...),
    box_y2:    int               = Form(...),
    tracking_wound_type: Optional[str] = Form(None),
):
    box_px = {"x1": box_x1, "y1": box_y1, "x2": box_x2, "y2": box_y2}
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
    if wound_type:
        localization = {
            "wound_found": True,
            "wound_type": wound_type,
            "wound_type_confidence": 0.9,
            "photo_quality": {"pass": True}
        }
    else:
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

    # ── Step 4: Segmentation — use box prompt ────────────────────────────────
    try:
        wound_mask = _segment_with_box(image_rgb, box_px, _segmenter, MOCK_MODE)
    except Exception as e:
        raise HTTPException(500, f"Segmentation failed: {e}")

    if wound_mask.sum() < 30:
        # Try expanding box 20% and retry once
        h, w = image_rgb.shape[:2]
        exp = 0.20
        dx, dy = int((box_x2-box_x1)*exp), int((box_y2-box_y1)*exp)
        box_exp = {
            "x1": max(0,box_x1-dx), "y1": max(0,box_y1-dy),
            "x2": min(w,box_x2+dx), "y2": min(h,box_y2+dy),
        }
        try:
            wound_mask = _segment_with_box(image_rgb, box_exp, _segmenter, MOCK_MODE)
        except Exception:
            pass

    if wound_mask.sum() < 30:
        # Last resort: use box itself as mask
        wound_mask = np.zeros(image_rgb.shape[:2], dtype=bool)
        wound_mask[box_y1:box_y2, box_x1:box_x2] = True

    # ── Step 5: Geometry ──────────────────────────────────────────────────────
    geometry = compute_geometry(wound_mask, px_per_mm)

    # ── Step 6: Inflammation ──────────────────────────────────────────────────
    inflammation = compute_inflammation_index(image_bgr, wound_mask)

    # ── Step 6b: LAB Colorimetry (deterministic tissue %, Wannous 2010) ───────
    # Crop wound region for colorimetry (higher accuracy on the wound only)
    h_img, w_img = image_rgb.shape[:2]
    cx1 = max(0, box_x1); cy1 = max(0, box_y1)
    cx2 = min(w_img, box_x2); cy2 = min(h_img, box_y2)
    crop_rgb = image_rgb[cy1:cy2, cx1:cx2]
    # Crop the mask too
    crop_mask = wound_mask[cy1:cy2, cx1:cx2]
    colorimetry = lab_tissue_analysis(crop_rgb, crop_mask)

    # ── Step 7: SegFormer tissue classification ───────────────────────────────
    tissue_raw = _tissue_clf.classify(image_rgb, wound_mask)
    seg_map    = tissue_raw.pop("seg_map", None)
    tissue_raw.pop("confidence_map", None)

    # ── Step 8: Gemini Flash — BWAT 12-item (3-view multi-image) ─────────────
    from ai.gemini_vision import assess_bwat
    bwat = _safe_gemini(assess_bwat, pil_image,
                        box_px=box_px, crop_rgb=crop_rgb, wound_mask=crop_mask,
                        fallback={"bwat_total": 0, "bwat_severity": "unknown",
                                  "bwat": {}, "TIME": {}, "healing_phase": "unknown",
                                  "biofilm_suspected": False, "moisture_balance": "unknown",
                                  "infection_signs_visual": [], "overall_concern": "unknown"},
                        label="bwat")

    # ── Step 9: Gemini Flash — tissue validation + 3-way blend ───────────────
    from ai.gemini_vision import validate_tissue
    validation = _safe_gemini(validate_tissue, pil_image, tissue_raw,
                              box_px=box_px,
                              fallback={"overall_agreement": 1.0}, label="validate")
    # 3-way blend: colorimetry + SegFormer + Gemini
    tissue = three_way_tissue_blend(colorimetry, tissue_raw, validation)

    # ── Step 10: Load session history ─────────────────────────────────────────
    if tracking_wound_type:
        localization["wound_type"] = tracking_wound_type
        
    session_number  = get_session_count(patient_id) + 1
    raw_history = get_session_history(patient_id, limit=50)
    
    # Filter history strictly to the wound type being tracked/scanned
    target_type = localization.get("wound_type")
    session_history = [s for s in raw_history if s.get("wound_type") == target_type][:10]

    # ── Step 10b: Compute Gilman Parameter (Healing Velocity) ─────────────────
    gilman_parameter = None
    if session_history and len(session_history) > 0:
        prev_session = session_history[0]
        prev_area = prev_session.get("geometry", {}).get("area_cm2")
        prev_perim = prev_session.get("geometry", {}).get("perimeter_cm")
        curr_area = geometry.get("area_cm2")
        curr_perim = geometry.get("perimeter_cm")
        if prev_area and prev_perim and curr_area and curr_perim:
            from datetime import datetime, timezone
            prev_date_str = prev_session.get("session_date")
            if prev_date_str:
                try:
                    if prev_date_str.endswith("Z"):
                        prev_date_str = prev_date_str[:-1]
                    prev_date = datetime.fromisoformat(prev_date_str)
                    # Convert both to naive UTC or both aware. For simplicity:
                    now = datetime.utcnow()
                    # drop timezone info if any
                    prev_date = prev_date.replace(tzinfo=None)
                    days_diff = (now - prev_date).days
                    if days_diff > 0:
                        delta_area = prev_area - curr_area
                        avg_perim = (prev_perim + curr_perim) / 2.0
                        if avg_perim > 0:
                            d_cm = delta_area / avg_perim
                            gilman_cm_per_week = (d_cm / days_diff) * 7
                            gilman_parameter = round(gilman_cm_per_week, 4)
                except Exception as e:
                    print(f"Gilman calculation error: {e}")
    geometry["gilman_parameter_cm_per_week"] = gilman_parameter

    # ── Step 11: Gemini Flash — clinical synthesis ────────────────────────────
    from ai.gemini_vision import clinical_report as gemini_clinical
    assessment = _safe_gemini(
        gemini_clinical,
        pil_image, localization, geometry, tissue, bwat, inflammation,
        session_number, session_history,
        box_px=box_px,
        colorimetry=colorimetry,
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
    # Resolve the best wound_type:
    # Priority: explicit tracking lock > Gemini confirmed name > localization AI guess
    resolved_wound_type = (
        tracking_wound_type
        or assessment.get("wound_type_confirmed")
        or localization.get("wound_type", "unknown")
    )
    # Normalize: strip whitespace, lowercase for consistent folder grouping
    resolved_wound_type = resolved_wound_type.strip().lower() if resolved_wound_type else "unknown"

    session_record = {
        "session_number":      session_number,
        "wound_type":          resolved_wound_type,
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
        "est_closure_days":    assessment.get("estimated_closure_days") or _calc_est_closure(geometry, gilman_parameter),
        "composite_score":     composite,
        "clinician_report":    assessment.get("clinician_report"),
        "patient_message":     assessment.get("patient_message"),
        "clinical_report_json": assessment,
    }
    try:
        import io
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='JPEG', quality=85)
        img_bytes = img_byte_arr.getvalue()
        # Debug: confirm AI report is non-empty before saving
        print(f"[save] wound_type={session_record.get('wound_type')} "
              f"patient_msg={bool(session_record.get('patient_message'))} "
              f"clinician_report={bool(session_record.get('clinician_report'))} "
              f"bwat={session_record.get('bwat_total')}")
        session_id = save_session(patient_id, session_record, original_image_bytes=img_bytes)
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
            "auto_detected":         True,
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
            "estimated_closure_days": assessment.get("estimated_closure_days") or _calc_est_closure(geometry, gilman_parameter),
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


def _calc_est_closure(geometry: dict, gilman_parameter: float | None) -> int | None:
    if not gilman_parameter or gilman_parameter <= 0:
        return None
    # Gilman parameter is edge advancement in cm/week.
    # Time to close = (shortest_axis / 2) / gilman_parameter
    shortest_axis = geometry.get("shortest_axis_cm")
    if shortest_axis and shortest_axis > 0:
        weeks_to_close = (shortest_axis / 2.0) / gilman_parameter
        return int(weeks_to_close * 7)
    return None


# ── Active Tracking & Guidance Engine ───────────────────────────────────────
from datetime import datetime, timedelta

@app.get("/tracking/{patient_id}")
async def get_tracking_dashboard(patient_id: str):
    """
    Returns the active tracking state, triage matrix, and trend data.
    """
    from db.session_store import get_session_history
    history = get_session_history(patient_id, limit=30)
    
    if not history:
        return {"status": "NO_HISTORY", "triage": None, "schedule": None, "trend": None}
        
    latest = history[0]
    
    # 1. Triage Escalation Matrix
    triage_status = "MAINTENANCE"
    triage_message = "Your wound is tracking normally. Continue your active care plan."
    
    # Clinical Assessment Data
    ca = latest.get("clinical_assessment", {})
    infection_risk = ca.get("infection_risk", "LOW")
    gilman = ca.get("gilman_velocity_cm_per_week")
    
    # Check ER Case
    if infection_risk in ["HIGH", "CRITICAL"]:
        triage_status = "ER_REQUIRED"
        triage_message = "URGENT MEDICAL REVIEW REQUIRED: Severe signs of infection detected."
    # Check Specialist Case
    elif gilman is not None and gilman < 0.1 and len(history) > 2:
        triage_status = "SPECIALIST_REQUIRED"
        triage_message = "Wound healing is stalled. Advanced clinical intervention is required."
        
    # 2. Dynamic Scan Scheduling
    # Infected -> 24h, Sloughy/High Exudate -> 72h, Granulating -> 7d
    scan_interval_days = 3 # Default
    if triage_status == "ER_REQUIRED":
        scan_interval_days = 1
    else:
        # Check tissue composition for scan interval
        granulation = latest.get("granulation_pct", 0)
        if granulation > 80:
            scan_interval_days = 7 # Do not disturb new tissue
            
    last_scan_date = datetime.fromisoformat(latest.get("session_date", datetime.utcnow().isoformat())[:19])
    next_scan_date = last_scan_date + timedelta(days=scan_interval_days)
    
    # 3. Build trend chart
    trend = _build_trend(history[1:], latest) if len(history) > 1 else _build_trend([], latest)
    
    return {
        "status": "ACTIVE",
        "triage": {
            "status": triage_status,
            "message": triage_message
        },
        "schedule": {
            "last_scan_date": last_scan_date.isoformat(),
            "next_scan_date": next_scan_date.isoformat(),
            "interval_days": scan_interval_days
        },
        "latest_care_plan": ca.get("care_plan", {}),
        "trend": trend,
        "history": history
    }

@app.delete("/tracking/wound/{wound_type}")
async def delete_wound_folder(wound_type: str, patient_id: str = Query(...)):
    """Deletes all scans associated with a specific wound folder."""
    try:
        from db.session_store import _supabase, _get_uuid
        sb = _supabase()
        db_patient = _get_uuid(patient_id)
        
        # Delete all sessions for this wound_type and patient
        sb.table("wound_sessions").delete().eq("patient_id", db_patient).eq("wound_type", wound_type).execute()
        return {"status": "success", "message": f"Wound folder '{wound_type}' deleted."}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete wound folder: {e}")
