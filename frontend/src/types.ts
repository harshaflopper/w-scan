// All TypeScript types mirroring backend response shapes

export interface QualityResult {
  pass: boolean;
  issues: string[];
  blur_score: number;
  brightness: number;
  resolution: [number, number];
}

export interface CalibrationInfo {
  px_per_mm: number;
  method: string;
}

export interface Geometry {
  area_cm2: number;
  perimeter_cm: number;
  circularity: number;
  longest_axis_cm: number;
  shortest_axis_cm: number;
  aspect_ratio: number;
  gilman_parameter_cm_per_week?: number | null;
}

export interface TissueBreakdown {
  granulation_pct: number;
  slough_pct: number;
  necrotic_pct: number;
  epithelial_pct: number;
  dominant_tissue: string;
  total_wound_px: number;
  tissue_source: "cv_model" | "blended_cv_gemini" | "gemini";
  gemini_agreement: number;
}

export interface InflammationResult {
  inflammation_index: number;
  erythema_mean: number;
  periwound_px_count: number;
  warning: string | null;
}

export interface BWATItem {
  score: number;
  finding: string;
  type?: string;
  edge_type?: string;
  tissue_type?: string;
  level?: string;
  quality?: string;
  pct_estimate?: number;
  present?: boolean;
}

export interface BWATResult {
  bwat: {
    depth: BWATItem;
    edges: BWATItem;
    undermining: BWATItem;
    necrotic_type: BWATItem;
    necrotic_amount: BWATItem;
    exudate_type: BWATItem;
    exudate_amount: BWATItem;
    skin_color: BWATItem;
    edema: BWATItem;
    induration: BWATItem;
    granulation: BWATItem;
    epithelialization: BWATItem;
  };
  bwat_total: number;
  bwat_severity: "healing" | "mild" | "moderate" | "severe";
  bwat_interpretation: string;
  TIME: { T: string; I: string; M: string; E: string };
  healing_phase: string;
  depth_classification: string;
  moisture_balance: string;
  infection_signs_visual: string[];
  biofilm_suspected: boolean;
  overall_concern: "low" | "moderate" | "high" | "urgent";
}

export interface NERDSResult {
  score: number;
  criteria_met: string[];
  interpretation: string;
}

export interface PrimaryScore {
  name: string;
  value: number;
  max: number;
  trend: string;
  interpretation: string;
}

export interface CarePlan {
  dressing_type: string;
  dressing_change_frequency: string;
  debridement_needed: boolean;
  debridement_type: string;
  compression_needed: boolean;
  offloading_needed: boolean;
  antimicrobial_needed: boolean;
  review_frequency_days: number;
  specific_actions: string[];
  care_video_youtube_id?: string;
  product_name?: string;
  product_search_query?: string;
}

export interface FortyPercentRule {
  applicable: boolean;
  weeks_elapsed: number | null;
  current_reduction_pct: number | null;
  target_pct: number;
  status: "ON_TRACK" | "BELOW_TARGET" | "ACHIEVED" | null;
  action: string | null;
}

export interface ClinicalAssessment {
  wound_type_confirmed: string;
  wound_staging?: { system: string; stage: string; description: string };
  healing_phase?: string;
  bwat_total?: number;
  bwat_trajectory?: string;
  primary_score?: PrimaryScore;
  TIME?: { T: string; I: string; M: string; E: string };
  nerds?: NERDSResult;
  stones?: NERDSResult;
  infection_risk?: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  healing_trajectory?: string;
  healing_velocity_cm2_per_day?: number;
  gilman_velocity_cm_per_week?: number | null;
  area_reduction_pct?: number | null;
  forty_percent_rule?: FortyPercentRule;
  estimated_closure_days?: number | null;
  closure_confidence?: string;
  care_plan?: CarePlan;
  red_flags?: string[];
  alerts?: string[];
  clinician_report?: string;
  patient_message?: string;
  guideline_references?: string[];
  assessment_confidence?: "high" | "moderate" | "low";
  confidence_note?: string;
  error?: string;
}

export interface Alert {
  type: "red_flag" | "infection" | "non_healing" | "deteriorating" | "milestone";
  severity: "urgent" | "warning" | "info";
  message: string;
  action?: string;
}

export interface TrendData {
  area_cm2: number[];
  bwat_total: number[];
  granulation_pct: number[];
  slough_pct: number[];
  necrotic_pct: number[];
  epithelial_pct: number[];
  inflammation: number[];
  session_dates: string[];
  session_numbers: number[];
}

export interface AnalysisResult {
  status: "success" | "quality_failed" | "calibration_failed" | "segmentation_failed" | "wound_not_found";
  session_id?: string;
  session_number?: number;
  patient_id?: string;
  issues?: string[];
  detail?: string;
  tip?: string;
  gemini_advice?: string;
  localization?: {
    wound_type: string;
    wound_type_confidence: number;
    wound_type_reasoning: string;
    auto_detected: boolean;
  };
  calibration?: CalibrationInfo;
  quality?: QualityResult;
  geometry?: Geometry;
  tissue?: TissueBreakdown;
  inflammation?: InflammationResult;
  bwat?: BWATResult;
  clinical_assessment?: ClinicalAssessment;
  scores?: {
    composite_score: number;
    healing_trajectory: string;
    infection_risk: string;
    primary_score?: PrimaryScore;
    nerds?: NERDSResult;
    stones?: NERDSResult;
    estimated_closure_days: number | null;
    forty_percent_rule?: FortyPercentRule;
  };
  care_plan?: CarePlan;
  red_flags?: string[];
  alerts?: Alert[];
  patient_message?: string;
  clinician_report?: string;
  images?: { annotated_b64: string; heatmap_b64: string };
  trend?: TrendData;
}

export interface CoinOption {
  key: string;
  label: string;
}

// Session data point for local chart history
export interface SessionDataPoint {
  date: string;
  area_cm2: number;
  composite_score: number;
  bwat_total?: number;
  push_score?: number;
  granulation_pct?: number;
  slough_pct?: number;
  necrotic_pct?: number;
}
