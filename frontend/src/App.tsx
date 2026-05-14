import { useState, useEffect, useRef } from "react";
import { Routes, Route, Link, useNavigate, useLocation } from "react-router-dom";
import { SignedIn, SignedOut, SignInButton, UserButton, useUser } from "@clerk/clerk-react";
import { LayoutDashboard, Camera, Activity, FileText, UploadCloud, ChevronRight, Settings } from "lucide-react";

import BoxDrawCanvas from "./components/BoxDrawCanvas";
import ResultsPanel from "./components/ResultsPanel";
import { fetchCoins, analyzeWound, suggestBox } from "./api";
import type { BoxCoords, SuggestBoxResponse } from "./api";
import type { CoinOption, AnalysisResult } from "./types";
import "./App.css";

// ─── TYPES ────────────────────────────────────────────────────────
type Step = "upload" | "configure" | "processing" | "results";

const PROCESSING_STEPS = [
  { msg: "Checking photo quality" },
  { msg: "Detecting wound location" },
  { msg: "Calibrating scale" },
  { msg: "Segmenting wound boundary" },
  { msg: "Computing geometry & area" },
  { msg: "Analysing tissue composition" },
  { msg: "Clinical assessment" },
  { msg: "Generating report" },
];

// ─── WIZARD COMPONENT ──────────────────────────────────────────────
function ScanWizard() {
  const { user } = useUser();
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
        <div className="animate-fade-in card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "400px" }}>
          <div className="spinner"></div>
          <h2 style={{ marginTop: "2rem", color: "var(--text-primary)" }}>{PROCESSING_STEPS[processingIdx].msg}...</h2>
          <p className="text-muted" style={{ marginTop: "0.5rem" }}>Step {processingIdx + 1} of {PROCESSING_STEPS.length}</p>
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
      {/* FLOATING TOP NAV */}
      <header className="top-nav">
        <div className="nav-brand">
          <Activity color="var(--teal)" size={32} strokeWidth={2.5} />
          <span>WoundScan</span>
        </div>
        
        <nav className="nav-links">
          <Link to="/" className={`nav-link ${location.pathname === "/" ? "active" : ""}`}>
            <LayoutDashboard size={18} /> Dashboard
          </Link>
          <Link to="/scan" className={`nav-link ${location.pathname === "/scan" ? "active" : ""}`}>
            <Camera size={18} /> New Scan
          </Link>
          <Link to="/history" className={`nav-link ${location.pathname === "/history" ? "active" : ""}`}>
            <FileText size={18} /> History
          </Link>
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <Settings size={20} color="var(--text-muted)" style={{ cursor: "pointer" }} />
          <UserButton showName />
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

// ─── LANDING PAGE (Signed Out) ─────────────────────────────────────
function LandingPage() {
  return (
    <div className="landing-page">
      <div className="landing-content">
        <Activity color="var(--teal)" size={64} style={{ marginBottom: "2rem" }} />
        <h1 style={{ fontSize: "3.5rem", fontWeight: 800, marginBottom: "1rem", letterSpacing: "-0.05em" }}>WoundScan AI</h1>
        <p style={{ fontSize: "1.2rem", color: "var(--text-secondary)", marginBottom: "3rem", maxWidth: "600px", lineHeight: 1.6 }}>
          The professional clinical platform for proactive wound healing, tissue analysis, and automated treatment matchmaking.
        </p>
        <SignInButton mode="modal">
          <button className="btn btn-primary" style={{ padding: "1rem 2.5rem", fontSize: "1.2rem", borderRadius: "50px" }}>
            Secure Clinical Login
          </button>
        </SignInButton>
      </div>
    </div>
  );
}

// ─── APP COMPONENT ─────────────────────────────────────────────────
export default function App() {
  return (
    <>
      <SignedOut>
        <LandingPage />
      </SignedOut>

      <SignedIn>
        <DashboardLayout>
          <Routes>
            <Route path="/" element={
              <div className="animate-fade-in">
                <h1 style={{ marginBottom: "2rem" }}>Welcome to WoundScan</h1>
                <p className="text-secondary" style={{ fontSize: "1.1rem" }}>Select "New Scan" from the menu to begin tracking a patient's wound.</p>
              </div>
            } />
            <Route path="/scan" element={<ScanWizard />} />
            <Route path="/history" element={<div className="animate-fade-in card"><h2>History</h2><p className="text-muted">Coming soon...</p></div>} />
          </Routes>
        </DashboardLayout>
      </SignedIn>
    </>
  );
}
