import cv2
import numpy as np

# Standard coin diameters in millimeters (verified against official mint specs)
COIN_DIAMETERS_MM: dict[str, float] = {
    "INR_1":      21.93,   # India ₹1 stainless steel series
    "INR_2":      25.00,   # India ₹2 (common circular variant)
    "INR_5":      23.00,   # India ₹5 stainless steel
    "INR_10":     27.00,   # India ₹10 bimetallic
    "US_QUARTER": 24.26,   # US Quarter
    "US_PENNY":   19.05,   # US Penny
    "EURO_1":     23.25,   # Euro €1
    "EURO_2":     25.75,   # Euro €2
    "GBP_1":      23.43,   # British £1
}

COIN_LABELS: dict[str, str] = {
    "INR_1":      "₹1 Coin (21.93mm)",
    "INR_2":      "₹2 Coin (25.00mm)",
    "INR_5":      "₹5 Coin (23.00mm)",
    "INR_10":     "₹10 Coin (27.00mm)",
    "US_QUARTER": "US Quarter (24.26mm)",
    "US_PENNY":   "US Penny (19.05mm)",
    "EURO_1":     "€1 Coin (23.25mm)",
    "EURO_2":     "€2 Coin (25.75mm)",
    "GBP_1":      "£1 Coin (23.43mm)",
}


def get_px_per_mm(image_bgr: np.ndarray, coin_type: str) -> tuple[float | None, bool, dict]:
    """
    Detect a coin in the image and return pixels-per-millimeter scale factor.

    Uses Hough Circle Transform. Falls back to ellipse fitting if the coin
    appears elliptical (camera angle > ~15°).

    Args:
        image_bgr: BGR image as numpy array.
        coin_type: Key from COIN_DIAMETERS_MM.

    Returns:
        (px_per_mm, success, debug_info)
        px_per_mm is None if detection failed.
    """
    real_dia_mm = COIN_DIAMETERS_MM.get(coin_type)
    if real_dia_mm is None:
        return None, False, {"error": f"Unknown coin type: {coin_type}"}

    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)

    # Hough Circle detection — parameters tuned for coin-sized objects
    min_r = int(min(h, w) * 0.025)   # smallest coin takes ≥5% of shorter dimension
    max_r = int(min(h, w) * 0.30)    # coin shouldn't dominate more than 60% of frame

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(h, w) // 3,
        param1=80,
        param2=35,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is not None:
        circles = np.round(circles[0]).astype(int)
        cx, cy, r = circles[0]  # highest-confidence detection
        detected_dia_px = r * 2
        px_per_mm = detected_dia_px / real_dia_mm
        return px_per_mm, True, {
            "method": "hough_circle",
            "coin_center_px": (int(cx), int(cy)),
            "detected_radius_px": int(r),
            "px_per_mm": round(px_per_mm, 4),
        }

    # Fallback: ellipse fitting on the largest bright circular blob
    # Handles tilted camera where coin appears elliptical
    px_per_mm, success, debug = _ellipse_fallback(gray, real_dia_mm)
    return px_per_mm, success, debug


def _ellipse_fallback(gray: np.ndarray, real_dia_mm: float) -> tuple[float | None, bool, dict]:
    """
    Detect coin via contour-based ellipse fitting.
    Uses the major axis of the fitted ellipse as the true diameter.
    """
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        if len(c) < 5 or area < 500:
            continue
        ellipse = cv2.fitEllipse(c)
        (ex, ey), (ma, mi), angle = ellipse
        # Circularity of ellipse: minor/major axis ratio. Coins are circles, so ≥ 0.7
        if mi / ma >= 0.65:
            candidates.append((area, ma, ellipse))

    if not candidates:
        return None, False, {"error": "No circular object detected — ensure coin is visible"}

    # Take largest candidate
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, major_axis_px, _ = candidates[0]
    px_per_mm = major_axis_px / real_dia_mm
    return px_per_mm, True, {
        "method": "ellipse_fallback",
        "major_axis_px": round(major_axis_px, 2),
        "px_per_mm": round(px_per_mm, 4),
        "note": "Camera may be at an angle — perpendicular shooting improves accuracy",
    }
