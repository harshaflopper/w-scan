import type { ClinicalAssessment, InfectionRisk, Scores } from "../types";

// ─── Shared score card ───────────────────────────────────────────────────────

function ScoreCard({
  label,
  value,
  max,
  unit = "",
  invert = false,
  color,
}: {
  label: string;
  value: number | string;
  max?: number;
  unit?: string;
  invert?: boolean;
  color?: string;
}) {
  const numVal = typeof value === "number" ? value : parseFloat(value as string);
  const pct    = max ? Math.min((numVal / max) * 100, 100) : null;
  const isGood = invert ? pct !== null && pct < 40 : pct !== null && pct > 55;
  const arc    = color ?? (isGood ? "var(--teal)" : numVal > 70 ? "var(--green)" : "var(--amber)");

  return (
    <div
      className="card"
      style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.4rem" }}
    >
      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      <span className="score-big" style={{ color: arc }}>
        {typeof value === "number" ? value.toFixed(value % 1 === 0 ? 0 : 1) : value}
        {unit && <span style={{ fontSize: "1rem", color: "var(--text-muted)", marginLeft: 2 }}>{unit}</span>}
      </span>
      {max && (
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          / {max}
        </span>
      )}
    </div>
  );
}

// ─── Infection risk panel ────────────────────────────────────────────────────

