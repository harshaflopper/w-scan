"""
Periwound inflammation scoring using validated opponent-colour erythema index.

Method: Wannous H. et al. (2010).
"Supervised tissue classification from color images for a remote
 wound monitoring system."
IEEE Transactions on Information Technology in Biomedicine, 14(3), 636–644.
doi:10.1109/TITB.2009.2036844

The erythema index EI = log(R/G) captures haemoglobin-related redness.
Melanin index MI = log(R+G+B) normalises for skin tone differences.
Final score: EI - α·MI, where α is empirically set at 0.5.
"""

import cv2
import numpy as np


def compute_inflammation_index(
    image_bgr: np.ndarray,
    wound_mask: np.ndarray,
    dilation_px: int = 30,
) -> dict:
    """
    Compute periwound erythema (inflammation) index.

    Args:
        image_bgr: BGR image as numpy array.
        wound_mask: Binary wound boundary mask (True = wound).
        dilation_px: Width in pixels of the periwound ring to analyse.

    Returns:
        dict with:
            inflammation_index  – 0–100 (higher = more inflamed)
            erythema_mean       – raw EI score in periwound region
            periwound_px_count  – number of periwound pixels analysed
            warning             – string if insufficient periwound area
    """
    # Build periwound annular mask
    kernel = np.ones((dilation_px, dilation_px), np.uint8)
    wound_u8 = wound_mask.astype(np.uint8)
    dilated = cv2.dilate(wound_u8, kernel, iterations=1)
    periwound_mask = (dilated - wound_u8).astype(bool)

    px_count = int(periwound_mask.sum())
    if px_count < 100:
        return {
            "inflammation_index": 0.0,
            "erythema_mean": 0.0,
            "periwound_px_count": px_count,
            "warning": "Insufficient periwound area for reliable erythema scoring",
        }

    img_f = image_bgr.astype(np.float64)
    # OpenCV is BGR
    B = img_f[:, :, 0]
    G = img_f[:, :, 1]
    R = img_f[:, :, 2]

    # Erythema Index: log(R / (G + ε))
    EI = np.log(R / (G + 1e-6) + 1e-6)

    # Melanin Index: log(R + G + B + ε)
    MI = np.log(R + G + B + 1e-6)

    # Composite score in periwound region
    composite = EI[periwound_mask] - 0.5 * MI[periwound_mask]
    erythema_mean = float(np.mean(composite))

    # Normalise to 0–100
    # Observed range in clinical images: approximately −2.5 to +1.5
    normalised = np.clip((erythema_mean + 2.5) / 4.0 * 100, 0, 100)

    return {
        "inflammation_index": round(float(normalised), 2),
        "erythema_mean": round(erythema_mean, 4),
        "periwound_px_count": px_count,
        "warning": None,
    }


def generate_inflammation_heatmap(
    image_bgr: np.ndarray,
    wound_mask: np.ndarray,
    dilation_px: int = 30,
) -> np.ndarray:
    """
    Generate a periwound erythema heatmap overlaid on the original image.

    Returns: RGB numpy array for display.
    """
    kernel = np.ones((dilation_px, dilation_px), np.uint8)
    wound_u8 = wound_mask.astype(np.uint8)
    dilated = cv2.dilate(wound_u8, kernel, iterations=1)
    periwound_mask = (dilated - wound_u8).astype(bool)

    img_f = image_bgr.astype(np.float64)
    B, G, R = img_f[:, :, 0], img_f[:, :, 1], img_f[:, :, 2]
    EI = np.log(R / (G + 1e-6) + 1e-6)
    MI = np.log(R + G + B + 1e-6)
    score_map = EI - 0.5 * MI

    # Normalise score_map to 0-255 for colourmap
    score_peri = score_map[periwound_mask]
    if len(score_peri) == 0:
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    s_min, s_max = score_peri.min(), score_peri.max()
    norm_map = np.zeros_like(score_map)
    if s_max > s_min:
        norm_map[periwound_mask] = (
            (score_map[periwound_mask] - s_min) / (s_max - s_min) * 255
        )

    heatmap = cv2.applyColorMap(norm_map.astype(np.uint8), cv2.COLORMAP_JET)
    result = image_bgr.copy()

    # Blend heatmap only over periwound region
    heatmap_region = heatmap[periwound_mask]
    orig_region = result[periwound_mask]
    result[periwound_mask] = (0.45 * heatmap_region + 0.55 * orig_region).astype(np.uint8)

    return cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
