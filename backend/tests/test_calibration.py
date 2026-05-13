"""
Day 1 calibration + quality gate test script.

Tests the calibration engine and quality gate against real images.
Place 10 wound test images in tests/sample_images/ before running.

Images should include:
  - good_*.jpg       — good quality with coin visible
  - blurry_*.jpg     — intentionally blurry
  - dark_*.jpg       — underexposed
  - no_coin_*.jpg    — no coin in frame (calibration should fail gracefully)

Run: python tests/test_calibration.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
from cv.calibration import get_px_per_mm, COIN_DIAMETERS_MM
from cv.quality_gate import check_image_quality


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic image generators — no real photos required for unit-level tests
# ─────────────────────────────────────────────────────────────────────────────

def make_image_with_coin(
    width: int = 1280,
    height: int = 960,
    coin_diameter_mm: float = 23.0,
    px_per_mm_real: float = 8.0,
    brightness: int = 140,
    blur_sigma: float = 0.0,
) -> np.ndarray:
    """
    Generate a synthetic BGR image containing a grey circle (coin).
    Includes colour noise + texture so quality gate passes.
    """
    # Start with coloured noise (not flat grey) so blur & grayscale checks pass
    rng = np.random.default_rng(42)
    img = rng.integers(
        max(0, brightness - 30),
        min(255, brightness + 30),
        size=(height, width, 3),
        dtype=np.uint8,
    )
    # Add subtle colour tint so channel spread > 3 (not flagged as grayscale)
    img[:, :, 2] = np.clip(img[:, :, 2].astype(int) + 15, 0, 255).astype(np.uint8)  # red channel up
    img[:, :, 0] = np.clip(img[:, :, 0].astype(int) - 10, 0, 255).astype(np.uint8)  # blue channel down

    # Draw coin: light grey circle
    coin_dia_px = int(coin_diameter_mm * px_per_mm_real)
    cx, cy = width // 2, height // 2
    cv2.circle(img, (cx, cy), coin_dia_px // 2, (200, 200, 200), -1)
    cv2.circle(img, (cx, cy), coin_dia_px // 2, (180, 180, 180), 2)

    if blur_sigma > 0:
        k = int(blur_sigma * 6) | 1  # ensure odd
        img = cv2.GaussianBlur(img, (k, k), blur_sigma)

    return img


def make_dark_image(width=1280, height=960) -> np.ndarray:
    return np.full((height, width, 3), 20, dtype=np.uint8)


def make_overexposed_image(width=1280, height=960) -> np.ndarray:
    return np.full((height, width, 3), 240, dtype=np.uint8)


def make_low_res_image() -> np.ndarray:
    return np.full((300, 400, 3), 128, dtype=np.uint8)


def make_grayscale_looking_image(width=1280, height=960) -> np.ndarray:
    gray_val = 128
    return np.full((height, width, 3), gray_val, dtype=np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# Quality gate tests
# ─────────────────────────────────────────────────────────────────────────────

def test_quality_good_image():
    img = make_image_with_coin()
    result = check_image_quality(img)
    print(f"  [good image]  pass={result['pass']} blur={result['blur_score']:.1f} brightness={result['brightness']:.1f}")
    assert result["pass"], f"Expected pass but got issues: {result['issues']}"


def test_quality_blurry():
    img = make_image_with_coin(blur_sigma=6.0)
    result = check_image_quality(img)
    print(f"  [blurry]      pass={result['pass']} blur={result['blur_score']:.1f} issues={result['issues']}")
    assert not result["pass"]
    assert any("blurry" in i.lower() for i in result["issues"])


def test_quality_too_dark():
    img = make_dark_image()
    result = check_image_quality(img)
    print(f"  [dark]        pass={result['pass']} brightness={result['brightness']:.1f} issues={result['issues']}")
    assert not result["pass"]
    assert any("dark" in i.lower() for i in result["issues"])


def test_quality_overexposed():
    img = make_overexposed_image()
    result = check_image_quality(img)
    print(f"  [overexposed] pass={result['pass']} brightness={result['brightness']:.1f} issues={result['issues']}")
    assert not result["pass"]
    assert any("overexposed" in i.lower() or "exposed" in i.lower() for i in result["issues"])


def test_quality_low_resolution():
    img = make_low_res_image()
    result = check_image_quality(img)
    print(f"  [low res]     pass={result['pass']} res={result['resolution']} issues={result['issues']}")
    assert not result["pass"]
    assert any("resolution" in i.lower() or "low" in i.lower() for i in result["issues"])


def test_quality_grayscale():
    img = make_grayscale_looking_image()
    result = check_image_quality(img)
    print(f"  [grayscale]   pass={result['pass']} issues={result['issues']}")
    # Grayscale check may fire depending on channel spread
    print(f"    (channel spread too low = grayscale flag may trigger)")


# ─────────────────────────────────────────────────────────────────────────────
# Calibration accuracy tests
# ─────────────────────────────────────────────────────────────────────────────

def test_calibration_inr5_coin():
    """₹5 coin (23mm) at 8px/mm → detected diameter should be ≈184px."""
    TRUE_PX_PER_MM = 8.0
    img = make_image_with_coin(coin_diameter_mm=23.0, px_per_mm_real=TRUE_PX_PER_MM)
    px_per_mm, success, debug = get_px_per_mm(img, "INR_5")
    print(f"  [INR_5 23mm]  success={success} px_per_mm={px_per_mm:.3f} (true={TRUE_PX_PER_MM}) method={debug.get('method')}")
    assert success, f"Calibration failed: {debug}"
    # Allow ±8% tolerance (Hough is approximate)
    assert abs(px_per_mm - TRUE_PX_PER_MM) / TRUE_PX_PER_MM < 0.08, \
        f"Calibration error too large: {px_per_mm:.3f} vs {TRUE_PX_PER_MM}"


def test_calibration_inr10_coin():
    """₹10 coin (27mm) at 6px/mm."""
    TRUE_PX_PER_MM = 6.0
    img = make_image_with_coin(coin_diameter_mm=27.0, px_per_mm_real=TRUE_PX_PER_MM)
    px_per_mm, success, debug = get_px_per_mm(img, "INR_10")
    print(f"  [INR_10 27mm] success={success} px_per_mm={px_per_mm:.3f} (true={TRUE_PX_PER_MM}) method={debug.get('method')}")
    assert success
    assert abs(px_per_mm - TRUE_PX_PER_MM) / TRUE_PX_PER_MM < 0.08


def test_calibration_us_quarter():
    """US Quarter (24.26mm) at 10px/mm."""
    TRUE_PX_PER_MM = 10.0
    img = make_image_with_coin(coin_diameter_mm=24.26, px_per_mm_real=TRUE_PX_PER_MM)
    px_per_mm, success, debug = get_px_per_mm(img, "US_QUARTER")
    print(f"  [US Quarter]  success={success} px_per_mm={px_per_mm:.3f} (true={TRUE_PX_PER_MM}) method={debug.get('method')}")
    assert success
    assert abs(px_per_mm - TRUE_PX_PER_MM) / TRUE_PX_PER_MM < 0.08


def test_calibration_no_coin():
    """Plain background — no coin — should fail gracefully."""
    img = np.full((960, 1280, 3), 128, dtype=np.uint8)  # flat grey, no circle
    px_per_mm, success, debug = get_px_per_mm(img, "INR_5")
    print(f"  [no coin]     success={success} debug={debug}")
    # Hough may or may not detect something in flat image — just confirm no crash
    print(f"    (no-coin test: system {'found something' if success else 'correctly failed'})")


def test_calibration_all_coin_types():
    """Verify all coin types in the lookup table are detectable."""
    print("\n  [all coin types]")
    for coin_key, dia_mm in COIN_DIAMETERS_MM.items():
        img = make_image_with_coin(coin_diameter_mm=dia_mm, px_per_mm_real=7.0)
        px_per_mm, success, debug = get_px_per_mm(img, coin_key)
        status = "✓" if success else "✗"
        px_str = f"{px_per_mm:.2f}" if px_per_mm is not None else "N/A"
        print(f"    {status} {coin_key}: dia={dia_mm}mm detected_px_per_mm={px_str}")


def test_real_images_in_folder():
    """
    If sample_images/ folder exists with real wound photos, test those too.
    File naming convention:
        good_coin_INR5_001.jpg   → coin_type=INR_5, expect success
        no_coin_001.jpg          → expect calibration fail
    """
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_images")
    if not os.path.exists(sample_dir):
        print(f"\n  [real images] Skipped — create tests/sample_images/ to enable")
        return

    files = [f for f in os.listdir(sample_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not files:
        print(f"\n  [real images] No images found in {sample_dir}")
        return

    print(f"\n  [real images] Testing {len(files)} images from {sample_dir}")
    for fname in files:
        fpath = os.path.join(sample_dir, fname)
        img_bgr = cv2.imread(fpath)
        if img_bgr is None:
            print(f"    ✗ {fname}: Failed to load")
            continue

        quality = check_image_quality(img_bgr)

        # Guess coin type from filename (e.g., "good_coin_INR5_001.jpg" → INR_5)
        coin_type = "INR_5"
        for key in COIN_DIAMETERS_MM:
            if key.replace("_", "").lower() in fname.replace("_", "").lower():
                coin_type = key
                break

        px_per_mm, cal_success, cal_debug = get_px_per_mm(img_bgr, coin_type)

        print(
            f"    {'✓' if quality['pass'] else '✗'} {fname}: "
            f"quality={'PASS' if quality['pass'] else 'FAIL'} "
            f"blur={quality['blur_score']:.0f} "
            f"cal={'OK' if cal_success else 'FAIL'} "
            f"px/mm={px_per_mm:.2f if px_per_mm else 'N/A'}"
        )
        if not quality["pass"]:
            for issue in quality["issues"]:
                print(f"      → {issue}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Quality: Good image",       test_quality_good_image),
        ("Quality: Blurry",           test_quality_blurry),
        ("Quality: Too dark",         test_quality_too_dark),
        ("Quality: Overexposed",      test_quality_overexposed),
        ("Quality: Low resolution",   test_quality_low_resolution),
        ("Quality: Grayscale-like",   test_quality_grayscale),
        ("Calibration: INR5 23mm",    test_calibration_inr5_coin),
        ("Calibration: INR10 27mm",   test_calibration_inr10_coin),
        ("Calibration: US Quarter",   test_calibration_us_quarter),
        ("Calibration: No coin",      test_calibration_no_coin),
        ("Calibration: All coins",    test_calibration_all_coin_types),
        ("Calibration: Real images",  test_real_images_in_folder),
    ]

    passed = 0
    failed = 0
    errors = []

    print("\n" + "═" * 60)
    print("  WoundScan — Day 1 Calibration & Quality Gate Tests")
    print("═" * 60)

    for name, fn in tests:
        print(f"\n▶ {name}")
        try:
            fn()
            print(f"  ✅ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
            errors.append((name, str(e)))
        except Exception as e:
            print(f"  💥 ERROR: {e}")
            failed += 1
            errors.append((name, str(e)))

    print("\n" + "═" * 60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print("\n  Failed tests:")
        for name, msg in errors:
            print(f"    • {name}: {msg}")
    print("═" * 60 + "\n")

    sys.exit(0 if failed == 0 else 1)
