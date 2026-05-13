"""
Download MedSAM model weights.

MedSAM: SAM ViT-B fine-tuned on 1.5M medical image pairs (BowangLab / NIH).
Reference: Ma J. et al. (2024). Nature Communications.

Usage:
    python scripts/download_models.py

Requirements:
    pip install gdown
"""

import os
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MEDSAM_PATH = os.path.join(MODELS_DIR, "medsam_vit_b.pth")

# Google Drive file ID for medsam_vit_b.pth
GDRIVE_FILE_ID = "1UAmWL88roYR7wKlnApw5Bcuzf2iQgk6_"
MEDSAM_SIZE_MB = 375


def _download_with_gdown():
    try:
        import gdown
        print(f"[gdown] Downloading MedSAM weights (~{MEDSAM_SIZE_MB}MB)...")
        url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
        gdown.download(url, MEDSAM_PATH, quiet=False)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[gdown] Failed: {e}")
        return False


def _download_with_progress(url: str, dest: str):
    """urllib fallback with progress bar."""
    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            print(f"\r  [{bar}] {pct:.1f}%", end="", flush=True)
    urllib.request.urlretrieve(url, dest, reporthook)
    print()


def download_medsam():
    os.makedirs(MODELS_DIR, exist_ok=True)

    if os.path.exists(MEDSAM_PATH):
        size_mb = os.path.getsize(MEDSAM_PATH) / (1024 * 1024)
        print(f"✅ MedSAM already exists at {MEDSAM_PATH} ({size_mb:.0f}MB)")
        return

    print(f"📥 Downloading MedSAM weights to {MEDSAM_PATH}")
    print(f"   Size: ~{MEDSAM_SIZE_MB}MB\n")

    # Try gdown first (handles Google Drive auth)
    if _download_with_gdown():
        if os.path.exists(MEDSAM_PATH):
            size_mb = os.path.getsize(MEDSAM_PATH) / (1024 * 1024)
            print(f"\n✅ Downloaded MedSAM ({size_mb:.0f}MB) → {MEDSAM_PATH}")
            return

    # Manual instructions if automated download fails
    print("\n⚠️  Automated download failed.")
    print("   Install gdown and retry:  pip install gdown")
    print("   Or download manually from Google Drive:")
    print(f"   https://drive.google.com/file/d/{GDRIVE_FILE_ID}")
    print(f"   Save to: {os.path.abspath(MEDSAM_PATH)}")
    sys.exit(1)


if __name__ == "__main__":
    download_medsam()
    print("\n📋 Next steps:")
    print("   1. Train SegFormer: python train/train_segformer.py  (needs FUSeg dataset)")
    print("   2. Set GEMINI_API_KEY in .env")
    print("   3. Start server: uvicorn main:app --reload")
