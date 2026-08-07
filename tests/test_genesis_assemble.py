"""genesis_assemble.py: the FIRST GENESIS CANDIDATE (G0) — composition of the
skeleton + type constructors into a self-contained document authored by us,
and the top-down assembly ladder that carries it into a validator-clean,
zero-Autodesk-element file.

Unit tests (no sample files needed) cover OUR content: self-containment,
schema round-trip, id range, the house object-styles standard, and the two
metadata-stream generators.  The end-to-end ladder test needs the base
reduction ``experiments/genesis/R10b.rvt`` and the rstbasic baseline sample;
it is skipped when either is absent.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import struct
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "genesis_assemble.py")
BASE = os.path.join(ROOT, "experiments", "genesis", "R10b.rvt")
BASELINE = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")


@pytest.fixture(scope="module")
def ga():
    spec = importlib.util.spec_from_file_location("genesis_assemble", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["genesis_assemble"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def content(ga):
    return ga.build_our_content(1_500_000)


# ---------------------------------------------------------------------------
# OUR content — pure construction, no files
# ---------------------------------------------------------------------------

def test_content_is_self_contained_and_roundtrips(content):
    """Every record encodes/decodes clean+byte-exact and every ElementId it
    references is another of OUR records (nothing points at a sample id)."""
    assert content.roundtrip["failed"] == 0, content.roundtrip["failures"][:3]
    assert content.roundtrip["ok"] == len(content.elements)
    assert content.dangling == [], f"references outside our content: {content.dangling[:5]}"


def test_content_id_range_and_uniqueness(content):
    ids = [el.elem_id for el in content.elements]
    assert len(ids) == len(set(ids)), "duplicate element ids"
    assert min(ids) == content.start_id == 1_500_000
    assert max(ids) == content.last_id
    # far above rstbasic's watermark (1,472,524): all read as CREATED by the ledger
    assert min(ids) > 1_472_524
    assert [el.elem_id for el in content.elements] == sorted(ids)  # id-sorted


def test_content_manifest_is_complete_and_named(content):
    m = content.manifest
    assert len(m) == len(content.elements)
    assert [x["id"] for x in m] == [el.elem_id for el in content.elements]
    kinds = {x["kind"] for x in m}
    for required in ("level", "phase", "phase-set", "project-info", "units-registry",
                     "wall-type", "material", "object-style", "voltage-type",
                     "project-view-constellation", "3d-view-constellation",
                     "plan-view-constellation", "conduit-type", "text-type"):
        assert required in kinds, f"missing {required}"
    # every one of OUR names carries the GEN prefix or our project identity
    named = [x for x in m if x["name"]]
    assert any(x["name"] == "GENESIS Base" or "GEN" in x["name"] or
               x["name"] in ("Level 1", "Level 2", "Existing", "New Construction",
                             "{3D}", "Internal", "Project")
               for x in named)


def test_content_has_the_skeleton_and_catalog(content, ga):
    ids = content.ids
    for k in ("units", "level1", "level2", "phase_new", "phase_existing",
              "phase_set", "project_view", "view_3d", "project_info", "geo_location"):
        assert k in ids and ids[k] >= content.start_id
    kinds = [x["kind"] for x in content.manifest]
    # the phase set, five standard filters, two levels
    assert kinds.count("phase-filter") == 5
    assert kinds.count("level") == 2
    assert kinds.count("phase") == 2


def test_house_object_styles_follow_our_scheme(content, ga):
    """The object-styles rows carry OUR discipline-coded pens/colours, one
    projection row per house category and one cut row per cuttable one."""
    # built-in-category rows only (sub-category styles carry 'parent', not 'category')
    styles = [x for x in content.manifest if x["kind"] == "object-style"
              and "category" in (x.get("params") or {})]
    n_proj = sum(1 for c in ga.HOUSE_CATEGORIES)
    n_cut = sum(1 for c in ga.HOUSE_CATEGORIES if c[3])
    assert len(styles) == n_proj + n_cut
    for x in styles:
        disc = x["params"]["discipline"]
        proj_pen, cut_pen, colour = ga.HOUSE_SCHEME[disc]
        assert x["params"]["color"] == colour
        assert x["params"]["pen"] in (proj_pen, cut_pen)


def test_electrical_definitions_are_ours_not_reproductions(content, ga):
    """Our electrical catalog uses GEN names/values (never a byte-reproduction
    of the sample's '120'/'208' Autodesk types).  Since genesis-2 the content
    comes from the own-content HOUSE STANDARD (nominal system voltages per
    ANSI C84.1, our 'GEN <volts>' naming)."""
    volts = [x for x in content.manifest if x["kind"] == "voltage-type"]
    nominal = {v["params"].get("nominal", v["params"].get("volts")) for v in volts}
    assert {120, 208, 277, 480} <= nominal
    assert all(v["name"].startswith("GEN ") for v in volts)


def test_wall_types_reference_only_our_materials(content, ga):
    """Compound-structure layers point at OUR MaterialElems (self-contained)."""
    from rvt.genesis import types as ty
    mats = {el.elem_id for el in content.elements if el.class_name == "MaterialElem"}
    walls = [el for el in content.elements if el.class_name == "BasicWallType"]
    assert len(walls) == 3
    for w in walls:
        layers = w.obj["m_pCompoundStructure"]["value"]["m_layers"]
        for lay in layers:
            mid = lay["m_materialId"]
            assert mid == -1 or mid in mats, f"wall layer references non-our material {mid}"


def test_project_meta_single_source_of_truth(ga):
    """The ProjectInfo element and the ProjectInformation stream agree."""
    pm = ga.PROJECT_META
    zbytes = ga.our_project_information_zip("00000000-0000-0000-0000-000000000000")
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    names = z.namelist()
    assert len(names) == 1 and names[0].endswith(".project.xml")
    assert "\\Users\\" not in names[0] and "AppData" not in names[0]     # no employee path
    x = z.read(names[0]).decode("utf-8")
    assert f"<title>{pm['project_name']}</title>" in x
    assert pm["project_number"] in x and pm["client_name"] in x
    assert "rstbasic" not in x.lower() and "hansonje" not in x


def test_transmission_data_framing_and_no_external_refs(ga):
    td = ga.our_transmission_data()
    n = struct.unpack_from("<I", td, 0)[0]
    body = td[4:]
    assert len(body) == 2 * n                                 # u32 = UTF-16 code units
    xml = body.decode("utf-16-le")
    assert xml.startswith("<?xml") and "</TransmissionData>" in xml
    assert "ExternalFileReference" not in xml                 # G0 references nothing external
    assert "\\Users\\" not in xml


def test_dangling_check_flags_a_foreign_reference(ga, content):
    """Sanity: the self-containment checker really catches a sample id."""
    import copy
    from rvt.genesis import types as ty
    wall = next(el for el in content.elements if el.class_name == "BasicWallType")
    tr = copy.deepcopy(wall)
    # graft a reference to a SAMPLE fill pattern (id 4) into a wall type
    tr.obj["m_pCompoundStructure"]["value"]["m_coarseScaleFillPatternElemId"] = 4
    fake = ty.TypeRecord(tr.elem_id, "wall", tr.class_name, 0, -1, tr.obj, tr.header, tr.rep)
    bad = ga._dangling_references([fake])
    assert any(d["target"] == 4 for d in bad), "checker missed a foreign reference"


# ---------------------------------------------------------------------------
# the ladder — end-to-end on real files
# ---------------------------------------------------------------------------

needs_base = pytest.mark.skipif(
    not (os.path.exists(BASE) and os.path.exists(BASELINE)),
    reason="needs experiments/genesis/R10b.rvt + samples/rstbasicsampleproject.rvt")


@needs_base
def test_ladder_end_to_end(tmp_path, ga):
    """Build the whole G0 ladder into a temp dir; every rung validates with
    ZERO errors; the final G0 holds exactly OUR elements, ZERO Autodesk-sample
    elements, ZERO embedded family documents, and OUR identity."""
    out = str(tmp_path)
    pipe = ga.build_ladder(out, base=BASE)

    files = pipe["files"]
    assert set(files) >= {"G0a", "G0b", "G0c", "G0d", "G0"}
    for tag, cert in files.items():
        assert cert["validator"]["ok"], f"{tag}: {cert['validator']['error_messages']}"
        assert cert["validator"]["errors"] == 0

    # monotone reduction of the Autodesk-derived count down the ladder
    counts = [files[t]["provenance"]["autodesk_sample"] for t in
              ("G0a", "G0b", "G0c", "G0d", "G0")]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > 0 and counts[-1] == 0

    g0 = files["G0"]
    assert g0["provenance"]["autodesk_sample"] == 0
    assert g0["provenance"]["ours_modified"] == 0
    assert g0["provenance"]["unmatched"] == 0
    assert g0["provenance"]["embedded_family_documents"]["count"] == 0
    n_ours = pipe["our_content"]["elements"]
    assert g0["provenance"]["host_elements"] == n_ours
    assert (g0["provenance"]["ours_created"]
            + g0["provenance"]["transitive_cloned"]) == n_ours

    # the own-save: our identity, GUID == History[0], coherent increments
    save = next(s for s in pipe["stages"] if s["stage"] == "G0")
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from rvt.container import open_rvt
    from rvt import stream_encoders as se
    from rvt.identity import identity_report
    with open_rvt(os.path.join(out, "G0.rvt")) as f:
        ident = identity_report(f.logical("BasicFileInfo"))
        hist = se.decode_history(f.inflate("Global/History"))
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        dit = se.decode_increment_table(f.inflate("Global/DocumentIncrementTable"))
        # our metadata streams
        z = zipfile.ZipFile(io.BytesIO(f.raw("ProjectInformation")))
        pxml = z.read(z.namelist()[0]).decode("utf-8")
        td = f.raw("TransmissionData")[4:].decode("utf-16-le")
    assert ident["author"] == ga.AUTHOR and ident["client_app_name"] == ga.AUTHOR
    assert ident["unique_document_guid"] == save["document_guid"] == hist["entries"][0][0]
    assert int(ident["unique_document_increments"]) == len(dit["records"])
    assert hist["hdr_count"] == max(r[2] for r in et["records"]) + 1
    assert len(et["records"]) == n_ours
    assert "GENESIS Base" in pxml and "hansonje" not in pxml
    assert "ExternalFileReference" not in td
