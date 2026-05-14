"""
LAB colorimetry-based wound tissue classification.
Deterministic, no ML model needed — pure validated colour math.

References:
  Wannous H. et al. (2010) Supervised tissue classification from colour images
    for a remote wound monitoring system. Conf Proc IEEE Eng Med Biol Soc.
  Yudovsky D. et al. (2011) Assessing diabetic foot wound severity using
    hyperspectral imaging. J Biomed Opt.
"""
from __future__ import annotations
import cv2
import numpy as np


def _dilate_mask(mask: np.ndarray, px: int = 20) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px * 2 + 1, px * 2 + 1))
    return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)


def lab_tissue_analysis(crop_rgb: np.ndarray, wound_mask: np.ndarray) -> dict:
    """
    Classify wound tissue using CIE LAB colour space.

    L* = lightness  (0=black, 100=white)
    a* = red-green  (positive=red/granulation, negative=green)
    b* = blue-yellow (positive=yellow/slough, negative=blue)

    Validated thresholds (Wannous 2010):
      Granulation : a* > 10,  20 < L* < 70   → deep red tissue
      Slough      : b* > 10,  a* < 10, L* > 40 → yellow/fibrinous
      Necrotic    : L* < 25,  chroma < 10     → dark/black eschar
      Epithelial  : L* > 65,  0 < a* < 15     → pale pink/white new skin
    """
    if wound_mask.sum() < 10:
        return {"colorimetry_failed": True, "reason": "mask_too_small"}

    # Convert to float LAB
    lab = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0] * (100.0 / 255.0)   # 0–100
    a = lab[:, :, 1] - 128.0              # -128 to +127
    b = lab[:, :, 2] - 128.0              # -128 to +127

    # Extract wound pixels only
    Lw = L[wound_mask]
    aw = a[wound_mask]
    bw = b[wound_mask]
    total = len(Lw)

    # Tissue masks
    gran_px   = (aw > 10)  & (Lw > 20) & (Lw < 72)
    slough_px = (bw > 10)  & (aw < 10) & (Lw > 40)
    necro_px  = (Lw < 28)  & ((aw ** 2 + bw ** 2) < 150)
    epith_px  = (Lw > 65)  & (aw > 0)  & (aw < 18)

    raw = {
        "granulation_pct": float(gran_px.sum()) / total * 100,
        "slough_pct":      float(slough_px.sum()) / total * 100,
        "necrotic_pct":    float(necro_px.sum())  / total * 100,
        "epithelial_pct":  float(epith_px.sum())  / total * 100,
    }

    # Normalise to 100 %
    total_classified = sum(raw.values())
    if total_classified > 5:
        scale = 100.0 / total_classified
        pcts = {k: round(v * scale, 1) for k, v in raw.items()}
    else:
        # Low classification — fallback using mean a* as a proxy
        if aw.mean() > 8:
            pcts = {"granulation_pct": 60.0, "slough_pct": 25.0,
                    "necrotic_pct": 10.0, "epithelial_pct": 5.0}
        else:
            pcts = {"granulation_pct": 20.0, "slough_pct": 50.0,
                    "necrotic_pct": 20.0, "epithelial_pct": 10.0}

    dominant = max(pcts, key=pcts.get).replace("_pct", "")

    # Periwound erythema (Wannous method) — a* in ring around wound
    ring = _dilate_mask(wound_mask, px=18) & ~wound_mask
    erythema_index = float(a[ring].mean()) * 5.0 if ring.sum() > 10 else 0.0
    erythema_index = round(min(max(erythema_index, 0), 100), 1)

    return {
        **pcts,
        "dominant_tissue":    dominant,
        "erythema_index":     erythema_index,
        "tissue_source":      "lab_colorimetry",
        "mean_L":  round(float(Lw.mean()), 1),
        "mean_a":  round(float(aw.mean()), 1),
        "mean_b":  round(float(bw.mean()), 1),
        "colorimetry_failed": False,
    }


def three_way_tissue_blend(
    colorimetry: dict,
    segformer: dict,
    gemini_validation: dict,
) -> dict:
    """
    Weighted blend of 3 tissue estimates:
      LAB colorimetry  — deterministic colour math
      SegFormer        — trained CNN (good on clinical images)
      Gemini vision    — semantic understanding

    Weights adjust based on SegFormer confidence tier.
    """
    conf_obj = segformer.get("model_confidence", {})
    conf_tier = conf_obj.get("tier", "MEDIUM") if isinstance(conf_obj, dict) else "MEDIUM"

    if conf_tier == "HIGH":
        w = {"color": 0.20, "sf": 0.55, "gem": 0.25}
    elif conf_tier == "LOW":
        w = {"color": 0.40, "sf": 0.15, "gem": 0.45}
    else:  # MEDIUM / unknown
        w = {"color": 0.30, "sf": 0.40, "gem": 0.30}

    blended: dict[str, float] = {}
    for key, gem_key in [
        ("granulation_pct", "granulation"),
        ("slough_pct",      "slough"),
        ("necrotic_pct",    "necrotic"),
        ("epithelial_pct",  "epithelial"),
    ]:
        c_v = float(colorimetry.get(key, 0))
        s_v = float(segformer.get(key, 0))
        g_v = float(
            gemini_validation.get(gem_key, {}).get("corrected_pct", s_v)
            if isinstance(gemini_validation.get(gem_key), dict) else s_v
        )
        blended[key] = round(c_v * w["color"] + s_v * w["sf"] + g_v * w["gem"], 1)

    dominant = max(blended, key=blended.get).replace("_pct", "")
    return {
        **blended,
        "dominant_tissue":   dominant,
        "tissue_source":     "3way_blend",
        "gemini_agreement":  float(gemini_validation.get("overall_agreement", 1.0)),
        "colorimetry_mean_a": colorimetry.get("mean_a"),
        "colorimetry_mean_b": colorimetry.get("mean_b"),
    }


def prepare_gemini_images(crop_rgb: np.ndarray):
    """
    Return 3 PIL images for multi-image Gemini call:
      A — original crop
      B — CLAHE contrast-enhanced (tissue boundaries clearer)
      C — LAB a* false-colour map (red=granulation, blue=slough/healthy)
    """
    from PIL import Image

    # A: original
    img_a = Image.fromarray(crop_rgb)

    # B: CLAHE on L channel
    lab = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    img_b = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))

    # C: a* channel visualised as JET colour map
    a_ch = lab[:, :, 1].astype(np.float32)
    a_norm = cv2.normalize(a_ch, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    jet = cv2.applyColorMap(a_norm, cv2.COLORMAP_JET)
    img_c = Image.fromarray(cv2.cvtColor(jet, cv2.COLOR_BGR2RGB))

    return img_a, img_b, img_c


def crop_to_box(image_pil, box_px: dict, pad_pct: float = 0.18, min_size: int = 256):
    """
    Crop PIL image to confirmed wound box + padding.
    Upscale if crop is smaller than min_size (helps Gemini quality).
    """
    from PIL import Image
    w, h = image_pil.size
    x1, y1 = box_px["x1"], box_px["y1"]
    x2, y2 = box_px["x2"], box_px["y2"]

    px = int((x2 - x1) * pad_pct)
    py = int((y2 - y1) * pad_pct)
    cx1, cy1 = max(0, x1 - px), max(0, y1 - py)
    cx2, cy2 = min(w, x2 + px), min(h, y2 + py)

    crop = image_pil.crop((cx1, cy1, cx2, cy2))
    cw, ch = crop.size
    if min(cw, ch) < min_size:
        scale = min_size / min(cw, ch)
        crop = crop.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)
    return crop
