// HealingTrendChart.tsx — multi-metric wound healing dashboard
import { useRef, useEffect } from "react";
import type { TrendData } from "../types";

export interface SessionDataPoint {
  date: string;
  area_cm2: number;
  composite_score: number;
  bwat_total?: number;
  push_score?: number;
  granulation_pct?: number;
  slough_pct?: number;
  necrotic_pct?: number;
}

interface Props {
  sessions?: SessionDataPoint[];
  trend?: TrendData;
}

function sparkline(
  ctx: CanvasRenderingContext2D,
  values: number[],
  x: number, y: number, w: number, h: number,
  color: string,
  fill = false,
) {
  if (values.length < 2) return;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => ({
    x: x + (i / (values.length - 1)) * w,
    y: y + h - ((v - min) / range) * h,
  }));
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.stroke();
  if (fill) {
    ctx.lineTo(pts[pts.length - 1].x, y + h);
    ctx.lineTo(x, y + h);
    ctx.closePath();
    ctx.fillStyle = color + "22";
    ctx.fill();
  }
  // dots
  pts.forEach(p => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  });
}

export default function HealingTrendChart({ sessions, trend }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Prefer trend data from API, fall back to local sessions
  const labels = trend?.session_dates ?? sessions?.map(s => s.date) ?? [];
  const areas  = trend?.area_cm2      ?? sessions?.map(s => s.area_cm2) ?? [];
  const bwats  = trend?.bwat_total    ?? sessions?.map(s => s.bwat_total ?? 0) ?? [];
  const grans  = trend?.granulation_pct ?? sessions?.map(s => s.granulation_pct ?? 0) ?? [];
  const sloughs = trend?.slough_pct    ?? sessions?.map(s => s.slough_pct ?? 0) ?? [];
  const necros = trend?.necrotic_pct  ?? sessions?.map(s => s.necrotic_pct ?? 0) ?? [];

  const n = areas.length;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || n < 2) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = "rgba(15,23,42,0.0)";
    ctx.fillRect(0, 0, W, H);

    const pad = 16;
    const chartH = (H - pad * 3) / 2;
    const chartW = W - pad * 2;

    // Top chart: Area over time
    sparkline(ctx, areas, pad, pad, chartW, chartH, "#14b8a6", true);

    // Bottom chart: Tissue stacked sparklines
    const y2 = pad * 2 + chartH;
    sparkline(ctx, grans,   pad, y2, chartW, chartH, "#22c55e");
    sparkline(ctx, sloughs, pad, y2, chartW, chartH, "#fbbf24");
    sparkline(ctx, necros,  pad, y2, chartW, chartH, "#f87171");

    // X labels (session dates)
    ctx.fillStyle = "rgba(148,163,184,0.7)";
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    labels.forEach((lbl, i) => {
      const lx = pad + (i / (n - 1)) * chartW;
      ctx.fillText(lbl.slice(5), lx, H - 2); // MM-DD
    });
  }, [areas, grans, sloughs, necros, labels, n]);

  if (n < 2) return null;

  const lastArea  = areas[n - 1];
  const firstArea = areas[0];
  const areaChange = firstArea > 0 ? ((lastArea - firstArea) / firstArea * 100) : 0;
  const lastBwat  = bwats[n - 1];
  const firstBwat = bwats[0];

  return (
    <div className="card" style={{ padding: "1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div>
          <h3 style={{ marginBottom: "0.2rem" }}>Healing Dashboard</h3>
          <p className="text-muted" style={{ fontSize: "0.72rem" }}>{n} sessions recorded</p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Area change</div>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: areaChange <= 0 ? "var(--green)" : "var(--red)" }}>
              {areaChange <= 0 ? "↓" : "↑"}{Math.abs(areaChange).toFixed(1)}%
            </div>
          </div>
          {lastBwat > 0 && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>BWAT</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: lastBwat < firstBwat ? "var(--green)" : "var(--red)" }}>
                {lastBwat}<span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>/60</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={680}
        height={160}
        style={{ width: "100%", height: 160, borderRadius: "var(--r-sm)", background: "rgba(15,23,42,0.4)" }}
      />

      {/* Legend */}
      <div style={{ display: "flex", gap: "1rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
        {[
          { color: "#14b8a6", label: "Wound area" },
          { color: "#22c55e", label: "Granulation" },
          { color: "#fbbf24", label: "Slough" },
          { color: "#f87171", label: "Necrotic" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.72rem", color: "var(--text-muted)" }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Session table */}
      <div style={{ marginTop: "0.75rem", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
          <thead>
            <tr style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", padding: "0.3rem 0.5rem", fontWeight: 500 }}>Date</th>
              <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontWeight: 500 }}>Area cm²</th>
              <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontWeight: 500 }}>BWAT</th>
              <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontWeight: 500 }}>Gran%</th>
              <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontWeight: 500 }}>Slough%</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((date, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)", background: i === n - 1 ? "rgba(20,184,166,0.05)" : "transparent" }}>
                <td style={{ padding: "0.3rem 0.5rem", color: i === n - 1 ? "var(--teal)" : "var(--text-secondary)", fontWeight: i === n - 1 ? 600 : 400 }}>{date}</td>
                <td style={{ padding: "0.3rem 0.5rem", textAlign: "right", fontFamily: "monospace" }}>{areas[i]?.toFixed(2)}</td>
                <td style={{ padding: "0.3rem 0.5rem", textAlign: "right", fontFamily: "monospace" }}>{bwats[i] || "—"}</td>
                <td style={{ padding: "0.3rem 0.5rem", textAlign: "right", fontFamily: "monospace", color: "var(--green)" }}>{grans[i]?.toFixed(0)}%</td>
                <td style={{ padding: "0.3rem 0.5rem", textAlign: "right", fontFamily: "monospace", color: "var(--amber)" }}>{sloughs[i]?.toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
