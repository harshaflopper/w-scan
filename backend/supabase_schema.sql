-- ==========================================
-- WOUNDSCAN SUPABASE DATABASE SCHEMA
-- ==========================================
-- Copy and paste this entirely into the Supabase SQL Editor and hit "Run".

-- 1. Enable pgvector for RAG / Similarity Search (Optional for future)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Patients Table
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 3. Wound Sessions Table (Longitudinal Tracking)
CREATE TABLE IF NOT EXISTS wound_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    session_date TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    session_number INTEGER NOT NULL DEFAULT 1,
    
    -- Clinical Classification
    wound_type TEXT,
    
    -- Geometry & Math
    area_cm2 NUMERIC,
    perimeter_cm NUMERIC,
    longest_axis_cm NUMERIC,
    shortest_axis_cm NUMERIC,
    gilman_parameter_cm_per_week NUMERIC, -- The Scientific Velocity Parameter
    
    -- AI Tissue Segmentation
    granulation_pct NUMERIC,
    slough_pct NUMERIC,
    necrotic_pct NUMERIC,
    epithelial_pct NUMERIC,
    dominant_tissue TEXT,
    
    -- Clinical Scores (BWAT)
    bwat_total INTEGER,
    bwat_severity TEXT,
    push_score INTEGER,
    
    -- Outcomes & Guidance
    healing_trajectory TEXT,
    patient_message TEXT,
    dressing_recommendation TEXT,
    
    -- We can store the full raw JSON of the Gemini analysis if needed
    raw_analysis_json JSONB
);

-- 4. Set up Row Level Security (RLS) - Allows anonymous inserts for the Hackathon
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE wound_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public inserts to patients" ON patients FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public reads to patients" ON patients FOR SELECT USING (true);

CREATE POLICY "Allow public inserts to wound_sessions" ON wound_sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public reads to wound_sessions" ON wound_sessions FOR SELECT USING (true);

-- ==========================================
-- Done! 
-- Your backend is now fully connected to Supabase.
-- ==========================================
