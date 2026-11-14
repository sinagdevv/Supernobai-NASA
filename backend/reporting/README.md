"""Layer 6 records research runs and writes dossiers from them.

The React application, Layer 2 registration, and the Layer 3 processing cache are unchanged.
GeoTIFF files stay on disk. This service stores their metadata, the analysis that used them, and the dossier produced from that stored run.

## Database

Use the direct Postgres URL for the MANTIKA Supabase project (port 5432), not the transaction pooler. Put it in an untracked environment variable:

```
TERRAWINDOW_DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres
```

Tables are created in schema `terrawindow`. Row Level Security is enabled and no API role is granted access. This process connects as the database owner.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e "reporting[dev]"
.venv/Scripts/terrawindow-report init
.venv/Scripts/terrawindow-report ingest-store
.venv/Scripts/terrawindow-report ingest-result data/results/compare_lola-5mpp-site01_vs_sp-crater.json
.venv/Scripts/terrawindow-report report RUN_ID --pdf dossier.pdf
.venv/Scripts/terrawindow-report verify RUN_ID
```

On macOS and Linux, use `.venv/bin/` in place of `.venv/Scripts/`.

`ingest-store` copies the merged Layer 2 manifest and provenance. It does not modify those files. `ingest-result` reads a profile, comparison, or screen document that Layer 3 already wrote. A second ingest of the same request, engine version, and dataset checksums returns the completed run instead of inserting another. Runs that do not finish are stored as `failed`. Only a `completed` run can be turned into a dossier.

The HTTP service listens on `127.0.0.1:8001` (`terrawindow-report serve`). It has no caller authentication.

## What a dossier contains

Template version, generation time, engine version, request hash, result hash, the dataset checksum recorded for that run, the stored criteria or candidate shortlist, and the PDF checksum. Generating a dossier again inserts a new report row.

## Tests

```bash
.venv/Scripts/python -m pytest
```

Tests that talk to Postgres are marked `postgres` and run only when `TERRAWINDOW_DATABASE_URL` is set.
