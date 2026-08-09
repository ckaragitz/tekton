"""test_frontdoor_wallsolid.py -- FRONT-DOOR CREATED WALLS CARRY AUTHORED
seq-103 SOLIDS (issue #144), on the 2026 / 2025 / 2024 pinned bases.

Fresh-clone runnable: the only inputs are the bundled pinned genesis bases
(``plugin/assets/genesis/G_ABPD*.rvt``) and the engine.  What is asserted:

* ``author --prompt "an electrical room 30 by 20 ft" --stages WV`` on each
  release writes 4 SWalls whose seq-103 record is a ``GElement`` (not the
  ``SerializedDummy``) that ``rvt.render.inspect`` classifies ``brep`` /
  ``drawable_3d`` (1 solid, 6 faces, 12 edges), whose bBox is the wall's
  location line +- half the type thickness x 12 ft;
* the validator gate is VALID / 0 errors and the self-checks pass on all
  three; the manifest's ``honesty.load_vs_render`` says the walls carry
  authored solids AND that this exact output is uncertified (no render claim);
* the tags come from the wall's own history (the W1_gabpd_wall_solid recipe);
* ``RVT_WALL_REP=dummy`` is the opt-out: SerializedDummy reps, the
  historical honesty wording, and ``BuildOptions.wall_rep`` follows the env;
* the solid build is deterministic (two builds, identical bytes).

Certification is NOT asserted here (hard rule 4): the viewer round for this
output shape is a STAGED probe batch, recorded in
docs/inbox/wall-solids-frontdoor.md.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import rvt.frontdoor as FD                                   # noqa: E402
from rvt.frontdoor import build as B                        # noqa: E402
from rvt.frontdoor import manifest as MF                    # noqa: E402
from rvt.frontdoor.base import sha256_of                    # noqa: E402
from rvt.render.inspect import inspect                      # noqa: E402

ASSETS = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(ASSETS, "G_ABPD.rvt"),
         2025: os.path.join(ASSETS, "G_ABPD_2025.rvt"),
         2024: os.path.join(ASSETS, "G_ABPD_2024.rvt")}
PROMPT = "an electrical room 30 by 20 ft"
WALL_HEIGHT_FT = 12.0
EPS = 1e-3

pytestmark = pytest.mark.skipif(
    not os.path.isfile(BASES[2026]),
    reason="bundled pinned genesis base (plugin/assets/genesis/G_ABPD.rvt) absent")


def _build(out_dir: str, release: int, monkeypatch, wall_rep: str = None,
           stages: str = "WV"):
    """One walls-only front-door build; returns (AuthorResult, rvt path, stage-W record)."""
    if wall_rep is None:
        monkeypatch.delenv(B.WALL_REP_ENV, raising=False)
    else:
        monkeypatch.setenv(B.WALL_REP_ENV, wall_rep)
    res = FD.author(prompt=PROMPT, out=out_dir, stages=stages, no_handoff=True,
                    target_version=release)
    assert not res.errors, res.errors
    path = res.files.get("combined")
    assert path and os.path.isfile(path), res.files
    stages_ = (res.manifest.get("build") or {}).get("stages") or []
    wrec = [s for s in stages_ if s.get("stage") == "W"]
    assert wrec and wrec[0]["ok"], stages_
    return res, path, wrec[0]


def _expected_bbox(wall: dict) -> list:
    """Location line +- half thickness (axis-aligned walls) x [0, 12] ft."""
    (x0, y0), (x1, y1) = wall["p0_ft"], wall["p1_ft"]
    half = wall["rep"]["thickness_ft"] / 2.0
    pad_x = half if abs(x0 - x1) < EPS else 0.0
    pad_y = half if abs(y0 - y1) < EPS else 0.0
    return [[min(x0, x1) - pad_x, min(y0, y1) - pad_y, 0.0],
            [max(x0, x1) + pad_x, max(y0, y1) + pad_y, WALL_HEIGHT_FT]]


def _close(a, b) -> bool:
    return all(abs(a[i][j] - b[i][j]) < EPS for i in range(2) for j in range(3))


@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_created_walls_carry_authored_solids(tmp_path, monkeypatch, release):
    if not os.path.isfile(BASES[release]):
        pytest.skip(f"bundled pinned base for {release} absent")
    res, path, wrec = _build(str(tmp_path / f"ws{release}"), release, monkeypatch)
    assert (res.manifest.get("target_version") or {}).get("output_release") == release

    # stage W wrote the solid rep for every wall, tagged from the wall's own history
    assert wrec["wall_rep"] == "solid"
    walls = wrec["walls"]
    assert len(walls) == 4
    for w in walls:
        assert w["rep"]["tags"] == "history"
        assert w["rep"]["thickness_ft"] > 0.1

    # read-back through the archaeology inspector (opens the file under its own release)
    rows = {r.element_id: r for r in inspect(path, classes=["SWall"])}
    assert set(rows) == {w["elem_id"] for w in walls}
    for w in walls:
        r = rows[w["elem_id"]]
        assert r.rep_class == "GElement", r.rep_class
        assert r.kind == "brep" and r.drawable_3d and r.has_baked_geometry
        assert (r.n_solids, r.n_faces, r.n_edges) == (1, 6, 12)
        assert _close(r.bbox, _expected_bbox(w)), (r.bbox, _expected_bbox(w))

    # the gates: validator 0 errors under the file's own release + self-checks
    gates = (res.manifest["build"].get("validation") or {}).get("combined") or {}
    assert gates.get("self_checks_ok") is True, gates
    assert gates["validate"]["n_errors"] == 0

    # honesty: solids stated, certification NOT claimed for this output
    lvr = res.manifest["honesty"]["tiers"]["load_vs_render"]
    assert "authored solids" in lvr and "uncertified" in lvr
    assert all(c.get("rep") == "solid" for c in res.manifest["build"]["elements_created"]
               if c.get("kind") == "wall")


def test_dummy_opt_out_and_determinism(tmp_path, monkeypatch):
    # env -> BuildOptions default
    monkeypatch.setenv(B.WALL_REP_ENV, "dummy")
    assert B.default_wall_rep() == "dummy"
    monkeypatch.setenv(B.WALL_REP_ENV, "nonsense")
    assert B.default_wall_rep() == "solid"
    monkeypatch.delenv(B.WALL_REP_ENV, raising=False)
    assert B.default_wall_rep() == "solid"

    # dummy opt-out: SerializedDummy reps + the historical honesty wording
    # (stage W only: nothing below reads the V gate)
    res_d, path_d, wrec_d = _build(str(tmp_path / "dummy"), 2026, monkeypatch,
                                   wall_rep="dummy", stages="W")
    assert wrec_d["wall_rep"] == "dummy"
    rows = inspect(path_d, classes=["SWall"])
    assert len(rows) == 4 and all(r.kind == "dummy" and not r.drawable_3d for r in rows)
    assert res_d.manifest["honesty"]["tiers"]["load_vs_render"] == MF.LOAD_VS_RENDER["dummy"]
    assert MF._honesty(None, {})["tiers"]["load_vs_render"] == MF.LOAD_VS_RENDER["dummy"]

    # solid default is deterministic: two builds, identical bytes; and it is
    # NOT the dummy file (the rep is the only variable between the two shapes)
    _, a, _ = _build(str(tmp_path / "a"), 2026, monkeypatch, stages="W")
    _, b, _ = _build(str(tmp_path / "b"), 2026, monkeypatch, stages="W")
    assert sha256_of(a) == sha256_of(b) != sha256_of(path_d)
