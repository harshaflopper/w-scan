# ════════════════════════════════════════════════════════════════════════════
# WoundScan — SegFormer Fine-tuning on Medetec/FUSeg Wound Dataset
# Google Colab T4  |  B0 ~25 min  |  B2 ~3 hrs  |  Free tier OK
#
# Dataset structure confirmed:
#   wound-segmentation-master/data/Medetec_foot_ulcer_224/{split}/images/*.png
#   wound-segmentation-master/data/Medetec_foot_ulcer_224/{split}/labels/*.png
#
# No albumentations — uses torchvision only (avoids version conflicts).
# Paste each CELL block into a separate Colab cell and run top-to-bottom.
# ════════════════════════════════════════════════════════════════════════════


# ── CELL 1 ── GPU check + install ───────────────────────────────────────────
"""
!nvidia-smi
!pip install -q transformers==4.46.3 accelerate
"""


# ── CELL 2 ── Mount Google Drive ────────────────────────────────────────────
"""
from google.colab import drive
drive.mount('/content/drive')
import os
DRIVE_DIR = '/content/drive/MyDrive/wscan_training'
os.makedirs(DRIVE_DIR, exist_ok=True)
print(f"Drive ready → {DRIVE_DIR}")
"""


# ── CELL 3 ── Download dataset ───────────────────────────────────────────────
"""
import os, shutil

FUSEG_URL = "https://github.com/uwm-bigdata/wound-segmentation/archive/refs/heads/master.zip"

# Remove previous extraction to avoid interactive "replace?" prompts
if os.path.exists('/content/wound-segmentation-master'):
    shutil.rmtree('/content/wound-segmentation-master')

print("Downloading uwm-bigdata/wound-segmentation ...")
!wget -q --show-progress -O /content/fuseg.zip "{FUSEG_URL}"
!unzip -o -q /content/fuseg.zip -d /content/
!ls /content/wound-segmentation-master/data/
print("\n✔ Dataset extracted")
"""


# ── CELL 4 ── Inspect + set BASE ────────────────────────────────────────────
"""
import os, glob

BASE = '/content/wound-segmentation-master'

img_pngs  = sorted(glob.glob(f"{BASE}/**/images/*.png", recursive=True))
mask_pngs = sorted(glob.glob(f"{BASE}/**/labels/*.png", recursive=True))

print(f"Image PNGs : {len(img_pngs)}")
print(f"Mask  PNGs : {len(mask_pngs)}")
print(f"\nSample image : {img_pngs[0] if img_pngs else 'NONE'}")
print(f"Sample mask  : {mask_pngs[0] if mask_pngs else 'NONE'}")
"""


# ── CELL 5 ── Build train / val split ────────────────────────────────────────
"""
import os, glob, shutil, random
import numpy as np
from PIL import Image

BASE      = '/content/wound-segmentation-master'
DATA      = '/content/wound_data'
VAL_RATIO = 0.15

for split in ['train', 'val']:
    os.makedirs(f'{DATA}/images/{split}', exist_ok=True)
    os.makedirs(f'{DATA}/masks/{split}',  exist_ok=True)

def remap_mask(arr):
    if int(arr.max()) <= 3:
        return arr.astype(np.uint8)
    out = np.zeros_like(arr, dtype=np.uint8)
    for src, dst in [(0,0),(85,1),(170,2),(255,3)]:
        out[arr == src] = dst
    return out

img_pngs  = sorted(glob.glob(f"{BASE}/**/images/*.png", recursive=True))
mask_pngs = sorted(glob.glob(f"{BASE}/**/labels/*.png", recursive=True))

mask_by_stem = {os.path.splitext(os.path.basename(m))[0]: m for m in mask_pngs}
pairs = [(img, mask_by_stem[os.path.splitext(os.path.basename(img))[0]])
         for img in img_pngs
         if os.path.splitext(os.path.basename(img))[0] in mask_by_stem]

print(f"Matched pairs: {len(pairs)}")
assert len(pairs) > 0, "No pairs matched — check BASE path"
print(f"Sample: {pairs[0][0].split('/')[-1]}  ↔  {pairs[0][1].split('/')[-1]}")

random.shuffle(pairs)
n_val = max(1, int(len(pairs) * VAL_RATIO))
split_data = {'val': pairs[:n_val], 'train': pairs[n_val:]}

for split, sp in split_data.items():
    for i, (img_path, msk_path) in enumerate(sp):
        stem = f"{split}_{i:04d}"
        Image.open(img_path).convert("RGB").save(f"{DATA}/images/{split}/{stem}.jpg", quality=95)
        Image.fromarray(remap_mask(np.array(Image.open(msk_path).convert("L")))).save(
            f"{DATA}/masks/{split}/{stem}.png")
    print(f"  {split}: {len(sp)} pairs")

print(f"\n✔ Dataset ready at {DATA}")
"""


