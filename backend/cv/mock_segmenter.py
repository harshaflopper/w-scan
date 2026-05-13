"""
Mock wound segmenter — used when MOCK_MODE=true in .env.

Returns a realistic elliptical wound mask without requiring MedSAM weights.
The mask is centred on the user's click point and sized proportionally
to the image so downstream metrics produce realistic numbers.

This lets you develop and test the full API pipeline without downloading
the 375MB MedSAM checkpoint.
"""

import numpy as np
import cv2


class MockWoundSegmenter:
    """
    Drop-in replacement for WoundSegmenter during development.

    Generates an elliptical wound mask at the click point.
    Size is randomised within a clinically realistic range (2–25 cm²)
    using the calibrated px_per_mm so area measurements are correct.
    """

    def segment(
        self,
        image_rgb: np.ndarray,
        click_x: int,
        click_y: int,
        px_per_mm: float = 8.0,
    ) -> np.ndarray:
        """
        Returns a boolean mask (H, W) with an ellipse centred at click point.

        px_per_mm is used to make the mock wound a realistic real-world size.
        Default wound: roughly 8cm² ellipse.
        """
        h, w = image_rgb.shape[:2]

        # Target wound area ~8 cm² → solve for axes
        # area = π * a * b,  use aspect ratio 1.3 (wound is rarely circular)
        # 8 cm² = π * a * (a/1.3)  →  a = sqrt(8 * 1.3 / π)
        target_area_cm2 = 8.0
        px_per_cm = px_per_mm * 10.0
        a_cm = np.sqrt(target_area_cm2 * 1.3 / np.pi)
        b_cm = a_cm / 1.3
        a_px = int(a_cm * px_per_cm)
        b_px = int(b_cm * px_per_cm)

        # Clamp so ellipse stays inside image
        a_px = min(a_px, click_x - 2, w - click_x - 2, h // 3)
        b_px = min(b_px, click_y - 2, h - click_y - 2, h // 3)
        a_px = max(a_px, 10)
        b_px = max(b_px, 10)

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(
            mask,
            center=(click_x, click_y),
            axes=(a_px, b_px),
            angle=15,           # slight rotation — wounds are rarely axis-aligned
            startAngle=0,
            endAngle=360,
            color=255,
            thickness=-1,
        )
        return mask.astype(bool)

    def segment_with_box(self, image_rgb, x1, y1, x2, y2) -> np.ndarray:
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return self.segment(image_rgb, cx, cy)
