import React, { useRef, useEffect, useState } from "react";

interface Props {
  imageFile: File;
  onClickPoint: (x: number, y: number) => void;
  clickPoint: { x: number; y: number } | null;
}

/**
 * Canvas that renders the uploaded wound image and captures
 * the clinician's click point (wound centre).
 *
 * The click coordinates are in ORIGINAL IMAGE pixel space
 * (scaled back from canvas display size).
 */
export default function ImageClickCanvas({ imageFile, onClickPoint, clickPoint }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [imgEl, setImgEl] = useState<HTMLImageElement | null>(null);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);

  // Load image into an HTMLImageElement
  useEffect(() => {
    const url = URL.createObjectURL(imageFile);
    const img = new Image();
    img.onload = () => {
      setImgEl(img);
      setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
      URL.revokeObjectURL(url);
    };
    img.src = url;
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  // Draw image + click marker on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imgEl || !naturalSize) return;

    const ctx = canvas.getContext("2d")!;
    const displayW = canvas.clientWidth;
    const displayH = Math.round((naturalSize.h / naturalSize.w) * displayW);

    canvas.width  = displayW;
    canvas.height = displayH;

    ctx.drawImage(imgEl, 0, 0, displayW, displayH);

    if (clickPoint) {
      // Scale original coords → canvas display coords
      const scaleX = displayW / naturalSize.w;
      const scaleY = displayH / naturalSize.h;
      const cx = clickPoint.x * scaleX;
      const cy = clickPoint.y * scaleY;

      // Outer ring
      ctx.beginPath();
      ctx.arc(cx, cy, 16, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(20,184,166,0.6)";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Crosshair lines
      ctx.strokeStyle = "#14b8a6";
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(cx - 20, cy); ctx.lineTo(cx + 20, cy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy - 20); ctx.lineTo(cx, cy + 20); ctx.stroke();

      // Centre dot
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#14b8a6";
      ctx.fill();
    }
  }, [imgEl, naturalSize, clickPoint]);

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || !naturalSize) return;
    const rect = canvas.getBoundingClientRect();
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;

    // Convert canvas display coords → original image coords
    const scaleX = naturalSize.w / canvas.width;
    const scaleY = naturalSize.h / canvas.height;
    onClickPoint(Math.round(canvasX * scaleX), Math.round(canvasY * scaleY));
  }

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        style={{
          width: "100%",
          cursor: "crosshair",
          borderRadius: "var(--r-md)",
          display: "block",
          border: clickPoint
            ? "2px solid var(--teal)"
            : "2px dashed var(--border)",
          transition: "border-color 0.2s",
        }}
      />
      {!clickPoint && (
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(0,0,0,0.75)",
            color: "var(--text-secondary)",
            fontSize: "0.78rem",
            padding: "4px 12px",
            borderRadius: 99,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          Click centre of wound
        </div>
      )}
    </div>
  );
}
