"""
Wound boundary segmentation using MedSAM.

MedSAM = SAM ViT-B fine-tuned on 1.5M medical image–mask pairs by BowangLab (NIH).
Weights: https://drive.google.com/file/d/1UAmWL88roYR7wKlnApw5Bcuzf2iQgk6_
~375 MB download, place at models/medsam_vit_b.pth

Reference:
    Ma J. et al. (2024). "Segment Anything in Medical Images".
    Nature Communications. doi:10.1038/s41467-024-44824-z
"""

import os
import numpy as np
import torch
from PIL import Image

# MedSAM uses the standard segment-anything package but with its own weights.
# The SamPredictor API is identical to vanilla SAM.
try:
    from segment_anything import sam_model_registry, SamPredictor
    SAM_AVAILABLE = True
except ImportError:
    SAM_AVAILABLE = False


class WoundSegmenter:
    """
    Interactive wound boundary segmenter.

    Usage:
        segmenter = WoundSegmenter(weights_path="models/medsam_vit_b.pth")
        mask = segmenter.segment(image_rgb, click_x=320, click_y=240)
    """

    def __init__(self, weights_path: str = "models/medsam_vit_b.pth"):
        if not SAM_AVAILABLE:
            raise ImportError(
                "segment-anything not installed. "
                "Run: pip install git+https://github.com/facebookresearch/segment-anything.git"
            )
        if not os.path.exists(weights_path):
            raise FileNotFoundError(
                f"MedSAM weights not found at '{weights_path}'.\n"
                "Download from: https://drive.google.com/file/d/1UAmWL88roYR7wKlnApw5Bcuzf2iQgk6_\n"
                "Place at: models/medsam_vit_b.pth"
            )

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # sam_model_registry calls torch.load internally without map_location,
        # which crashes on CPU-only machines when weights were saved on GPU.
        # Monkey-patch torch.load to always use map_location="cpu".
        _original_load = torch.load
        torch.load = lambda f, *a, **kw: _original_load(
            f, *a, **{**kw, "map_location": device, "weights_only": False}
        )
        try:
            sam = sam_model_registry["vit_b"](checkpoint=weights_path)
        finally:
            torch.load = _original_load  # restore original

        sam.to(device)
        sam.eval()
        self.predictor = SamPredictor(sam)
        self.device = device


    def segment(
        self,
        image_rgb: np.ndarray,
        click_x: int,
        click_y: int,
        multimask: bool = True,
    ) -> np.ndarray:
        """
        Segment the wound region at the given click point.

        Args:
            image_rgb: H×W×3 uint8 RGB array.
            click_x: X coordinate (column) of click in image pixels.
            click_y: Y coordinate (row) of click in image pixels.
            multimask: If True, return best of 3 SAM masks (recommended).

        Returns:
            Boolean mask of shape (H, W). True = wound pixel.
        """
        self.predictor.set_image(image_rgb)

        masks, scores, _ = self.predictor.predict(
            point_coords=np.array([[click_x, click_y]], dtype=np.float32),
            point_labels=np.array([1]),           # 1 = foreground point
            multimask_output=multimask,
        )

        if multimask:
            best_idx = int(np.argmax(scores))
            mask = masks[best_idx]
        else:
            mask = masks[0]

        return self._postprocess_mask(mask.astype(bool), click_x, click_y)

    def _postprocess_mask(
        self,
        mask: np.ndarray,
        click_x: int | None = None,
        click_y: int | None = None,
        max_radius_px: int = 400,
    ) -> np.ndarray:
        """
        Clean up SAM mask to prevent background bleed:
          1. Keep only the connected component that contains the click point.
          2. Clamp mask to a circle of max_radius_px around the click point.
          3. Morphological erosion to remove 1-2px noise streaks.
        """
        import cv2
        mask_u8 = mask.astype(np.uint8)

        # ── 1. Connected-component filter ──────────────────────────────────────
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8)

        if num_labels <= 1:
            return mask  # nothing to filter

        if click_x is not None and click_y is not None:
            # Pick component whose bounding box contains the click point
            best_label = 0
            best_area  = 0
            for lbl in range(1, num_labels):
                x, y, w, h, area = stats[lbl]
                # Check if click is inside this component's bounding box
                if x <= click_x <= x + w and y <= click_y <= y + h:
                    if area > best_area:
                        best_area  = area
                        best_label = lbl
            if best_label == 0:
                # click not inside any bbox — fall back to largest component
                best_label = int(np.argmax(stats[1:, cv2.CC_STAT_AREA]) + 1)
        else:
            # No click — use largest component
            best_label = int(np.argmax(stats[1:, cv2.CC_STAT_AREA]) + 1)

        mask_clean = (labels == best_label).astype(np.uint8)

        # ── 2. Radius clamp around click point ─────────────────────────────────
        if click_x is not None and click_y is not None:
            H, W = mask.shape
            ys, xs = np.ogrid[:H, :W]
            dist   = np.sqrt((xs - click_x) ** 2 + (ys - click_y) ** 2)
            mask_clean[dist > max_radius_px] = 0

        # ── 3. Morphological erosion — kill 1-2px noise streaks ────────────────
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, kernel)

        return mask_clean.astype(bool)


    def segment_with_box(
        self,
        image_rgb: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
    ) -> np.ndarray:
        """
        Segment using a bounding box prompt (more accurate than click when
        wound shape is known).

        Args:
            x1, y1, x2, y2: bounding box in image pixel coordinates.

        Returns:
            Boolean mask of shape (H, W).
        """
        self.predictor.set_image(image_rgb)
        box = np.array([x1, y1, x2, y2], dtype=np.float32)
        masks, scores, _ = self.predictor.predict(
            box=box,
            multimask_output=True,
        )
        best_idx = int(np.argmax(scores))
        return masks[best_idx].astype(bool)