# ── CELL 6 ── Dataset class (pure torchvision — no albumentations) ───────────
"""
import os, random
import numpy as np
from PIL import Image
from torch.utils.data import Dataset
import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TF
import torchvision.transforms as T

DATA          = '/content/wound_data'
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]


def train_transform(image, mask):
    # Random resized crop (paired)
    i, j, h, w = T.RandomResizedCrop.get_params(image, scale=(0.6, 1.0), ratio=(0.75, 1.33))
    image = TF.resized_crop(image, i, j, h, w, size=[512, 512])
    mask  = TF.resized_crop(mask,  i, j, h, w, size=[512, 512],
                            interpolation=TF.InterpolationMode.NEAREST)
    # Horizontal flip
    if random.random() > 0.5:
        image, mask = TF.hflip(image), TF.hflip(mask)
    # Vertical flip
    if random.random() > 0.3:
        image, mask = TF.vflip(image), TF.vflip(mask)
    # 90° rotation
    if random.random() > 0.4:
        k = random.choice([90, 180, 270])
        image = TF.rotate(image, k)
        mask  = TF.rotate(mask,  k)
    # Colour jitter (image only)
    image = TF.adjust_brightness(image, 1 + random.uniform(-0.3, 0.3))
    image = TF.adjust_contrast(image,   1 + random.uniform(-0.3, 0.3))
    image = TF.adjust_saturation(image, 1 + random.uniform(-0.3, 0.3))
    # To tensor + normalise
    pv  = TF.normalize(TF.to_tensor(image), IMAGENET_MEAN, IMAGENET_STD)
    lbl = torch.from_numpy(np.array(mask)).long()
    return pv, lbl


def val_transform(image, mask):
    image = TF.resize(image, [512, 512])
    mask  = TF.resize(mask,  [512, 512], interpolation=TF.InterpolationMode.NEAREST)
    pv  = TF.normalize(TF.to_tensor(image), IMAGENET_MEAN, IMAGENET_STD)
    lbl = torch.from_numpy(np.array(mask)).long()
    return pv, lbl


class WoundDataset(Dataset):
    def __init__(self, split):
        self.img_dir  = f"{DATA}/images/{split}"
        self.msk_dir  = f"{DATA}/masks/{split}"
        self.files    = sorted(f for f in os.listdir(self.img_dir) if f.endswith(".jpg"))
        self.is_train = (split == "train")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        stem  = os.path.splitext(self.files[idx])[0]
        image = Image.open(f"{self.img_dir}/{self.files[idx]}").convert("RGB")
        mask  = Image.open(f"{self.msk_dir}/{stem}.png").convert("L")
        pv, lbl = (train_transform if self.is_train else val_transform)(image, mask)
        # Downsample label to match SegFormer output (H/4, W/4)
        lbl_4x = F.interpolate(
            lbl.unsqueeze(0).unsqueeze(0).float(),
            size=(pv.shape[1] // 4, pv.shape[2] // 4),
            mode="nearest"
        ).squeeze().long()
        return {"pixel_values": pv, "labels": lbl_4x}


# Sanity check
ds = WoundDataset("train")
s  = ds[0]
print(f"pixel_values : {s['pixel_values'].shape}  dtype={s['pixel_values'].dtype}")
print(f"labels       : {s['labels'].shape}  unique={s['labels'].unique().tolist()}")
print(f"Train={len(WoundDataset('train'))}  Val={len(WoundDataset('val'))}")
"""