function InfectionRiskPanel({ risk }: { risk: InfectionRisk }) {
  const levelColor = risk.level === "HIGH" ? "var(--red)" : risk.level === "MODERATE" ? "var(--amber)" : "var(--green)";
  const badgeClass = risk.level === "HIGH" ? "badge-red" : risk.level === "MODERATE" ? "badge-amber" : "badge-green";

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3>Infection Risk</h3>
        <span className={`badge ${badgeClass}`}>{risk.level}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>NERDS</div>
          <div className="mono" style={{ fontSize: "1.3rem", fontWeight: 700, color: levelColor }}>
            {risk.NERDS_score} <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/ 5</span>
          </div>
        </div>
        <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>STONES</div>
          <div className="mono" style={{ fontSize: "1.3rem", fontWeight: 700, color: levelColor }}>
            {risk.STONES_score} <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/ 6</span>
          </div>
        </div>
      </div>

      {[...risk.NERDS, ...risk.STONES].length > 0 && (
        <ul style={{ paddingLeft: "1rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {[...risk.NERDS, ...risk.STONES].map((flag, i) => (
            <li key={i} style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{flag}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── TIME framework panel ────────────────────────────────────────────────────

function TimePanel({ time }: { time: { T: string; I: string; M: string; E: string } }) {
  const items = [
    { key: "T", label: "Tissue",            value: time.T },
    { key: "I", label: "Infection/Inflam.", value: time.I },
    { key: "M", label: "Moisture",          value: time.M },
    { key: "E", label: "Edge",              value: time.E },
  ];
  return (
    <div className="card">
      <h3 style={{ marginBottom: "0.75rem" }}>TIME Framework</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {items.map(({ key, label, value }) => (
          <div key={key} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
            <span
              className="mono"
              style={{
                background: "var(--teal-glow)",
                color: "var(--teal)",
                borderRadius: "var(--r-sm)",
                padding: "0 8px",
                fontWeight: 700,
                fontSize: "0.85rem",
                lineHeight: "1.8",
                minWidth: 24,
                textAlign: "center",
              }}
            >
              {key}
            </span>
            <div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 1 }}>{label}</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{value}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Recommendations panel ───────────────────────────────────────────────────

function RecommendationsPanel({ recs, redFlags }: { recs: string[]; redFlags: string[] }) {
  return (
    <div className="card">
      {redFlags.length > 0 && (
        <div
          style={{
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: "var(--r-sm)",
            padding: "0.75rem",
            marginBottom: "0.75rem",
          }}
        >
          <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--red)", marginBottom: 4 }}>
            ⚠ Red Flags
          </div>
          <ul style={{ paddingLeft: "1rem" }}>
            {redFlags.map((f, i) => (
              <li key={i} style={{ fontSize: "0.83rem", color: "#f87171", marginBottom: 2 }}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <h3 style={{ marginBottom: "0.75rem" }}>Clinical Recommendations</h3>
      <ol style={{ paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
        {recs.map((r, i) => (
          <li key={i} style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{r}</li>
        ))}
      </ol>
    </div>
  );
}

// ─── Healing scores panel ────────────────────────────────────────────────────

function HealingScores({ scores, push, resvech }: { scores: Scores; push?: number; resvech?: number }) {
  const traj = scores.trajectory;
  const trajColor = traj === "IMPROVING" ? "var(--green)" : traj === "WORSENING" ? "var(--red)" : "var(--amber)";
  const trajBadge = traj === "IMPROVING" ? "badge-green" : traj === "WORSENING" ? "badge-red" : "badge-amber";

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3>Healing Scores</h3>
        {traj !== "FIRST_SESSION" && (
          <span className={`badge ${trajBadge}`}>{traj}</span>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
        {push !== undefined && (
          <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>PUSH Score</div>
            <div className="mono" style={{ fontSize: "1.4rem", fontWeight: 700, color: push <= 5 ? "var(--green)" : push <= 10 ? "var(--amber)" : "var(--red)" }}>
              {push} <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/ 17</span>
            </div>
          </div>
        )}
        {resvech !== undefined && (
          <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>RESVECH 2.0</div>
            <div className="mono" style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--text-primary)" }}>
              {resvech} <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/ 35</span>
            </div>
          </div>
        )}
        {scores.healing_velocity_cm2_per_day !== 0 && (
          <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Velocity</div>
            <div className="mono" style={{ fontSize: "1rem", fontWeight: 600, color: scores.healing_velocity_cm2_per_day > 0 ? "var(--green)" : "var(--red)" }}>
              {scores.healing_velocity_cm2_per_day > 0 ? "−" : "+"}{Math.abs(scores.healing_velocity_cm2_per_day).toFixed(3)}
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginLeft: 3 }}>cm²/day</span>
            </div>
          </div>
        )}
        {scores.estimated_closure_days !== null && scores.estimated_closure_days !== undefined && (
          <div style={{ background: "var(--bg-surface)", borderRadius: "var(--r-sm)", padding: "0.5rem 0.75rem" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Est. Closure</div>
            <div className="mono" style={{ fontSize: "1rem", fontWeight: 600, color: "var(--teal)" }}>
              ~{scores.estimated_closure_days} <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>days</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Results Panel ──────────────────────────────────────────────────────

interface Props {
  ca: ClinicalAssessment;
  risk: InfectionRisk;
  scores: Scores;
  compositeScore: number;
  inflammationIndex: number;
  areaCm2: number;
  annotatedB64: string;
  heatmapB64: string;
}

export default function ResultsPanel({
  ca, risk, scores, compositeScore, inflammationIndex, areaCm2,
  annotatedB64, heatmapB64,
}: Props) {
  return (
    <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

      {/* Summary row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
        <ScoreCard label="Composite Score" value={compositeScore} max={100}
          color={compositeScore >= 65 ? "var(--green)" : compositeScore >= 40 ? "var(--amber)" : "var(--red)"} />
        <ScoreCard label="Area" value={areaCm2} unit="cm²"
          color="var(--text-primary)" />
        <ScoreCard label="Inflammation" value={inflammationIndex} max={100} invert
          color={inflammationIndex < 40 ? "var(--green)" : inflammationIndex < 65 ? "var(--amber)" : "var(--red)"} />
      </div>

      {/* Clinical summary */}
      {ca.clinical_summary && (
        <div
          style={{
            background: "linear-gradient(135deg, rgba(20,184,166,0.06), rgba(59,130,246,0.04))",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-lg)",
            padding: "1rem 1.25rem",
          }}
        >
          <div style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--teal)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
            Clinical Summary · {ca.healing_phase ?? "Unknown Phase"}
          </div>
          <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>
            {ca.clinical_summary}
          </p>
        </div>
      )}

      {/* Annotated images */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 6 }}>TISSUE OVERLAY</div>
          <img
            src={`data:image/jpeg;base64,${annotatedB64}`}
            alt="Tissue segmentation overlay"
            style={{ width: "100%", borderRadius: "var(--r-md)", border: "1px solid var(--border)" }}
          />
        </div>
        <div>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 6 }}>ERYTHEMA HEATMAP</div>
          <img
            src={`data:image/jpeg;base64,${heatmapB64}`}
            alt="Periwound erythema heatmap"
            style={{ width: "100%", borderRadius: "var(--r-md)", border: "1px solid var(--border)" }}
          />
        </div>
      </div>

      {/* Scores + infection */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <HealingScores scores={scores} push={ca.push_score} resvech={ca.resvech_score} />
        <InfectionRiskPanel risk={risk} />
      </div>

      {/* TIME framework */}
      {ca.TIME && <TimePanel time={ca.TIME} />}

      {/* Recommendations */}
      {ca.recommendations && ca.recommendations.length > 0 && (
        <RecommendationsPanel recs={ca.recommendations} redFlags={ca.red_flags ?? []} />
      )}
    </div>
  );
}
