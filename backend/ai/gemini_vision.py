"""
Gemini 2.5 Flash — all visual intelligence roles for WoundScan.

Role A : Photo quality gate + wound localization + type detection
Role B : Full BWAT 12-item visual assessment + TIME framework
Role C : Tissue validation (cross-check SegFormer estimates)
Role D : Clinical synthesis — full evidence-based report

Medical references embedded in prompts:
  NPUAP/EPUAP/PPPIA 2019 — pressure injury staging, PUSH v3.0
  IWGDF 2023             — DFU Wagner/UT staging, 40% rule (Sheehan 2003)
  EWMA 2022              — VLU RESVECH 2.0, CEAP
  Schultz 2003           — TIME framework
  Sibbald 2006           — NERDS/STONES infection criteria
  Bates-Jensen 1995      — BWAT scoring
"""

from __future__ import annotations
import json, os, re
import numpy as np
from PIL import Image
import google.generativeai as genai
from google.generativeai.types import GenerationConfig


import random

def _model(system: str | None = None, json_schema: dict | None = None) -> genai.GenerativeModel:
    keys = []
    if "GEMINI_API_KEY" in os.environ: keys.append(os.environ["GEMINI_API_KEY"])
    if "GEMINI_API_KEY_1" in os.environ: keys.append(os.environ["GEMINI_API_KEY_1"])
    if "GEMINI_API_KEY_2" in os.environ: keys.append(os.environ["GEMINI_API_KEY_2"])
    
    if not keys:
        raise ValueError("No GEMINI_API_KEY found")
        
    api_key = random.choice(keys)
    genai.configure(api_key=api_key)
    gen_cfg: dict = {"temperature": 0.1}  # low temp = consistent medical scoring
    if json_schema:
        gen_cfg["response_mime_type"] = "application/json"
        gen_cfg["response_schema"]    = json_schema
    kwargs: dict = {
        "model_name":        "gemini-2.5-flash",
        "generation_config": GenerationConfig(**gen_cfg),
    }
    if system:
        kwargs["system_instruction"] = system
    return genai.GenerativeModel(**kwargs)


def _parse(text: str) -> dict:
    """Robustly parse JSON from Gemini response (fallback if schema not used)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        text = m.group(1)
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {"error": "parse_failed", "raw": text[:400]}


# ─────────────────────────────────────────────────────────────────────────────
# ROLE A — Photo QA + Wound Localization + Type Detection
# ─────────────────────────────────────────────────────────────────────────────
_LOCALIZE_PROMPT = """You are a wound care imaging specialist. Examine this image carefully.

Return ONLY valid JSON (no markdown fences):
{
  "photo_quality": {
    "pass": true,
    "issues": [],
    "lighting": "good|dark|overexposed",
    "sharpness": "sharp|slightly_blurry|blurry",
    "wound_fully_visible": true,
    "advice": "specific advice for retake if needed, else null"
  },
  "wound_found": true,
  "wound_type": "diabetic_foot_ulcer|pressure_ulcer|venous_leg_ulcer|arterial_ulcer|surgical_wound|traumatic_laceration|abrasion|burn|skin_tear|unknown",
  "wound_type_confidence": 0.85,
  "wound_type_reasoning": "brief clinical reasoning",
  "wound_location_in_image": "e.g. centre-left, lower third",
  "bbox_pct": {"top": 20, "left": 30, "bottom": 70, "right": 65},
  "coin_visible": true,
  "coin_approximate_location": "right of wound"
}"""


def localize_wound(image_pil: Image.Image) -> dict:
    """Role A: Photo QA + wound detection + bounding box + wound type."""
    resp = _model().generate_content([_LOCALIZE_PROMPT, image_pil])
    result = _parse(resp.text)

    # Convert bbox_pct → pixel coords (with 10% padding)
    if isinstance(result.get("bbox_pct"), dict):
        w, h = image_pil.size
        b = result["bbox_pct"]
        pad_x = w * 0.08
        pad_y = h * 0.08
        result["bbox_px"] = {
            "x1": max(0,  int(b.get("left",   20) / 100 * w - pad_x)),
            "y1": max(0,  int(b.get("top",    20) / 100 * h - pad_y)),
            "x2": min(w,  int(b.get("right",  80) / 100 * w + pad_x)),
            "y2": min(h,  int(b.get("bottom", 80) / 100 * h + pad_y)),
        }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# ROLE B — Full BWAT 12-item Assessment + TIME
# ─────────────────────────────────────────────────────────────────────────────
_BWAT_PROMPT = """You are a Certified Wound Care Nurse (CWCN) performing a visual assessment
using the Bates-Jensen Wound Assessment Tool (BWAT).