# ── CELL 7 ── Choose model size + load backbone ──────────────────────────────
"""
import torch
from transformers import SegformerForSemanticSegmentation

# ┌──────────────────────────────────────────────────────────────────┐
# │  'B0'  → 3.7M params  ~25 min on T4   mIoU ≈ 0.60–0.65        │
# │  'B2'  → 25M  params  ~3 hrs on T4    mIoU ≈ 0.70–0.75        │
# └──────────────────────────────────────────────────────────────────┘
MODEL_SIZE = 'B0'   # ← change to 'B2' for production

BACKBONE_MAP = {
    'B0': ('nvidia/mit-b0', 8e-5,  30),
    'B2': ('nvidia/mit-b2', 6e-5,  80),
    'B4': ('nvidia/mit-b4', 4e-5, 100),
}
HF_ID, DEFAULT_LR, DEFAULT_EPOCHS = BACKBONE_MAP[MODEL_SIZE]

ID2LABEL = {0: 'granulation', 1: 'slough', 2: 'necrotic', 3: 'epithelial'}
LABEL2ID = {v: k for k, v in ID2LABEL.items()}

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Device : {device}  |  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
print(f"Model  : SegFormer-{MODEL_SIZE}  ({HF_ID})")

model = SegformerForSemanticSegmentation.from_pretrained(
    HF_ID,
    num_labels=4,
    id2label=ID2LABEL,
    label2id=LABEL2ID,
    ignore_mismatched_sizes=True,
)
model.to(device)
params = sum(p.numel() for p in model.parameters()) / 1e6
print(f"Params : {params:.1f}M")
print(f"Est.   : ~{int(DEFAULT_EPOCHS * (0.5 if MODEL_SIZE=='B0' else 2.2))} min on T4")
"""


# ── CELL 8 ── DataLoaders + optimizer + scheduler ────────────────────────────
"""
from torch.utils.data import DataLoader
from transformers import get_cosine_schedule_with_warmup
from torch.optim import AdamW
import os

NUM_EPOCHS   = DEFAULT_EPOCHS
BATCH_SIZE   = 8
LR           = DEFAULT_LR
WEIGHT_DECAY = 0.01

OUTPUT_DIR = '/content/segformer_wound'
DRIVE_CKPT = '/content/drive/MyDrive/wscan_training/segformer_wound'
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DRIVE_CKPT, exist_ok=True)

train_dl = DataLoader(WoundDataset('train'), batch_size=BATCH_SIZE,
                      shuffle=True,  num_workers=2, pin_memory=True, drop_last=True)
val_dl   = DataLoader(WoundDataset('val'),   batch_size=4,
                      shuffle=False, num_workers=2, pin_memory=True)

optimizer   = AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
total_steps = NUM_EPOCHS * len(train_dl)
scheduler   = get_cosine_schedule_with_warmup(
    optimizer,
    num_warmup_steps   = len(train_dl) * 2,
    num_training_steps = total_steps,
)
print(f"Train batches : {len(train_dl)}  |  Val batches : {len(val_dl)}")
print(f"Total steps   : {total_steps}")
"""


# ── CELL 9 ── mIoU helper ────────────────────────────────────────────────────
"""
import numpy as np

def compute_miou(preds_flat, labels_flat, num_classes=4):
    ious = []
    for c in range(num_classes):
        p = preds_flat == c
        l = labels_flat == c
        if l.sum() == 0:
            continue
        ious.append((p & l).sum() / ((p | l).sum() + 1e-6))
    return float(np.mean(ious)) if ious else 0.0
"""


