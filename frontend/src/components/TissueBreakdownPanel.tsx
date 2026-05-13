import type { TissueBreakdown } from "../types";

interface Props {
  tissue: TissueBreakdown;
}

const TISSUES = [
  { key: "granulation_pct", label: "Granulation", color: "var(--granulation)", note: "Healthy" },
  { key: "epithelial_pct",  label: "Epithelial",  color: "var(--epithelial)",  note: "Closure" },
  { key: "slough_pct",      label: "Slough",      color: "var(--slough)",      note: "Non-viable" },
  { key: "necrotic_pct",    label: "Necrotic",    color: "var(--necrotic)",    note: "Dead" },
] as const;

export default function TissueBreakdownPanel({ tissue }: Props) {
  return (
    <div className="card">
      <h3 style={{ marginBottom: "1rem" }}>Tissue Composition</h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {TISSUES.map(({ key, label, color, note }) => {
          const pct = (tissue as Record<string, number>)[key] ?? 0;
          return (
            <div key={key}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  {label}
                  <span className="text-muted" style={{ fontSize: "0.75rem", marginLeft: 6 }}>
                    {note}
                  </span>
                </span>
                <span
                  className="mono"
                  style={{ color, fontWeight: 600, fontSize: "0.88rem" }}
                >
                  {pct.toFixed(1)}%
                </span>
              </div>
              <div className="progress-bar-wrap">
                <div
                  className="progress-bar-fill"
                  style={{
                    width: `${Math.min(pct, 100)}%`,
                    background: color,
                    opacity: 0.85,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border)" }}>
        <span className="text-muted" style={{ fontSize: "0.78rem" }}>Dominant tissue: </span>
        <span style={{ fontSize: "0.85rem", fontWeight: 600, textTransform: "capitalize" }}>
          {tissue.dominant_tissue}
        </span>
      </div>
    </div>
  );
}
