# WoundScan — Notebooks Directory

## Directory structure

```
w-scan/
├── backend/
│   ├── models/
│   │   ├── medsam_vit_b.pth          ← ✅ already downloaded
│   │   └── segformer_wound/           ← ⬅ training output goes here
│   └── train/
│       └── train_segformer.py         ← local training script (optional)
│
└── notebooks/
    └── segformer_finetune.py          ← copy cells from here into Colab
```

## How to use

1. Open Google Colab: https://colab.research.google.com
2. Runtime → Change runtime type → **T4 GPU**
3. Create a new notebook
4. Copy each `# ── CELL N ──` block from `segformer_finetune.py` into separate cells
5. Run top to bottom
6. After training, download `segformer_wound.zip` and unzip into `backend/models/`
