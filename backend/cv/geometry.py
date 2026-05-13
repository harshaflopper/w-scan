"""
Geometric wound metrics from binary wound mask.

All measurements are in real-world units (cm, cm²) after calibration.
Formulas sourced from photo-planimetry literature:
    Leaper DJ, Harding KG (2011). Wounds: Biology and Management.
    Oxford University Press.
"""

import cv2
import numpy as np


def compute_geometry(mask: np.ndarray, px_per_mm: float) -> dict:
    """
    Compute area, perimeter, and shape metrics from a binary wound mask.

    Args:
        mask: Boolean or uint8 binary mask (True/255 = wound pixels).
        px_per_mm: Pixels per millimetre from calibration engine.

    Returns:
        dict with keys:
            area_cm2        – wound surface area in cm²
            perimeter_cm    – wound boundary length in cm
            circularity     – shape regularity: 1.0=circle, 0=very irregular
            longest_axis_cm – length of longest axis (max caliper distance)
            shortest_axis_cm– perpendicular shortest axis
            aspect_ratio    – longest/shortest axis
    """
    px_per_cm = px_per_mm * 10.0
    mask_u8 = (mask > 0).astype(np.uint8) * 255

    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return {
            "area_cm2": 0.0, "perimeter_cm": 0.0, "circularity": 0.0,
            "longest_axis_cm": 0.0, "shortest_axis_cm": 0.0, "aspect_ratio": 1.0,
        }

    # Use largest contour (main wound body)
    main_contour = max(contours, key=cv2.contourArea)

    area_px = cv2.contourArea(main_contour)
    perim_px = cv2.arcLength(main_contour, closed=True)

    area_cm2 = area_px / (px_per_cm ** 2)
    perim_cm = perim_px / px_per_cm

    # Circularity: 4π·A / P²  — 1.0 = perfect circle, 0 = highly irregular
    # Source: ISO 9276-6 shape descriptors
    circularity = (4.0 * np.pi * area_cm2) / (perim_cm ** 2) if perim_cm > 0 else 0.0
    circularity = min(circularity, 1.0)

    # Minimum enclosing ellipse → clinical length × width measurement
    if len(main_contour) >= 5:
        (_, _), (ma, mi), _ = cv2.fitEllipse(main_contour)
        longest_axis_cm  = max(ma, mi) / px_per_cm
        shortest_axis_cm = min(ma, mi) / px_per_cm
    else:
        rect = cv2.minAreaRect(main_contour)
        (_, _), (rw, rh), _ = rect
        longest_axis_cm  = max(rw, rh) / px_per_cm
        shortest_axis_cm = min(rw, rh) / px_per_cm

    aspect_ratio = (longest_axis_cm / shortest_axis_cm) if shortest_axis_cm > 0 else 1.0

    return {
        "area_cm2":         round(area_cm2, 3),
        "perimeter_cm":     round(perim_cm, 3),
        "circularity":      round(circularity, 4),
        "longest_axis_cm":  round(longest_axis_cm, 3),
        "shortest_axis_cm": round(shortest_axis_cm, 3),
        "aspect_ratio":     round(aspect_ratio, 3),
    }


def generate_annotated_overlay(
    image_rgb: np.ndarray,
    wound_mask: np.ndarray,
    seg_map: np.ndarray | None = None,
) -> np.ndarray:
    """
    Generate a colour-annotated overlay image for display.

    Tissue colours match clinical convention:
        Granulation → red overlay
        Slough      → yellow overlay
        Necrotic    → dark grey overlay
        Epithelial  → light pink overlay

    Args:
        image_rgb: Original RGB image.
        wound_mask: Binary wound boundary mask.
        seg_map: Per-pixel tissue class map (0–3). If None, only boundary drawn.

    Returns:
        Annotated RGB image as numpy array.
    """
    overlay = image_rgb.copy()

    TISSUE_COLORS_RGB = {
        0: (220, 80,  80),   # granulation — red
        1: (230, 200, 50),   # slough — yellow
        2: (70,  60,  60),   # necrotic — dark
        3: (255, 180, 200),  # epithelial — pink
    }

    if seg_map is not None:
        tissue_layer = np.zeros_like(image_rgb)
        for cls_id, color in TISSUE_COLORS_RGB.items():
            tissue_mask = (seg_map == cls_id) & wound_mask
            tissue_layer[tissue_mask] = color
        # Blend tissue layer over original at 45% opacity
        wound_region = wound_mask[:, :, np.newaxis]
        overlay = np.where(
            wound_region,
            (overlay * 0.55 + tissue_layer * 0.45).astype(np.uint8),
            overlay
        )

    # Draw wound boundary contour
    mask_u8 = (wound_mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 150), 2)  # green boundary

    return overlay
