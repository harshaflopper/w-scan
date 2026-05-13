"""
Mock tissue classifier — used when MOCK_MODE=true in .env.

Returns clinically realistic tissue percentages without SegFormer weights.
Uses HSV colour-space heuristics on the actual wound image pixels
so outputs are image-dependent (not hardcoded).
"""

import numpy as np
import cv2


class MockTissueClassifier:
    """
    Drop-in replacement for TissueClassifier during development.

    Analyses HSV colour distribution inside the wound mask to
    produce tissue percentages that respond to the actual image:
        - High red saturation  → granulation
        - High yellow hue      → slough
        - Very dark pixels     → necrotic
        - Light/desaturated    → epithelial
    """

    LABELS = ["granulation", "slough", "necrotic", "epithelial"]

    def classify(
        self,
        image_rgb: np.ndarray,
        wound_mask: np.ndarray,
    ) -> dict:
        wound_bool = wound_mask.astype(bool)
        total = int(wound_bool.sum())

        if total == 0:
            return {f"{l}_pct": 0.0 for l in self.LABELS} | {
                "dominant_tissue": "granulation",
                "total_wound_px": 0,
            }

        # Convert to HSV for colour-based tissue estimation
        img_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        H = hsv[:, :, 0].astype(float)[wound_bool]  # 0-179
        S = hsv[:, :, 1].astype(float)[wound_bool]  # 0-255
        V = hsv[:, :, 2].astype(float)[wound_bool]  # 0-255

        # Tissue classification rules (HSV-based, Wannous 2010 inspired)
        granulation = ((H < 15) | (H > 160)) & (S > 80)           # red hue, saturated
        slough      = (H >= 15) & (H <= 40) & (S > 60)             # yellow hue
        necrotic    = V < 60                                        # very dark
        epithelial  = (S < 60) & (V > 140)                         # desaturated, bright

        # Resolve overlaps: priority order — necrotic > slough > granulation > epithelial
        gran_px = int((granulation & ~necrotic & ~slough).sum())
        slou_px = int((slough & ~necrotic).sum())
        necr_px = int(necrotic.sum())
        epith_px = int((epithelial & ~necrotic & ~slough & ~granulation).sum())

        classified = gran_px + slou_px + necr_px + epith_px
        remainder = max(0, total - classified)

        # Distribute unclassified pixels to granulation (most common in healing wounds)
        gran_px += remainder

        counts = {
            "granulation": gran_px,
            "slough":      slou_px,
            "necrotic":    necr_px,
            "epithelial":  epith_px,
        }
        result = {f"{l}_pct": round(counts[l] / total * 100, 2) for l in self.LABELS}
        result["dominant_tissue"] = max(counts, key=counts.get)
        result["total_wound_px"] = total
        return result
