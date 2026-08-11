"""test_genesis_identity.py -- the G2 identity rungs of tools/genesis_identity.py
(issue #134, the fresh-clone half of #19).

Runs on a fresh clone / in CI: the only inputs are the three tracked, sha-pinned
composed bases under plugin/assets/genesis/.  Everything is built into tmp_path
(never into experiments/), 2026 fully (every rung + probes.json + the
probe_batch gate + a STAGED batch in a tmp acceptance dir), 2025/2024 as a smoke
of the I_all candidate under their own release.

Run: .venv/bin/python -m pytest tests/test_genesis_identity.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_identity as GI                               # noqa: E402
from conftest import context_constants                     # noqa: E402
from rvt import identity as ID                             # noqa: E402
from rvt.provenance import identity_report                 # noqa: E402
from rvt.roundtrip import read_entries                     # noqa: E402

PINS = GI.pinned_bases()                                   # {year: {path, ledger_relpath, sha256}}
IDENTITY_STREAMS = {"BasicFileInfo", "Global/DocumentIncrementTable",
                    "ProjectInformation", "TransmissionData"}
LEDGER_2026 = "experiments/genesis/subst_k4/compose/G_ABPD.rvt"

pytestmark = [pytest.mark.skipif(set(PINS) != {2026, 2025, 2024},
                                 reason="bundled genesis bases missing (or not ledger-certified)"),
              pytest.mark.usefixtures("no_release_leak")]  # no release context leaks out of the tool


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too, not the framing table alone."""
    return context_constants


@pytest.fixture(scope="module")
def built_2026(tmp_path_factory):
    """The full 2026 rung set (+ the optional I_guid rung), built once."""
    out = str(tmp_path_factory.mktemp("identity_g2"))
    rep = GI.build_release(2026, out_dir=out, with_guid=True, verbose=False)
    GI.write_probes_json(out)
    return out, rep


def _rung(rep, name):
    return next(r for r in rep["rungs"] if r["rung"] == name)


# ---------------------------------------------------------------------------
# the facts this stream starts from (so a re-pin that fixes them is noticed)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_pinned_base_still_carries_the_inherited_identity(year):
    assert PINS[year]["ledger_relpath"].startswith("experiments/genesis/")
    fields = {v["field"] for v in identity_report(PINS[year]["path"])["violations"]}
    assert {"author", "client_app_name", "last_save_path",
            "DocumentIncrementTable.username"} <= fields, fields


# ---------------------------------------------------------------------------
# 2026: every rung, fully
# ---------------------------------------------------------------------------
def test_2026_every_rung_passes_its_assertions(built_2026):
    out, rep = built_2026
    assert rep["ok"], [(r["rung"], r["problems"]) for r in rep["rungs"] if not r["ok"]]
    assert [r["rung"] for r in rep["rungs"]] == ["I_all", "I_bfi", "I_dit", "I_pi", "I_td", "I_guid"]
    for r in rep["rungs"]:
        assert os.path.isfile(os.path.join(ROOT, r["file"]))


def test_2026_each_rung_changes_exactly_its_streams(built_2026):
    out, rep = built_2026
    n_streams = sum(1 for e in read_entries(PINS[2026]["path"]) if e.entry_type == "stream")
    want = {"I_all": IDENTITY_STREAMS,
            "I_bfi": {"BasicFileInfo"}, "I_dit": {"Global/DocumentIncrementTable"},
            "I_pi": {"ProjectInformation"}, "I_td": {"TransmissionData"},
            "I_guid": {"BasicFileInfo", "Global/History"}}
    for r in rep["rungs"]:
        assert set(r["stream_diff"]["changed"]) == want[r["rung"]], (r["rung"], r["stream_diff"])
        assert r["stream_diff"]["structure_ok"]
        assert r["stream_diff"]["identical_count"] + len(want[r["rung"]]) == n_streams


def test_2026_every_rung_validates_zero_errors_under_its_release(built_2026):
    out, rep = built_2026
    for r in rep["rungs"]:
        assert r["validate"]["release_detected"] == 2026
        assert r["validate"]["counts"].get("error", 0) == 0, (r["rung"], r["validate"]["errors"])


