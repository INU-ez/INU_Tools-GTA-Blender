"""Build the addon as a Blender extension and assert the produced zip
is clean and valid.

This test needs a Blender executable. It auto-skips when one isn't
findable so the rest of the pure-Python test suite stays runnable on
machines without Blender.

There is a SINGLE build — the same .zip is uploaded to
extensions.blender.org and attached to the GitHub release. (The old
"full" split was dropped when the external-binary compression path was
removed; the addon now compresses DXT purely in-process via core.dxt.)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest


# ── Paths ────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
ADDON_DIR = REPO_ROOT / "INU_tools"


# ── Blender discovery ────────────────────────────────────────────

def _find_blender() -> str | None:
    """Locate a blender executable. Mirrors `dev/tests/run_e2e.ps1`
    candidates, plus the `BLENDER` env var, plus PATH lookup."""
    if env := os.environ.get("BLENDER"):
        if Path(env).is_file():
            return env

    candidates = [
        r"D:\Program\Steam\steamapps\common\Blender\blender.exe",
        r"D:\blender-4.2.23-windows-x64\blender.exe",
        r"D:\Program\Blender 5.1\blender.exe",
        r"D:\Program\blender-4.2.20-windows-x64\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c

    if path_blender := shutil.which("blender"):
        return path_blender
    return None


@pytest.fixture(scope="module")
def blender() -> str:
    exe = _find_blender()
    if not exe:
        pytest.skip("Blender executable not found; set BLENDER env var to run packaging tests")
    return exe


# ── Build runner ─────────────────────────────────────────────────

def _run(argv: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(argv, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout, p.stderr


def _build_zip(blender: str, source_dir: Path, output_dir: Path) -> Path:
    """Invoke Blender's `extension build` command. Returns the produced
    zip path. Asserts on non-zero exit and on missing artefact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run([
        blender, "--command", "extension", "build",
        "--source-dir", str(source_dir),
        "--output-dir", str(output_dir),
    ])
    assert rc == 0, (
        f"`extension build` failed (rc={rc})\n"
        f"stdout:\n{out}\nstderr:\n{err}"
    )
    zips = sorted(output_dir.glob("*.zip"))
    assert zips, f"no zip produced in {output_dir}; build output:\n{out}"
    # extension build emits exactly one zip per invocation; if more,
    # something stale is in the dir and our assertion needs updating.
    assert len(zips) == 1, f"expected exactly one zip, got: {[z.name for z in zips]}"
    return zips[0]


def _validate_zip(blender: str, zip_path: Path) -> None:
    """Run Blender's official extension validator on the produced zip.
    A non-zero exit here is what extensions.blender.org would also
    reject — fix locally before submission."""
    rc, out, err = _run([
        blender, "--command", "extension", "validate", str(zip_path),
    ])
    assert rc == 0, (
        f"`extension validate` rejected {zip_path.name} (rc={rc})\n"
        f"stdout:\n{out}\nstderr:\n{err}"
    )


# ── Tests ────────────────────────────────────────────────────────

def test_build_succeeds(tmp_path, blender):
    """The extension zip builds and `extension validate` accepts it."""
    zip_path = _build_zip(blender, ADDON_DIR, tmp_path)
    _validate_zip(blender, zip_path)


def test_build_no_pycache(tmp_path, blender):
    """`__pycache__/` is excluded by manifest, but verify — a stale
    .pyc snuck in once before."""
    zip_path = _build_zip(blender, ADDON_DIR, tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        offenders = [
            n for n in zf.namelist()
            if "__pycache__" in n or n.endswith(".pyc")
        ]
    assert not offenders, f"bytecode leaked into zip: {offenders}"


def test_zip_contains_manifest(tmp_path, blender):
    """The produced zip must have blender_manifest.toml at its
    addon-root path. If it's missing, the addon won't register."""
    zip_path = _build_zip(blender, ADDON_DIR, tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    manifests = [n for n in names if n.endswith("blender_manifest.toml")]
    assert manifests, f"zip missing blender_manifest.toml: {names[:20]}"
