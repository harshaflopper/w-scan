"""
Tissue classification using SegFormer-B2 fine-tuned on FUSeg wound dataset.

Architecture: SegFormer-B2 (Mix Transformer encoder + lightweight MLP decoder)
Reference:
    Xie E. et al. (2021). SegFormer: Simple and Efficient Design for
    Semantic Segmentation with Transformers. NeurIPS.

Training dataset: FUSeg (Foot Ulcer Segmentation Challenge)
    https://github.com/uwm-bigdata/wound-image-segmentation
    1,210 pixel-labelled wound images.

Training instructions: see train/train_segformer.py

Classes:
    0 – granulation  (healthy proliferative tissue)
    1 – slough       (non-viable fibrin)
    2 – necrotic     (dead/eschar tissue)
    3 – epithelial   (new skin, wound closure front)
"""

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

try:
    from transformers import (
        SegformerForSemanticSegmentation,
        SegformerImageProcessor,
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


TISSUE_LABELS = {
    0: "granulation",
    1: "slough",
    2: "necrotic",
    3: "epithelial",
}

# Display colours for each class (RGB)
TISSUE_COLORS_RGB = {
    0: (220, 80,  80),   # granulation — red
    1: (230, 200, 50),   # slough      — yellow
    2: (70,  60,  60),   # necrotic    — near-black
    3: (255, 180, 200),  # epithelial  — pink
}


class TissueClassifier:
    """
    Pixel-level wound tissue classifier.

    After loading, only pixels inside the SAM/MedSAM wound_mask are counted
    for tissue percentages — surrounding skin does not pollute results.
    """

    def __init__(self, model_path: str = "models/segformer_wound"):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers not installed. Run: pip install transformers")

        # ── Auto-download from Google Drive if weights missing ────────────────
        import os
        config_file = os.path.join(model_path, "config.json")
        if not os.path.exists(config_file):
            drive_id = os.environ.get("SEGFORMER_DRIVE_ID", "")
            if drive_id:
                import sys, subprocess, zipfile
                zip_path = os.path.join(model_path, "..", "segformer_wound.zip")
                os.makedirs(model_path, exist_ok=True)
                print(f"[TissueClassifier] Downloading weights from Drive ({drive_id}) ...")
                subprocess.run(
                    [sys.executable, "-m", "gdown", drive_id, "-O", zip_path],
                    check=True
                )
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(model_path)
                os.remove(zip_path)
                print("[TissueClassifier] Weights downloaded and extracted.")
            else:
                raise FileNotFoundError(
                    f"SegFormer weights not found at '{model_path}'.\n"
                    "Options:\n"
                    "  A) Run Colab training (Cell 14 downloads segformer_wound.zip),\n"
                    "     unzip and place at backend/models/segformer_wound/\n"
                    "  B) Set SEGFORMER_DRIVE_ID=<your_drive_file_id> in .env\n"
                    "     and run: pip install gdown\n"
                    "  C) Set MOCK_MODE=true in .env to use HSV mock classifier"
                )

        self.processor = SegformerImageProcessor.from_pretrained(model_path)
        self.model = SegformerForSemanticSegmentation.from_pretrained(model_path)
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)


    def classify(
        self,
        image_rgb: np.ndarray,
        wound_mask: np.ndarray,
    ) -> dict:
        """
        Run tissue segmentation and compute per-class statistics.

        Args:
            image_rgb: H×W×3 uint8 RGB array.
            wound_mask: Boolean mask — True = inside wound boundary.

        Returns:
            dict with:
                granulation_pct, slough_pct, necrotic_pct, epithelial_pct
                dominant_tissue
                seg_map  – H×W int array of class IDs (for overlay generation)
                confidence_map – H×W float array, max softmax confidence per pixel
        """
        pil_img = Image.fromarray(image_rgb)
        inputs = self.processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self.model(**inputs).logits  # (1, num_classes, H/4, W/4)

        # Upsample to original image size
        logits_up = F.interpolate(
            logits,
            size=(image_rgb.shape[0], image_rgb.shape[1]),
            mode="bilinear",
            align_corners=False,
        )

        probs = F.softmax(logits_up, dim=1)                         # (1, 4, H, W)
        seg_map = probs.argmax(dim=1).squeeze(0).cpu().numpy()      # (H, W)
        confidence_map = probs.max(dim=1).values.squeeze(0).cpu().numpy()  # (H, W)

        # Count tissue pixels ONLY inside the wound boundary
        wound_bool = wound_mask.astype(bool)
        total_wound_px = int(wound_bool.sum())

        result: dict = {}
        tissue_counts: dict[str, int] = {}

        for cls_id, label in TISSUE_LABELS.items():
            count = int(((seg_map == cls_id) & wound_bool).sum())
            tissue_counts[label] = count
            result[f"{label}_pct"] = (
                round(count / total_wound_px * 100, 2) if total_wound_px > 0 else 0.0
            )

        result["dominant_tissue"] = (
            max(tissue_counts, key=tissue_counts.get) if total_wound_px > 0 else "unknown"
        )
        result["seg_map"] = seg_map
        result["confidence_map"] = confidence_map
        result["total_wound_px"] = total_wound_px

        return result
