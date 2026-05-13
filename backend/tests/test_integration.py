"""
Integration test — full pipeline without real model weights.

Tests the complete /analyze flow using:
  - Synthetic wound image (generated in-process)
  - MockWoundSegmenter   (ellipse mask)
  - MockTissueClassifier (HSV heuristics)
  - Real calibration engine (Hough circles)
  - Real scoring engine (PUSH, RESVECH, GHI, NERDS/STONES)
  - Gemini agent is SKIPPED (no API key required)

Run: python -m pytest tests/test_integration.py -v

NOTE: Skips tests that need GEMINI_API_KEY unless it's set in env.
"""

import sys
import os
import io
import base64
import json
import numpy as np
import cv2
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic image factory
# ─────────────────────────────────────────────────────────────────────────────

def _make_wound_image_bytes(
    width: int = 1024,
    height: int = 768,
    coin_dia_mm: float = 23.0,
    px_per_mm: float = 7.5,
) -> bytes:
    """
    Generate a JPEG-encoded synthetic wound image with:
      - Textured reddish skin background
      - A grey coin circle (for calibration)
      - A darker wound region in the centre
    """
    rng = np.random.default_rng(99)

    # Skin-tone noise background
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 2] = rng.integers(160, 200, (height, width)).astype(np.uint8)  # R
    img[:, :, 1] = rng.integers(100, 140, (height, width)).astype(np.uint8)  # G
    img[:, :, 0] = rng.integers(80,  120, (height, width)).astype(np.uint8)  # B

    # Draw wound (dark reddish ellipse centre)
    cx, cy = width // 2, height // 2
    cv2.ellipse(img, (cx, cy), (90, 65), 10, 0, 360, (45, 30, 80), -1)   # dark wound
    cv2.ellipse(img, (cx, cy), (70, 50), 10, 0, 180, (60, 50, 120), -1)  # granulation tone
    # Slough patch (yellowish)
    cv2.ellipse(img, (cx - 20, cy + 10), (25, 18), 0, 0, 360, (30, 160, 180), -1)

    # Draw coin (top-right corner)
    coin_r = int(coin_dia_mm * px_per_mm / 2)
    coin_cx, coin_cy = width - coin_r - 40, coin_r + 40
    cv2.circle(img, (coin_cx, coin_cy), coin_r, (200, 200, 200), -1)
    cv2.circle(img, (coin_cx, coin_cy), coin_r, (170, 170, 170), 2)

    # Add grain noise for sharpness (Laplacian > 80)
    noise = rng.integers(-18, 18, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Encode to JPEG bytes
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Unit-level pipeline component tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineComponents:

    def setup_method(self):
        self.img_bytes = _make_wound_image_bytes()
        pil = Image.open(io.BytesIO(self.img_bytes)).convert("RGB")
        self.img_rgb = np.array(pil)
        self.img_bgr = cv2.cvtColor(self.img_rgb, cv2.COLOR_RGB2BGR)

    def test_quality_gate_passes(self):
        from cv.quality_gate import check_image_quality
        result = check_image_quality(self.img_bgr)
        assert result["pass"], f"Quality gate failed on synthetic image: {result['issues']}"
        assert result["blur_score"] > 80
        assert 40 < result["brightness"] < 230

    def test_calibration_detects_coin(self):
        from cv.calibration import get_px_per_mm
        px_per_mm, success, debug = get_px_per_mm(self.img_bgr, "INR_5")
        assert success, f"Calibration failed: {debug}"
        assert 3.0 < px_per_mm < 20.0, f"px/mm out of range: {px_per_mm}"

    def test_mock_segmenter_produces_mask(self):
        from cv.mock_segmenter import MockWoundSegmenter
        seg = MockWoundSegmenter()
        cx, cy = self.img_rgb.shape[1] // 2, self.img_rgb.shape[0] // 2
        mask = seg.segment(self.img_rgb, cx, cy, px_per_mm=7.5)
        assert mask.dtype == bool
        assert mask.shape == (self.img_rgb.shape[0], self.img_rgb.shape[1])
        wound_px = mask.sum()
        assert wound_px > 500, f"Mask too small: {wound_px}px"
        assert wound_px < (mask.size * 0.5), "Mask covers >50% of image — unrealistic"

    def test_geometry_computes_real_units(self):
        from cv.mock_segmenter import MockWoundSegmenter
        from cv.geometry import compute_geometry
        seg = MockWoundSegmenter()
        cx, cy = self.img_rgb.shape[1] // 2, self.img_rgb.shape[0] // 2
        mask = seg.segment(self.img_rgb, cx, cy, px_per_mm=7.5)
        geo = compute_geometry(mask, px_per_mm=7.5)

        assert 0.5 < geo["area_cm2"] < 50.0,     f"Area out of range: {geo['area_cm2']}"
        assert geo["perimeter_cm"] > 0,           "Perimeter must be > 0"
        assert 0 < geo["circularity"] <= 1.0,     f"Circularity out of range: {geo['circularity']}"
        assert geo["longest_axis_cm"] > 0
        assert geo["shortest_axis_cm"] > 0
        assert geo["aspect_ratio"] >= 1.0

    def test_inflammation_index_range(self):
        from cv.mock_segmenter import MockWoundSegmenter
        from cv.periwound import compute_inflammation_index
        seg = MockWoundSegmenter()
        cx, cy = self.img_rgb.shape[1] // 2, self.img_rgb.shape[0] // 2
        mask = seg.segment(self.img_rgb, cx, cy, px_per_mm=7.5)
        result = compute_inflammation_index(self.img_bgr, mask)

        assert 0.0 <= result["inflammation_index"] <= 100.0
        assert result["periwound_px_count"] >= 0

    def test_mock_tissue_classifier_sums_to_100(self):
        from cv.mock_segmenter import MockWoundSegmenter
        from cv.mock_tissue_classifier import MockTissueClassifier
        seg = MockWoundSegmenter()
        clf = MockTissueClassifier()
        cx, cy = self.img_rgb.shape[1] // 2, self.img_rgb.shape[0] // 2
        mask = seg.segment(self.img_rgb, cx, cy, px_per_mm=7.5)
        result = clf.classify(self.img_rgb, mask)

        total_pct = (
            result["granulation_pct"] + result["slough_pct"] +
            result["necrotic_pct"] + result["epithelial_pct"]
        )
        assert abs(total_pct - 100.0) < 1.0, f"Tissue pct sum {total_pct:.2f} ≠ 100"
        assert result["dominant_tissue"] in ["granulation", "slough", "necrotic", "epithelial"]
        assert result["total_wound_px"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Scoring engine integration with mock pipeline outputs
# ─────────────────────────────────────────────────────────────────────────────

class TestScoringIntegration:

    def _run_mock_pipeline(self):
        """Run the mock CV pipeline and return aggregated metrics dict."""
        import io
        from PIL import Image
        from cv.mock_segmenter import MockWoundSegmenter
        from cv.mock_tissue_classifier import MockTissueClassifier
        from cv.geometry import compute_geometry
        from cv.periwound import compute_inflammation_index

        img_bytes = _make_wound_image_bytes()
        pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_rgb = np.array(pil)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

        px_per_mm = 7.5
        cx, cy = img_rgb.shape[1] // 2, img_rgb.shape[0] // 2

        seg  = MockWoundSegmenter()
        clf  = MockTissueClassifier()
        mask = seg.segment(img_rgb, cx, cy, px_per_mm=px_per_mm)
        geo  = compute_geometry(mask, px_per_mm=px_per_mm)
        infl = compute_inflammation_index(img_bgr, mask)
        tissue = clf.classify(img_rgb, mask)

        return {**geo, **tissue, **infl}

    def test_push_score_in_valid_range(self):
        from scoring.engine import ClinicalScoringEngine
        scorer = ClinicalScoringEngine()
        metrics = self._run_mock_pipeline()
        score = scorer.push_score(metrics["area_cm2"], "light", metrics["dominant_tissue"])
        assert 0 <= score <= 17, f"PUSH score {score} out of valid range 0-17"

    def test_resvech_score_in_valid_range(self):
        from scoring.engine import ClinicalScoringEngine
        scorer = ClinicalScoringEngine()
        metrics = self._run_mock_pipeline()
        score = scorer.resvech_score(
            area_cm2=metrics["area_cm2"],
            edges="diffuse",
            tissue_pct=metrics,
            exudate="moderate",
            infection_flag_count=0,
        )
        assert 0 <= score <= 35, f"RESVECH score {score} out of valid range 0-35"

    def test_composite_score_in_valid_range(self):
        from scoring.engine import ClinicalScoringEngine
        scorer = ClinicalScoringEngine()
        metrics = self._run_mock_pipeline()
        score = scorer.composite_score(metrics, metrics["inflammation_index"], metrics["circularity"])
        assert 0 <= score <= 100, f"Composite score {score} out of range"

    def test_full_metrics_dict_complete(self):
        """All keys consumed by WoundAgent must be present in aggregated metrics."""
        metrics = self._run_mock_pipeline()
        required_keys = [
            "area_cm2", "perimeter_cm", "circularity",
            "granulation_pct", "slough_pct", "necrotic_pct", "epithelial_pct",
            "dominant_tissue", "inflammation_index",
        ]
        for key in required_keys:
            assert key in metrics, f"Missing metric key: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI endpoint integration test (uses httpx + TestClient)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping full API test"
)
class TestAPIEndpoint:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Boot FastAPI in MOCK_MODE for testing."""
        os.environ["MOCK_MODE"] = "true"
        try:
            from fastapi.testclient import TestClient
            from main import app
            self.client = TestClient(app)
        except ImportError:
            pytest.skip("httpx not installed — pip install httpx")

    def test_health_endpoint(self):
        r = self.client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["mock_mode"] is True
        assert data["medsam_loaded"] is True
        assert data["segformer_loaded"] is True

    def test_coins_endpoint(self):
        r = self.client.get("/coins")
        assert r.status_code == 200
        coins = r.json()
        assert len(coins) > 0
        assert all("key" in c and "label" in c for c in coins)

    def test_analyze_endpoint_full_pipeline(self):
        img_bytes = _make_wound_image_bytes()
        h, w = 768, 1024
        r = self.client.post(
            "/analyze",
            data={
                "coin_type": "INR_5",
                "click_x":   str(w // 2),
                "click_y":   str(h // 2),
            },
            files={"image": ("wound.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        )
        assert r.status_code == 200, f"API returned {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["status"] == "success", f"Expected success, got: {data.get('status')}"

        # Calibration
        assert data["calibration"]["px_per_mm"] > 0

        # Geometry
        assert data["geometry"]["area_cm2"] > 0

        # Tissue
        assert "granulation_pct" in data["tissue"]
        total_pct = sum(data["tissue"][k] for k in
                        ["granulation_pct", "slough_pct", "necrotic_pct", "epithelial_pct"])
        assert abs(total_pct - 100.0) < 2.0

        # Scores
        assert 0 <= data["scores"]["composite_score"] <= 100

        # Annotated images
        assert "annotated_b64" in data["images"]
        b64 = data["images"]["annotated_b64"]
        assert len(b64) > 100
        # Verify it's valid base64 JPEG
        decoded = base64.b64decode(b64)
        assert decoded[:3] == b"\xff\xd8\xff"  # JPEG magic bytes


class TestAPIWithoutGemini:
    """Tests that run WITHOUT Gemini API key — mocks the agent."""

    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        os.environ["MOCK_MODE"] = "true"

        # Stub out WoundAgent so no Gemini call is made
        class _MockAgent:
            def __init__(self, computed_metrics): pass
            def run(self, pil_image): return {
                "healing_phase": "Proliferative",
                "TIME": {"T": "Mock T", "I": "Mock I", "M": "Mock M", "E": "Mock E"},
                "push_score": 7,
                "resvech_score": 12,
                "composite_healing_score": 58.0,
                "infection_risk": {"level": "LOW", "NERDS_score": 0, "STONES_score": 0, "active_flags": []},
                "healing_trajectory": "FIRST_SESSION",
                "estimated_closure_days": None,
                "clinical_summary": "Mock clinical summary for integration testing.",
                "recommendations": ["Mock recommendation 1"],
                "red_flags": [],
            }

        monkeypatch.setattr("main.WoundAgent", _MockAgent)

        try:
            from fastapi.testclient import TestClient
            import importlib
            import main as main_mod
            importlib.reload(main_mod)
            self.client = TestClient(main_mod.app)
        except ImportError:
            pytest.skip("httpx not installed — pip install httpx")

    def test_health(self):
        r = self.client.get("/health")
        assert r.status_code == 200

    def test_analyze_without_gemini_key(self):
        img_bytes = _make_wound_image_bytes()
        h, w = 768, 1024
        r = self.client.post(
            "/analyze",
            data={"coin_type": "INR_5", "click_x": str(w // 2), "click_y": str(h // 2)},
            files={"image": ("wound.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["geometry"]["area_cm2"] > 0
        assert data["clinical_assessment"]["healing_phase"] == "Proliferative"
        assert data["images"]["annotated_b64"]
