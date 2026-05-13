import { useState, useEffect, useRef } from "react";
import ImageClickCanvas from "./components/ImageClickCanvas";
import TissueBreakdownPanel from "./components/TissueBreakdownPanel";
import ResultsPanel from "./components/ResultsPanel";
import HealingTrendChart from "./components/HealingTrendChart";
import AlertsPanel from "./components/AlertsPanel";
import BWATPanel from "./components/BWATPanel";
import { fetchCoins, analyzeWound } from "./api";
import type { CoinOption, AnalysisResult } from "./types";
import "./App.css";

type Step = "upload" | "configure" | "processing" | "results";

const PATIENT_KEY = "wscan_patient_id";
function getOrCreatePatientId(): string {
  let id = localStorage.getItem(PATIENT_KEY);
  if (!id) { id = `patient_${Date.now()}`; localStorage.setItem(PATIENT_KEY, id); }
  return id;
}

const PROCESSING_STEPS = [
  { msg: "Checking photo quality…",            icon: "🔍" },
  { msg: "AI detecting wound location…",       icon: "🤖" },
  { msg: "Detecting coin for calibration…",    icon: "🪙" },
  { msg: "Segmenting wound boundary…",         icon: "✂️" },
  { msg: "Computing geometry & area…",         icon: "📐" },
  { msg: "Analysing tissue composition…",      icon: "🧬" },
  { msg: "BWAT clinical assessment…",          icon: "📋" },
  { msg: "Generating clinical report…",        icon: "📄" },
];

