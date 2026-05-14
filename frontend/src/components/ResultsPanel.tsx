import { useState, useEffect } from "react";
import type { AnalysisResult } from "../types";

interface Props {
  result: AnalysisResult;
  imageFile: File;
}

export default function ResultsPanel({ result, imageFile }: Props) {
  const [originalImageUrl, setOriginalImageUrl] = useState<string>("");
  const [sliderValue, setSliderValue] = useState<number>(50);

  useEffect(() => {
    if (imageFile) {
      const url = URL.createObjectURL(imageFile);
      setOriginalImageUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [imageFile]);

  const ca = result.clinical_assessment;
  if (!ca) return null;

  return (
    <div className="bento-grid animate-fade-in">
      
      {/* HEADER BENTO (Large) */}
      <div className="bento-item bento-large" style={{ background: "linear-gradient(135deg, rgba(20,20,30,0.8) 0%, rgba(0,255,209,0.1) 100%)" }}>
        <h2 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>AI Care Plan</h2>
        <p style={{ fontSize: "1.1rem", color: "var(--text-primary)", lineHeight: 1.6, maxWidth: "800px" }}>
          {result.patient_message || "Your wound is healing. Follow standard care protocols."}
        </p>
        
        <div style={{ display: "flex", gap: "2rem", marginTop: "2rem" }}>
          <div>
            <div style={{ fontSize: "0.85rem", color: "var(--teal)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>Recommended Dressing</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 600, color: "#fff" }}>{result.care_plan?.dressing_type || "Standard Bandage"}</div>
          </div>
          <div style={{ width: "1px", background: "rgba(255,255,255,0.1)" }}></div>
          <div>
            <div style={{ fontSize: "0.85rem", color: "var(--teal)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>Change Frequency</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 600, color: "#fff" }}>{result.care_plan?.dressing_change_frequency || "Daily"}</div>
          </div>
        </div>
      </div>

      {/* TISSUE X-RAY BENTO (Medium/Large) */}
      <div className="bento-item bento-large" style={{ padding: 0 }}>
        <div style={{ padding: "1.5rem", position: "absolute", top: 0, left: 0, zIndex: 10, pointerEvents: "none" }}>
          <h3 style={{ textShadow: "0 2px 10px rgba(0,0,0,0.8)" }}>Tissue X-Ray</h3>
          <p style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.8)", textShadow: "0 2px 10px rgba(0,0,0,0.8)" }}>Slide to reveal Tissue & Inflammation Maps</p>
        </div>
        
        <div style={{ position: "relative", width: "100%", height: "400px", background: "#000", overflow: "hidden" }}>
          {/* Base Layer: Original Image */}
          <img src={originalImageUrl} alt="Original" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover" }} />
          
          {/* Middle Layer: Annotated Tissue (Shows when slider > 33%) */}
          {result.images?.annotated_b64 && (
            <img 
              src={`data:image/jpeg;base64,${result.images.annotated_b64}`} 
              alt="Tissue Map" 
              style={{ 
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover",
                clipPath: `inset(0 ${100 - Math.min(Math.max((sliderValue - 33) * 3, 0), 100)}% 0 0)`
              }} 
            />
          )}

          {/* Top Layer: Inflammation Heatmap (Shows when slider > 66%) */}
          {result.images?.heatmap_b64 && (
            <img 
              src={`data:image/jpeg;base64,${result.images.heatmap_b64}`} 
              alt="Heatmap" 
              style={{ 
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover", mixBlendMode: "screen",
                clipPath: `inset(0 ${100 - Math.min(Math.max((sliderValue - 66) * 3, 0), 100)}% 0 0)`
              }} 
            />
          )}

          {/* The Slider Control */}
          <input 
            type="range" min="0" max="100" value={sliderValue} onChange={(e) => setSliderValue(Number(e.target.value))}
            style={{
              position: "absolute", bottom: "20px", left: "5%", width: "90%", zIndex: 10,
              accentColor: "var(--teal)", cursor: "pointer", filter: "drop-shadow(0 2px 5px rgba(0,0,0,0.5))"
            }}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "1rem 2rem", fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 600, background: "rgba(10,10,15,0.8)" }}>
          <span style={{ color: sliderValue < 33 ? "#fff" : "inherit" }}>Original</span>
          <span style={{ color: sliderValue >= 33 && sliderValue < 66 ? "#fff" : "inherit" }}>Tissue Map</span>
          <span style={{ color: sliderValue >= 66 ? "#fff" : "inherit" }}>Inflammation</span>
        </div>
      </div>

      {/* GILMAN VELOCITY SPEEDOMETER (Small/Medium) */}
      <div className="bento-item bento-medium" style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <h3 style={{ marginBottom: "1.5rem", color: "var(--text-secondary)" }}>Gilman Healing Velocity</h3>
        <div style={{ position: "relative", width: "180px", height: "90px", overflow: "hidden", margin: "0 auto" }}>
          {/* Gauge Background */}
          <div style={{ width: "180px", height: "180px", borderRadius: "50%", background: "conic-gradient(from 180deg, var(--red) 0deg, var(--red) 30deg, var(--amber) 30deg, var(--amber) 90deg, var(--green) 90deg, var(--green) 180deg)", opacity: 0.2 }} />
          {/* Active Gauge */}
          {ca.gilman_velocity_cm_per_week !== null && ca.gilman_velocity_cm_per_week !== undefined && (
            <div style={{
              position: "absolute", top: 0, left: 0, width: "180px", height: "180px", borderRadius: "50%",
              background: "conic-gradient(from 180deg, var(--red) 0deg, var(--red) 30deg, var(--amber) 30deg, var(--amber) 90deg, var(--green) 90deg, var(--green) 180deg)",
              clipPath: `polygon(50% 50%, 0% 50%, 0% 0%, ${Math.min(100, Math.max(0, (ca.gilman_velocity_cm_per_week / 0.5) * 100))}% 0%, 100% 50%)`,
              transition: "clip-path 1s ease-out"
            }} />
          )}
          {/* Gauge Inner Cutout */}
          <div style={{ position: "absolute", top: "15px", left: "15px", width: "150px", height: "150px", borderRadius: "50%", background: "var(--bg-card)" }} />
        </div>
        <div style={{ marginTop: "1rem" }}>
          <div className="score-big" style={{ color: "var(--text-primary)" }}>
            {ca.gilman_velocity_cm_per_week !== null && ca.gilman_velocity_cm_per_week !== undefined 
              ? `${ca.gilman_velocity_cm_per_week.toFixed(2)}` 
              : "—"}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: "0.2rem" }}>cm / week</div>
          
          <div style={{ fontSize: "0.95rem", color: ca.gilman_velocity_cm_per_week && ca.gilman_velocity_cm_per_week < 0.1 ? "var(--red)" : "var(--green)", fontWeight: 700, marginTop: "1rem", padding: "0.5rem", background: "rgba(0,0,0,0.3)", borderRadius: "100px" }}>
            {ca.gilman_velocity_cm_per_week === null || ca.gilman_velocity_cm_per_week === undefined 
              ? "Baseline Established" 
              : ca.gilman_velocity_cm_per_week < 0.1 ? "WARNING: WOUND STALLED" : "ACTIVELY HEALING"}
          </div>
        </div>
      </div>

      {/* METRICS (Small/Medium) */}
      <div className="bento-item bento-medium" style={{ display: "flex", flexDirection: "column", gap: "1.5rem", justifyContent: "center" }}>
        <h3 style={{ color: "var(--text-secondary)" }}>Clinical Metrics</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div style={{ background: "rgba(0,0,0,0.3)", padding: "1rem", borderRadius: "var(--r-md)" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Estimated Area</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--text-primary)" }}>{result.geometry?.area_cm2?.toFixed(1) || "—"} cm²</div>
          </div>
          <div style={{ background: "rgba(0,0,0,0.3)", padding: "1rem", borderRadius: "var(--r-md)" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Infection Risk</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: ca.infection_risk === "High" ? "var(--red)" : "var(--green)" }}>{ca.infection_risk || "Low"}</div>
          </div>
          <div style={{ background: "rgba(0,0,0,0.3)", padding: "1rem", borderRadius: "var(--r-md)", gridColumn: "span 2" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Est. Time to Closure</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--teal)" }}>{ca.estimated_time_to_closure || "Unknown"}</div>
          </div>
        </div>
      </div>

    </div>
  );
}