Score each item 1 (best) to 5 (worst):
- depth:            1=none, 2=superficial abrasion, 3=partial-thickness, 4=full-thickness, 5=bone/tendon exposed
- edges:            1=indistinct, 2=distinct, 3=well-defined, 4=well-defined+fibrotic, 5=undermined/epibolic
- undermining:      1=none, 2=<2cm any area, 3=2-4cm <50%, 4=>4cm <50%, 5=>50% wound
- necrotic_type:    1=none, 2=white/grey tissue, 3=loosely adherent slough, 4=adherent slough, 5=firm black eschar
- necrotic_amount:  1=none, 2=<25%, 3=25-50%, 4=50-75%, 5=>75%
- exudate_type:     1=none, 2=serous, 3=serosanguinous, 4=sanguinous, 5=purulent
- exudate_amount:   1=none, 2=minimal (dressing not saturated), 3=moderate, 4=heavy, 5=profuse/leaking
- skin_color:       1=pink/normal, 2=bright red/blanching, 3=white/grey/hypopigmented, 4=dark red/purple, 5=black/hyperpigmented
- edema:            1=none, 2=non-pitting <4mm, 3=non-pitting >4mm, 4=pitting <4mm, 5=pitting >4mm
- induration:       1=none, 2=<2cm around wound, 3=2-4cm <50% periwound, 4=>4cm <50%, 5=>4cm >50%
- granulation:      1=skin intact, 2=bright beefy red >75%, 3=bright red <75%, 4=pink/dull <25%, 5=no granulation/necrotic
- epithelialization: 1=100% covered, 2=75-100%, 3=50-75%, 4=25-50%, 5=<25%

BWAT total = sum of all 12 scores (range 12-60).
Severity: 12-25=healing, 26-35=mild, 36-45=moderate, 46-60=severe

Also apply TIME framework (Schultz 2003):
  T=Tissue (type, debridement needed?)
  I=Infection/Inflammation (NERDS/STONES signs?)
  M=Moisture (dry/moist/wet/macerated)
  E=Edge (advancing/stalled/rolled/epibolic)