# ── CELL 10 ── Training loop ─────────────────────────────────────────────────
"""
import torch
import torch.nn.functional as F
from torch.cuda.amp import GradScaler, autocast
import numpy as np

scaler    = GradScaler()
best_miou = 0.0
history   = {'loss': [], 'miou': []}

print(f"\n{'═'*56}")
print(f"  SegFormer-{MODEL_SIZE}  |  {NUM_EPOCHS} epochs  |  lr={LR:.0e}")
print(f"{'═'*56}\n")

for epoch in range(NUM_EPOCHS):

    # ── Train ────────────────────────────────────────────────────────────────
    model.train()
    epoch_loss = 0.0
    for batch in train_dl:
        pv  = batch['pixel_values'].to(device)
        lbl = batch['labels'].to(device)
        optimizer.zero_grad()
        with autocast():
            loss = model(pixel_values=pv, labels=lbl).loss
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        epoch_loss += loss.item()

    # ── Validate ─────────────────────────────────────────────────────────────
    model.eval()
    mious = []
    with torch.no_grad():
        for batch in val_dl:
            pv  = batch['pixel_values'].to(device)
            lbl = batch['labels'].to(device)
            with autocast():
                logits = model(pixel_values=pv).logits
            up    = F.interpolate(logits, size=lbl.shape[-2:],
                                  mode='bilinear', align_corners=False)
            preds = up.argmax(1).cpu().numpy().flatten()
            lbls  = lbl.cpu().numpy().flatten()
            mious.append(compute_miou(preds, lbls))

    avg_loss = epoch_loss / len(train_dl)
    val_miou = float(np.mean(mious))
    history['loss'].append(avg_loss)
    history['miou'].append(val_miou)

    print(f"Epoch {epoch+1:03d}/{NUM_EPOCHS}  "
          f"loss={avg_loss:.4f}  mIoU={val_miou:.4f}  "
          f"lr={scheduler.get_last_lr()[0]:.2e}")

    if val_miou > best_miou:
        best_miou = val_miou
        model.save_pretrained(OUTPUT_DIR)
        print(f"  ↑ Best mIoU {best_miou:.4f} — saved")

    if (epoch + 1) % 10 == 0:
        model.save_pretrained(DRIVE_CKPT)
        print(f"  ✓ Drive backup")

print(f"\nTraining complete. Best val mIoU: {best_miou:.4f}")
"""


# ── CELL 11 ── Per-class IoU breakdown ───────────────────────────────────────
"""
import torch, torch.nn.functional as F, numpy as np
from torch.cuda.amp import autocast

model.eval()
cls_ious = {i: [] for i in range(4)}

with torch.no_grad():
    for batch in val_dl:
        pv  = batch['pixel_values'].to(device)
        lbl = batch['labels'].to(device)
        with autocast():
            logits = model(pixel_values=pv).logits
        up    = F.interpolate(logits, size=lbl.shape[-2:], mode='bilinear', align_corners=False)
        preds = up.argmax(1).cpu().numpy().flatten()
        lbls  = lbl.cpu().numpy().flatten()
        for c in range(4):
            p = preds == c; l = lbls == c
            if l.sum():
                cls_ious[c].append((p & l).sum() / ((p | l).sum() + 1e-6))

print(f"{'─'*42}")
print(f"  Per-class Validation IoU")
print(f"{'─'*42}")
for c, name in ID2LABEL.items():
    iou = float(np.mean(cls_ious[c])) if cls_ious[c] else 0.0
    bar = '█' * int(iou * 30)
    print(f"  {name:12s}  {iou:.3f}  {bar}")
print(f"{'─'*42}")
print(f"  Mean IoU  {best_miou:.3f}")
"""


