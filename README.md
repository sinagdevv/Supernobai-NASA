# TERRAWINDOW

Mission-specific Earth analog discovery and rehearsal planning, for the NASA Space Apps Challenge. The working scope is
lunar south-polar rover mobility and navigation under low-angle illumination; Mars is a locked roadmap item.

This is a research prototype. It does not certify any site, produces no single Moon–Earth similarity score, and implies no
NASA endorsement.

## Status by layer

| Layer | What | State | Where |
|---|---|---|---|
| 1 | Foundations and contracts | No separate code in this repository; the API contract in `docs/` and the types in `frontend/src/lib/api/types.ts` are what is shared | – |
| 2 | Data integration: catalog, retrieval, validation, provenance | Done | `backend/data_integration` |
| 3 | Geoprocessing: slope, roughness, relief, profile, compare, screen, overlays; FastAPI service | Done | `backend/geoprocessing`, `docs/layer3-api-contract.md` |
| 4 | Illumination and shadow modelling (rehearsal windows) | Not started | – |
| 5 | Mission-specific criteria and assessment | Not started | – |
| 6+ | Reporting and beyond | Not started | – |
| UI | TERRAWINDOW V4 frontend | Done, integrated | `frontend/` |

## What is live and what is demonstration

The frontend is complete on its own and runs on illustrative fixture data. Only one panel reads the real services:

| Screen | Data |
|---|---|
| Landing, Mission, Analog Explorer, Rehearsal Windows, Dossier | Illustrative demonstration data (Layers 4–5 are not built, so there is nothing real to connect) |
| Comparison, demonstration sections | Illustrative |
| Comparison, **Measured terrain evidence** | **Live**: slope, roughness and relief statistics computed by Layer 3 from DEMs that Layer 2 stored, with citation, pixel size, coverage and limitations. Labelled *Live · Layer 3 service* |

If the service is offline, that panel says so and shows nothing; the rest of the app is unaffected. Service errors are shown with
their code. Demonstration values are never substituted for a missing or failed result. The header chip reads
*Illustrative data* when the service is offline and *Demo data · Layer 3 live* when it is connected.

## Run it

Requirements: Node 20+, Python 3.12+.

```bash
# backend: one virtual environment for Layers 2 and 3
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e "geoprocessing[dev]" -e "data_integration[dev]"   # Windows; use .venv/bin/python elsewhere

# fetch the data the live panel uses (rasters are not versioned; the NASA download takes several minutes)
.venv/Scripts/terrawindow-data fetch lola-5mpp-site01
.venv/Scripts/terrawindow-data region copernicus-glo30 sp-crater -111.72 35.51 -111.54 35.655

# start the service
cd geoprocessing
../.venv/Scripts/python -m uvicorn terrawindow_geo.api.app:app --port 8000

# frontend, in another terminal
cd frontend
npm ci
npm run dev
```

The dev and preview servers proxy `/api` to `http://localhost:8000`. Set `VITE_TERRAWINDOW_API` to point somewhere else.
Set `TERRAWINDOW_DATA_DIR` (for both the `terrawindow-data` commands and the service) to keep the store outside the repository.

### Scripts

| | |
|---|---|
| `npm run dev` / `build` / `preview` / `lint` | in `frontend/` (`build` runs `tsc -b` first) |
| `python -m pytest` | in `backend/geoprocessing` and in `backend/data_integration` (no network) |

## Frontend structure

`frontend/src/lib/api/` is the only boundary to the backend: `types.ts` (contract types), `client.ts` (requests and a single
`ApiError`), `backend.tsx` (connection state). `components/LiveEvidence.tsx` is its one consumer. Everything else in
`frontend/src` is the V4 interface and its fixture data in `src/data` and `src/lib`.

## Limitations

- Rehearsal-window timing uses a simplified flat-horizon solar model in the UI; terrain shadowing is Layer 4.
- Mission criteria on the demonstration screens are screening assumptions, not mission requirements (Layer 5).
- Layer 3's lunar and Earth datasets differ in resolution and in what they measure (Copernicus GLO-30 is a surface model). The panel shows the limitations the service returns beside the numbers.
- Landing-to-workspace uses the View Transitions API where available.
