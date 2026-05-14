// BoxDrawCanvas.tsx
// User draws a rectangle around the wound.
// Gemini's suggested box shown first (dashed teal).
// User can accept, adjust corners, or redraw.

import { useRef, useEffect, useState, useCallback } from "react";
import type { BoxCoords } from "../api";

interface Props {
  imageFile: File;
  suggestedBox: BoxCoords | null;       // in original image pixels
  onBoxConfirmed: (box: BoxCoords) => void;
  onBoxCleared: () => void;
  disabled?: boolean;
}

type Mode = "idle" | "drawing" | "adjusting" | "confirmed";

interface CanvasBox { x1: number; y1: number; x2: number; y2: number; }

const HANDLE_R = 7;  // corner handle radius px

function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }

function nearHandle(mx: number, my: number, b: CanvasBox): number {
  // Returns: 0=none 1=TL 2=TR 3=BL 4=BR 5=inside
  const corners = [
    { x: b.x1, y: b.y1 }, { x: b.x2, y: b.y1 },
    { x: b.x1, y: b.y2 }, { x: b.x2, y: b.y2 },
  ];
  for (let i = 0; i < corners.length; i++) {
    const dx = mx - corners[i].x, dy = my - corners[i].y;
    if (Math.sqrt(dx * dx + dy * dy) <= HANDLE_R + 4) return i + 1;
  }
  if (mx > b.x1 && mx < b.x2 && my > b.y1 && my < b.y2) return 5;
  return 0;
}

