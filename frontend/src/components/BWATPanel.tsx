// BWATPanel.tsx — Bates-Jensen Wound Assessment Tool display
import type { BWATResult } from "../types";

interface Props { bwat: BWATResult }

const BWAT_LABELS: Record<string, string> = {
  depth: "Depth", edges: "Edges", undermining: "Undermining",
  necrotic_type: "Necrotic Type", necrotic_amount: "Necrotic Amount",
  exudate_type: "Exudate Type", exudate_amount: "Exudate Amount",
  skin_color: "Skin Colour", edema: "Edema", induration: "Induration",
  granulation: "Granulation", epithelialization: "Epithelialisation",
};

function scoreColor(score: number) {
  if (score <= 2) return "var(--green)";
  if (score <= 3) return "var(--amber)";
  return "var(--red)";
}

function severityColor(s: string) {
  return s === "healing" ? "var(--green)" : s === "mild" ? "#60a5fa"
    : s === "moderate" ? "var(--amber)" : "var(--red)";
}

export default function BWATPanel({ bwat }: Props) {
  if (!bwat || !bwat.bwat) return null;
  const items = Object.entries(bwat.bwat) as [string, { score: number; finding: string }][];

  return (
    <div className="card">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div>
          <h3 style={{ marginBottom: "0.2rem" }}>BWAT Assessment</h3>
          <p className="text-muted" style={{ fontSize: "0.72rem" }}>Bates-Jensen Wound Assessment Tool (Bates-Jensen 1995)</p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: severityColor(bwat.bwat_severity), lineHeight: 1 }}>
            {bwat.bwat_total}<span style={{ fontSize: "0.9rem", fontWeight: 400, color: "var(--text-muted)" }}>/60</span>
          </div>
          <div style={{ fontSize: "0.72rem", color: severityColor(bwat.bwat_severity), fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            {bwat.bwat_severity}
          </div>
        </div>
      </div>

      {/* Interpretation banner */}
      {bwat.bwat_interpretation && (
        <div style={{ background: "rgba(20,184,166,0.06)", border: "1px solid rgba(20,184,166,0.2)", borderRadius: "var(--r-sm)", padding: "0.6rem 0.8rem", marginBottom: "1rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
          {bwat.bwat_interpretation}
        </div>
      )}

      {/* 12 items */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginBottom: "1rem" }}>
        {items.map(([key, item]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.3rem 0", borderBottom: "1px solid var(--border)" }}>
            <div style={{ width: 24, height: 24, borderRadius: "50%", background: `${scoreColor(item.score)}22`, border: `1.5px solid ${scoreColor(item.score)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.72rem", fontWeight: 700, color: scoreColor(item.score), flexShrink: 0 }}>
              {item.score}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>{BWAT_LABELS[key] || key}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.finding}</div>
            </div>
          </div>
        ))}
      </div>

      {/* TIME framework */}
      {bwat.TIME && (
        <div>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: "0.5rem" }}>TIME FRAMEWORK</div>
          {(["T", "I", "M", "E"] as const).map(key => (
            <div key={key} style={{ display: "flex", gap: "0.6rem", marginBottom: "0.4rem", fontSize: "0.8rem" }}>
              <span style={{ fontWeight: 700, color: "var(--teal)", width: 16, flexShrink: 0 }}>{key}</span>
              <span style={{ color: "var(--text-secondary)" }}>{bwat.TIME[key]}</span>
            </div>
          ))}
        </div>
      )}

      {/* Flags row */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
        {bwat.biofilm_suspected && <span className="badge" style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)" }}>⚠ Biofilm suspected</span>}
        {bwat.overall_concern === "urgent" && <span className="badge" style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)" }}>Urgent review</span>}
        <span className="badge badge-blue">{bwat.healing_phase}</span>
        <span className="badge">{bwat.moisture_balance}</span>
      </div>
    </div>
  );
}
