"""The gateway against a stand-in service: what it refuses, what it bounds, what it hides, what it passes through."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI, Request

from terrawindow_gateway import app as gw

DATA = gw.ROOTS[0][0] if gw.ROOTS[0][1] == "<data>" else dict((t, p) for p, t in gw.ROOTS)["<data>"]
SECRET_PATH = DATA + "\\lunar\\site.tif"


def upstream_app(calls: list, slow: float = 0.0) -> FastAPI:
    up = FastAPI()

    @up.get("/v1/datasets")
    def datasets():
        return {"stored_datasets": [{"id": "lola-5mpp-site01"}, {"id": "jezero-mola-megdr128"}]}

    @up.get("/health")
    def health():
        return {"status": "ok"}

    @up.post("/v1/patches/profile")
    async def profile(request: Request):
        body = await request.json()
        calls.append(body)
        if slow:
            await asyncio.sleep(slow)
        return {"provenance": {"sources": [SECRET_PATH], "citation": "https://pds-geosciences.wustl.edu/x"}, "echo": body}

    @up.post("/v1/rehearsal/evaluate")
    async def rehearsal(request: Request):
        calls.append(await request.json())
        await asyncio.sleep(slow)
        return {"ok": True}

    @up.post("/v1/suitability/assess")
    async def assess(request: Request):
        calls.append(await request.json())
        return {"ok": True}

    @up.get("/v1/suitability/metrics")
    def boom():
        raise RuntimeError("Traceback with C:\\Users\\someone\\secret.py")

    @up.get("/docs")
    def docs():
        return {"leak": True}

    return up


@pytest.fixture
def setup(monkeypatch):
    calls: list = []
    state = {"slow": 0.0}

    def build(slow=0.0):
        up = httpx.AsyncClient(transport=httpx.ASGITransport(app=upstream_app(calls, slow), raise_app_exceptions=False), base_url="http://up")
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=gw.create_app(up)), base_url="http://gw")

    return build, calls


def run(coro):
    return asyncio.run(coro)


PROFILE = {"dataset": {"id": "lola-5mpp-site01"}, "scales_m": [40]}


def test_only_the_interface_calls_get_through(setup):
    build, calls = setup

    async def go():
        async with build() as c:
            assert (await c.get("/health")).json() == {"status": "ok"}
            for path in ("/docs", "/openapi.json", "/redoc", "/v1/anything", "/", "/v1/patches/profile/../../docs"):
                assert (await c.get(path)).status_code == 404, path
            assert (await c.delete("/v1/patches/profile")).status_code == 405
            assert (await c.get("/v1/patches/profile")).status_code == 405
            assert (await c.put("/health")).status_code == 405 or (await c.put("/health")).status_code == 404

    run(go())
    assert calls == []


def test_datasets_must_be_known_ids_never_paths_or_urls(setup):
    build, calls = setup

    async def go():
        async with build() as c:
            bad = [
                {"dataset": {"id": "copernicus-glo30"}},
                {"dataset": {"id": "lola-5mpp-site01", "uri": "http://169.254.169.254/latest"}},
                {"dataset": {"uri": "http://example.org/x.tif"}},
                {"dataset": {"path": "C:/Windows/system.ini"}},
                {"dataset": {"id": "lola-5mpp-site01"}, "candidate": {"dataset": {"uris": ["file:///etc/passwd"]}}},
                {"dataset": "lola-5mpp-site01"},
                {"dataset": {"id": "lola-5mpp-site01"}, "kernel_path": "C:/x.bsp"},
            ]
            for payload in bad:
                r = await c.post("/v1/patches/profile", json=payload)
                assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request", payload

    run(go())
    assert calls == []


def test_extents_scales_and_sizes_are_bounded(setup):
    build, calls = setup
    ds = {"id": "jezero-mola-megdr128"}

    async def go():
        async with build() as c:
            bad = [
                {"dataset": ds, "bbox": {"west": 0, "south": 0, "east": 5, "north": 0.5}},
                {"dataset": ds, "bbox": {"west": 0, "south": 0, "east": 500000, "north": 10, "crs": "native"}},
                {"dataset": ds, "scales_m": [0.01]},
                {"dataset": ds, "scales_m": [1e9]},
                {"dataset": ds, "scales_m": list(range(30, 130, 10))},
                {"dataset": ds, "patch_size_m": 1e9},
                {"dataset": ds, "scale_m": float("nan")},
            ]
            for payload in bad:
                assert (await c.post("/v1/patches/profile", content=__import__("json").dumps(payload), headers={"content-type": "application/json"})).status_code == 422, payload
            assert (await c.post("/v1/patches/profile", json={"dataset": ds, "bbox": {"west": 77.4, "south": 18.3, "east": 77.8, "north": 18.6}, "scales_m": [926]})).status_code == 200
            assert (await c.post("/v1/patches/profile", content=b"not json")).status_code == 400
            assert (await c.post("/v1/patches/profile", content=b"[1,2]")).status_code == 422
            assert (await c.post("/v1/patches/profile", content=b"x" * (gw.MAX_BODY + 1))).status_code == 413

    run(go())
    assert len(calls) == 1


def test_filesystem_paths_are_hidden_and_restored_on_the_way_back(setup):
    build, calls = setup

    async def go():
        async with build() as c:
            r = await c.post("/v1/patches/profile", json=PROFILE)
            shown = r.json()["provenance"]
            assert shown["sources"] == ["<data>\\lunar\\site.tif"]
            assert shown["citation"] == "https://pds-geosciences.wustl.edu/x"  # URLs are not paths
            # A client that echoes the token back (as Layer 4 evidence does) reaches the service with the real path.
            r = await c.post("/v1/suitability/assess", json={"dataset": PROFILE["dataset"], "layer4_result": {"provenance": {"terrain_sources": "<data>\\lunar\\site.tif"}}})
            assert r.status_code == 200

    run(go())
    assert calls[-1]["layer4_result"]["provenance"]["terrain_sources"] == SECRET_PATH


def test_upstream_failures_become_one_safe_shape(setup):
    build, _ = setup

    async def go():
        async with build() as c:
            r = await c.get("/v1/suitability/metrics")
            assert r.status_code == 502 and r.json()["error"]["code"] == "upstream_error"
            assert "Traceback" not in r.text and "someone" not in r.text
        dead = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ConnectError("refused C:\\secret"))), base_url="http://up")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gw.create_app(dead)), base_url="http://gw") as c:
            r = await c.post("/v1/patches/profile", json=PROFILE)
            assert r.status_code == 503 and "secret" not in r.text
            r = await c.get("/health")
            assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"

    run(go())


def test_calls_that_run_too_long_are_stopped(setup, monkeypatch):
    build, _ = setup
    monkeypatch.setitem(gw.RULES, ("POST", "/v1/rehearsal/evaluate"), gw.Rule(0.2, heavy=True, exclusive=True))

    async def go():
        async with build(slow=1.0) as c:
            r = await c.post("/v1/rehearsal/evaluate", json=PROFILE)
            assert r.status_code == 504 and r.json()["error"]["code"] == "timeout"

    run(go())


def test_one_rehearsal_at_a_time_and_the_rest_are_told_to_retry(setup, monkeypatch):
    build, _ = setup
    monkeypatch.setattr(gw, "BUSY_WAIT_S", 0.1)

    async def go():
        async with build(slow=0.6) as c:
            first = asyncio.create_task(c.post("/v1/rehearsal/evaluate", json=PROFILE))
            await asyncio.sleep(0.15)
            second = await c.post("/v1/rehearsal/evaluate", json=PROFILE)
            assert second.status_code == 503 and second.headers["retry-after"] and second.json()["error"]["code"] == "busy"
            assert (await first).status_code == 200

    run(go())


def test_rate_limits_apply_per_client_and_say_when_to_return(setup, monkeypatch):
    build, _ = setup
    monkeypatch.setattr(gw, "RATE_PER_MIN", 5)
    monkeypatch.setattr(gw, "HEAVY_PER_MIN", 2)

    async def go():
        async with build() as c:
            codes = [(await c.post("/v1/suitability/assess", json=PROFILE, headers={"cf-connecting-ip": "203.0.113.7"})).status_code for _ in range(3)]
            assert codes == [200, 200, 429]
            limited = await c.post("/v1/suitability/assess", json=PROFILE, headers={"cf-connecting-ip": "203.0.113.7"})
            assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
            # A different client is not affected.
            assert (await c.post("/v1/suitability/assess", json=PROFILE, headers={"cf-connecting-ip": "203.0.113.8"})).status_code == 200

    run(go())


def test_only_the_site_origin_may_call_from_a_browser(setup):
    build, _ = setup

    async def go():
        async with build() as c:
            ok = await c.get("/health", headers={"origin": "https://terrawindow.vercel.app"})
            assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://terrawindow.vercel.app"
            assert (await c.get("/health", headers={"origin": "https://evil.example"})).status_code == 403
            pre = await c.options("/v1/patches/profile", headers={"origin": "https://terrawindow.vercel.app", "access-control-request-method": "POST"})
            assert pre.status_code == 204 and pre.headers["access-control-allow-methods"] == "GET, POST"
            assert (await c.options("/docs", headers={"origin": "https://terrawindow.vercel.app"})).status_code == 403
            assert ok.headers["x-content-type-options"] == "nosniff"

    run(go())
