// API helpers — all calls go through Vite proxy → FastAPI backend

import type { AnalysisResult, CoinOption } from "./types";

const BASE = "/api";

export async function fetchCoins(): Promise<CoinOption[]> {
  const res = await fetch(`${BASE}/coins`);
  if (!res.ok) throw new Error("Failed to load coin options");
  return res.json();
}

export interface AnalyzePayload {
  image: File;
  coinType: string;
  patientId?: string;
  // Click coords now optional — Gemini auto-detects wound
  clickX?: number;
  clickY?: number;
}

export async function analyzeWound(payload: AnalyzePayload): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("image", payload.image);
  form.append("coin_type", payload.coinType);

  if (payload.patientId)
    form.append("patient_id", payload.patientId);
  if (payload.clickX !== undefined)
    form.append("click_x", String(Math.round(payload.clickX)));
  if (payload.clickY !== undefined)
    form.append("click_y", String(Math.round(payload.clickY)));

  const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

export async function fetchHistory(patientId: string, limit = 20) {
  const res = await fetch(`${BASE}/history/${patientId}?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to load history");
  return res.json();
}
