import { useState, useEffect, useRef } from "react";
import { Routes, Route, Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { SignedIn, SignedOut, SignInButton, UserButton, useUser, RedirectToSignIn } from "@clerk/clerk-react";
import { LayoutDashboard, Camera, Activity, FileText, UploadCloud, ChevronRight, Settings } from "lucide-react";

import BoxDrawCanvas from "./components/BoxDrawCanvas";
import ResultsPanel from "./components/ResultsPanel";
import TrackingDashboard from "./components/TrackingDashboard";
import { fetchCoins, analyzeWound, suggestBox } from "./api";
import type { BoxCoords, SuggestBoxResponse } from "./api";
import type { CoinOption, AnalysisResult } from "./types";
import "./App.css";

// ─── TYPES ────────────────────────────────────────────────────────
type Step = "upload" | "configure" | "processing" | "results";

const PROCESSING_STEPS = [
  { msg: "Validating Image Quality & Exposure" },
  { msg: "Calibrating Spatial Geometry & Scale" },
  { msg: "Running MedSAM-B2 Segmentation" },
  { msg: "Extracting Wound Boundaries" },
  { msg: "Quantifying Tissue (Granulation vs Slough)" },
  { msg: "Analyzing Periwound Inflammation" },
  { msg: "Cross-referencing BWAT Heuristics" },
  { msg: "Synthesizing Clinical Evidence" },
];

// ─── WIZARD COMPONENT ──────────────────────────────────────────────
function ScanWizard() {
  const { user } = useUser();
  const [searchParams] = useSearchParams();
  const trackingWoundType = searchParams.get("wound") || undefined;
  const [coins, setCoins] = useState<CoinOption[]>([]);
  const [step, setStep] = useState<Step>("upload");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [coinType, setCoinType] = useState("INR_5");
  const [confirmedBox, setConfirmedBox] = useState<BoxCoords | null>(null);
  const [suggestedBox, setSuggestedBox] = useState<BoxCoords | null>(null);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [woundTypeHint, setWoundTypeHint] = useState<string | null>(null);
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
    setImageFile(file);
    setConfirmedBox(null);
    setSuggestedBox(null);
    setSuggestionError(null);
    setWoundTypeHint(null);
    setResult(null);
    setError(null);
    setStep("configure");
    setSuggestionLoading(true);
    
    suggestBox(file).then((res: SuggestBoxResponse) => {
        setSuggestedBox(res.bbox_px);
        if (res.wound_type && res.wound_type !== "unknown") setWoundTypeHint(res.wound_type);
        setSuggestionLoading(false);
        if (!res.gemini_ok || !res.wound_found) {
          setSuggestionError(res.fallback_message || "AI couldn't detect wound — draw box manually");
        }
      }).catch(() => {
        setSuggestionLoading(false);
        setSuggestionError("AI detection failed — draw box manually");
      });
  }

  async function handleAnalyze() {
    if (!imageFile || !confirmedBox) return;
    setLoading(true); setStep("processing"); setProcessingIdx(0);
    intervalRef.current = setInterval(() =>
      setProcessingIdx(i => Math.min(i + 1, PROCESSING_STEPS.length - 1)), 3500);
    
    try {
      const patientId = user?.id || "anonymous";
      const res = await analyzeWound({
        image: imageFile, coinType, patientId,
        box: confirmedBox,
        woundType: woundTypeHint || undefined,
        trackingWoundType: trackingWoundType,
      });
      setResult(res);
      setStep(res.status === "success" ? "results" : "configure");
      if (res.status !== "success") setError(res.detail || res.gemini_advice || "Analysis failed");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setStep("configure");
    } finally {
      setLoading(false);
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  }

  return (
    <div className="wizard-container">
      {/* TRACKING CONTEXT BANNER */}
      {trackingWoundType && (
        <div className="animate-fade-in" style={{ background: "rgba(180,139,108,0.08)", border: "1px solid rgba(180,139,108,0.2)", borderRadius: 12, padding: "0.85rem 1.25rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Activity size={16} color="var(--tertiary)" />
          <div>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Updating wound: </span>
            <span style={{ fontWeight: 600, color: "var(--tertiary)", textTransform: "capitalize" }}>{trackingWoundType}</span>
          </div>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "auto" }}>AI will compare against your last scan</span>
        </div>
      )}
      {/* STEPS INDICATOR */}
      <div className="stepper">
        {["Upload", "Calibration", "Analysis", "Results"].map((label, idx) => {
          const isActive = 
            (idx === 0 && step === "upload") ||
            (idx === 1 && step === "configure") ||
            (idx === 2 && step === "processing") ||
            (idx === 3 && step === "results");
          const isPassed = 
            (idx === 0 && step !== "upload") ||
            (idx === 1 && (step === "processing" || step === "results")) ||
            (idx === 2 && step === "results");

          return (
            <div key={label} className={`step ${isActive ? "active" : ""} ${isPassed ? "passed" : ""}`}>
              <div className="step-indicator"></div>
              <span className="step-label">{label}</span>
            </div>
          );
        })}
      </div>

      {/* UPLOAD STEP */}
      {step === "upload" && (
        <div className="animate-fade-in card upload-card">
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.8rem", color: "var(--text-primary)" }}>New AI Scan</h2>
            <p className="text-secondary" style={{ marginTop: "0.5rem" }}>Upload a clear photo of the wound with a reference coin.</p>
          </div>
          <label htmlFor="file-upload" className="drop-zone"
            onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith("image/")) handleFile(f); }}
            onDragOver={e => e.preventDefault()}>
            <input id="file-upload" type="file" accept="image/*" style={{ display: "none" }}
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
            <div className="drop-zone-content">
              <UploadCloud size={48} color="var(--teal)" style={{ marginBottom: "1rem" }} />
              <span style={{ fontSize: "1.1rem", color: "var(--text-secondary)", fontWeight: 500 }}>
                Drag & Drop or <span style={{ color: "var(--teal)", textDecoration: "underline" }}>Browse</span>
              </span>
            </div>
          </label>
        </div>
      )}

      {/* CONFIGURE STEP */}
      {step === "configure" && imageFile && (
        <div className="animate-fade-in configure-grid">
          <div className="card">
            <h3 style={{ marginBottom: "1rem" }}>Wound Boundary</h3>
            <p className="text-secondary" style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
              Please confirm the AI-detected boundary or draw a new box tightly around the wound bed.
            </p>
            <BoxDrawCanvas 
              imageFile={imageFile} 
              suggestedBox={suggestedBox} 
              onBoxConfirmed={setConfirmedBox} 
              onBoxCleared={() => setConfirmedBox(null)} 
              disabled={loading}
            />
          </div>
          
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div className="card">
              <h3 style={{ marginBottom: "1rem" }}>Scale Calibration</h3>
              <label htmlFor="coin-select" style={{ fontSize: "0.85rem", color: "var(--text-muted)", display: "block", marginBottom: "0.5rem" }}>Reference Coin Type</label>
              <select id="coin-select" value={coinType} onChange={e => setCoinType(e.target.value)} className="modern-select">
                {coins.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </div>
            
            <button 
              className="btn btn-primary" 
              style={{ width: "100%", padding: "1rem", fontSize: "1.1rem" }}
              disabled={loading || !confirmedBox} 
              onClick={handleAnalyze}
            >
              Start AI Analysis
            </button>
            <button className="btn btn-ghost" onClick={() => setStep("upload")} style={{ width: "100%" }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* PROCESSING STEP */}
      {step === "processing" && (
        <div className="animate-fade-in card" style={{ position: "relative", overflow: "hidden", minHeight: "400px", padding: 0, border: "1px solid var(--tertiary)", borderRadius: "var(--r-md)" }}>
          {/* Background Image with Overlay */}
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
            {imageFile && (
              <img src={URL.createObjectURL(imageFile)} alt="Scanning" style={{ width: "100%", height: "100%", objectFit: "cover", filter: "blur(4px) brightness(0.2)" }} />
            )}
            <div className="scan-line"></div>
          </div>
          
          {/* Content overlay */}
          <div style={{ position: "relative", zIndex: 10, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "400px", padding: "2rem", textAlign: "center" }}>
            <div className="radar-spinner" style={{ marginBottom: "2rem" }}></div>
            <h2 style={{ color: "var(--text-primary)", fontSize: "1.8rem", textShadow: "0 2px 10px rgba(0,0,0,0.5)", marginBottom: "0.5rem" }}>
              {PROCESSING_STEPS[processingIdx].msg}...
            </h2>
            <div style={{ width: "60%", height: "4px", background: "rgba(255,255,255,0.1)", borderRadius: "2px", overflow: "hidden", marginTop: "1rem" }}>
               <div style={{ height: "100%", width: `${((processingIdx + 1) / PROCESSING_STEPS.length) * 100}%`, background: "var(--tertiary)", transition: "width 0.5s ease" }}></div>
            </div>
            <p style={{ color: "var(--flesh-tone)", marginTop: "1rem", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              STEP {processingIdx + 1} OF {PROCESSING_STEPS.length}
            </p>
          </div>
        </div>
      )}

      {/* RESULTS STEP */}
      {step === "results" && result?.status === "success" && (
        <div className="animate-fade-in">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <h2>Analysis Complete</h2>
            <button className="btn btn-primary" onClick={() => setStep("upload")}>
              New Scan
            </button>
          </div>
          <ResultsPanel result={result} imageFile={imageFile!} />
        </div>
      )}
    </div>
  );
}

// ─── DASHBOARD LAYOUT ──────────────────────────────────────────────
function DashboardLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <div className="app-layout">
      {/* MINIMALIST TOP BRANDING */}
      <div className="top-brand">
        <Activity color="var(--tertiary)" size={24} />
        WoundScan
      </div>

      {/* MAIN CONTENT */}
      <main className="main-content">
        {children}
      </main>

      {/* REFERENCE FLOATING DOCK */}
      <nav className="dock-container">
        <Link to="/" className={`dock-link ${location.pathname === "/" ? "active" : ""}`} title="Home">
          <LayoutDashboard size={20} />
        </Link>
        <Link to="/scan" className={`dock-link ${location.pathname === "/scan" ? "active" : ""}`} title="New Scan">
          <Camera size={20} />
        </Link>
        <Link to="/tracking" className={`dock-link ${location.pathname === "/tracking" ? "active" : ""}`} title="Tracking">
          <Activity size={20} />
        </Link>
        <div style={{ width: "1px", height: "24px", background: "var(--border)", margin: "0 0.5rem" }}></div>
        <UserButton />
      </nav>
    </div>
  );
}

// LandingPage removed as requested, using RedirectToSignIn directly.

// ─── HOME PAGE ─────────────────────────────────────────────────────
function EmptyHome() {
  const navigate = useNavigate();
  return (
    <div className="animate-fade-in" style={{ maxWidth: 700, margin: "0 auto", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "70vh", textAlign: "center", gap: "2rem" }}>
      <div style={{ width: 90, height: 90, borderRadius: "50%", background: "rgba(180,139,108,0.1)", border: "1px solid rgba(180,139,108,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Activity size={42} color="var(--tertiary)" />
      </div>
      <div>
        <h1 style={{ fontSize: "2.5rem", marginBottom: "0.75rem", letterSpacing: "-0.04em" }}>WoundScan <span style={{ color: "var(--tertiary)" }}>AI</span></h1>
        <p style={{ color: "var(--text-muted)", fontSize: "1.05rem", maxWidth: 480, margin: "0 auto", lineHeight: 1.7 }}>
          Clinical-grade wound tracking powered by AI. Scan, compare, and monitor healing progress over time.
        </p>
      </div>
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center" }}>
        <button onClick={() => navigate("/scan")} className="btn btn-primary" style={{ padding: "0.9rem 2rem", fontSize: "1rem" }}>
          <Camera size={18} /> New Scan
        </button>
        <button onClick={() => navigate("/tracking")} className="btn btn-ghost" style={{ padding: "0.9rem 2rem", fontSize: "1rem" }}>
          <FileText size={18} /> View Tracking
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", width: "100%", marginTop: "1rem" }}>
        {[{ icon: <Camera size={20}/>, label: "Scan", desc: "Upload wound photo" }, { icon: <Activity size={20}/>, label: "Analyse", desc: "AI tissue segmentation" }, { icon: <FileText size={20}/>, label: "Track", desc: "Compare & monitor" }].map((item, i) => (
          <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 12, padding: "1.25rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
            <div style={{ color: "var(--tertiary)" }}>{item.icon}</div>
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{item.label}</div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── APP COMPONENT ─────────────────────────────────────────────────
export default function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<EmptyHome />} />
        
        <Route path="/scan" element={
          <>
            <SignedIn><ScanWizard /></SignedIn>
            <SignedOut><RedirectToSignIn /></SignedOut>
          </>
        } />
        
        <Route path="/tracking" element={
          <>
            <SignedIn><TrackingDashboard /></SignedIn>
            <SignedOut><RedirectToSignIn /></SignedOut>
          </>
        } />
      </Routes>
    </DashboardLayout>
  );
}
