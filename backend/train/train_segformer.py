"""
SegFormer-B2 fine-tuning on FUSeg wound tissue dataset.

Run this on Google Colab T4 GPU (free tier) — takes ~3 hours.

Dataset download:
    git clone https://github.com/uwm-bigdata/wound-image-segmentation
    Dataset structure expected:
        data/wound_tissue/
            images/train/*.jpg
            images/val/*.jpg
            masks/train/*.png   (0=granulation,1=slough,2=necrotic,3=epithelial)
            masks/val/*.png

Usage:
    python train/train_segformer.py

Output:
    models/segformer_wound/   (drop-in for TissueClassifier)
"""

import os
import numpy as np
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from transformers import (
    SegformerForSemanticSegmentation,
    SegformerImageProcessor,
    get_scheduler,
)
import torch
import torch.nn.functional as F
from torch.optim import AdamW

# ─── Config ──────────────────────────────────────────────────────────────────

DATA_ROOT   = "data/wound_tissue"
OUTPUT_DIR  = "models/segformer_wound"
NUM_EPOCHS  = 100
BATCH_SIZE  = 8
LR          = 6e-5
NUM_CLASSES = 4

ID2LABEL = {0: "granulation", 1: "slough", 2: "necrotic", 3: "epithelial"}
LABEL2ID = {v: k for k, v in ID2LABEL.items()}

# ─── Dataset ─────────────────────────────────────────────────────────────────

class WoundDataset(Dataset):
    def __init__(self, split: str, processor: SegformerImageProcessor):
        self.img_dir  = os.path.join(DATA_ROOT, "images", split)
        self.mask_dir = os.path.join(DATA_ROOT, "masks",  split)
        self.files    = sorted([f for f in os.listdir(self.img_dir) if f.endswith((".jpg", ".png"))])
        self.processor = processor

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        fname  = self.files[idx]
        stem   = os.path.splitext(fname)[0]
        image  = Image.open(os.path.join(self.img_dir, fname)).convert("RGB")
        mask   = Image.open(os.path.join(self.mask_dir, f"{stem}.png"))

        # Augmentation (training only)
        if "train" in self.img_dir:
            import random
            if random.random() > 0.5:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
                mask  = mask.transpose(Image.FLIP_LEFT_RIGHT)
            angle = random.uniform(-30, 30)
            image = image.rotate(angle, resample=Image.BILINEAR, fillcolor=(0, 0, 0))
            mask  = mask.rotate(angle, resample=Image.NEAREST,   fillcolor=255)

        encoded = self.processor(
            images=image,
            segmentation_maps=mask,
            return_tensors="pt",
        )
        return {
            "pixel_values": encoded["pixel_values"].squeeze(0),
            "labels":       encoded["labels"].squeeze(0).long(),
        }

# ─── Training loop ────────────────────────────────────────────────────────────

def compute_miou(preds: torch.Tensor, labels: torch.Tensor, num_classes: int) -> float:
    ious = []
    preds  = preds.view(-1)
    labels = labels.view(-1)
    for cls in range(num_classes):
        pred_c  = preds == cls
        label_c = labels == cls
        if label_c.sum() == 0:
            continue
        intersection = (pred_c & label_c).sum().float()
        union        = (pred_c | label_c).sum().float()
        ious.append((intersection / (union + 1e-6)).item())
    return float(np.mean(ious)) if ious else 0.0


def train():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Training on: {device}")

    processor = SegformerImageProcessor.from_pretrained("nvidia/mit-b2", do_reduce_labels=False)
    model = SegformerForSemanticSegmentation.from_pretrained(
        "nvidia/mit-b2",
        num_labels=NUM_CLASSES,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    ).to(device)

    train_ds = WoundDataset("train", processor)
    val_ds   = WoundDataset("val",   processor)
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=2, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)

    optimizer  = AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    scheduler  = get_scheduler("cosine", optimizer, num_warmup_steps=len(train_dl), num_training_steps=NUM_EPOCHS * len(train_dl))

    best_miou = 0.0
    for epoch in range(NUM_EPOCHS):
        # ── Train
        model.train()
        train_loss = 0.0
        for batch in train_dl:
            pixel_values = batch["pixel_values"].to(device)
            labels       = batch["labels"].to(device)

            outputs = model(pixel_values=pixel_values, labels=labels)
            loss    = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            train_loss += loss.item()

        # ── Validate
        model.eval()
        val_mious = []
        with torch.no_grad():
            for batch in val_dl:
                pv  = batch["pixel_values"].to(device)
                lbl = batch["labels"].to(device)
                out = model(pixel_values=pv)
                logits_up = F.interpolate(out.logits, size=lbl.shape[-2:], mode="bilinear", align_corners=False)
                preds = logits_up.argmax(dim=1)
                # Ignore 255 (unlabelled)
                valid = lbl != 255
                val_mious.append(compute_miou(preds[valid], lbl[valid], NUM_CLASSES))

        epoch_miou = float(np.mean(val_mious))
        print(f"Epoch {epoch+1:03d}/{NUM_EPOCHS} | loss: {train_loss/len(train_dl):.4f} | val mIoU: {epoch_miou:.4f}")

        if epoch_miou > best_miou:
            best_miou = epoch_miou
            model.save_pretrained(OUTPUT_DIR)
            processor.save_pretrained(OUTPUT_DIR)
            print(f"  ↑ New best mIoU {best_miou:.4f} — saved to {OUTPUT_DIR}")

    print(f"Training complete. Best val mIoU: {best_miou:.4f}")


if __name__ == "__main__":
    train()
