import cv2
import numpy as np


def check_image_quality(image_bgr: np.ndarray) -> dict:
    """
    Gate to run before any CV analysis. Returns pass/fail with specific issues.

    Checks:
    1. Blur (Laplacian variance — industry standard for focus detection)
    2. Exposure (mean brightness)
    3. Resolution (minimum 640×480 for reliable segmentation)
    4. Color channel sanity (not grayscale-only)

    Returns:
        {
            "pass": bool,
            "issues": list[str],
            "blur_score": float,     # higher = sharper
            "brightness": float,     # 0-255
            "resolution": [h, w],
        }
    """
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # 1. Blur: Laplacian variance
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = blur_score < 80.0

    # 2. Exposure
    mean_brightness = float(gray.mean())
    is_too_dark = mean_brightness < 40.0
    is_overexposed = mean_brightness > 230.0

    # 3. Resolution
    is_low_res = (h * w) < (640 * 480)

    # 4. Color check — if std of channel differences is near 0, image is grayscale
    b, g, r = image_bgr[:, :, 0], image_bgr[:, :, 1], image_bgr[:, :, 2]
    channel_spread = float(np.std(r.astype(float) - g.astype(float)))
    is_grayscale = channel_spread < 3.0

    issues: list[str] = []
    if is_blurry:
        issues.append("Image is blurry — hold camera steady or move closer")
    if is_too_dark:
        issues.append("Image too dark — improve lighting before retaking")
    if is_overexposed:
        issues.append("Image overexposed — reduce light source or move back")
    if is_low_res:
        issues.append(f"Resolution {w}×{h} too low — minimum 640×480 required")
    if is_grayscale:
        issues.append("Grayscale image detected — colour image required for tissue analysis")

    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "blur_score": round(blur_score, 2),
        "brightness": round(mean_brightness, 2),
        "resolution": [h, w],
    }
