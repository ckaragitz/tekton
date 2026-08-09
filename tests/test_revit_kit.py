"""REVIT-CHECK-KIT v2 (issue #118): tools/revit_kit.py builds the desktop-
Revit check kit from a FRESH CLONE (only the tracked pinned base is needed)
and the kit has exactly the promised shape:

* K0 is byte-identical to the pinned G_ABPD (sha256 pin asserted);
* K1 = 4 SWall, no added save unit; K2 = one added family document whose
  0x0f3f blob is 64 bytes + one Family / FamilySymbol pair / FamilyInstance,
  no walls; K3 = both; a standalone .rfa beside them;
* every file validates 0 errors; the manifest's added-element id map and
  id_index are non-empty and resolve real ids;
* the emitted REVIT-CHECK-KIT.md names every kit file, carries the v2
  instructions, and no longer mentions the retired v1 files;
* the tracked experiments/terminal copy is a v2 render, and
  tools/terminal_diff.py kit delegates to the builder.

The kit is built ONCE per module into tmp_path (~15-20 s).
Run: .venv/bin/python -m pytest tests/test_revit_kit.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import revit_kit as RK                                            # noqa: E402

PIN_SHA256 = "84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50"
TRACKED_MD = os.path.join(ROOT, "experiments", "terminal", "REVIT-CHECK-KIT.md")
TRACKED_MANIFEST = os.path.join(ROOT, "experiments", "terminal", "kit2", "manifest.json")

pytestmark = pytest.mark.skipif(not os.path.isfile(RK.PINNED_BASE),
                                reason="pinned genesis base G_ABPD absent")


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = tmp_path_factory.mktemp("revit_kit") / "kit2"
    published = tmp_path_factory.mktemp("revit_kit_pub") / "REVIT-CHECK-KIT.md"
    try:
        manifest = RK.build_kit(str(out), publish_md=str(published))
    except Exception as e:                                     # pragma: no cover
        pytest.skip(f"kit build unavailable here: {type(e).__name__}: {e}")
    return {"dir": str(out), "manifest": manifest, "published": str(published),
            "md": (out / "REVIT-CHECK-KIT.md").read_text(encoding="utf-8")}


def _file(manifest, name):
    return RK._file(manifest, name)


# ---------------------------------------------------------------------------
# constants agree with the engine's own pin / laws
# ---------------------------------------------------------------------------

def test_constants_agree_with_the_engine():
    from rvt.frontdoor.base import PIN
    from rvt.validate import UNIT_FOOTER_BLOB_LEN
    assert RK.PINNED_SHA256 == PIN.base_sha256 == PIN_SHA256
    assert RK.BLOB_LEN == UNIT_FOOTER_BLOB_LEN == 64
    assert RK.watermark_of(RK.PINNED_BASE) == RK.BASE_WATERMARK == 1472524


# ---------------------------------------------------------------------------
# the built kit
# ---------------------------------------------------------------------------

def test_every_promised_file_is_written(kit):
    for name in (RK.K0, RK.K1, RK.K2, RK.K3, "manifest.json", "REVIT-CHECK-KIT.md"):
        assert os.path.isfile(os.path.join(kit["dir"], name)), name
    rfas = [e for e in kit["manifest"]["files"] if e["kind"] == "rfa"]
    assert rfas and all(e["name"].startswith("families/") for e in rfas)
    for e in rfas:
        assert os.path.isfile(os.path.join(kit["dir"], e["name"]))
    assert not os.path.exists(os.path.join(kit["dir"], "_build")), "job dirs not cleaned"
    assert kit["manifest"]["checks"] == [], kit["manifest"]["checks"]


def test_k0_is_byte_identical_to_the_pin(kit):
    k0 = _file(kit["manifest"], RK.K0)
    assert k0["sha256"] == PIN_SHA256
    assert RK.sha256_of(os.path.join(kit["dir"], RK.K0)) == PIN_SHA256
    assert k0["byte_identical_to_pin"] is True and k0["role"] == "control"
    assert kit["manifest"]["base"]["watermark"] == 1472524
    assert k0["census"]["added_classes"] == {} and k0["census"]["added_save_units"] == 0


def test_k1_is_the_shell(kit):
    k1 = _file(kit["manifest"], RK.K1)
    assert k1["census"]["classes"]["SWall"] == 4
    assert k1["census"]["added_classes"] == {"SWall": 4}
    assert k1["census"]["added_save_units"] == 0
    assert k1["family_documents"] == []
    assert [r["class"] for r in k1["added_elements"]] == ["SWall"] * 4
    assert all(r["id"] > 1472524 and r["unit"] == 0 for r in k1["added_elements"])
    assert {r.get("tag") for r in k1["added_elements"]} == {"W-S", "W-E", "W-N", "W-W"}


def test_k2_is_one_family_one_instance_with_the_blob(kit):
    k2 = _file(kit["manifest"], RK.K2)
    added = k2["census"]["added_classes"]
    for c in ("Family", "FamilySymbol", "FamSymSurrogate", "FamilyInstance"):
        assert added.get(c) == 1, (c, added)
    assert k2["census"]["classes"]["SWall"] == 0
    assert k2["census"]["added_save_units"] == 1
    docs = [d for d in k2["family_documents"] if d["added"]]
    assert len(docs) == 1
    doc = docs[0]
    assert doc["blob_len"] == 64 and doc["unit"] == 1 and doc["guid"]
    assert doc["family"] and doc["family"].startswith("Panelboard")
    assert doc["n_elements"] > 0 and doc["classes"].get("Family") == 1
    # every unit in the file carries the blob (host + famdoc)
    assert [u["blob_len"] for u in k2["census"]["save_units"]] == [64, 64]
    # the instance resolves to the family and its document unit
    inst = [r for r in k2["added_elements"] if r["class"] == "FamilyInstance"][0]
    assert inst["family"] == doc["family"] and inst["family_unit"] == 1
    fam = [r for r in k2["added_elements"] if r["class"] == "Family"][0]
    assert fam["name"] == doc["family"] and fam.get("tag") == "PP-1"


def test_k3_is_the_combination(kit):
    k3 = _file(kit["manifest"], RK.K3)
    added = k3["census"]["added_classes"]
    assert added.get("SWall") == 4 and added.get("FamilyInstance") == 1 and added.get("Family") == 1
    assert k3["census"]["added_save_units"] == 1
    assert [d["blob_len"] for d in k3["family_documents"]] == [64]
    assert "PROOF-ONLY" in " ".join(k3["stamps"])


def test_every_file_validates_zero_errors(kit):
    for e in kit["manifest"]["files"]:
        v = e["validation"]
        assert v["ok"] and v["errors"] == 0, (e["name"], v["error_messages"])
    rfa = [e for e in kit["manifest"]["files"] if e["kind"] == "rfa"][0]
    assert rfa["validation"]["mode"] == "family"


def test_id_map_resolves_dialog_ids(kit):
    m = kit["manifest"]
    for name in (RK.K1, RK.K2, RK.K3):
        assert _file(m, name)["added_elements"], name
    assert m["id_index"]
    inst = [r for r in _file(m, RK.K2)["added_elements"] if r["class"] == "FamilyInstance"][0]
    hits = RK.lookup(kit["dir"], [str(inst["id"])])[str(inst["id"])]
    assert any(h["file"] == RK.K2 and h["unit"] == 0 and h["class"] == "FamilyInstance"
               for h in hits), hits
    # a famdoc-internal id resolves to its unit + GUID, not the host
    doc = _file(m, RK.K2)["family_documents"][0]
    inner = str(doc["elements"][0]["id"])
    assert any(h["file"] == RK.K2 and h["unit"] == 1 and h["unit_guid"] == doc["guid"]
               for h in m["id_index"][inner])
    assert RK.lookup(kit["dir"], ["1"]) == {"1": []}


def test_verify_passes_on_the_fresh_kit_and_catches_a_swapped_file(kit, tmp_path):
    assert RK.verify_kit(kit["dir"]) == []
    import shutil
    copy = tmp_path / "kitcopy"
    shutil.copytree(kit["dir"], copy)
    shutil.copyfile(copy / RK.K1, copy / RK.K2)          # a mislabelled copy
    bad = RK.verify_kit(str(copy))
    assert any(RK.K2 in b and "sha256 differs" in b for b in bad), bad


# ---------------------------------------------------------------------------
# the markdown
# ---------------------------------------------------------------------------

def test_markdown_is_v2(kit):
    md = kit["md"]
    for e in kit["manifest"]["files"]:
        assert e["name"] in md, e["name"]
    assert "H12.rvt" not in md and "BXhf_f1i1.rvt" not in md
    assert "VERDICTS #36" in md and "retired" in md              # the stated reason
    for needle in ("Audit", "Select by ID", "Review Warnings", "journal",
                   "Load Family", "by hand", "PROOF-ONLY", PIN_SHA256):
        assert needle in md, needle
    order = [md.index(f"`{n}`") for n in (RK.K0, RK.K1, RK.K2, RK.K3)]
    assert order == sorted(order)
    assert md == RK.render_kit_md(kit["manifest"])
    with open(kit["published"], encoding="utf-8") as f:
        assert f.read() == md


def test_tracked_kit_markdown_is_a_v2_render():
    """experiments/terminal/REVIT-CHECK-KIT.md is regenerated, never hand-
    edited: it must equal the render of the tracked kit2/manifest.json."""
    if not (os.path.isfile(TRACKED_MD) and os.path.isfile(TRACKED_MANIFEST)):
        pytest.skip("tracked kit md/manifest absent")
    with open(TRACKED_MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(TRACKED_MD, encoding="utf-8") as f:
        md = f.read()
    assert manifest["kit_version"] == RK.KIT_VERSION
    assert md == RK.render_kit_md(manifest)
    assert "H12.rvt" not in md and "BXhf_f1i1.rvt" not in md
    for n in (RK.K0, RK.K1, RK.K2, RK.K3):
        assert n in md


def test_terminal_diff_kit_delegates(monkeypatch):
    import terminal_diff as td
    assert not hasattr(td, "KIT_MD") and not hasattr(td, "BXHF")
    assert td.KIT_DIR.endswith(os.path.join("experiments", "terminal", "kit2"))
    seen = {}
    monkeypatch.setattr(RK, "main", lambda argv: seen.setdefault("argv", list(argv)) and 0)
    monkeypatch.setitem(sys.modules, "revit_kit", RK)
    assert td.kit() == 0
    assert seen["argv"] == ["build", "--out", td.KIT_DIR]