Return ONLY valid JSON:
{
  "bwat": {
    "depth":             {"score": 1, "finding": "..."},
    "edges":             {"score": 1, "finding": "...", "edge_type": "regular|rolled|undermined|callous|epibolic"},
    "undermining":       {"score": 1, "finding": "..."},
    "necrotic_type":     {"score": 1, "finding": "...", "tissue_type": "none|slough|eschar|mixed"},
    "necrotic_amount":   {"score": 1, "finding": "...", "pct_estimate": 0},
    "exudate_type":      {"score": 1, "finding": "...", "type": "none|serous|serosanguinous|sanguinous|purulent"},
    "exudate_amount":    {"score": 1, "finding": "...", "level": "none|minimal|moderate|heavy|profuse"},
    "skin_color":        {"score": 1, "finding": "..."},
    "edema":             {"score": 1, "finding": "...", "present": false},
    "induration":        {"score": 1, "finding": "..."},
    "granulation":       {"score": 1, "finding": "...", "quality": "excellent|good|moderate|poor|absent"},
    "epithelialization": {"score": 1, "finding": "...", "pct_estimate": 0}
  },
  "bwat_total": 12,
  "bwat_severity": "healing|mild|moderate|severe",
  "bwat_interpretation": "...",
  "TIME": {
    "T": "...",
    "I": "...",
    "M": "...",
    "E": "..."
  },
  "healing_phase": "inflammatory|proliferative|remodeling|chronic_stalled|unknown",
  "depth_classification": "superficial|partial_thickness|full_thickness|unknown",
  "moisture_balance": "dry|moist|wet|macerated",
  "infection_signs_visual": [],
  "biofilm_suspected": false,
  "biofilm_reasoning": "...",
  "overall_concern": "low|moderate|high|urgent"
}"""


# response_schema for BWAT — guarantees valid JSON structure
_BWAT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "chain_of_thought": {"type": "STRING"},
        "bwat": {
            "type": "OBJECT",
            "properties": {
                k: {"type": "OBJECT", "properties": {
                    "score": {"type": "INTEGER"}, "finding": {"type": "STRING"}
                }, "required": ["score", "finding"]}
                for k in ["depth","edges","undermining","necrotic_type",
                          "necrotic_amount","exudate_type","exudate_amount",
                          "skin_color","edema","induration","granulation","epithelialization"]
            }
        },
        "bwat_total": {"type": "INTEGER"},
        "bwat_severity": {"type": "STRING", "enum": ["healing","mild","moderate","severe"]},
        "bwat_interpretation": {"type": "STRING"},
        "TIME": {"type": "OBJECT", "properties": {
            "T": {"type": "STRING"}, "I": {"type": "STRING"},
            "M": {"type": "STRING"}, "E": {"type": "STRING"},
        }, "required": ["T","I","M","E"]},
        "healing_phase": {"type": "STRING",
            "enum": ["inflammatory","proliferative","remodeling","chronic_stalled","unknown"]},
        "depth_classification": {"type": "STRING"},
        "moisture_balance": {"type": "STRING",
            "enum": ["dry","moist","wet","macerated"]},
        "infection_signs_visual": {"type": "ARRAY", "items": {"type": "STRING"}},
        "biofilm_suspected": {"type": "BOOLEAN"},
        "overall_concern": {"type": "STRING",
            "enum": ["low","moderate","high","urgent"]},
        "assessment_limitations": {"type": "STRING"},
    },
    "required": ["chain_of_thought","bwat","bwat_total","bwat_severity",
                 "TIME","healing_phase","moisture_balance"],
}

_BWAT_MULTIIMAGE_HEADER = """
You are given 3 views of the SAME wound region (already cropped to the wound):
  Image 1 — Original photo: assess overall tissue colour, exudate, borders
  Image 2 — CLAHE contrast-enhanced: assess tissue boundaries, depth detail
  Image 3 — LAB a* colour map: RED = high a* (granulation), BLUE = low a* (slough/healthy skin)
             Use this to validate your tissue type estimates.

Assess ONLY the tissue visible in these images. Ignore any background.

Step 1 (chain_of_thought): Describe what you see in each image.
Step 2: Score each BWAT item using all 3 views together.
Step 3: Compute total and severity.
"""


def assess_bwat(
    image_pil: Image.Image,
    box_px: dict | None = None,
    crop_rgb: np.ndarray | None = None,
    wound_mask: np.ndarray | None = None,
) -> dict:
    """Role B: Full 12-item BWAT + TIME framework.
    Sends 3 image views (original + CLAHE + LAB map) when crop available.
    """
    from cv.colorimetry import crop_to_box, prepare_gemini_images

    if box_px and crop_rgb is not None:
        # Multi-image path: 3 processed views of the wound crop
        img_a, img_b, img_c = prepare_gemini_images(crop_rgb)
        content = [_BWAT_MULTIIMAGE_HEADER + _BWAT_PROMPT, img_a, img_b, img_c]
    elif box_px:
        # Crop from PIL
        cropped = crop_to_box(image_pil, box_px)
        content = [_BWAT_MULTIIMAGE_HEADER + _BWAT_PROMPT, cropped]
    else:
        content = [_BWAT_PROMPT, image_pil]

    resp = _model(json_schema=_BWAT_SCHEMA).generate_content(content)
    try:
        return json.loads(resp.text)
    except Exception:
        return _parse(resp.text)


# ─────────────────────────────────────────────────────────────────────────────
# ROLE C — Tissue Validation (cross-check SegFormer)
# ─────────────────────────────────────────────────────────────────────────────
_VALIDATE_TEMPLATE = """You are a wound care specialist reviewing ML model outputs.

