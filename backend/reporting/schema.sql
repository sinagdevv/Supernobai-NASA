-- Layer 6 persistence. Rasters stay GeoTIFF files on disk.
-- Apply with: terrawindow-report init
-- Safe to run again.

SET search_path TO terrawindow, public, extensions;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS terrawindow;

CREATE TABLE IF NOT EXISTS terrawindow.datasets (
    id text PRIMARY KEY,
    name text,
    body text,
    kind text,
    product text,
    citation text,
    license text,
    source_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
    file_path text,
    bytes bigint,
    sha256 text,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    validation jsonb,
    native_bounds jsonb,
    center geography(Point, 4326),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS terrawindow.analysis_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('profile', 'compare', 'screen')),
    request jsonb NOT NULL,
    request_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS terrawindow.runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id uuid NOT NULL REFERENCES terrawindow.analysis_configs (id),
    engine_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    failure_message text,
    result jsonb,
    result_hash text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS runs_config_idx ON terrawindow.runs (config_id);
CREATE INDEX IF NOT EXISTS runs_completed_idx ON terrawindow.runs (config_id, engine_version) WHERE status = 'completed';

CREATE TABLE IF NOT EXISTS terrawindow.run_datasets (
    run_id uuid NOT NULL REFERENCES terrawindow.runs (id),
    dataset_id text NOT NULL REFERENCES terrawindow.datasets (id),
    role text NOT NULL CHECK (role IN ('reference', 'candidate', 'input')),
    sha256 text NOT NULL,
    PRIMARY KEY (run_id, role)
);

CREATE INDEX IF NOT EXISTS run_datasets_dataset_idx ON terrawindow.run_datasets (dataset_id);

CREATE TABLE IF NOT EXISTS terrawindow.candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES terrawindow.runs (id),
    patch_id text NOT NULL,
    status text NOT NULL,
    geom geometry(Polygon, 4326),
    center geography(Point, 4326),
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    criteria jsonb NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (run_id, patch_id)
);

CREATE INDEX IF NOT EXISTS candidates_run_idx ON terrawindow.candidates (run_id);
CREATE INDEX IF NOT EXISTS candidates_geom_idx ON terrawindow.candidates USING gist (geom);

CREATE TABLE IF NOT EXISTS terrawindow.reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES terrawindow.runs (id),
    title text NOT NULL,
    template_version text NOT NULL,
    generated_at timestamptz NOT NULL,
    markdown text NOT NULL,
    pdf bytea NOT NULL,
    pdf_sha256 text NOT NULL
);

CREATE INDEX IF NOT EXISTS reports_run_idx ON terrawindow.reports (run_id);

ALTER TABLE terrawindow.datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrawindow.analysis_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrawindow.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrawindow.run_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrawindow.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrawindow.reports ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON SCHEMA terrawindow FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA terrawindow FROM PUBLIC;