def test_2026_provenance_identity_goes_from_four_violations_to_zero_on_I_all(built_2026):
    out, rep = built_2026
    assert len(rep["base"]["provenance_identity"]["violation_fields"]) == 4
    assert _rung(rep, "I_all")["provenance_identity"]["violation_fields"] == []
    assert _rung(rep, "I_all")["provenance_identity"]["ok"] is True
    # singles clear exactly their own surface
    assert _rung(rep, "I_bfi")["provenance_identity"]["violation_fields"] == ["DocumentIncrementTable.username"]
    assert set(_rung(rep, "I_dit")["provenance_identity"]["violation_fields"]) == \
        {"author", "client_app_name", "last_save_path"}
    # and the CLI instrument agrees on the written file
    idr = identity_report(os.path.join(out, "2026", "I_all_2026.rvt"))
    assert idr["ok"] and not idr["violations"]


def test_2026_byte_scan_of_I_all_finds_no_usernames_and_no_foreign_paths(built_2026):
    out, rep = built_2026
    i_all = _rung(rep, "I_all")
    assert i_all["byte_scan"] == {"owned_hits": {}, "residual_hits": {}}
    # independent re-scan of the file on disk (raw + de-paged + inflated views)
    scan = GI.byte_scan(os.path.join(out, "2026", "I_all_2026.rvt"))
    assert scan["hits"] == {}, scan["hits"]


def test_2026_decodes_round_trip_to_our_identity(built_2026):
    out, rep = built_2026
    by = {r["rung"]: r["decoded"] for r in rep["rungs"]}
    base = rep["base"]["identity"]
    a = by["I_all"]
    # BFI: our placeholder author/client (counsel C1 -- the existing constant, nothing invented),
    # username '', bare filename, version marker + increments + GUID untouched
    assert a["bfi"]["author"] == ID.PRODUCT_AUTHOR_PLACEHOLDER == "rvt-writer"
    assert a["bfi"]["client_app_name"] == ID.PRODUCT_AUTHOR_PLACEHOLDER
    assert a["bfi"]["username"] == ""
    assert a["bfi"]["last_save_path"] == "G_ABPD.rvt"
    for keep in ("format", "build", "unique_document_guid", "central_episode_guid",
                 "unique_document_increments", "central_version_number", "locale"):
        assert a["bfi"][keep] == base["bfi"][keep], keep
    assert a["bfi"]["unique_document_guid"] == a["history"]["entry0_guid"] == base["history"]["entry0_guid"]
    # DIT: every episode ours, both copies equal, row count unchanged
    assert a["dit"]["usernames"] == {"": base["dit"]["records"]}
    assert a["dit"]["records"] == base["dit"]["records"] and a["dit"]["records2_equal"]
    # PI: one member, no directory, our values, this release
    assert a["pi"]["members"] == [f"Revit{base['bfi']['unique_document_guid']}.project.xml"]
    assert a["pi"]["design_file"]["product_version"] == "2026"
    assert a["pi"]["design_file"]["title"] == "G_ABPD.rvt"
    assert "\\" in base["pi"]["members"][0]                      # the base's IS a foreign temp path
    # TD: same references, absolute paths replaced by the relative ones
    assert [r["ElementId"] for r in a["td"]["references"]] == [r["ElementId"] for r in base["td"]["references"]]
    for r in a["td"]["references"]:
        assert r["LastSavedAbsolutePath"] == r["LastSavedPath"]
        assert not r["LastSavedAbsolutePath"].lower().startswith("c:")
    assert any(r["LastSavedAbsolutePath"].lower().startswith("c:") for r in base["td"]["references"])
    # singles leave the OTHER surfaces exactly as the base has them
    assert by["I_bfi"]["dit"] == base["dit"] and by["I_bfi"]["pi"] == base["pi"] and by["I_bfi"]["td"] == base["td"]
    assert by["I_td"]["bfi"] == base["bfi"]


def test_2026_optional_guid_rung_is_coherent(built_2026):
    out, rep = built_2026
    g = _rung(rep, "I_guid")
    base = rep["base"]["identity"]
    assert g["ok"], g["problems"]
    assert "higher" in g["risk"] and g["kind"] == "probe"
    new = g["decoded"]["bfi"]["unique_document_guid"]
    assert new != base["bfi"]["unique_document_guid"]
    assert new == g["decoded"]["bfi"]["central_episode_guid"] == g["decoded"]["history"]["entry0_guid"]
    assert g["decoded"]["history"]["count"] == base["history"]["count"]
    assert g["decoded"]["bfi"]["author"] == base["bfi"]["author"]      # GUID is the ONLY variable


