import { useState, useEffect } from "react";
import type { AnalysisResult } from "../types";
import { Activity, Clock, Package, Layers, Droplets, AlertTriangle, ExternalLink } from "lucide-react";

interface Props {
  result: AnalysisResult;
  imageFile: File;
}

export default function ResultsPanel({ result, imageFile }: Props) {
  const [originalImageUrl, setOriginalImageUrl] = useState<string>("");
  const [sliderValue, setSliderValue] = useState<number>(0);

  useEffect(() => {
    if (imageFile) {
      const url = URL.createObjectURL(imageFile);
      setOriginalImageUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [imageFile]);

  const ca = result.clinical_assessment;
  if (!ca) return null;

  const riskColor =
    ca.infection_risk?.toUpperCase() === "HIGH" ? "#ef4444" :
    ca.infection_risk?.toUpperCase() === "MODERATE" ? "#f59e0b" : "#4ade80";

  const velocityCm = ca.gilman_velocity_cm_per_week;
  const velocityStatus =
    velocityCm === null || velocityCm === undefined
      ? { label: "Needs 2+ Scans", color: "var(--text-muted)" }
      : velocityCm < 0.1
        ? { label: "Stalled", color: "#ef4444" }
        : { label: "Healing", color: "#4ade80" };

  const card: React.CSSProperties = {
    background: "rgba(30, 30, 30, 0.7)",
    backdropFilter: "blur(12px)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 14,
    padding: "1.25rem 1.5rem",
  };

  return (
    <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem", width: "100%" }}>

      {/* ── ROW 1: CARE PLAN STRIP (full width) ── */}
      <div style={{ ...card, padding: 0, overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <Activity size={18} color="var(--tertiary)" />
          <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "var(--text-primary)" }}>Care Plan</span>
        </div>

        <div style={{ padding: "1.25rem 1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Patient message — full width */}
          <p style={{ fontSize: "0.95rem", color: "rgba(255,255,255,0.82)", lineHeight: 1.7, margin: 0 }}>
            {result.patient_message || "Follow standard wound care protocols."}
          </p>

          {/* Pills row */}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "stretch" }}>

            {/* Dressing type */}
            <div style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 10, padding: "0.7rem 1.1rem", minWidth: 130 }}>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Layers size={12} /> Dressing
              </div>
              <div style={{ fontSize: "0.95rem", fontWeight: 500, color: "var(--text-primary)", marginTop: "0.3rem" }}>
                {result.care_plan?.dressing_type || "Standard"}
              </div>
            </div>

            {/* Frequency */}
            <div style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 10, padding: "0.7rem 1.1rem", minWidth: 130 }}>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Clock size={12} /> Frequency
              </div>
              <div style={{ fontSize: "0.95rem", fontWeight: 500, color: "var(--text-primary)", marginTop: "0.3rem" }}>
                {result.care_plan?.dressing_change_frequency || "Daily"}
              </div>
            </div>

            {/* Pharmacy */}
            {result.care_plan?.product_name && (
              <a
                href={`https://www.google.com/search?tbm=shop&q=${result.care_plan.product_search_query || result.care_plan.product_name.replace(/ /g, "+")}`}
                target="_blank" rel="noreferrer"
                style={{ display: "flex", alignItems: "center", gap: "0.6rem", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "0.7rem 1.1rem", textDecoration: "none", transition: "all 0.2s ease", flex: 1, minWidth: 180 }}
                className="hover-lift"
              >
                <Package size={16} color="var(--tertiary)" style={{ flexShrink: 0 }} />
                <div style={{ overflow: "hidden" }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Recommended</div>
                  <div style={{ fontSize: "0.92rem", color: "var(--text-primary)", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{result.care_plan.product_name}</div>
                </div>
                <ExternalLink size={14} color="var(--text-muted)" style={{ flexShrink: 0, marginLeft: "auto" }} />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* ── ROW 2: TISSUE OVERLAY (left) + STATS COLUMN (right) ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: "1rem", alignItems: "stretch" }}>

        {/* LEFT: Tissue overlay */}
        <div style={{ ...card, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "0.85rem 1.25rem", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Droplets size={16} color="var(--tertiary)" /> AI Tissue Overlay
            </span>
            <div style={{ display: "flex", background: "rgba(0,0,0,0.4)", borderRadius: 100, padding: "3px" }}>
              {["Original", "Tissue", "Heat"].map((label, i) => {
                const targetVal = i === 0 ? 0 : i === 1 ? 50 : 100;
                const isActive = (i === 0 && sliderValue < 33) || (i === 1 && sliderValue >= 33 && sliderValue < 66) || (i === 2 && sliderValue >= 66);
                return (
                  <button key={label} onClick={() => setSliderValue(targetVal)}
                    style={{ background: isActive ? "rgba(255,255,255,0.12)" : "transparent", color: isActive ? "#fff" : "var(--text-muted)", border: "none", padding: "0.35rem 0.85rem", borderRadius: 100, fontSize: "0.8rem", fontWeight: 600, cursor: "pointer", transition: "all 0.2s" }}>
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ position: "relative", width: "100%", height: "360px", background: "#000" }}>
            <img src={originalImageUrl} alt="Original" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" }} />
            {result.images?.annotated_b64 && (
              <img src={`data:image/jpeg;base64,${result.images.annotated_b64}`} alt="Tissue"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", clipPath: `inset(0 ${100 - Math.min(Math.max((sliderValue - 33) * 3, 0), 100)}% 0 0)`, transition: "clip-path 0.1s ease" }} />
            )}
            {result.images?.heatmap_b64 && (
              <img src={`data:image/jpeg;base64,${result.images.heatmap_b64}`} alt="Heatmap"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", mixBlendMode: "screen", clipPath: `inset(0 ${100 - Math.min(Math.max((sliderValue - 66) * 3, 0), 100)}% 0 0)`, transition: "clip-path 0.1s ease" }} />
            )}
            <input type="range" min="0" max="100" value={sliderValue} onChange={e => setSliderValue(Number(e.target.value))}
              style={{ position: "absolute", bottom: 16, left: "5%", width: "90%", zIndex: 10, accentColor: "var(--tertiary)", cursor: "pointer" }} />
          </div>
        </div>

        {/* RIGHT: Stats column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

          {/* Healing Velocity */}
          <div style={{ ...card, flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "1.5rem 1rem" }}>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "1rem" }}>
              <Activity size={14} /> Healing Velocity
            </div>

            {/* Semicircle gauge */}
            <div style={{ position: "relative", width: 140, height: 70, overflow: "hidden", marginBottom: "0.75rem" }}>
              <div style={{ width: 140, height: 140, borderRadius: "50%", background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.06)" }} />
              {velocityCm !== null && velocityCm !== undefined && (
                <div style={{
                  position: "absolute", top: 0, left: 0, width: 140, height: 140, borderRadius: "50%",
                  background: `conic-gradient(from 180deg, ${velocityStatus.color} 0deg, ${velocityStatus.color} 180deg)`,
                  clipPath: `polygon(50% 50%, 0% 50%, 0% 0%, ${Math.min(100, Math.max(0, (velocityCm / 0.5) * 100))}% 0%, 100% 50%)`,
                  transition: "clip-path 1.5s ease", boxShadow: `0 0 16px ${velocityStatus.color}`
                }} />
              )}
              <div style={{ position: "absolute", top: 10, left: 10, width: 120, height: 120, borderRadius: "50%", background: "var(--bg-card)" }} />
            </div>

            <div style={{ fontSize: "2.2rem", fontWeight: 700, letterSpacing: "-0.05em", lineHeight: 1 }}>
              {velocityCm !== null && velocityCm !== undefined ? velocityCm.toFixed(2) : "—"}
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", textTransform: "uppercase", marginTop: "0.3rem" }}>cm / week</div>
            <div style={{ marginTop: "0.85rem", padding: "0.35rem 1rem", borderRadius: 100, fontSize: "0.82rem", fontWeight: 600,
              background: `rgba(${velocityStatus.color === "#4ade80" ? "74,222,128" : velocityStatus.color === "#ef4444" ? "239,68,68" : "255,255,255"}, 0.1)`,
              color: velocityStatus.color, border: `1px solid ${velocityStatus.color}30` }}>
              {velocityStatus.label}
            </div>
          </div>

          {/* Clinical Metrics */}
          <div style={{ ...card, flex: 1, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.25rem" }}>Clinical Metrics</div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(0,0,0,0.25)", borderRadius: 10, padding: "0.75rem" }}>
              <div style={{ background: "rgba(255,255,255,0.06)", padding: "0.5rem", borderRadius: 8 }}><Layers size={16} color="var(--text-secondary)" /></div>
              <div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Area</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>{result.geometry?.area_cm2?.toFixed(1) || "—"} cm²</div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(0,0,0,0.25)", border: `1px solid ${riskColor}25`, borderRadius: 10, padding: "0.75rem" }}>
              <div style={{ background: `${riskColor}18`, padding: "0.5rem", borderRadius: 8 }}><AlertTriangle size={16} color={riskColor} /></div>
              <div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Infection Risk</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600, color: riskColor }}>{ca.infection_risk || "Low"}</div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(0,0,0,0.25)", borderRadius: 10, padding: "0.75rem" }}>
              <div style={{ background: "rgba(255,255,255,0.05)", padding: "0.5rem", borderRadius: 8 }}><Clock size={16} color="var(--text-secondary)" /></div>
              <div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Est. Closure</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>
                  {ca.estimated_closure_days ? `${ca.estimated_closure_days} days` : "—"}
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
