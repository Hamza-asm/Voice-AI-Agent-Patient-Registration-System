-- ============================================================================
-- Voice AI Patient Registration System - Database Schema (PostgreSQL / Supabase)
-- ============================================================================

-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- Table: patients
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.patients (
    patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    sex VARCHAR(20) NOT NULL,
    phone_number VARCHAR(10) NOT NULL,
    email TEXT,
    address_line_1 TEXT NOT NULL,
    address_line_2 TEXT,
    city VARCHAR(100) NOT NULL,
    state CHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    insurance_provider TEXT,
    insurance_member_id TEXT,
    preferred_language TEXT NOT NULL DEFAULT 'English',
    emergency_contact_name TEXT,
    emergency_contact_phone VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Field constraints per PRD
    CONSTRAINT chk_first_name CHECK (first_name ~ '^[A-Za-z\-\''\s]{1,50}$'),
    CONSTRAINT chk_last_name CHECK (last_name ~ '^[A-Za-z\-\''\s]{1,50}$'),
    CONSTRAINT chk_sex CHECK (sex IN ('Male', 'Female', 'Other', 'Decline to Answer')),
    CONSTRAINT chk_phone_number CHECK (phone_number ~ '^\d{10}$'),
    CONSTRAINT chk_state CHECK (state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY')),
    CONSTRAINT chk_zip_code CHECK (zip_code ~ '^\d{5}$' OR zip_code ~ '^\d{5}-\d{4}$'),
    CONSTRAINT chk_insurance_member_id CHECK (insurance_member_id IS NULL OR insurance_member_id ~ '^[A-Za-z0-9\-]+$'),
    CONSTRAINT chk_emergency_contact_phone CHECK (emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^\d{10}$'),
    CONSTRAINT chk_date_of_birth CHECK (date_of_birth <= CURRENT_DATE)
);

-- ----------------------------------------------------------------------------
-- Trigger: Automatic updated_at timestamp
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_patients_updated_at ON public.patients;
CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON public.patients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- Indexes
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_patients_phone_number ON public.patients (phone_number) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_patients_last_name ON public.patients (last_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_patients_deleted_at ON public.patients (deleted_at);

-- ----------------------------------------------------------------------------
-- Row-Level Security (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;

-- Backend access via service_role key
DROP POLICY IF EXISTS "service_role_all" ON public.patients;
CREATE POLICY "service_role_all" ON public.patients
    TO service_role
    USING (true)
    WITH CHECK (true);

-- API access via anon / authenticated key
DROP POLICY IF EXISTS "anon_all" ON public.patients;
CREATE POLICY "anon_all" ON public.patients
    TO anon
    USING (true)
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- Seed Data
-- ----------------------------------------------------------------------------
INSERT INTO public.patients (
    first_name, last_name, date_of_birth, sex, phone_number, email,
    address_line_1, city, state, zip_code,
    insurance_provider, insurance_member_id, preferred_language,
    emergency_contact_name, emergency_contact_phone
) VALUES
(
    'Sarah', 'Mitchell', '1985-03-22', 'Female', '2125550134',
    'sarah.mitchell@email.com',
    '42 Maple Street', 'New York', 'NY', '10001',
    'Blue Cross Blue Shield', 'BCBS-7821934', 'English',
    'James Mitchell', '2125550198'
),
(
    'Carlos', 'Rivera', '1972-11-08', 'Male', '3105550267',
    'c.rivera@gmail.com',
    '8901 Sunset Blvd Apt 4B', 'Los Angeles', 'CA', '90028',
    'Aetna', 'AET-45610293', 'Spanish',
    'Maria Rivera', '3105550301'
);

