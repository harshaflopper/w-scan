# WoundScan Model Weights

Place model weight files here before running the backend.

---

## 1. MedSAM (wound boundary segmentation)

**File:** `medsam_vit_b.pth` (~375 MB)

**Download:**
```
https://drive.google.com/file/d/1UAmWL88roYR7wKlnApw5Bcuzf2iQgk6_
```

Or via gdown:
```bash
pip install gdown
gdown "1UAmWL88roYR7wKlnApw5Bcuzf2iQgk6_" -O models/medsam_vit_b.pth
```

**Reference:**
Ma J. et al. (2024). "Segment Anything in Medical Images."
Nature Communications. doi:10.1038/s41467-024-44824-z

---

## 2. SegFormer-B2 Wound Tissue Classifier

**Directory:** `segformer_wound/` (created by training script)

Train on Google Colab T4 (~3 hours, free tier):

```bash
# Step 1: Download FUSeg dataset
git clone https://github.com/uwm-bigdata/wound-image-segmentation
# Follow dataset setup in train/train_segformer.py comments

# Step 2: Run training
python train/train_segformer.py
```

After training, `models/segformer_wound/` will contain:
- `config.json`
- `pytorch_model.bin`
- `preprocessor_config.json`

**Reference:**
Xie E. et al. (2021). "SegFormer: Simple and Efficient Design for
Semantic Segmentation with Transformers." NeurIPS.

---

## Directory structure after setup

```
models/
├── medsam_vit_b.pth          ← download manually
└── segformer_wound/           ← created by training
    ├── config.json
    ├── pytorch_model.bin
    └── preprocessor_config.json
```
