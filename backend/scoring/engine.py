"""
Clinical wound scoring engine.

All scoring functions are implementations of validated clinical frameworks:

PUSH Tool:
    Thomas DR et al. (1997). "Pressure Ulcer Scale for Healing: derivation
    and validation of the PUSH tool." Advances in Wound Care, 10(5), 96–101.
    Score range: 0 (healed) – 17 (severe).

RESVECH 2.0:
    Restrepo-Medrano JC (2018). "Development of a Wound Healing Index for
    Chronic Wounds." University of Alicante.
    Score range: 0 – 35 (lower = better healing).

Global Healing Index (GHI):
    Adapted from wound contraction indices used in:
    Wound Healing Society (2006). Guidelines for the treatment of arterial
    insufficiency, venous and pressure ulcers.

NERDS / STONES Infection Criteria:
    Sibbald RG et al. (2006). "Preparing the wound bed 2006."
    Advances in Skin & Wound Care, 19(6), 326–337.

Composite Healing Score (0–100):
    Custom composite using tissue %, inflammation, and shape metrics.
    Calibrated so that 50 = baseline partial healing, 100 = fully healed.
"""

from __future__ import annotations
from datetime import date


class ClinicalScoringEngine:

    # ─────────────────────────────────────────────────────────────────────────
    # PUSH Tool (NPUAP)
    # ─────────────────────────────────────────────────────────────────────────
    _PUSH_AREA_BRACKETS: list[tuple[float, int]] = [
        (0.0,         0),
        (0.3,         1),
        (0.6,         2),
        (1.0,         3),
        (2.0,         4),
        (3.0,         5),
        (4.0,         6),
        (8.0,         7),
        (12.0,        8),
        (24.0,        9),
        (float("inf"), 10),
    ]

    _PUSH_EXUDATE = {"none": 0, "light": 1, "moderate": 2, "heavy": 3}
    _PUSH_TISSUE  = {"epithelial": 1, "granulation": 2, "slough": 3, "necrotic": 4}

    def push_score(
        self,
        area_cm2: float,
        exudate: str,
        dominant_tissue: str,
    ) -> int:
        area_s = next(
            s for (limit, s) in self._PUSH_AREA_BRACKETS if area_cm2 <= limit
        )
        exudate_s = self._PUSH_EXUDATE.get(exudate, 1)
        tissue_s  = self._PUSH_TISSUE.get(dominant_tissue, 2)
        return area_s + exudate_s + tissue_s

    # ─────────────────────────────────────────────────────────────────────────
    # RESVECH 2.0
    # ─────────────────────────────────────────────────────────────────────────
    _RESVECH_EDGES = {"closed": 0, "defined": 1, "diffuse": 2, "callous": 3, "undermined": 4}
    _RESVECH_EXUDATE = {"none": 0, "scarce": 1, "moderate": 2, "abundant": 3, "hemorrhagic": 4}

    def resvech_score(
        self,
        area_cm2: float,
        edges: str,
        tissue_pct: dict,
        exudate: str,
        infection_flag_count: int,
    ) -> int:
        # Size subscale (0–4)
        if area_cm2 == 0:
            sz = 0
        elif area_cm2 <= 4:
            sz = 1
        elif area_cm2 <= 16:
            sz = 2
        elif area_cm2 <= 36:
            sz = 3
        else:
            sz = 4

        eg = self._RESVECH_EDGES.get(edges, 1)

        # Tissue subscale: best tissue type dominates
        ep  = tissue_pct.get("epithelial_pct",  0)
        gr  = tissue_pct.get("granulation_pct", 0)
        sl  = tissue_pct.get("slough_pct",       0)
        ne  = tissue_pct.get("necrotic_pct",     0)
        ts = 1 if ep > 75 else 2 if gr > 75 else 3 if sl > 50 else 4 if ne > 50 else 2

        ex  = self._RESVECH_EXUDATE.get(exudate, 1)
        inf = min(infection_flag_count, 4)

        return sz + eg + ts + ex + inf

    # ─────────────────────────────────────────────────────────────────────────
    # Global Healing Index (adapted)
    # ─────────────────────────────────────────────────────────────────────────
    def global_healing_index(
        self,
        initial_area_cm2: float,
        current_area_cm2: float,
        initial_perim_cm: float,
        current_perim_cm: float,
        tissue_pct: dict,
    ) -> float:
        """
        GHI ranges roughly −1 to +1.
        Positive = wound improving. Negative = deteriorating.
        """
        if initial_area_cm2 <= 0:
            return 0.0

        # Superficial Contraction Index: fractional area reduction
        SCI = (initial_area_cm2 - current_area_cm2) / initial_area_cm2

        # Wound Contraction Index: perimeter ratio (< 1 = boundary shortening = good)
        WCI = current_perim_cm / initial_perim_cm if initial_perim_cm > 0 else 1.0

        # Tissue Improvement Index (−1 to +1)
        TII = (
            tissue_pct.get("granulation_pct", 0) * 0.40
            + tissue_pct.get("epithelial_pct",  0) * 0.60
            - tissue_pct.get("necrotic_pct",    0) * 0.50
            - tissue_pct.get("slough_pct",       0) * 0.20
        ) / 100.0

        ghi = SCI * 0.40 + TII * 0.40 + (1.0 - WCI) * 0.20
        return round(ghi, 4)

    # ─────────────────────────────────────────────────────────────────────────
    # Healing Velocity & Rate (photo-planimetry standard)
    # ─────────────────────────────────────────────────────────────────────────
    def healing_velocity(self, sessions: list[dict]) -> float:
        """
        Returns cm²/day area reduction. Positive = wound shrinking.
        sessions: list of {"area_cm2": float, "date": date} dicts, any order.
        """
        if len(sessions) < 2:
            return 0.0
        s = sorted(sessions, key=lambda x: x["date"])
        area_delta = s[0]["area_cm2"] - s[-1]["area_cm2"]
        day_delta  = (s[-1]["date"] - s[0]["date"]).days
        return round(area_delta / day_delta, 4) if day_delta > 0 else 0.0

    def healing_rate_pct(self, prev_area: float, curr_area: float) -> float:
        """% reduction from previous session. Positive = healing."""
        if prev_area <= 0:
            return 0.0
        return round((prev_area - curr_area) / prev_area * 100.0, 2)

    def classify_trajectory(self, velocity: float, score_delta: float) -> str:
        """
        Returns: "IMPROVING" | "STAGNATING" | "WORSENING"
        velocity: cm²/day
        score_delta: composite_score_current - composite_score_previous
        """
        if velocity > 0.03 and score_delta >= -2:
            return "IMPROVING"
        if velocity < -0.02 or score_delta < -5:
            return "WORSENING"
        return "STAGNATING"

    def estimated_closure_days(self, current_area: float, velocity: float) -> int | None:
        """Returns estimated days to closure. None if wound not healing."""
        if velocity <= 0 or current_area <= 0:
            return None
        return int(current_area / velocity)

    # ─────────────────────────────────────────────────────────────────────────
    # Composite Healing Score (0–100)
    # ─────────────────────────────────────────────────────────────────────────
    def composite_score(
        self,
        tissue_pct: dict,
        inflammation_index: float,
        circularity: float,
    ) -> float:
        """
        Weighted composite: 100 = optimal healing, 0 = critical.

        Weights derived from BWAT item importance rankings
        (Bates-Jensen et al., 2001).
        """
        gr = tissue_pct.get("granulation_pct", 0)
        ep = tissue_pct.get("epithelial_pct",  0)
        ne = tissue_pct.get("necrotic_pct",    0)
        sl = tissue_pct.get("slough_pct",       0)

        raw = (
            gr  * 0.30
            + ep  * 0.25
            - ne  * 0.25
            - sl  * 0.10
            - (inflammation_index / 100.0) * 15.0
            + circularity * 10.0       # regular shape → better edge closure
        )
        # Normalise: raw theoretical range ≈ −40 to +60 → map to 0–100
        normalised = (raw + 40.0) / 100.0 * 100.0
        return round(max(0.0, min(100.0, normalised)), 1)

    # ─────────────────────────────────────────────────────────────────────────
    # NERDS / STONES Infection Risk
    # Source: Sibbald et al. (2006)
    # ─────────────────────────────────────────────────────────────────────────
    def infection_risk(self, m: dict) -> dict:
        """
        NERDS = superficial critical colonisation (5 criteria)
        STONES = deep/spreading infection (6 criteria)

        Args:
            m: dict containing wound metrics. Keys used:
                healing_velocity, exudate, granulation_pct,
                slough_pct, inflammation_index, necrotic_pct,
                wound_size_increasing (bool)
        """
        nerds: list[str] = []
        stones: list[str] = []

        vel  = m.get("healing_velocity", 0.0)
        exu  = m.get("exudate", "none")
        gran = m.get("granulation_pct", 0.0)
        slou = m.get("slough_pct", 0.0)
        infl = m.get("inflammation_index", 0.0)
        necr = m.get("necrotic_pct", 0.0)

        # ── NERDS criteria ──────────────────────────────────────────────────
        # N: Non-healing (no area reduction over ≥2 sessions)
        if vel <= 0.0:
            nerds.append("N – Non-healing wound (velocity ≤ 0)")

        # E: Exudate increasing
        if exu in ("moderate", "heavy"):
            nerds.append("E – Increased exudate")

        # R: Red/friable granulation (high granulation but wound not healing)
        if gran > 75 and vel <= 0.02:
            nerds.append("R – Friable / hypergranulation tissue")

        # D: Debris (slough burden)
        if slou > 30.0:
            nerds.append(f"D – Slough debris ({slou:.1f}%)")

        # S (in NERDS): Smell — cannot detect from image, skip

        # ── STONES criteria ─────────────────────────────────────────────────
        # S: Size increasing
        if vel < -0.05:
            stones.append("S – Wound size increasing (velocity < −0.05 cm²/day)")

        # T: Temperature — not measurable from image

        # O: Os (bone exposure) — not reliably detectable from surface image

        # N: New breakdown
        if necr > 30.0:
            stones.append(f"N – Necrotic tissue burden ({necr:.1f}%)")

        # E: Erythema / edema
        if infl > 65.0:
            stones.append(f"E – Elevated periwound erythema (index {infl:.1f})")

        # S: Smell — skipped

        n_score = len(nerds)
        s_score = len(stones)
        total   = n_score + s_score

        if n_score >= 3 or s_score >= 2:
            level = "HIGH"
        elif total >= 2:
            level = "MODERATE"
        else:
            level = "LOW"

        return {
            "level":        level,
            "NERDS":        nerds,
            "STONES":       stones,
            "NERDS_score":  n_score,
            "STONES_score": s_score,
        }
