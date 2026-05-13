"""
Unit tests for scoring/engine.py — Day 4 requirement.

Tests every scoring function with known inputs against expected outputs
derived from clinical framework documentation.

Run: python -m pytest tests/test_scoring.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date
from scoring.engine import ClinicalScoringEngine

scorer = ClinicalScoringEngine()


# ─────────────────────────────────────────────────────────────────────────────
# PUSH Tool (NPUAP validated)
# Reference: Thomas DR et al. (1997)
# ─────────────────────────────────────────────────────────────────────────────

class TestPushScore:

    def test_healed_wound(self):
        # Area=0, no exudate, epithelial → score should be 0+0+1 = 1
        # Note: PUSH area=0 gives 0, but tissue=epithelial gives 1
        score = scorer.push_score(0.0, "none", "epithelial")
        assert score == 1

    def test_small_granulating(self):
        # Area 0.5cm² → bracket 2, light exudate=1, granulation=2 → total=5
        score = scorer.push_score(0.5, "light", "granulation")
        assert score == 5

    def test_large_necrotic(self):
        # Area 15cm² → bracket 9 (12 < 15 ≤ 24), heavy exudate=3, necrotic=4 → total=16
        score = scorer.push_score(15.0, "heavy", "necrotic")
        assert score == 16

    def test_max_score(self):
        # Area >24 → bracket 10, heavy=3, necrotic=4 → 17
        score = scorer.push_score(30.0, "heavy", "necrotic")
        assert score == 17

    def test_area_brackets(self):
        brackets = [
            (0.0,    0), (0.15,   1), (0.45,   2), (0.8,    3),
            (1.5,    4), (2.5,    5), (3.5,    6), (6.0,    7),
            (10.0,   8), (20.0,   9), (25.0,  10),
        ]
        for area, expected_area_score in brackets:
            # Use none exudate (0) + epithelial (1) so only area_score varies
            total = scorer.push_score(area, "none", "epithelial")
            assert total == expected_area_score + 1, \
                f"area={area}: expected area_score={expected_area_score}, got total={total}"

    def test_invalid_exudate_defaults(self):
        # Unknown exudate defaults to 1 (light)
        score = scorer.push_score(1.0, "unknown_value", "granulation")
        assert score == 3 + 1 + 2  # area_bracket=3, exudate=1, granulation=2


# ─────────────────────────────────────────────────────────────────────────────
# RESVECH 2.0
# Reference: Restrepo-Medrano JC (2018)
# ─────────────────────────────────────────────────────────────────────────────

class TestResvechScore:

    def test_closed_wound(self):
        tissue = {"epithelial_pct": 90, "granulation_pct": 5, "slough_pct": 3, "necrotic_pct": 2}
        score = scorer.resvech_score(
            area_cm2=0,
            edges="closed",
            tissue_pct=tissue,
            exudate="none",
            infection_flag_count=0,
        )
        # sz=0, eg=0, ts=1(epithelial>75), ex=0, inf=0
        assert score == 1

    def test_large_necrotic_wound(self):
        tissue = {"epithelial_pct": 2, "granulation_pct": 5, "slough_pct": 10, "necrotic_pct": 60}
        score = scorer.resvech_score(
            area_cm2=40,
            edges="callous",
            tissue_pct=tissue,
            exudate="abundant",
            infection_flag_count=3,
        )
        # sz=4, eg=3, ts=4(necrotic>50), ex=3, inf=3
        assert score == 17

    def test_moderate_healing(self):
        tissue = {"epithelial_pct": 10, "granulation_pct": 80, "slough_pct": 5, "necrotic_pct": 5}
        score = scorer.resvech_score(
            area_cm2=5,
            edges="defined",
            tissue_pct=tissue,
            exudate="scarce",
            infection_flag_count=0,
        )
        # sz=2(4<5≤16), eg=1, ts=2(granulation>75), ex=1, inf=0
        assert score == 6

    def test_infection_flag_capped_at_4(self):
        tissue = {"epithelial_pct": 5, "granulation_pct": 5, "slough_pct": 5, "necrotic_pct": 5}
        s1 = scorer.resvech_score(0, "closed", tissue, "none", 10)  # capped at 4
        s2 = scorer.resvech_score(0, "closed", tissue, "none", 4)
        assert s1 == s2


# ─────────────────────────────────────────────────────────────────────────────
# Global Healing Index
# ─────────────────────────────────────────────────────────────────────────────

class TestGlobalHealingIndex:

    def test_perfect_healing(self):
        # Area halved, perimeter halved, all granulation
        tissue = {"granulation_pct": 60, "epithelial_pct": 40, "necrotic_pct": 0, "slough_pct": 0}
        ghi = scorer.global_healing_index(10, 5, 20, 10, tissue)
        # SCI=0.5, WCI=0.5, TII=(60*0.4+40*0.6)/100=0.48
        # GHI = 0.5*0.4 + 0.48*0.4 + 0.5*0.2 = 0.2 + 0.192 + 0.1 = 0.492
        assert ghi == pytest.approx(0.492, abs=0.005)

    def test_worsening_wound(self):
        # Area grew, necrosis dominant
        tissue = {"granulation_pct": 5, "epithelial_pct": 0, "necrotic_pct": 80, "slough_pct": 15}
        ghi = scorer.global_healing_index(10, 15, 20, 25, tissue)
        assert ghi < 0  # Negative = deteriorating

    def test_no_initial_area(self):
        tissue = {"granulation_pct": 50, "epithelial_pct": 20, "necrotic_pct": 10, "slough_pct": 20}
        ghi = scorer.global_healing_index(0, 5, 0, 10, tissue)
        assert ghi == 0.0

    def test_fully_healed(self):
        tissue = {"granulation_pct": 0, "epithelial_pct": 100, "necrotic_pct": 0, "slough_pct": 0}
        ghi = scorer.global_healing_index(10, 0, 20, 0, tissue)
        # SCI=1.0, WCI=0.0, TII=0.6
        # GHI = 1.0*0.4 + 0.6*0.4 + 1.0*0.2 = 0.4 + 0.24 + 0.2 = 0.84
        assert ghi == pytest.approx(0.84, abs=0.005)


# ─────────────────────────────────────────────────────────────────────────────
# Healing Velocity & Rate
# ─────────────────────────────────────────────────────────────────────────────

class TestHealingMetrics:

    def test_velocity_two_sessions(self):
        sessions = [
            {"area_cm2": 10.0, "date": date(2024, 1, 1)},
            {"area_cm2":  8.0, "date": date(2024, 1, 8)},
        ]
        vel = scorer.healing_velocity(sessions)
        # (10 - 8) / 7 days = 0.2857
        assert vel == pytest.approx(0.2857, abs=0.001)

    def test_velocity_single_session(self):
        sessions = [{"area_cm2": 10.0, "date": date(2024, 1, 1)}]
        assert scorer.healing_velocity(sessions) == 0.0

    def test_velocity_worsening(self):
        sessions = [
            {"area_cm2": 5.0,  "date": date(2024, 1, 1)},
            {"area_cm2": 8.0,  "date": date(2024, 1, 7)},
        ]
        vel = scorer.healing_velocity(sessions)
        assert vel < 0  # wound growing

    def test_velocity_unsorted_input(self):
        # Should sort by date internally
        sessions = [
            {"area_cm2":  6.0, "date": date(2024, 1, 14)},
            {"area_cm2": 10.0, "date": date(2024, 1,  1)},
            {"area_cm2":  8.0, "date": date(2024, 1,  7)},
        ]
        vel = scorer.healing_velocity(sessions)
        # (10 - 6) / 13 days = 0.3077
        assert vel == pytest.approx(0.3077, abs=0.001)

    def test_healing_rate_pct(self):
        rate = scorer.healing_rate_pct(prev_area=10.0, curr_area=8.0)
        assert rate == pytest.approx(20.0, abs=0.01)  # 20% reduction

    def test_healing_rate_zero_prev(self):
        assert scorer.healing_rate_pct(0.0, 5.0) == 0.0

    def test_healing_rate_worsening(self):
        rate = scorer.healing_rate_pct(5.0, 7.0)
        assert rate < 0  # negative = worsening


# ─────────────────────────────────────────────────────────────────────────────
# Trajectory Classification
# ─────────────────────────────────────────────────────────────────────────────

class TestTrajectory:

    def test_improving(self):
        result = scorer.classify_trajectory(velocity=0.15, score_delta=5.0)
        assert result == "IMPROVING"

    def test_worsening_velocity(self):
        result = scorer.classify_trajectory(velocity=-0.1, score_delta=0.0)
        assert result == "WORSENING"

    def test_worsening_score(self):
        result = scorer.classify_trajectory(velocity=0.01, score_delta=-10.0)
        assert result == "WORSENING"

    def test_stagnating(self):
        result = scorer.classify_trajectory(velocity=0.01, score_delta=0.0)
        assert result == "STAGNATING"

    def test_estimated_closure(self):
        days = scorer.estimated_closure_days(current_area=9.0, velocity=0.36)
        assert days == 25  # int(9.0 / 0.36) = 25

    def test_no_closure_if_not_healing(self):
        assert scorer.estimated_closure_days(9.0, 0.0) is None
        assert scorer.estimated_closure_days(9.0, -0.1) is None


# ─────────────────────────────────────────────────────────────────────────────
# Composite Score
# ─────────────────────────────────────────────────────────────────────────────

class TestCompositeScore:

    def test_optimal_healing(self):
        tissue = {"granulation_pct": 60, "epithelial_pct": 40, "necrotic_pct": 0, "slough_pct": 0}
        score = scorer.composite_score(tissue, inflammation_index=5.0, circularity=0.9)
        assert score > 75  # Should be high for healthy tissue

    def test_poor_healing(self):
        tissue = {"granulation_pct": 5, "epithelial_pct": 0, "necrotic_pct": 70, "slough_pct": 25}
        score = scorer.composite_score(tissue, inflammation_index=85.0, circularity=0.2)
        assert score < 25

    def test_score_bounds(self):
        # Should always be 0-100
        for gran in [0, 50, 100]:
            for necr in [0, 50, 100]:
                tissue = {"granulation_pct": gran, "epithelial_pct": max(0, 100-gran-necr),
                          "necrotic_pct": necr, "slough_pct": 0}
                score = scorer.composite_score(tissue, inflammation_index=50.0, circularity=0.5)
                assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"


# ─────────────────────────────────────────────────────────────────────────────
# NERDS / STONES Infection Risk
# Reference: Sibbald et al. (2006)
# ─────────────────────────────────────────────────────────────────────────────

class TestInfectionRisk:

    def test_low_risk_healthy_wound(self):
        m = {
            "healing_velocity":   0.3,
            "exudate":            "light",
            "granulation_pct":    60,
            "slough_pct":         10,
            "inflammation_index": 30.0,
            "necrotic_pct":       5,
        }
        result = scorer.infection_risk(m)
        assert result["level"] == "LOW"
        assert result["NERDS_score"] == 0
        assert result["STONES_score"] == 0

    def test_high_risk_all_flags(self):
        m = {
            "healing_velocity":   -0.2,  # N (non-healing) + S (size increasing)
            "exudate":            "heavy",  # E (exudate)
            "granulation_pct":    85,    # R (friable — high gran + not healing)
            "slough_pct":         40,    # D (debris)
            "inflammation_index": 80.0,  # E (erythema)
            "necrotic_pct":       35,    # N (necrotic)
        }
        result = scorer.infection_risk(m)
        assert result["level"] == "HIGH"
        assert result["NERDS_score"] >= 3

    def test_moderate_risk(self):
        m = {
            "healing_velocity":   0.0,   # N: non-healing
            "exudate":            "moderate",  # E: increased exudate
            "granulation_pct":    40,
            "slough_pct":         10,
            "inflammation_index": 50.0,
            "necrotic_pct":       10,
        }
        result = scorer.infection_risk(m)
        assert result["level"] in ("MODERATE", "HIGH")
        assert result["NERDS_score"] >= 2

    def test_nerds_non_healing_flag(self):
        m = {"healing_velocity": 0.0, "exudate": "none",
             "granulation_pct": 30, "slough_pct": 5,
             "inflammation_index": 20, "necrotic_pct": 5}
        result = scorer.infection_risk(m)
        assert any("Non-healing" in f for f in result["NERDS"])

    def test_stones_size_increasing_flag(self):
        m = {"healing_velocity": -0.15, "exudate": "none",
             "granulation_pct": 30, "slough_pct": 5,
             "inflammation_index": 20, "necrotic_pct": 5}
        result = scorer.infection_risk(m)
        assert any("size" in f.lower() for f in result["STONES"]), \
            f"Expected size-increasing STONES flag, got: {result['STONES']}"

    def test_erythema_flag(self):
        m = {"healing_velocity": 0.1, "exudate": "none",
             "granulation_pct": 30, "slough_pct": 5,
             "inflammation_index": 75.0, "necrotic_pct": 5}
        result = scorer.infection_risk(m)
        assert any("erythema" in f.lower() for f in result["STONES"]), \
            f"Expected erythema STONES flag, got: {result['STONES']}"

    def test_result_structure(self):
        m = {"healing_velocity": 0.1, "exudate": "none",
             "granulation_pct": 50, "slough_pct": 10,
             "inflammation_index": 25.0, "necrotic_pct": 5}
        result = scorer.infection_risk(m)
        assert "level" in result
        assert "NERDS" in result
        assert "STONES" in result
        assert "NERDS_score" in result
        assert "STONES_score" in result
        assert result["level"] in ("LOW", "MODERATE", "HIGH")