# ── CELL 12 ── Training curves ───────────────────────────────────────────────
"""
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
fig.suptitle(f"SegFormer-{MODEL_SIZE} Training", color='white', fontsize=12)
fig.patch.set_facecolor('#0b0f1a')

for ax in (ax1, ax2):
    ax.set_facecolor('#111827')
    ax.tick_params(colors='#94a3b8')
    for spine in ax.spines.values():
        spine.set_color('#2a3a52')

ax1.plot(history['loss'], color='#ef4444', linewidth=1.8)
ax1.set_title('Train Loss', color='#e2e8f0')
ax1.set_xlabel('Epoch', color='#94a3b8')

ax2.plot(history['miou'], color='#14b8a6', linewidth=1.8)
ax2.axhline(best_miou, linestyle='--', color='#22c55e', alpha=0.7,
            label=f'Best {best_miou:.4f}')
ax2.set_ylim(0, 1)
ax2.set_title('Val mIoU', color='#e2e8f0')
ax2.set_xlabel('Epoch', color='#94a3b8')
ax2.legend(facecolor='#1a2236', labelcolor='white')

plt.tight_layout()
plt.savefig('/content/training_curves.png', dpi=150, facecolor=fig.get_facecolor())
plt.show()
print("Saved → /content/training_curves.png")
"""


# ── CELL 13 ── Visual prediction check ──────────────────────────────────────
"""
import matplotlib.pyplot as plt
import numpy as np, torch, torch.nn.functional as F
from torch.cuda.amp import autocast

COLORS = {0: [220,80,80], 1: [230,200,50], 2: [70,60,60], 3: [255,180,200]}

def colorise(seg):
    rgb = np.zeros((*seg.shape, 3), dtype=np.uint8)
    for c, col in COLORS.items():
        rgb[seg == c] = col
    return rgb

model.eval()
sample = WoundDataset('val')[0]
pv     = sample['pixel_values'].unsqueeze(0).to(device)
lbl    = sample['labels'].numpy()

with torch.no_grad(), autocast():
    logits = model(pixel_values=pv).logits
up   = F.interpolate(logits, size=lbl.shape, mode='bilinear', align_corners=False)
pred = up.argmax(1).squeeze(0).cpu().numpy()

img = sample['pixel_values'].permute(1, 2, 0).numpy()
img = (img * np.array([0.229, 0.224, 0.225]) + np.array([0.485, 0.456, 0.406])).clip(0, 1)

fig, axes = plt.subplots(1, 3, figsize=(14, 4))
fig.patch.set_facecolor('#0b0f1a')
for ax, im, title in zip(axes, [img, colorise(lbl), colorise(pred)],
                         ['Input Image', 'Ground Truth', f'SegFormer-{MODEL_SIZE}']):
    ax.imshow(im); ax.set_title(title, color='white'); ax.axis('off')

handles = [plt.Rectangle((0,0),1,1, color=[c/255 for c in v]) for v in COLORS.values()]
axes[2].legend(handles, list(ID2LABEL.values()), loc='lower right',
               facecolor='#1a2236', labelcolor='white', fontsize=8)

plt.tight_layout()
plt.savefig('/content/pred_sample.png', dpi=150, facecolor=fig.get_facecolor())
plt.show()
"""


# ── CELL 14 ── Package + download ────────────────────────────────────────────
"""
import shutil, os
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

model = SegformerForSemanticSegmentation.from_pretrained(OUTPUT_DIR)
print(f"Loaded best model (mIoU={best_miou:.4f})")

processor = SegformerImageProcessor.from_pretrained(HF_ID, do_reduce_labels=False)
processor.save_pretrained(OUTPUT_DIR)

shutil.make_archive('/content/segformer_wound', 'zip', OUTPUT_DIR)
size_mb = os.path.getsize('/content/segformer_wound.zip') / 1024 / 1024
print(f"Zipped ({size_mb:.1f} MB) → /content/segformer_wound.zip")

from google.colab import files
files.download('/content/segformer_wound.zip')

print("""
✅ Download started!
   1. Unzip segformer_wound.zip
   2. Move to: backend/models/segformer_wound/
   3. Set MOCK_MODE=false in backend/.env
   4. Restart uvicorn
""")
"""
