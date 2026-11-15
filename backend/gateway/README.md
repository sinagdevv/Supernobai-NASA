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
# 1. Scientific API: loopback only, one worker, with the verified resource limits (backend\geoprocessing)
$env:TWGEO_MAX_PATCH_PIXELS=4000000; $env:NUMBA_NUM_THREADS=2
..\.venv\Scripts\python -m uvicorn terrawindow_geo.api.app:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 8 --no-server-header

# 2. Gateway (backend\gateway)
..\.venv\Scripts\python -m uvicorn terrawindow_gateway.app:app --host 127.0.0.1 --port 8787 --workers 1 --no-server-header

# 3. Cloudflare quick tunnel to the gateway
cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate
```

Check `curl http://127.0.0.1:8787/health` and `curl http://127.0.0.1:8787/v1/rehearsal/status` before starting the tunnel. Run the processes in your own terminals: tasks started from an assistant's background shell are stopped after two hours or under memory pressure.

### Resource limits (measured on a 16 GB Windows machine)

| Setting | Why |
|---|---|
| `--workers 1` | One API worker holds about 240 MB resident (peak 317 MB across Moon, Earth and Mars Layer 4 runs, no growth over repeated runs); the gateway about 60 MB; the tunnel about 40 MB |
| `TWGEO_MAX_PATCH_PIXELS=4000000` | Refuses grids over 4 million cells with a clear message. Without it a near-native lunar request (5.5 m, about 8.5 million cells) peaked at 977 MB; with it the worst case is about 470 MB. The interface's own requests, including the full-region Arizona overlay, are unaffected |
| `NUMBA_NUM_THREADS=2` | Bounds Layer 4 worker threads |
| `--limit-concurrency 8` | Bounds simultaneous connections to the API |
| Gateway limits | 120 requests/min and 12 heavy requests/min per client, two heavy calculations at once, one Layer 4 run at a time, per-call timeouts, 2 MB bodies |

The first Layer 4 request after a start may take about 30 seconds while Numba compiles; later requests take seconds.

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
