# TERRAWINDOW demonstration gateway

A small restricted front door for the scientific API (`backend/geoprocessing`). It exists so a temporary public tunnel
can point at something that is safe to expose. It computes nothing and changes no result.

**Temporary demonstration use only.** A quick tunnel's address changes every time it starts, the process runs on one
machine, and nothing here is a production deployment.

## What it does

| Concern | Behaviour |
|---|---|
| Reachable calls | Only the ten the interface makes: `GET /health`, `/v1/datasets`, `/v1/rehearsal/status`, `/v1/suitability/metrics`; `POST /v1/patches/profile`, `/v1/patches/compare`, `/v1/patches/overlay`, `/v1/discovery/screen`, `/v1/suitability/assess`, `/v1/rehearsal/evaluate`. Everything else (including `/docs`, `/openapi.json`) is 404; other methods 405 |
| Data sources | A dataset is `{"id": ...}` and must be a stored dataset. Paths, URLs, `uri`/`uris`/`path` keys and the built-in remote datasets (open-ended downloads) are refused |
| Bounds | Geographic boxes up to 1 degree, native boxes up to 200 km, scales 1 m to 10 km (at most 8), patch size 100 m to 20 km, body 2 MB. Layer 4 itself limits samples (96), span (30 days) and patch cells (200,000) |
| Limits | Per client: 120 requests/min, 12 heavy requests/min (429 with `Retry-After`). At most two heavy calculations at once and one Layer 4 run at a time (503 `busy`). Per-call time limits (Layer 4: 170 s) |
| Errors | One shape `{"error": {"code", "message", "details"}}`. Upstream failures never carry a traceback or a path |
| Paths | The service reports file locations on this machine. The gateway replaces them with `<data>`, `<kernels>`, `<repo>` tokens and restores the same tokens in requests, so Layer 5 can still pair Layer 4 evidence with a Layer 3 candidate |
| Browsers | Only origins in `GATEWAY_ALLOWED_ORIGINS` (default: the Vercel site and local dev) are answered. CORS is a convenience; the controls above are the protection |

Not provided: authentication (there is nothing secret in the frontend and no key to protect), persistence, or any write
operation. The scientific service has none either.

## Run the demonstration

Three terminals (Windows paths shown; `backend/.venv` is the environment from the main README, with `terrawindow-gateway`
and the Layer 4 package installed: `pip install -e gateway -e ../solar_geometry_engine`, plus `spiceypy numba`).

```powershell
# 1. Scientific API, bound to loopback only (backend\geoprocessing)
..\.venv\Scripts\python -m uvicorn terrawindow_geo.api.app:app --host 127.0.0.1 --port 8000

# 2. Gateway (backend\gateway)
..\.venv\Scripts\python -m uvicorn terrawindow_gateway.app:app --host 127.0.0.1 --port 8787 --no-server-header

# 3. Cloudflare quick tunnel to the gateway
cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate
```

`cloudflared` prints `https://<words>.trycloudflare.com`. Set that address as the `VITE_TERRAWINDOW_API` environment
variable of the Vercel project and redeploy (Vite reads it at build time). It is a public address, not a secret, and
is not committed.

## Stop and recover

- **Stop:** end the three processes (Ctrl+C in each). The public site then shows its honest "service unavailable" state.
- **Tunnel dropped or restarted:** a new quick tunnel has a new address. Restart `cloudflared`, update
  `VITE_TERRAWINDOW_API` and redeploy. Nothing keeps the old address alive; this is by design.
- **Gateway or API crashed:** restart it; no state is lost (results are recomputed or read from the on-disk cache).
- **Layer 4 first call is slow** (about 30 s) while numba compiles; later calls take seconds.

## Tests

```powershell
..\.venv\Scripts\python -m pytest      # in backend\gateway
```