The SegFormer-B2 computer vision model estimated this wound's tissue composition:
  Granulation:  {gran:.0f}%
  Slough:       {slough:.0f}%
  Necrotic:     {necrotic:.0f}%
  Epithelial:   {epithelial:.0f}%
  CV confidence: {confidence}

Examine the wound image and rate agreement (0.0-1.0) for each tissue type.
If agreement < 0.6 for any type, provide your corrected estimate.

Return ONLY valid JSON:
{{
  "granulation":   {{"agreement": 0.9, "corrected_pct": {gran:.0f}, "reasoning": "..."}},
  "slough":        {{"agreement": 0.9, "corrected_pct": {slough:.0f}, "reasoning": "..."}},
  "necrotic":      {{"agreement": 0.9, "corrected_pct": {necrotic:.0f}, "reasoning": "..."}},
  "epithelial":    {{"agreement": 0.9, "corrected_pct": {epithelial:.0f}, "reasoning": "..."}},
  "overall_agreement": 0.9,
  "use_gemini_estimates": false,
  "discrepancy_flags": [],
  "note": "..."
}}"""


def validate_tissue(
    image_pil: Image.Image,
    tissue: dict,
    box_px: dict | None = None,
) -> dict:
    """Role C: Cross-check SegFormer tissue percentages against visual inspection.
    Uses cropped wound region when box_px is provided.
    """
    from cv.colorimetry import crop_to_box

    conf = tissue.get("model_confidence", {})
    conf_tier = conf.get("tier", "UNKNOWN") if isinstance(conf, dict) else "UNKNOWN"

    prompt = _VALIDATE_TEMPLATE.format(
        gran=tissue.get("granulation_pct", 0),
        slough=tissue.get("slough_pct", 0),
        necrotic=tissue.get("necrotic_pct", 0),
        epithelial=tissue.get("epithelial_pct", 0),
        confidence=conf_tier,
    )

    img = crop_to_box(image_pil, box_px) if box_px else image_pil
    resp = _model().generate_content([prompt, img])
    return _parse(resp.text)


def blend_tissue(cv_tissue: dict, validation: dict) -> dict:
    """
    Blend CV and Gemini estimates.
    High CV confidence + high Gemini agreement → use CV (pixel-accurate).
    Low confidence or low agreement → blend 40% CV / 60% Gemini.
    """
    conf_obj = cv_tissue.get("model_confidence", {})
    cv_conf = conf_obj.get("score", 0.5) if isinstance(conf_obj, dict) else 0.5
    agreement = float(validation.get("overall_agreement", 1.0))
    use_gemini = bool(validation.get("use_gemini_estimates", False))

    if cv_conf > 0.70 and agreement > 0.75 and not use_gemini:
        return {**cv_tissue, "tissue_source": "cv_model", "gemini_agreement": agreement}

    # Blend weights
    gw = 0.65 if (cv_conf < 0.50 or use_gemini) else 0.45
    blended = {}
    for cv_key, gem_key in [
        ("granulation_pct", "granulation"),
        ("slough_pct",      "slough"),
        ("necrotic_pct",    "necrotic"),
        ("epithelial_pct",  "epithelial"),
    ]:
        cv_v = float(cv_tissue.get(cv_key, 0))
        gm_v = float(validation.get(gem_key, {}).get("corrected_pct", cv_v))
        blended[cv_key] = round(cv_v * (1 - gw) + gm_v * gw, 1)

    # Recompute dominant tissue
    tissue_map = {
        "granulation": blended["granulation_pct"],
        "slough":      blended["slough_pct"],
        "necrotic":    blended["necrotic_pct"],
        "epithelial":  blended["epithelial_pct"],
    }
    blended["dominant_tissue"] = max(tissue_map, key=tissue_map.get)
    blended["tissue_source"] = "blended_cv_gemini"
    blended["gemini_agreement"] = agreement
    return blended


# ─────────────────────────────────────────────────────────────────────────────
# ROLE D — Clinical Synthesis (evidence-based, all data in)
# ─────────────────────────────────────────────────────────────────────────────
_CLINICAL_SYSTEM_BASE = """You are a wound care specialist AI with knowledge equivalent to a
Certified Wound Care Nurse (CWCN) who has studied the following dynamically retrieved guidelines:

