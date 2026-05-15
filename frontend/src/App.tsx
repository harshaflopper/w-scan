import { useState, useEffect, useRef } from "react";
import { Routes, Route, Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { SignedIn, SignedOut, SignInButton, UserButton, useUser, RedirectToSignIn } from "@clerk/clerk-react";
import { LayoutDashboard, Camera, Activity, FileText, UploadCloud, ChevronRight, Settings, ShieldAlert } from "lucide-react";

import BoxDrawCanvas from "./components/BoxDrawCanvas";
import ResultsPanel from "./components/ResultsPanel";
import TrackingDashboard from "./components/TrackingDashboard";
import { fetchCoins, analyzeWound, suggestBox } from "./api";
import type { BoxCoords, SuggestBoxResponse } from "./api";
import type { CoinOption, AnalysisResult } from "./types";
import "./App.css";

import imgUpload from "../../images/Screenshot 2026-05-16 005329.png";
import imgCalibrate from "../../images/Screenshot 2026-05-16 005423.png";
import imgResults from "../../images/Screenshot 2026-05-16 011827.png";
import imgTracking from "../../images/Screenshot 2026-05-16 012014.png";

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

// ─── PARTICLE BACKGROUND ───────────────────────────────────────────
function ParticleBackground() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#000000');
    scene.fog = new THREE.FogExp2('#000000', 0.0025);

    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2000);
    camera.position.set(0, 120, 350);

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance", alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    const renderScene = new RenderPass(scene, camera);
    const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.8, 0.4, 0);

    const composer = new EffectComposer(renderer);
    composer.addPass(renderScene);
    composer.addPass(bloomPass);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;
    controls.enableDamping = true;
    controls.enableZoom = false;
    controls.enablePan = false;

    const count = 20000;
    const geometry = new THREE.TetrahedronGeometry(0.25);
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const instancedMesh = new THREE.InstancedMesh(geometry, material, count);

    const dummy = new THREE.Object3D();
    const target = new THREE.Vector3();
    const color = new THREE.Color();
    const positions: THREE.Vector3[] = [];

    for (let i = 0; i < count; i++) {
      positions.push(new THREE.Vector3((Math.random() - 0.5) * 100, (Math.random() - 0.5) * 100, (Math.random() - 0.5) * 100));
      instancedMesh.setColorAt(i, new THREE.Color(0xffffff));
    }

    instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    if (instancedMesh.instanceColor) instancedMesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
    scene.add(instancedMesh);

    const PARAMS = { orbitRad: 60, orbitSpeed: 0.8, diskSize: 90, swirlSpeed: 12, exchange: 0.75 };
    const clock = new THREE.Clock();

    let animationId: number;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      const time = clock.getElapsedTime();
      controls.update();

      for (let i = 0; i < count; i++) {
        const sign = (i % 2) * 2.0 - 1.0;
        const t = time * PARAMS.orbitSpeed;

        const sX = Math.cos(t) * PARAMS.orbitRad * sign;
        const sZ = Math.sin(t) * PARAMS.orbitRad * sign;
        const sY = Math.sin(t * 0.5) * (PARAMS.orbitRad * 0.15) * sign;

        const pT = i / count;
        const localR = 1.5 + Math.pow(pT, 1.4) * PARAMS.diskSize;
        const localSpeed = PARAMS.swirlSpeed / Math.sqrt(localR);
        const localTheta = i * 137.5 + time * localSpeed * sign;

        const x = Math.cos(localTheta) * localR;
        const z = Math.sin(localTheta) * localR;
        const noise = Math.sin(i * 43.21) * Math.cos(i * 12.34);
        const verticalPinch = Math.exp(-localR * 0.03);
        const y = noise * (localR * 0.1) * verticalPinch;

        const bridgeFactor = Math.max(0.0, (localR - PARAMS.diskSize * 0.35) / (PARAMS.diskSize * 0.65));
        const massTransfer = bridgeFactor * PARAMS.exchange * Math.pow(Math.sin(time * 2.0 + i * 0.02), 2.0);
        const finalWeight = 1.0 - massTransfer;

        target.set((sX + x) * finalWeight, (sY + y) * finalWeight, (sZ + z) * finalWeight);

        const hueBase = sign > 0.0 ? 0.6 : 0.05;
        const coreGlow = Math.max(0.0, 1.0 - (localR / (PARAMS.diskSize * 0.2)));
        const bridgeGlow = massTransfer * 0.6;
        const hue = hueBase + coreGlow * 0.1 - bridgeGlow * 0.15 + (time * 0.02);
        const sat = 0.7 + coreGlow * 0.3;
        const lit = 0.02 + coreGlow * 0.85 + bridgeGlow * 1.2;
        color.setHSL(Math.abs(hue) % 1.0, Math.max(0, Math.min(1, sat)), Math.max(0, Math.min(1, lit)));

        positions[i].lerp(target, 0.1);
        dummy.position.copy(positions[i]);
        dummy.updateMatrix();
        instancedMesh.setMatrixAt(i, dummy.matrix);
        instancedMesh.setColorAt(i, color);
      }

      instancedMesh.instanceMatrix.needsUpdate = true;
      if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true;

      composer.render();
    };

    animate();

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      composer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, []);

  return (
    <div ref={mountRef} style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", zIndex: -1, pointerEvents: "none" }} />
  );
}

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
            <h2 style={{ fontSize: "1.8rem", color: "var(--text-primary)" }}>New Scan</h2>
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
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
            {imageFile && (
              <img src={URL.createObjectURL(imageFile)} alt="Scanning" style={{ width: "100%", height: "100%", objectFit: "cover", filter: "blur(4px) brightness(0.2)" }} />
            )}
            <div className="scan-line"></div>
          </div>
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
      {/* Background injection */}
      <ParticleBackground />

      {/* MINIMALIST TOP BRANDING */}
      <div className="top-brand">
        Mediscan
      </div>

      {/* MAIN CONTENT */}
      <main className="main-content" style={{ zIndex: 10, position: "relative" }}>
        {children}
      </main>

      {/* REFERENCE FLOATING DOCK */}
      <nav className="dock-container" style={{ zIndex: 100 }}>
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