def test_build_is_byte_reproducible(built_2026, tmp_path):
    out, rep = built_2026
    pin = PINS[2026]
    other = str(tmp_path / "again.rvt")
    GI.write_rung(pin["path"], other,
                  GI.author_streams(pin["path"], GI.FAMILIES, GI.Ctx(2026, "G_ABPD.rvt", pin["sha256"])))
    assert GI.sha256_of(other) == _rung(rep, "I_all")["sha256"]


def test_probes_json_declares_candidate_and_probes_against_the_ledger_relpath(built_2026):
    out, rep = built_2026
    with open(os.path.join(out, "probes.json")) as fh:
        man = json.load(fh)
    assert man["releases"]["2026"]["base"] == LEDGER_2026
    assert [p["rung"] for p in man["probes"]] == ["I_all", "I_bfi", "I_dit", "I_pi", "I_td", "I_guid"]
    kinds = {p["rung"]: p["kind"] for p in man["probes"]}
    assert kinds["I_all"] == "candidate-base"
    assert {kinds[k] for k in ("I_bfi", "I_dit", "I_pi", "I_td", "I_guid")} == {"probe"}
    for p in man["probes"]:
        assert p["base"] == LEDGER_2026
        assert p["release"] == 2026 and p["sha256"] and p["checks_ok"] is True
    assert "V31" in man["expected_reading"] and "#36" in man["expected_reading"]


def test_committed_json_is_proof_only_and_redacts_employee_logins(built_2026):
    out, rep = built_2026
    from rvt.provenance import AUTODESK_EMPLOYEE_USERNAMES
    # in memory the base's real DIT usernames are there (the assertions need them) ...
    assert set(rep["base"]["provenance_identity"]["dit_usernames"]) & AUTODESK_EMPLOYEE_USERNAMES
    # ... on disk they are placeholders, and both manifests carry the stamp
    for relp in (os.path.join("2026", "rungs.json"), "probes.json"):
        with open(os.path.join(out, relp)) as fh:
            text = fh.read()
        low = text.lower()
        assert not [n for n in AUTODESK_EMPLOYEE_USERNAMES if n in low], relp
        assert json.loads(text)["stamp"].startswith("PROOF-ONLY"), relp
    with open(os.path.join(out, "2026", "rungs.json")) as fh:
        on_disk = json.load(fh)
    assert set(on_disk["base"]["provenance_identity"]["dit_usernames"]) <= \
        {f"<employee_{i}>" for i in range(1, 9)}
    assert "<employee_" in on_disk["base"]["identity"]["bfi"]["last_save_path"]


def test_probe_batch_gate_admits_the_batch_and_stages_it_with_a_byte_identical_control(built_2026, tmp_path):
    out, rep = built_2026
    g = GI.gate_release(2026, out_dir=out, stage=False)
    assert g["admissible"], g["violations"]
    assert sorted(e["kind"] for e in g["entries"]) == ["candidate-base"] + ["probe"] * 5
    for e in g["entries"]:
        assert e["base"] == LEDGER_2026
        assert e["base_status"].startswith("certified")
    acc = str(tmp_path / "acceptance")
    s = GI.gate_release(2026, out_dir=out, stage=True, acceptance_dir=acc, batch_n=99)
    assert s["admissible"] and s["batch"] == 99
    with open(os.path.join(acc, "batch_99.json")) as fh:
        man = json.load(fh)
    first = man["entries"][0]
    assert first["kind"] == "control" and first["order"] == 0
    assert first["control_source"] == "plugin/assets/genesis/G_ABPD.rvt" == s["control_source"]
    assert first["control_certified_as"] == LEDGER_2026
    ctrl = os.path.join(acc, man["reading_order"][0])
    assert GI.sha256_of(ctrl) == PINS[2026]["sha256"]                       # byte-identical control
    assert man["reading_order"][1] == "I_all_2026.rvt"                       # candidate right after
    assert man["entries"][1]["kind"] == "candidate-base"
    assert {e["kind"] for e in man["entries"][2:]} == {"probe"}