export default function App() {
  const [coins, setCoins] = useState<CoinOption[]>([]);
  const [step, setStep] = useState<Step>("upload");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [coinType, setCoinType] = useState("INR_5");
  const [clickPoint, setClickPoint] = useState<{ x: number; y: number } | null>(null);
  const [patientId] = useState(getOrCreatePatientId);
  const [loading, setLoading] = useState(false);
  const [processingIdx, setProcessingIdx] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchCoins().then(setCoins).catch(() => setCoins([
      { key: "INR_5", label: "₹5 Coin (23mm)" },
      { key: "INR_10", label: "₹10 Coin (27mm)" },
      { key: "US_QUARTER", label: "US Quarter (24.26mm)" },
    ]));
  }, []);

  function handleFile(file: File) {
    setImageFile(file); setClickPoint(null); setResult(null);
    setError(null); setStep("configure");
  }

  async function handleAnalyze() {
    if (!imageFile) return;
    setLoading(true); setStep("processing"); setProcessingIdx(0);
    intervalRef.current = setInterval(() =>
      setProcessingIdx(i => Math.min(i + 1, PROCESSING_STEPS.length - 1)), 3500);
    try {
      const res = await analyzeWound({
        image: imageFile, coinType, patientId,
        clickX: clickPoint?.x, clickY: clickPoint?.y,
      });
      setResult(res);
      setStep(res.status === "success" ? "results" : "configure");
      if (res.status !== "success") setError(res.detail || res.gemini_advice || "Analysis failed");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setStep("configure");
    } finally {
      if (intervalRef.current) clearInterval(intervalRef.current);
      setLoading(false);
    }
  }

  function reset() { setStep("upload"); setImageFile(null); setClickPoint(null); setResult(null); setError(null); }

  function exportPDF() {
    if (!result) return;
    const r = result;
    const lines = [
      "WOUNDSCAN CLINICAL REPORT",
      `Generated: ${new Date().toLocaleDateString()}  Patient: ${patientId}  Session: ${r.session_number}`,
      "",
      `WOUND TYPE: ${r.localization?.wound_type?.replace(/_/g," ").toUpperCase()} (${((r.localization?.wound_type_confidence??0)*100).toFixed(0)}% confidence)`,
      r.localization?.wound_type_reasoning ?? "",
      "",
      "MEASUREMENTS",
      `Area: ${r.geometry?.area_cm2.toFixed(2)} cm²   Perimeter: ${r.geometry?.perimeter_cm.toFixed(2)} cm   Circularity: ${r.geometry?.circularity.toFixed(3)}`,
      `Tissue: Gran ${r.tissue?.granulation_pct.toFixed(1)}%  Slough ${r.tissue?.slough_pct.toFixed(1)}%  Necrotic ${r.tissue?.necrotic_pct.toFixed(1)}%  Epithelial ${r.tissue?.epithelial_pct.toFixed(1)}%`,
      "",
      `BWAT SCORE: ${r.bwat?.bwat_total}/60 — ${r.bwat?.bwat_severity?.toUpperCase()}`,
      r.bwat?.bwat_interpretation ?? "",
      "",
      "TIME FRAMEWORK",
      `T: ${r.bwat?.TIME?.T ?? ""}`,
      `I: ${r.bwat?.TIME?.I ?? ""}`,
      `M: ${r.bwat?.TIME?.M ?? ""}`,
      `E: ${r.bwat?.TIME?.E ?? ""}`,
      "",
      `PRIMARY SCORE: ${r.scores?.primary_score?.name} ${r.scores?.primary_score?.value}/${r.scores?.primary_score?.max}`,
      `NERDS: ${r.scores?.nerds?.score}/5  STONES: ${r.scores?.stones?.score}/6`,
      `INFECTION RISK: ${r.scores?.infection_risk}`,
      `HEALING TRAJECTORY: ${r.scores?.healing_trajectory}`,
      r.scores?.estimated_closure_days ? `ESTIMATED CLOSURE: ${r.scores.estimated_closure_days} days` : "",
      "",
      "CARE PLAN",
      `Dressing: ${r.care_plan?.dressing_type ?? ""}`,
      `Change frequency: ${r.care_plan?.dressing_change_frequency ?? ""}`,
      `Debridement: ${r.care_plan?.debridement_needed ? r.care_plan.debridement_type : "Not needed"}`,
      ...(r.care_plan?.specific_actions ?? []).map(a => `• ${a}`),
      "",
      "CLINICAL SUMMARY",
      r.clinician_report ?? "",
      "",
      "PATIENT MESSAGE",
      r.patient_message ?? "",
      "",
      "GUIDELINE REFERENCES",
      ...(r.clinical_assessment?.guideline_references ?? []).map(ref => `• ${ref}`),
      "",
      "---",
      "This report was generated by WoundScan AI. It supports clinical decision-making",
      "and does not replace physical examination by a qualified clinician.",
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `woundscan_report_${r.session_number ?? 1}.txt`;
    a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="var(--teal)" strokeWidth="1.5" />
            <circle cx="14" cy="14" r="6" fill="var(--teal)" opacity="0.2" />
            <circle cx="14" cy="14" r="3" fill="var(--teal)" />
          </svg>
          <span className="header-logo">WoundScan</span>
          <span className="badge badge-teal">AI</span>
        </div>
        <nav className="header-nav">
          <span className="text-muted" style={{ fontSize: "0.78rem" }}>
            Patient: <span style={{ color: "var(--teal)", fontFamily: "monospace" }}>{patientId}</span>
          </span>
          <span className="text-muted" style={{ fontSize: "0.75rem" }}>
            MedSAM · SegFormer · Gemini Flash
          </span>
        </nav>
      </header>

      <main className="app-main">

        {/* ── UPLOAD ─────────────────────────────────────────────────────── */}
        {step === "upload" && (
          <div className="upload-screen animate-fade-in">
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <h1>AI Wound Tracking</h1>
              <p className="text-secondary" style={{ marginTop: "0.5rem", maxWidth: 500, margin: "0.5rem auto 0" }}>
                Daily wound analysis using BWAT, TIME, PUSH/RESVECH, NERDS/STONES.
                Upload a photo — AI auto-detects the wound.
              </p>
            </div>
            <label htmlFor="file-upload" className="drop-zone"
              onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith("image/")) handleFile(f); }}
              onDragOver={e => e.preventDefault()}>
              <input id="file-upload" type="file" accept="image/*" style={{ display: "none" }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
              <div className="drop-zone-content">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ marginBottom: 12 }}>
                  <rect x="4" y="8" width="40" height="32" rx="6" stroke="var(--border-bright)" strokeWidth="1.5" />
                  <circle cx="17" cy="20" r="4" stroke="var(--border-bright)" strokeWidth="1.5" />
                  <path d="M4 32l11-10 8 7 7-6 14 11" stroke="var(--border-bright)" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
                <span style={{ fontSize: "0.95rem", color: "var(--text-secondary)" }}>
                  Drop wound image or <span style={{ color: "var(--teal)" }}>browse</span>
                </span>
                <span className="text-muted" style={{ fontSize: "0.78rem", marginTop: 4 }}>JPEG · PNG · WEBP</span>
              </div>
            </label>
            <div className="upload-tips">
              {["Place a coin flat next to the wound", "Photograph from directly above", "Ensure even lighting — no harsh shadows", "Keep wound fully in frame"].map((tip, i) => (
                <div key={i} className="tip-item"><span className="tip-num">{i + 1}</span><span>{tip}</span></div>
              ))}
            </div>
          </div>
        )}

        {/* ── CONFIGURE ──────────────────────────────────────────────────── */}
        {step === "configure" && imageFile && (
          <div className="configure-screen animate-fade-in">
            <div className="configure-left">
              <h2 style={{ marginBottom: "0.4rem" }}>Optional: Click wound centre</h2>
              <p className="text-secondary" style={{ fontSize: "0.83rem", marginBottom: "0.75rem" }}>
                AI auto-detects the wound. You can click to override.
              </p>
              <ImageClickCanvas imageFile={imageFile} onClickPoint={(x, y) => setClickPoint({ x, y })} clickPoint={clickPoint} />
              {clickPoint && <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--teal)" }}>✓ Click at ({clickPoint.x}, {clickPoint.y})</div>}
            </div>
            <div className="configure-right">
              <div className="card">
                <h3 style={{ marginBottom: "1rem" }}>Calibration</h3>
                <label htmlFor="coin-select">Coin in image</label>
                <select id="coin-select" value={coinType} onChange={e => setCoinType(e.target.value)}>
                  {coins.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select>
              </div>
              <div className="card" style={{ marginTop: "0.75rem" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Pipeline</h3>
                {PROCESSING_STEPS.map(({ msg, icon }) => (
                  <div key={msg} style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", color: "var(--text-muted)", padding: "0.2rem 0" }}>
                    <span>{icon}</span><span>{msg}</span>
                  </div>
                ))}
              </div>
              {error && (
                <div style={{ marginTop: "0.75rem", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "var(--r-sm)", padding: "0.75rem", fontSize: "0.83rem", color: "#f87171" }}>
                  {error}
                </div>
              )}
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                <button className="btn btn-ghost" onClick={reset} style={{ flex: 1 }}>← Back</button>
                <button className="btn btn-primary" style={{ flex: 2 }} disabled={loading} onClick={handleAnalyze}>
                  Run Full Analysis
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── PROCESSING ─────────────────────────────────────────────────── */}
        {step === "processing" && (
          <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 400, gap: "1.5rem" }}>
            <div style={{ width: 60, height: 60, border: "3px solid var(--border)", borderTop: "3px solid var(--teal)", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>{PROCESSING_STEPS[processingIdx].icon}</div>
              <div style={{ fontSize: "1rem", color: "var(--text-primary)", fontWeight: 600 }}>{PROCESSING_STEPS[processingIdx].msg}</div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>Step {processingIdx + 1} of {PROCESSING_STEPS.length}</div>
            </div>
            <div style={{ display: "flex", gap: "0.4rem" }}>
              {PROCESSING_STEPS.map((_, i) => (
                <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: i <= processingIdx ? "var(--teal)" : "var(--border)" }} />
              ))}
            </div>
          </div>
        )}

        {/* ── RESULTS ────────────────────────────────────────────────────── */}
        {step === "results" && result?.status === "success" && (
          <div className="results-screen animate-fade-in">
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <div>
                <h2 style={{ marginBottom: "0.2rem" }}>Session {result.session_number} — {result.localization?.wound_type?.replace(/_/g, " ")}</h2>
                <p className="text-muted" style={{ fontSize: "0.78rem" }}>
                  {result.localization?.wound_type_confidence != null && `${(result.localization.wound_type_confidence * 100).toFixed(0)}% confidence · `}
                  Calibration: {result.calibration?.px_per_mm.toFixed(2)} px/mm
                </p>
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn btn-ghost" style={{ fontSize: "0.8rem" }} onClick={exportPDF}>⬇ Export Report</button>
                <button className="btn btn-ghost" onClick={reset}>New Analysis</button>
              </div>
            </div>

            {/* Patient message banner */}
            {result.patient_message && (
              <div style={{ background: "rgba(20,184,166,0.08)", border: "1px solid rgba(20,184,166,0.25)", borderRadius: "var(--r-sm)", padding: "1rem 1.25rem", marginBottom: "1rem" }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.08em", color: "var(--teal)", marginBottom: "0.35rem" }}>FOR YOU</div>
                <p style={{ fontSize: "0.9rem", color: "var(--text-primary)", margin: 0, lineHeight: 1.6 }}>{result.patient_message}</p>
              </div>
            )}

            {/* Alerts */}
            {result.alerts && result.alerts.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                <AlertsPanel alerts={result.alerts} />
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "1rem", alignItems: "start" }}>
              {/* Left column */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <ResultsPanel
                  ca={result.clinical_assessment!}
                  risk={{ level: (result.scores?.infection_risk ?? "LOW") as "LOW" | "MODERATE" | "HIGH", NERDS: [], STONES: [], NERDS_score: result.scores?.nerds?.score ?? 0, STONES_score: result.scores?.stones?.score ?? 0 }}
                  scores={{ composite_score: result.scores?.composite_score ?? 0, global_healing_index: null, healing_velocity_cm2_per_day: 0, healing_rate_pct: result.clinical_assessment?.area_reduction_pct ?? null, trajectory: (result.scores?.healing_trajectory ?? "FIRST_SESSION") as any, estimated_closure_days: result.scores?.estimated_closure_days ?? null }}
                  compositeScore={result.scores?.composite_score ?? 0}
                  inflammationIndex={result.inflammation?.inflammation_index ?? 0}
                  areaCm2={result.geometry?.area_cm2 ?? 0}
                  annotatedB64={result.images?.annotated_b64 ?? ""}
                  heatmapB64={result.images?.heatmap_b64 ?? ""}
                />
                {result.bwat && <BWATPanel bwat={result.bwat} />}
                {result.trend && result.trend.area_cm2.length >= 2 && (
                  <HealingTrendChart trend={result.trend} />
                )}
                {/* Clinician report */}
                {result.clinician_report && (
                  <div className="card">
                    <h3 style={{ marginBottom: "0.75rem" }}>Clinical Summary</h3>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>{result.clinician_report}</p>
                    {result.clinical_assessment?.guideline_references?.map((ref, i) => (
                      <div key={i} style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>📚 {ref}</div>
                    ))}
                  </div>
                )}
              </div>

              {/* Right column */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <TissueBreakdownPanel tissue={result.tissue!} />

                {/* Key scores */}
                <div className="card">
                  <h3 style={{ marginBottom: "0.75rem" }}>Clinical Scores</h3>
                  {result.scores?.primary_score && (
                    <div style={{ marginBottom: "0.75rem", padding: "0.5rem", background: "rgba(20,184,166,0.06)", borderRadius: "var(--r-sm)" }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.2rem" }}>{result.scores.primary_score.name}</div>
                      <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--teal)", lineHeight: 1 }}>
                        {result.scores.primary_score.value}<span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>/{result.scores.primary_score.max}</span>
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>{result.scores.primary_score.interpretation}</div>
                    </div>
                  )}
                  {[
                    { label: "NERDS", value: `${result.scores?.nerds?.score ?? 0}/5`, note: result.scores?.nerds?.interpretation },
                    { label: "STONES", value: `${result.scores?.stones?.score ?? 0}/6`, note: result.scores?.stones?.interpretation },
                    { label: "Infection risk", value: result.scores?.infection_risk ?? "—" },
                    { label: "Trajectory", value: result.scores?.healing_trajectory ?? "—" },
                    { label: "Est. closure", value: result.scores?.estimated_closure_days ? `${result.scores.estimated_closure_days} days` : "—" },
                  ].map(({ label, value, note }) => (
                    <div key={label} style={{ padding: "0.3rem 0", borderBottom: "1px solid var(--border)", fontSize: "0.83rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="text-muted">{label}</span>
                        <span className="mono" style={{ fontWeight: 600 }}>{value}</span>
                      </div>
                      {note && <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{note}</div>}
                    </div>
                  ))}
                </div>

                {/* Geometry */}
                <div className="card">
                  <h3 style={{ marginBottom: "0.75rem" }}>Geometry</h3>
                  {[
                    { label: "Area",      value: `${result.geometry!.area_cm2.toFixed(2)} cm²` },
                    { label: "Perimeter", value: `${result.geometry!.perimeter_cm.toFixed(2)} cm` },
                    { label: "Length",    value: `${result.geometry!.longest_axis_cm.toFixed(2)} cm` },
                    { label: "Width",     value: `${result.geometry!.shortest_axis_cm.toFixed(2)} cm` },
                    { label: "Circularity", value: result.geometry!.circularity.toFixed(3) },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "0.3rem 0", borderBottom: "1px solid var(--border)", fontSize: "0.83rem" }}>
                      <span className="text-muted">{label}</span>
                      <span className="mono">{value}</span>
                    </div>
                  ))}
                </div>

                {/* Care plan */}
                {result.care_plan && (
                  <div className="card">
                    <h3 style={{ marginBottom: "0.75rem" }}>Care Plan</h3>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                      <div><span className="text-muted">Dressing: </span>{result.care_plan.dressing_type}</div>
                      <div><span className="text-muted">Change: </span>{result.care_plan.dressing_change_frequency}</div>
                      <div><span className="text-muted">Review in: </span>{result.care_plan.review_frequency_days} days</div>
                      {result.care_plan.debridement_needed && <div style={{ color: "var(--amber)" }}>⚠ Debridement: {result.care_plan.debridement_type}</div>}
                      {result.care_plan.offloading_needed && <div style={{ color: "var(--amber)" }}>⚠ Offloading required</div>}
                      {result.care_plan.antimicrobial_needed && <div style={{ color: "#f87171" }}>🚨 Topical antimicrobial indicated</div>}
                      {result.care_plan.specific_actions?.map((a, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>• {a}</div>)}
                    </div>
                  </div>
                )}

                {/* Inflammation */}
                <div className="card">
                  <h3 style={{ marginBottom: "0.5rem" }}>Inflammation</h3>
                  <div className="mono" style={{ fontSize: "1.6rem", fontWeight: 700, color: (result.inflammation?.inflammation_index ?? 0) > 65 ? "var(--red)" : (result.inflammation?.inflammation_index ?? 0) > 40 ? "var(--amber)" : "var(--green)" }}>
                    {result.inflammation?.inflammation_index.toFixed(1)}
                    <span className="text-muted" style={{ fontSize: "0.85rem", marginLeft: 4 }}>/ 100</span>
                  </div>
                  <p className="text-muted" style={{ fontSize: "0.72rem", marginTop: 4 }}>Wannous erythema index · periwound</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