// ─── HOME PAGE ─────────────────────────────────────────────────────
function EmptyHome() {
  const navigate = useNavigate();

  const featureSections = [
    {
      img: imgUpload,
      icon: <Camera size={24} />,
      title: "Wound Upload & Detection",
      desc: "Upload a photo of any wound. Our AI will automatically detect the wound bed and prepare it for analysis.",
      direction: "row"
    },
    {
      img: imgCalibrate,
      icon: <Activity size={24} />,
      title: "Real-world Scale Calibration",
      desc: "Simply place a reference coin next to the wound. The system auto-calibrates to provide sub-millimetre measurements for true area tracking.",
      direction: "row-reverse"
    },
    {
      img: imgResults,
      icon: <ShieldAlert size={24} />,
      title: "Deep Clinical Analysis",
      desc: "Instant breakdown of tissue composition (Granulation vs Slough), infection risk, healing velocity, and a tailored AI care plan.",
      direction: "row"
    },
    {
      img: imgTracking,
      icon: <LayoutDashboard size={24} />,
      title: "Longitudinal Tracking",
      desc: "Compare sessions side-by-side. Track area reduction, clinical metrics, and get automatic flags if a wound becomes 'stalled'.",
      direction: "row-reverse"
    }
  ];

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1000, margin: "0 auto", padding: "4rem 1rem 8rem", display: "flex", flexDirection: "column", gap: "6rem" }}>

      {/* Hero */}
      <div style={{ textAlign: "center", paddingTop: "2rem", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ background: "rgba(180,139,108,0.1)", border: "1px solid rgba(180,139,108,0.2)", width: 72, height: 72, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1.5rem" }}>
          <Activity size={32} color="var(--tertiary)" />
        </div>
        <h1 style={{ fontSize: "3.5rem", letterSpacing: "-0.04em", marginBottom: "1rem" }}>
          Mediscan <span style={{ color: "var(--tertiary)" }}>AI</span>
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "1.2rem", maxWidth: 600, margin: "0 auto 2.5rem", lineHeight: 1.6 }}>
          Clinical-grade wound monitoring. Upload a photo — get instant AI analysis, care plans, and a full healing history.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={() => navigate("/scan")} className="btn btn-primary" style={{ padding: "1rem 2.5rem", fontSize: "1.1rem" }}>
            <Camera size={20} /> Start New Scan
          </button>
          <button onClick={() => navigate("/tracking")} className="btn btn-secondary" style={{ padding: "1rem 2.5rem", fontSize: "1.1rem" }}>
            <FileText size={20} /> View History
          </button>
        </div>
      </div>

      {/* Feature Showcase Rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: "5rem" }}>
        {featureSections.map((f, i) => (
          <div key={i} style={{ 
            display: "flex", 
            flexDirection: f.direction as any, 
            alignItems: "center", 
            gap: "4rem",
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.05)",
            borderRadius: 24,
            padding: "2.5rem",
            flexWrap: "wrap"
          }}>
            <div style={{ flex: "1 1 400px", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--tertiary)" }}>
                {f.icon}
              </div>
              <h2 style={{ fontSize: "2rem", fontWeight: 600, letterSpacing: "-0.03em", margin: 0 }}>{f.title}</h2>
              <p style={{ fontSize: "1.1rem", color: "var(--text-muted)", lineHeight: 1.7, margin: 0 }}>{f.desc}</p>
            </div>
            <div style={{ flex: "1 1 500px", borderRadius: 16, overflow: "hidden", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "0 20px 40px rgba(0,0,0,0.4)" }}>
              <img src={f.img} alt={f.title} style={{ width: "100%", height: "auto", display: "block" }} />
            </div>
          </div>
        ))}
      </div>

      {/* Call to action */}
      <div style={{ textAlign: "center", padding: "4rem 2rem", background: "linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%)", borderRadius: 24, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        <h2 style={{ fontSize: "2.2rem", marginBottom: "1rem", letterSpacing: "-0.03em" }}>Ready to track healing?</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: "2rem", fontSize: "1.1rem" }}>Stop guessing. Start measuring with AI precision.</p>
        <button onClick={() => navigate("/scan")} className="btn btn-primary" style={{ padding: "1rem 3rem", fontSize: "1.1rem", borderRadius: 100 }}>
          Launch Mediscan
        </button>
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