export default function BoxDrawCanvas({
  imageFile, suggestedBox, onBoxConfirmed, onBoxCleared, disabled = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef    = useRef<HTMLImageElement | null>(null);
  const [mode, setMode]     = useState<Mode>("idle");
  const [box, setBox]       = useState<CanvasBox | null>(null);
  const [status, setStatus] = useState("Gemini is detecting wound…");

  // Scale factors: canvas → original image
  const scaleRef = useRef({ x: 1, y: 1, iw: 1, ih: 1 });

  const toOrig = (cb: CanvasBox): BoxCoords => {
    const s = scaleRef.current;
    return {
      x1: Math.round(cb.x1 * s.x), y1: Math.round(cb.y1 * s.y),
      x2: Math.round(cb.x2 * s.x), y2: Math.round(cb.y2 * s.y),
    };
  };
  const toCanvas = (ob: BoxCoords): CanvasBox => {
    const s = scaleRef.current;
    return { x1: ob.x1 / s.x, y1: ob.y1 / s.y, x2: ob.x2 / s.x, y2: ob.y2 / s.y };
  };

  // Load image onto canvas
  useEffect(() => {
    const url = URL.createObjectURL(imageFile);
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const maxW = canvas.parentElement?.clientWidth || 640;
      const scale = maxW / img.naturalWidth;
      canvas.width  = Math.round(img.naturalWidth  * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      scaleRef.current = {
        x: img.naturalWidth  / canvas.width,
        y: img.naturalHeight / canvas.height,
        iw: img.naturalWidth,
        ih: img.naturalHeight,
      };
      draw(null, "idle");
    };
    img.src = url;
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  // When Gemini suggestion arrives
  useEffect(() => {
    if (suggestedBox && imgRef.current) {
      const cb = toCanvas(suggestedBox);
      setBox(cb);
      setMode("adjusting");
      setStatus("🤖 AI detected wound — confirm or drag corners to adjust");
      draw(cb, "adjusting");
    } else if (suggestedBox === null && mode === "idle") {
      setStatus("Draw a box around your wound");
    }
  }, [suggestedBox]);

  const draw = useCallback((b: CanvasBox | null, m: Mode) => {
    const canvas = canvasRef.current;
    const img    = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    if (!b) return;

    // Dark overlay outside box
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.clearRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
    ctx.restore();

    // Draw box
    ctx.beginPath();
    ctx.rect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
    if (m === "confirmed") {
      ctx.strokeStyle = "#14b8a6";
      ctx.lineWidth   = 2.5;
      ctx.setLineDash([]);
    } else if (m === "drawing") {
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.lineWidth   = 1.5;
      ctx.setLineDash([6, 3]);
    } else {
      ctx.strokeStyle = "#14b8a6";
      ctx.lineWidth   = 2;
      ctx.setLineDash(m === "adjusting" && !suggestedBox ? [] : [8, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Corner handles
    const corners = [
      { x: b.x1, y: b.y1 }, { x: b.x2, y: b.y1 },
      { x: b.x1, y: b.y2 }, { x: b.x2, y: b.y2 },
    ];
    corners.forEach(({ x, y }) => {
      ctx.beginPath();
      ctx.arc(x, y, HANDLE_R, 0, Math.PI * 2);
      ctx.fillStyle   = m === "confirmed" ? "#14b8a6" : "#fff";
      ctx.strokeStyle = "#14b8a6";
      ctx.lineWidth   = 2;
      ctx.fill();
      ctx.stroke();
    });

    // Dimension label
    const pw = Math.abs(b.x2 - b.x1), ph = Math.abs(b.y2 - b.y1);
    const ow = Math.round(pw * scaleRef.current.x), oh = Math.round(ph * scaleRef.current.y);
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(b.x1, b.y1 - 20, 100, 18);
    ctx.fillStyle    = "#fff";
    ctx.font         = "11px monospace";
    ctx.textBaseline = "middle";
    ctx.fillText(`${ow}×${oh}px`, b.x1 + 4, b.y1 - 11);
  }, [suggestedBox]);

  // Interaction
  const dragRef = useRef<{ mode: string; corner: number; startX: number; startY: number; origBox: CanvasBox } | null>(null);

  function getPos(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const scaleX = canvasRef.current!.width  / rect.width;
    const scaleY = canvasRef.current!.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function onMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    if (disabled || mode === "confirmed") return;
    const { x, y } = getPos(e);
    if (box) {
      const hit = nearHandle(x, y, box);
      if (hit > 0 && hit <= 4) {
        dragRef.current = { mode: "resize", corner: hit, startX: x, startY: y, origBox: { ...box } };
        return;
      }
      if (hit === 5) {
        dragRef.current = { mode: "move", corner: 0, startX: x, startY: y, origBox: { ...box } };
        return;
      }
    }
    // Start fresh draw
    setBox({ x1: x, y1: y, x2: x, y2: y });
    setMode("drawing");
    dragRef.current = { mode: "draw", corner: 0, startX: x, startY: y, origBox: { x1: x, y1: y, x2: x, y2: y } };
  }

  function onMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!dragRef.current) return;
    const { x, y } = getPos(e);
    const canvas = canvasRef.current!;
    const W = canvas.width, H = canvas.height;
    const d = dragRef.current;

    let nb: CanvasBox = { ...box! };

    if (d.mode === "draw") {
      nb = { x1: d.startX, y1: d.startY, x2: clamp(x, 0, W), y2: clamp(y, 0, H) };
    } else if (d.mode === "resize") {
      const ob = d.origBox;
      const cx = clamp(x, 0, W), cy = clamp(y, 0, H);
      if (d.corner === 1) { nb = { ...ob, x1: cx, y1: cy }; }
      if (d.corner === 2) { nb = { ...ob, x2: cx, y1: cy }; }
      if (d.corner === 3) { nb = { ...ob, x1: cx, y2: cy }; }
      if (d.corner === 4) { nb = { ...ob, x2: cx, y2: cy }; }
    } else if (d.mode === "move") {
      const dx = x - d.startX, dy = y - d.startY;
      nb = {
        x1: clamp(d.origBox.x1 + dx, 0, W),
        y1: clamp(d.origBox.y1 + dy, 0, H),
        x2: clamp(d.origBox.x2 + dx, 0, W),
        y2: clamp(d.origBox.y2 + dy, 0, H),
      };
    }

    setBox(nb);
    draw(nb, mode === "confirmed" ? "confirmed" : d.mode === "draw" ? "drawing" : "adjusting");
  }

  function onMouseUp() {
    if (!dragRef.current || !box) return;
    dragRef.current = null;
    const w = Math.abs(box.x2 - box.x1), h = Math.abs(box.y2 - box.y1);
    if (w < 20 || h < 20) {
      setStatus("Box too small — draw a bigger area");
      return;
    }
    // Normalise (ensure x1<x2, y1<y2)
    const nb: CanvasBox = {
      x1: Math.min(box.x1, box.x2), y1: Math.min(box.y1, box.y2),
      x2: Math.max(box.x1, box.x2), y2: Math.max(box.y1, box.y2),
    };
    setBox(nb);
    setMode("adjusting");
    setStatus("Drag corners to adjust, then click Confirm");
    draw(nb, "adjusting");
  }

  function handleConfirm() {
    if (!box) return;
    const nb: CanvasBox = {
      x1: Math.min(box.x1, box.x2), y1: Math.min(box.y1, box.y2),
      x2: Math.max(box.x1, box.x2), y2: Math.max(box.y1, box.y2),
    };
    setMode("confirmed");
    setStatus("✓ Wound region confirmed");
    draw(nb, "confirmed");
    onBoxConfirmed(toOrig(nb));
  }

  function handleRedraw() {
    setBox(null);
    setMode("idle");
    setStatus("Draw a box around your wound");
    onBoxCleared();
    if (imgRef.current) {
      const ctx = canvasRef.current?.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvasRef.current!.width, canvasRef.current!.height);
        ctx.drawImage(imgRef.current, 0, 0, canvasRef.current!.width, canvasRef.current!.height);
      }
    }
  }

  const cursorStyle = disabled ? "default"
    : mode === "confirmed" ? "default"
    : !box ? "crosshair"
    : "move";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {/* Status banner */}
      <div style={{
        padding: "0.45rem 0.75rem",
        borderRadius: "var(--r-sm)",
        background: mode === "confirmed" ? "rgba(20,184,166,0.10)"
          : mode === "idle" ? "rgba(255,255,255,0.04)"
          : "rgba(255,255,255,0.06)",
        border: `1px solid ${mode === "confirmed" ? "rgba(20,184,166,0.4)" : "var(--border)"}`,
        fontSize: "0.82rem",
        color: mode === "confirmed" ? "var(--teal)" : "var(--text-secondary)",
      }}>
        {status}
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        style={{ width: "100%", borderRadius: "var(--r-sm)", cursor: cursorStyle, display: "block" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      />

      {/* Controls */}
      {(mode === "adjusting" || mode === "confirmed") && (
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn btn-ghost" style={{ flex: 1, fontSize: "0.8rem" }} onClick={handleRedraw}>
            ↺ Redraw
          </button>
          {mode !== "confirmed" && (
            <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleConfirm}>
              Confirm wound region ✓
            </button>
          )}
          {mode === "confirmed" && (
            <div style={{ flex: 2, display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--teal)", fontWeight: 600, fontSize: "0.85rem" }}>
              ✓ Region confirmed
            </div>
          )}
        </div>
      )}
      {(mode === "idle" || mode === "drawing") && !box && (
        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0, textAlign: "center" }}>
          Click and drag to draw a box around the wound
        </p>
      )}
    </div>
  );
}
