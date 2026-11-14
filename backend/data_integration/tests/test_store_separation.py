"""Setting up data must not dirty a checkout, and must not overwrite the version-controlled record.

The store is a real git repository here: reference manifest and provenance committed, rasters and local/ ignored, exactly as
in the project. The assertions are on `git status`, which is what a teammate sees.
"""

import json
import subprocess

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from terrawindow_data import fetch, prepare, store
from terrawindow_data.cli import main as cli

# Fixtures shared with the main Layer 2 tests (pytest picks up imported fixtures).
from test_data_integration import MOON, earth_tiles, fake_download, isolated_store, lunar_file, write  # noqa: F401

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]


def git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True, text=True, check=True).stdout


def dirty(root) -> str:
    return git(root, "status", "--porcelain").strip()


@pytest.fixture
def checkout(isolated_store, fake_download):
    """A clean checkout: reference record of lola-5mpp-site01 committed, its raster absent (rasters are not versioned)."""
    root = isolated_store
    fetch.fetch_dataset("lola-5mpp-site01", reference=True)
    (root / ".gitignore").write_text("*.tif\n*.part\nlocal/\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "reference data")
    for tif in root.rglob("*.tif"):
        tif.unlink()
    assert not (root / "local").exists()  # the reference run wrote nothing local
    assert dirty(root) == ""
    return root


def test_normal_setup_of_a_tracked_dataset_leaves_the_tree_clean(checkout):
    ref_manifest = (checkout / "manifest.json").read_text()
    record = fetch.fetch_dataset("lola-5mpp-site01")
    assert (checkout / record["path"]).is_file() and record["ready"]
    assert dirty(checkout) == ""  # the symptom: this used to modify manifest.json and the provenance sidecar
    assert (checkout / "manifest.json").read_text() == ref_manifest
    assert (checkout / "local" / "manifest.json").is_file()
    assert store.read_provenance(record["path"])["retrieved_at"]


def test_the_same_data_is_reported_as_matching_the_reference(checkout):
    record = fetch.fetch_dataset("lola-5mpp-site01")
    assert record["reference_check"] == {"status": "matches"}


def test_a_new_dataset_is_usable_without_touching_tracked_files(checkout, fake_download):
    fetch.fetch_dataset("lola-5mpp-site04")
    assert dirty(checkout) == ""
    merged = store.load_manifest()["datasets"]
    assert {"lola-5mpp-site04"} <= set(merged) and "lola-5mpp-site01" in merged  # reference and local entries together
    assert "lola-5mpp-site04" not in store.load_reference_manifest()["datasets"]
    assert fetch.compare_to_reference({"sha256": "x"}, None) == {"status": "no_reference"}


def test_a_region_setup_leaves_the_tree_clean(checkout, earth_tiles):
    record = prepare.prepare_region("copernicus-glo30", "test-site", 10.05, 50.02, 10.15, 50.08, sources=list(earth_tiles))
    assert (checkout / record["path"]).is_file() and dirty(checkout) == ""
    assert record["reference_check"]["status"] == "no_reference"
    assert "test-site-copernicus-glo30" in store.load_manifest()["datasets"]


def test_different_bytes_are_flagged_and_never_overwrite_the_reference(checkout, monkeypatch, tmp_path, capsys):
    other = write(tmp_path / "other.tif", np.random.default_rng(1).normal(900, 80, (200, 200)), Affine(5, 0, -19000, 0, -5, -4000), MOON, nodata=np.nan)

    def copy(url, dest, *, progress=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(open(other, "rb").read())

    monkeypatch.setattr(fetch, "download", copy)
    reference_sidecar = (checkout / "lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif.provenance.json")
    before = reference_sidecar.read_text()
    assert cli(["fetch", "lola-5mpp-site01"]) == 0
    out = capsys.readouterr().out
    assert "differs from the reference provenance" in out and "sha256" in out and "left untouched" in out
    assert dirty(checkout) == "" and reference_sidecar.read_text() == before  # meaningful tracked metadata is preserved
    check = store.read_provenance("lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif")["reference_check"]
    assert check["status"] == "differs" and "sha256" in check["fields"]
    assert check["reference_sha256"] == json.loads(before)["sha256"]


def test_update_reference_is_the_deliberate_way_to_change_tracked_files(checkout):
    assert cli(["fetch", "lola-5mpp-site01", "--update-reference"]) == 0
    changed = dirty(checkout)
    assert "manifest.json" in changed and "provenance.json" in changed  # on purpose, and visible in git
    assert not (checkout / "local").exists()


def test_an_external_store_works_with_no_reference_at_all(tmp_path, monkeypatch, fake_download):
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("TERRAWINDOW_DATA_DIR", str(elsewhere))
    record = fetch.fetch_dataset("lola-5mpp-site01")
    assert (elsewhere / record["path"]).is_file()
    assert not (elsewhere / "manifest.json").exists()  # nothing version-controlled is invented
    assert "lola-5mpp-site01" in store.load_manifest()["datasets"]


def test_a_local_entry_replaces_the_reference_entry_of_the_same_id(checkout):
    store.register("lola-5mpp-site01", {"path": "somewhere/else.tif", "body": "moon"})
    assert store.load_manifest()["datasets"]["lola-5mpp-site01"]["path"] == "somewhere/else.tif"
    assert store.load_reference_manifest()["datasets"]["lola-5mpp-site01"]["path"].startswith("lunar/")
    assert dirty(checkout) == ""


def test_a_raster_with_only_a_reference_record_is_reused_not_downloaded_again(checkout, fake_download, lunar_file):
    import shutil

    target = checkout / "lunar/lola-5mpp-site01/Site01_final_adj_5mpp_surf.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(lunar_file, target)  # as if copied in by hand after a fresh checkout
    calls_before = len(fake_download)
    fetch.fetch_dataset("lola-5mpp-site01")
    assert len(fake_download) == calls_before and dirty(checkout) == ""


def test_list_does_not_call_a_missing_file_in_store(checkout, capsys):
    assert cli(["list"]) == 0
    assert "listed, file missing" in capsys.readouterr().out
    fetch.fetch_dataset("lola-5mpp-site01")
    capsys.readouterr()
    assert cli(["list"]) == 0 and "in store" in capsys.readouterr().out
