-- ==========================================
-- WOUNDSCAN SUPABASE DATABASE SCHEMA V2
-- ==========================================

-- 0. Wipe old tables to ensure a clean slate
DROP TABLE IF EXISTS clinical_assessments CASCADE;
DROP TABLE IF EXISTS wound_media CASCADE;
DROP TABLE IF EXISTS wound_sessions CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS clinical_knowledge_base CASCADE;

-- 1. Enable pgvector for RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Patients Table
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT UNIQUE NOT NULL, -- Clerk user ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 3. Wound Sessions Table (Core Metrics)
CREATE TABLE wound_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    session_date TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    session_number INTEGER NOT NULL DEFAULT 1,
    
    wound_type TEXT,
    
    -- Geometry
    area_cm2 NUMERIC,
    perimeter_cm NUMERIC,
    longest_axis_cm NUMERIC,
    shortest_axis_cm NUMERIC,
    gilman_parameter_cm_per_week NUMERIC,
    
    -- Tissue Segmentation
    granulation_pct NUMERIC,
    slough_pct NUMERIC,
    necrotic_pct NUMERIC,
    epithelial_pct NUMERIC,
    dominant_tissue TEXT,
    
    -- Status
    healing_trajectory TEXT
);

-- 4. Clinical Assessments Table (Normalized AI Data)
CREATE TABLE clinical_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES wound_sessions(id) ON DELETE CASCADE UNIQUE,
    
    bwat_total INTEGER,
    bwat_severity TEXT,
    bwat_depth TEXT,
    bwat_edges TEXT,
    
    time_t_tissue TEXT,
    time_i_infection TEXT,
    time_m_moisture TEXT,
    time_e_edge TEXT,
    
    nerds_score INTEGER,
    stones_score INTEGER,
    infection_risk TEXT,
    
    push_score INTEGER,
    est_closure_days INTEGER,
    
    dressing_recommendation TEXT,
    patient_message TEXT,
    clinician_report TEXT
);

-- 5. Wound Media Table (Supabase Storage Links)
CREATE TABLE wound_media (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES wound_sessions(id) ON DELETE CASCADE,
    media_type TEXT, -- 'original', 'tissue_map', 'heatmap'
    storage_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. Knowledge Base for RAG
CREATE TABLE clinical_knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wound_type_tag TEXT NOT NULL,
    guideline_source TEXT NOT NULL, -- e.g., 'IWGDF 2023'
    content TEXT NOT NULL,
    embedding vector(768) -- gemini embedding size
);

-- 7. Set up Row Level Security (RLS) - Allows anonymous inserts for the Hackathon
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE wound_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE wound_media ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public all to patients" ON patients FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all to wound_sessions" ON wound_sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all to clinical_assessments" ON clinical_assessments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all to wound_media" ON wound_media FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all to clinical_knowledge_base" ON clinical_knowledge_base FOR ALL USING (true) WITH CHECK (true);

-- ==========================================
-- 8. Storage Bucket Setup
-- ==========================================
-- Create the public bucket for wound images
INSERT INTO storage.buckets (id, name, public) 
VALUES ('wound-images', 'wound-images', true) 
ON CONFLICT (id) DO NOTHING;

-- Set up storage policies to allow public upload and viewing
CREATE POLICY "Public Access" ON storage.objects FOR SELECT USING ( bucket_id = 'wound-images' );
CREATE POLICY "Public Insert" ON storage.objects FOR INSERT WITH CHECK ( bucket_id = 'wound-images' );

-- ==========================================
-- Done! 
-- ==========================================