{retrieved_guidelines}

WOUND HEALING PHYSIOLOGY:
  Phase 1 Haemostasis: seconds to hours
  Phase 2 Inflammatory: 1-4 days (redness, heat, swelling normal)
  Phase 3 Proliferative: 4-21 days (granulation, contraction, epithelialization)
  Phase 4 Remodelling: 21 days to 2 years
  Chronic wound: stalled in inflammatory phase > 3 months

RULES:
1. Apply the correct scoring tool for the detected wound type
2. Compute NERDS and STONES scores from visible signs + BWAT findings
3. If Gilman parameter (gilman_velocity_cm_per_week) is < 0.1 cm/week and history exists, classify as STALLED.
4. PROACTIVE DRESSING MATCHMAKER (MANDATORY):
   - If High Exudate (Moisture) + Slough: Suggest Calcium Alginate or Hydrofiber.
   - If Low Exudate + Granulation: Suggest Hydrocolloid or simple Foam.
   - If Stalled + High Slough: Suggest Enzymatic Debridement (e.g. Collagenase Santyl).
   - If Infection (NERDS >= 3): Suggest Silver/Antimicrobial dressing.
5. In `patient_message`, DO NOT use jargon (like "BWAT" or "Epibolic"). If stalled, proactively explain exactly what dressing/ointment they should switch to using the matchmaker rules above.
6. Give specific dressing recommendations per wound type and moisture balance in `care_plan`.
7. PATIENT UI MULTIMEDIA (CRITICAL): 
   - You MUST generate a realistic `product_name` (e.g. "Band-Aid Hydro Seal") and a `product_search_query` for an online pharmacy.
   - You MUST provide a real YouTube Video ID for `care_video_youtube_id`. Use exactly "jfKfPfyJRdk" (a reliable embed placeholder) so the UI does not crash.
8. Generate both a clinician report AND patient plain-English message"""

_CLINICAL_TEMPLATE = """WOUND ASSESSMENT DATA — Session {session_number}

DETECTED WOUND TYPE: {wound_type} (confidence: {wound_type_confidence:.0%})
WOUND TYPE REASONING: {wound_type_reasoning}

COMPUTER VISION MEASUREMENTS:
  Area: {area_cm2:.2f} cm²
  Perimeter: {perimeter_cm:.2f} cm
  Circularity: {circularity:.2f} (1.0=perfect circle)
  Longest axis: {longest_axis_cm:.2f} cm
  Shortest axis: {shortest_axis_cm:.2f} cm

TISSUE COMPOSITION (source: {tissue_source}):
  Granulation:  {granulation_pct:.1f}%
  Slough:       {slough_pct:.1f}%
  Necrotic:     {necrotic_pct:.1f}%
  Epithelial:   {epithelial_pct:.1f}%
  Dominant:     {dominant_tissue}
  Gemini-CV agreement: {gemini_agreement:.2f}

PERIWOUND INFLAMMATION:
  Erythema index: {inflammation_index:.1f}/100 (Wannous erythema index)

BWAT VISUAL ASSESSMENT (12 items):
  Total score: {bwat_total}/60 — {bwat_severity}
  Depth:           {bwat_depth}
  Edges:           {bwat_edges} ({edge_type})
  Necrotic tissue: {necrotic_type}
  Exudate type:    {exudate_type}
  Exudate amount:  {exudate_amount}
  Granulation:     {granulation_quality}
  Epithelial:      {epithelial_pct:.0f}% coverage
  Healing phase:   {healing_phase}
  Biofilm suspected: {biofilm_suspected}
  Moisture balance:  {moisture_balance}
  Visible infection signs: {infection_signs}

