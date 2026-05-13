// AlertsPanel.tsx — shows automated clinical alerts with severity styling
import type { Alert } from "../types";

interface Props { alerts: Alert[] }

const SEVERITY_CONFIG = {
  urgent:  { bg: "rgba(239,68,68,0.10)",  border: "rgba(239,68,68,0.4)",  icon: "🚨", label: "URGENT",  color: "#f87171" },
  warning: { bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.4)", icon: "⚠️", label: "WARNING", color: "#fbbf24" },
  info:    { bg: "rgba(20,184,166,0.08)",  border: "rgba(20,184,166,0.3)", icon: "✓",  label: "INFO",    color: "var(--teal)" },
};

export default function AlertsPanel({ alerts }: Props) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {alerts.map((alert, i) => {
        const cfg = SEVERITY_CONFIG[alert.severity];
        return (
          <div key={i} style={{
            background: cfg.bg,
            border: `1px solid ${cfg.border}`,
            borderRadius: "var(--r-sm)",
            padding: "0.8rem 1rem",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: alert.action ? "0.35rem" : 0 }}>
              <span style={{ fontSize: "1rem" }}>{cfg.icon}</span>
              <span style={{ fontWeight: 700, fontSize: "0.72rem", color: cfg.color, letterSpacing: "0.08em" }}>{cfg.label}</span>
              <span style={{ fontSize: "0.85rem", color: "var(--text-primary)", flex: 1 }}>{alert.message}</span>
            </div>
            {alert.action && (
              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", paddingLeft: "1.5rem" }}>
                → {alert.action}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