def test_gate_refuses_a_stale_or_failed_rung(built_2026, tmp_path):
    out, rep = built_2026
    # a copy of the manifest whose I_td entry claims different bytes and a failed check
    stale = str(tmp_path / "stale")
    os.makedirs(stale)
    with open(os.path.join(out, "probes.json")) as fh:
        man = json.load(fh)
    for p in man["probes"]:
        if p["rung"] == "I_td":
            p["sha256"] = "0" * 64
            p["checks_ok"] = False
    with open(os.path.join(stale, "probes.json"), "w") as fh:
        json.dump(man, fh)
    g = GI.gate_release(2026, out_dir=stale, stage=False)
    assert not g["admissible"]
    assert any("stale build" in v for v in g["violations"])
    assert any("FAILED its own" in v for v in g["violations"])


# ---------------------------------------------------------------------------
# 2025 / 2024: the candidate under its own release (smoke)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year,pinned", [(2025, "G_ABPD_2025.rvt"), (2024, "G_ABPD_2024.rvt")])
def test_I_all_on_the_older_releases(year, pinned, tmp_path):
    assert os.path.basename(PINS[year]["ledger_relpath"]) == pinned
    rep = GI.build_release(year, out_dir=str(tmp_path), only=("all",), verbose=False)
    (r,) = rep["rungs"]
    assert r["ok"], r["problems"]                    # stream set, 0 validate errors, identity, decodes, scan
    assert set(r["stream_diff"]["changed"]) == IDENTITY_STREAMS
    assert r["validate"]["release_detected"] == year
    assert r["provenance_identity"]["violation_fields"] == []
    assert r["decoded"]["bfi"]["format"] == str(year)
    assert r["decoded"]["bfi"]["last_save_path"] == pinned
    assert r["decoded"]["pi"]["design_file"]["product_version"] == str(year)
    assert r["byte_scan"]["owned_hits"] == {}
    # The ONLY residue is pre-existing ELEMENT data in the model partition of the
    # certified 2025/2024 pins (the AssemblyCodeTable element's external-resource
    # path strings, #273) -- a fifth surface outside the four metadata families,
    # byte-identical to the base (this rung did not touch it).
    assert r["byte_scan"]["residual_hits"] == rep["base"]["byte_scan"]["residual_hits"]
    assert all(k.startswith("Partitions/") for k in r["byte_scan"]["residual_hits"])


# ---------------------------------------------------------------------------
# unit: the TransmissionData rewrite is minimal
# ---------------------------------------------------------------------------
def test_transmission_rewrite_touches_only_the_absolute_path():
    xml = ('<?xml version="1.0"?>\r\n<TransmissionData isTransmitted="false" userData="" version="5">'
           '<ExternalFileReference><ElementId>1</ElementId><LastSavedPath>a.txt</LastSavedPath>'
           '<LastSavedAbsolutePath>C:\\Users\\someone\\a.txt</LastSavedAbsolutePath>'
           '<DesiredPath>a.txt</DesiredPath></ExternalFileReference>'
           '<ExternalFileReference><ElementId>2</ElementId><LastSavedPath>..\\b.rvt</LastSavedPath>'
           '<LastSavedAbsolutePath>C:\\..\\b.rvt</LastSavedAbsolutePath></ExternalFileReference>'
           '</TransmissionData>')
    new, n = GI.own_transmission_xml(xml)
    assert n == 2
    assert "<LastSavedAbsolutePath>a.txt</LastSavedAbsolutePath>" in new
    assert "<LastSavedAbsolutePath>..\\b.rvt</LastSavedAbsolutePath>" in new
    assert "someone" not in new and new.startswith('<?xml version="1.0"?>\r\n')
    assert new.replace("a.txt</LastSavedAbsolutePath>", "C:\\Users\\someone\\a.txt</LastSavedAbsolutePath>") \
              .replace("<LastSavedAbsolutePath>..\\b.rvt", "<LastSavedAbsolutePath>C:\\..\\b.rvt") == xml
    from rvt.meta import parse_transmission
    back = parse_transmission(GI.encode_transmission(new))
    assert back["size_ok"] and back["xml"] == new and len(back["references"]) == 2
