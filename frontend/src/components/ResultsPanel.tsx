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
      <div className="bento-item bento-large" style={{ background: "var(--bg-card)", border: "1px solid var(--border)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", padding: "0" }}>
        
        {/* Left Side: Care Details */}
        <div style={{ padding: "2rem" }}>
          <h2 style={{ fontSize: "1.8rem", marginBottom: "0.5rem", color: "var(--text-primary)" }}>Care Plan & Tutorial</h2>
          <p style={{ fontSize: "1.05rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "2rem" }}>
            {result.patient_message || "Your wound is healing. Follow standard care protocols."}
          </p>
          
          <div style={{ display: "flex", gap: "2rem", marginBottom: "2rem" }}>
            <div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Dressing Type</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 500, color: "var(--text-primary)" }}>{result.care_plan?.dressing_type || "Standard Bandage"}</div>
            </div>
            <div style={{ width: "1px", background: "var(--border)" }}></div>
            <div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Change Frequency</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 500, color: "var(--text-primary)" }}>{result.care_plan?.dressing_change_frequency || "Daily"}</div>
            </div>
          </div>

          {/* Pharmacy Link */}
          {result.care_plan?.product_name && (
            <div style={{ background: "rgba(255,255,255,0.03)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: "0.85rem", color: "var(--tertiary)", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.5rem" }}>Recommended Product</div>
              <div style={{ fontSize: "1.1rem", color: "var(--text-primary)", fontWeight: 500, marginBottom: "1rem" }}>{result.care_plan.product_name}</div>
              <a 
                href={`https://www.google.com/search?tbm=shop&q=${result.care_plan.product_search_query || result.care_plan.product_name.replace(/ /g, '+')}`}
                target="_blank" rel="noreferrer"
                className="btn btn-primary" style={{ width: "100%", fontSize: "0.95rem" }}
              >
                Find at Pharmacy
              </a>
            </div>
          )}
        </div>

        {/* Right Side: Interactive Care Mode Video */}
        <div style={{ background: "#000", borderLeft: "1px solid var(--border)", position: "relative", minHeight: "300px" }}>
          {result.care_plan?.care_video_youtube_id ? (
            <iframe 
              width="100%" 
              height="100%" 
              src={`https://www.youtube.com/embed/${result.care_plan.care_video_youtube_id}`} 
              title="Wound Care Tutorial" 
              frameBorder="0" 
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
              allowFullScreen
              style={{ position: "absolute", top: 0, left: 0 }}
            />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)" }}>
              No specific video tutorial available.
            </div>
          )}
        </div>
      </div>

      {/* TISSUE X-RAY BENTO (Medium/Large) */}
      <div className="bento-item bento-large" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "1.5rem", position: "absolute", top: 0, left: 0, zIndex: 10, pointerEvents: "none" }}>
          <h3 style={{ textShadow: "0 2px 4px rgba(0,0,0,0.8)" }}>Tissue Overlay</h3>
        </div>
        
        <div style={{ position: "relative", width: "100%", height: "400px", background: "#000" }}>
          {/* Base Layer: Original Image */}
          <img src={originalImageUrl} alt="Original" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "contain" }} />
          
          {/* Middle Layer: Annotated Tissue (Shows when slider > 33%) */}
          {result.images?.annotated_b64 && (
            <img 
              src={`data:image/jpeg;base64,${result.images.annotated_b64}`} 
              alt="Tissue Map" 
              style={{ 
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "contain",
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
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "contain", mixBlendMode: "screen",
                clipPath: `inset(0 ${100 - Math.min(Math.max((sliderValue - 66) * 3, 0), 100)}% 0 0)`
              }} 
            />
          )}

          {/* The Slider Control */}
          <input 
            type="range" min="0" max="100" value={sliderValue} onChange={(e) => setSliderValue(Number(e.target.value))}
            style={{
              position: "absolute", bottom: "20px", left: "5%", width: "90%", zIndex: 10,
              accentColor: "var(--tertiary)", cursor: "pointer", filter: "drop-shadow(0 2px 5px rgba(0,0,0,0.8))"
            }}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "1rem 2rem", fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 500, background: "var(--bg-surface)" }}>
          <span style={{ color: sliderValue < 33 ? "var(--text-primary)" : "inherit" }}>Original</span>
          <span style={{ color: sliderValue >= 33 && sliderValue < 66 ? "var(--text-primary)" : "inherit" }}>Tissue Map</span>
          <span style={{ color: sliderValue >= 66 ? "var(--text-primary)" : "inherit" }}>Inflammation</span>
        </div>
      </div>

      {/* GILMAN VELOCITY SPEEDOMETER (Small/Medium) */}
      <div className="bento-item bento-medium" style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <h3 style={{ marginBottom: "1.5rem", color: "var(--text-secondary)" }}>Healing Velocity</h3>
        <div style={{ position: "relative", width: "180px", height: "90px", overflow: "hidden", margin: "0 auto" }}>
          {/* Gauge Background */}
          <div style={{ width: "180px", height: "180px", borderRadius: "50%", background: "var(--border)", opacity: 0.5 }} />
          {/* Active Gauge */}
          {ca.gilman_velocity_cm_per_week !== null && ca.gilman_velocity_cm_per_week !== undefined && (
            <div style={{
              position: "absolute", top: 0, left: 0, width: "180px", height: "180px", borderRadius: "50%",
              background: "conic-gradient(from 180deg, var(--tertiary) 0deg, var(--tertiary) 180deg)",
              clipPath: `polygon(50% 50%, 0% 50%, 0% 0%, ${Math.min(100, Math.max(0, (ca.gilman_velocity_cm_per_week / 0.5) * 100))}% 0%, 100% 50%)`,
              transition: "clip-path 1s ease-out"
            }} />
          )}
          {/* Gauge Inner Cutout */}
          <div style={{ position: "absolute", top: "15px", left: "15px", width: "150px", height: "150px", borderRadius: "50%", background: "var(--bg-surface)" }} />
        </div>
        <div style={{ marginTop: "1rem" }}>
          <div className="score-big">
            {ca.gilman_velocity_cm_per_week !== null && ca.gilman_velocity_cm_per_week !== undefined 
              ? `${ca.gilman_velocity_cm_per_week.toFixed(2)}` 
              : "—"}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", marginTop: "0.2rem" }}>cm / week</div>
          
          <div style={{ fontSize: "0.85rem", color: "var(--flesh-tone)", fontWeight: 500, marginTop: "1rem", padding: "0.5rem 1rem", border: "1px solid var(--border)", borderRadius: "var(--r-sm)" }}>
            {ca.gilman_velocity_cm_per_week === null || ca.gilman_velocity_cm_per_week === undefined 
              ? "Needs 2+ Scans" 
              : ca.gilman_velocity_cm_per_week < 0.1 ? "Stalled" : "Healing"}
          </div>
        </div>
      </div>

      {/* METRICS (Small/Medium) */}
      <div className="bento-item bento-medium" style={{ display: "flex", flexDirection: "column", gap: "1.5rem", justifyContent: "center" }}>
        <h3 style={{ color: "var(--text-secondary)" }}>Clinical Metrics</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div style={{ border: "1px solid var(--border)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Estimated Area</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--text-primary)" }}>{result.geometry?.area_cm2?.toFixed(1) || "—"} cm²</div>
          </div>
          <div style={{ border: "1px solid var(--border)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Infection Risk</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--text-primary)" }}>{ca.infection_risk || "Low"}</div>
          </div>
          <div style={{ border: "1px solid var(--border)", padding: "1rem", borderRadius: "var(--r-sm)", gridColumn: "span 2" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Est. Time to Closure</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--tertiary)" }}>
              {ca.estimated_closure_days ? `${ca.estimated_closure_days} days` : "Needs 2+ Scans"}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