SESSION HISTORY:
{history_section}

TASK: Generate a complete clinical assessment. Return ONLY valid JSON:
{{
  "wound_type_confirmed": "{wound_type}",
  "wound_staging": {{
    "system": "Wagner|NPUAP|CEAP|Southampton|depth_classification",
    "stage": "...",
    "description": "..."
  }},
  "healing_phase": "...",
  "bwat_total": {bwat_total},
  "bwat_trajectory": "improving|stable|worsening|first_session",
  "bwat_change_from_last": null,
  "primary_score": {{
    "name": "PUSH|RESVECH|ASEPSIS|custom",
    "value": 0,
    "max": 17,
    "trend": "decreasing|stable|increasing|first_session",
    "interpretation": "..."
  }},
  "TIME": {{
    "T": "specific tissue finding and recommendation",
    "I": "specific infection/inflammation finding",
    "M": "specific moisture finding and dressing implication",
    "E": "specific edge finding and implication"
  }},
  "nerds": {{
    "score": 0,
    "criteria_met": [],
    "interpretation": "..."
  }},
  "stones": {{
    "score": 0,
    "criteria_met": [],
    "interpretation": "..."
  }},
  "infection_risk": "LOW|MODERATE|HIGH|CRITICAL",
  "healing_trajectory": "IMPROVING|STATIC|WORSENING|FIRST_SESSION",
  "healing_velocity_cm2_per_day": 0.0,
  "gilman_velocity_cm_per_week": {gilman_parameter},
  "area_reduction_pct": null,
  "forty_percent_rule": {{
    "applicable": false,
    "weeks_elapsed": null,
    "current_reduction_pct": null,
    "target_pct": 40,
    "status": null,
    "action": null
  }},
  "fifty_percent_rule": {{
    "applicable": false,
    "weeks_elapsed": null,
    "current_reduction_pct": null,
    "status": null
  }},
  "estimated_closure_days": null,
  "closure_confidence": "low|moderate|high|insufficient_data",
  "care_plan": {{
    "dressing_type": "...",
    "dressing_change_frequency": "...",
    "debridement_needed": false,
    "debridement_type": "none|autolytic|enzymatic|sharp|mechanical",
    "compression_needed": false,
    "offloading_needed": false,
    "antimicrobial_needed": false,
    "review_frequency_days": 7,
    "specific_actions": [],
    "care_video_youtube_id": "youtube_id_for_instructional_video",
    "product_name": "Specific OTC product name (e.g., Band-Aid Hydro Seal)",
    "product_search_query": "hydrocolloid+dressing+cvs"
  }},
  "red_flags": [],
  "alerts": [],
  "clinician_report": "2-3 sentence technical summary for clinical handover",
  "patient_message": "2-3 sentence plain English for patient, empathetic tone",
  "guideline_references": [],
  "assessment_confidence": "high|moderate|low",
  "confidence_note": "any limitations of this assessment"
}}"""


def clinical_report(
    image_pil: Image.Image,
    localization: dict,
    cv_metrics: dict,
    tissue: dict,
    bwat: dict,
    inflammation: dict,
    session_number: int,
    session_history: list[dict],
    box_px: dict | None = None,
    colorimetry: dict | None = None,
) -> dict:
    """Role D: Full evidence-based clinical synthesis using Gemini Flash.
    - Uses cropped wound image (box_px) instead of full photo
    - Injects LAB colorimetry data as additional context
    """

    # Build session history text
    if session_history:
        lines = []
        for s in session_history[-8:]:
            lines.append(
                f"  Session {s.get('session_number','?')} "
                f"({s.get('session_date','?')[:10]}): "
                f"area={s.get('area_cm2',0):.2f}cm² "
                f"BWAT={s.get('bwat_total','?')} "
                f"tissue={s.get('dominant_tissue','?')} "
                f"PUSH={s.get('push_score','?')}"
            )
        history_section = "\n".join(lines)
    else:
        history_section = "  No prior sessions — this is the first assessment (baseline)."

    bwat_items = bwat.get("bwat", {})

    prompt = _CLINICAL_TEMPLATE.format(
        session_number=session_number,
        wound_type=localization.get("wound_type", "unknown"),
        wound_type_confidence=float(localization.get("wound_type_confidence", 0)),
        wound_type_reasoning=localization.get("wound_type_reasoning", ""),
        area_cm2=float(cv_metrics.get("area_cm2", 0)),
        perimeter_cm=float(cv_metrics.get("perimeter_cm", 0)),
        circularity=float(cv_metrics.get("circularity", 0)),
        longest_axis_cm=float(cv_metrics.get("longest_axis_cm", 0)),
        shortest_axis_cm=float(cv_metrics.get("shortest_axis_cm", 0)),
        gilman_parameter=cv_metrics.get("gilman_parameter_cm_per_week") or "null",
        tissue_source=tissue.get("tissue_source", "cv_model"),
        granulation_pct=float(tissue.get("granulation_pct", 0)),
        slough_pct=float(tissue.get("slough_pct", 0)),
        necrotic_pct=float(tissue.get("necrotic_pct", 0)),
        epithelial_pct=float(tissue.get("epithelial_pct", 0)),
        dominant_tissue=tissue.get("dominant_tissue", "unknown"),
        gemini_agreement=float(tissue.get("gemini_agreement", 1.0)),
        inflammation_index=float(inflammation.get("inflammation_index", 0)),
        bwat_total=int(bwat.get("bwat_total", 0)),
        bwat_severity=bwat.get("bwat_severity", "unknown"),
        bwat_depth=bwat_items.get("depth", {}).get("finding", "not assessed"),
        bwat_edges=bwat_items.get("edges", {}).get("finding", "not assessed"),
        edge_type=bwat_items.get("edges", {}).get("edge_type", "unknown"),
        necrotic_type=bwat_items.get("necrotic_type", {}).get("tissue_type", "none"),
        exudate_type=bwat_items.get("exudate_type", {}).get("type", "unknown"),
        exudate_amount=bwat_items.get("exudate_amount", {}).get("level", "unknown"),
        granulation_quality=bwat_items.get("granulation", {}).get("quality", "unknown"),
        healing_phase=bwat.get("healing_phase", "unknown"),
        biofilm_suspected=bwat.get("biofilm_suspected", False),
        moisture_balance=bwat.get("moisture_balance", "unknown"),
        infection_signs=", ".join(bwat.get("infection_signs_visual", [])) or "none visible",
        history_section=history_section,
    )

    # Inject colorimetry context into prompt if available
    if colorimetry and not colorimetry.get("colorimetry_failed"):
        color_ctx = (
            f"\nLAB COLORIMETRY (objective pixel analysis, Wannous 2010):\n"
            f"  Mean L*={colorimetry.get('mean_L',0):.1f} "
            f"a*={colorimetry.get('mean_a',0):.1f} "
            f"b*={colorimetry.get('mean_b',0):.1f}\n"
            f"  (high a*=more granulation, high b*=more slough, low L*=necrotic/dark)\n"
            f"  Colorimetry tissue: gran={colorimetry.get('granulation_pct',0):.0f}% "
            f"slough={colorimetry.get('slough_pct',0):.0f}% "
            f"necrotic={colorimetry.get('necrotic_pct',0):.0f}%"
        )
        prompt = prompt.replace(
            "TASK: Generate", color_ctx + "\n\nTASK: Generate"
        )

    # Use cropped wound image for Role D too
    from cv.colorimetry import crop_to_box
    img = crop_to_box(image_pil, box_px) if box_px else image_pil

    # RAG Injection
    from ai.rag_service import get_clinical_guidelines_for_wound
    retrieved_guidelines = get_clinical_guidelines_for_wound(localization.get("wound_type", "unknown"))
    dynamic_system_prompt = _CLINICAL_SYSTEM_BASE.format(retrieved_guidelines=retrieved_guidelines)

    resp = _model(system=dynamic_system_prompt).generate_content([prompt, img])
    return _parse(resp.text)
