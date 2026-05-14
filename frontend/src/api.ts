// API helpers

import type { AnalysisResult, CoinOption } from "./types";

const BASE = "/api";

export async function fetchCoins(): Promise<CoinOption[]> {
  const res = await fetch(`${BASE}/coins`);
  if (!res.ok) throw new Error("Failed to load coin options");
  return res.json();
}

export interface BoxCoords { x1: number; y1: number; x2: number; y2: number; }

export interface SuggestBoxResponse {
  wound_found: boolean;
  wound_type: string;
  wound_type_confidence: number;
  wound_type_reasoning: string;
  bbox_px: BoxCoords | null;
  photo_quality: { pass: boolean; issues: string[]; advice?: string };
  gemini_ok: boolean;
  fallback_message?: string;
}

export async function suggestBox(image: File): Promise<SuggestBoxResponse> {
  const form = new FormData();
  form.append("image", image);
  const res = await fetch(`${BASE}/suggest-box`, { method: "POST", body: form });
  if (!res.ok) throw new Error("suggest-box failed");
  return res.json();
}

export interface AnalyzePayload {
  image: File;
  coinType: string;
  patientId?: string;
  box: BoxCoords;  // confirmed box in original image pixels — required
  woundType?: string; // from suggest-box, avoids duplicate Gemini call
}

export async function analyzeWound(payload: AnalyzePayload): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("image",     payload.image);
  form.append("coin_type", payload.coinType);
  form.append("box_x1",   String(Math.round(payload.box.x1)));
  form.append("box_y1",   String(Math.round(payload.box.y1)));
  form.append("box_x2",   String(Math.round(payload.box.x2)));
  form.append("box_y2",   String(Math.round(payload.box.y2)));
  if (payload.patientId) form.append("patient_id", payload.patientId);
  if (payload.woundType) form.append("wound_type", payload.woundType);
  if (payload.patientId) form.append("patient_id", payload.patientId);

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
