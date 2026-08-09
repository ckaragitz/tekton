"""test_famload_batch.py -- N generated families load in ONE host pass (issue #124).

The prompt route's L stage used to chain ``load_family_into_project`` once per
family (survey + Global/Latest edit + commit + container rewrite + verify, N
times).  ``rvt.famgen.loader.load_families_into_project`` does all N in one
host pass, and ``rvt.frontdoor.build.stage_load_batched`` drives it.  These
tests pin, sample-free (the bundled certified genesis bases are in git):

  * the batch writes the container ONCE for N families (a seam counts
    ``cfb_writer.write_cfb`` calls) and every family lands four-registry
    coherent, VALID 0 errors under the base's own release (2026 and 2025);
  * chain == batch at the logical level: with the same GUIDs, ElemTable /
    ContentDocuments / Latest are byte-identical, every partition block's
    inflated payload is identical and the units carry the same GUIDs in the
    same order (only BasicFileInfo's save name and the re-framed final-page
    trailer bytes differ);
  * a family whose authoring fails stops the batch THERE and the prefix is
    written (chain semantics), the failure named in ``stop_reason``;
  * the front door's manifest carries ``build.stages[*].seconds`` as numbers
    and its L stage reports ``host_passes == 1`` for a multi-family prompt;
  * ``tools/surface_bench.stage_breakdown`` reads that breakdown back.

Run: .venv/bin/python -m pytest tests/test_famload_batch.py -q
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rvt.versions as V                                    # noqa: E402

GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASE26 = os.path.join(GEN, "G_ABPD.rvt")
BASE25 = os.path.join(GEN, "G_ABPD_2025.rvt")

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(BASE26) and os.path.isfile(BASE25)),
    reason="bundled certified genesis bases missing")

SPECS = [
    dict(vendor="eaton", line="pow-r-line", mains_a=400, spaces=42, voltage="480Y/277",
         mcb=True, mounting="surface", name="Distribution Panelboard DP-1 480Y/277 400A"),
    dict(vendor="eaton", line="pow-r-line", mains_a=225, spaces=42, voltage="208Y/120",
         mcb=False, mounting="surface", name="Lighting Panelboard LP-1 208Y/120 225A"),
    dict(vendor="eaton", line="pow-r-line", mains_a=100, spaces=30, voltage="208Y/120",
         mcb=True, mounting="surface", name="Receptacle Panelboard RP-1 208Y/120 100A"),
]


@pytest.fixture(scope="module", autouse=True)
def _schema():
    """Standalone schema resolution (the base's own Formats/Latest), exactly
    as the front door installs it -- no samples/, no research corpus."""
    from rvt.frontdoor import standalone as SA
    SA.install_schema(BASE26)
    yield


def _factory(i):
    from rvt.famgen import factory as F
    return lambda start_id: F.make_panelboard(solid=True, start_id=start_id, **SPECS[i])


class _CountWrites:
    """Seam: count the loader's container writes (its call-time import of
    ``rvt.cfb_writer.write_cfb`` -- one per host pass; ``rvt.commit``'s
    pass-1 temp write binds the name at import and is not counted)."""

    def __init__(self, monkeypatch):
        import rvt.cfb_writer as CW
        self.n = 0
        real = CW.write_cfb

        def counting(path, entries, *a, **kw):
            self.n += 1
            return real(path, entries, *a, **kw)
        monkeypatch.setattr(CW, "write_cfb", counting)


class _DetUUID:
    """Deterministic uuid4 so the chain and the batch mint the same GUIDs."""

    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return uuid.UUID(int=(0x124 << 96) | self.n)


# ---------------------------------------------------------------------------
# the batched loader itself
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def batch26(tmp_path_factory):
    from rvt.famgen import loader as L
    out = str(tmp_path_factory.mktemp("batch26") / "batch3.rvt")
    res = L.load_families_into_project(BASE26, out, [_factory(i) for i in range(3)],
                                       symbol_solid=True, validate=True,
                                       report_path=out + ".load.json")
    return res


def test_batch_loads_n_families_ok(batch26):
    res = batch26
    assert res.ok, res.stop_reason
    assert res.culprit is None
    assert res.n_loaded == 3 and len(res.loads) == 3
    assert all(r.ok and r.plan is not None for r in res.loads)
    # ids ladder like the chain: family i+1's ids all above family i's
    tops = [max(r.plan.symbol_surrogate_id, *r.plan.twin_of.values()) for r in res.loads]
    lows = [r.proofs["plan"]["our_doc_ids"][0] for r in res.loads]
    assert lows[1] > tops[0] and lows[2] > tops[1]
    assert [r.proofs["plan"]["host_watermark"] for r in res.loads] == \
        [res.shared["host_watermark"], tops[0], tops[1]]
    # distinct GUIDs, all registered
    guids = [r.plan.guid for r in res.loads]
    assert len(set(guids)) == 3
    cd = res.shared["content_documents"]
    assert cd["entries_after"] == cd["entries_before"] + 3 and cd["ours_present"]
    assert res.shared["adocument_reencode"]["clean"] is True
    assert len(res.shared["pass2_partition_splice"]) == 3
    assert os.path.isfile(res.out_path + ".load.json")


def test_batch_file_is_four_registry_coherent_and_valid(batch26):
    from rvt.famload import four_registry_census
    from rvt.validate import validate_file
    res = batch26
    vw = res.shared["verify_written"]
    assert vw["file_ok"], vw["file_errors"]
    assert vw["validate"]["verdict"] == "VALID" and vw["validate"]["n_errors"] == 0
    for r in res.loads:
        pv = r.proofs["verify_written"]
        assert pv["ok"], json.dumps(pv, default=str)[:800]
        assert pv["adocument"] == {"content_table_record": True, "family_mgr_entry": True,
                                   "symbol_tracked": True}
        assert pv["family_documents"]["ok"] and pv["provenance_ours"]["ok"]
    census = four_registry_census(res.out_path)
    assert census["coherent"] is True, census
    base = four_registry_census(BASE26)
    assert census["contentdocs_entries"] == base["contentdocs_entries"] + 3
    assert census["save_units"] == base["save_units"] + 3
    ours = sorted(r.plan.guid for r in res.loads)
    assert sorted(census["unit_guids"]) == sorted(census["contentdocs_guids"]) \
        == sorted(census["contenttable_guids"]) == ours
    vr = validate_file(res.out_path)
    assert vr.ok and not vr.errors
    assert V.detect_release(res.out_path) == 2026


def test_batch_writes_the_container_once(tmp_path, monkeypatch):
    """The lever: ONE container rewrite for N families (the chained loader
    does N -- one per family)."""
    from rvt.famgen import loader as L
    seam = _CountWrites(monkeypatch)
    out = str(tmp_path / "b2.rvt")
    res = L.load_families_into_project(BASE26, out, [_factory(0), _factory(1)],
                                       validate=False)
    assert res.ok, res.stop_reason
    assert seam.n == 1                              # ONE container write for two families
    n_batch = seam.n
    # the chained way: two single loads = twice the rewrites
    seam.n = 0
    mid = str(tmp_path / "c1.rvt")
    r1 = L.load_family_into_project(BASE26, mid, product=_factory(0)(res.shared["host_watermark"] + 1),
                                    place=False, validate=False)
    assert r1.ok, r1.stop_reason
    wm = max(r1.plan.symbol_surrogate_id, *r1.plan.twin_of.values())
    r2 = L.load_family_into_project(mid, str(tmp_path / "c2.rvt"), product=_factory(1)(wm + 1),
                                    place=False, validate=False)
    assert r2.ok, r2.stop_reason
    assert seam.n == 2 * n_batch


def test_chain_and_batch_are_logically_identical(tmp_path, monkeypatch):
    """Same GUIDs in both arms -> ElemTable / ContentDocuments / Latest
    byte-identical; every partition block's inflated payload identical, same
    units in the same order.  What differs is NOT content: BasicFileInfo's
    last-save NAME and the final-page ECC trailer bytes each rewrite re-frames
    past the end record (the chain accumulates one per rewrite)."""
    from rvt.famgen import loader as L
    from rvt.roundtrip import read_entries
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    from rvt.identity import identity_report

    monkeypatch.setattr(uuid, "uuid4", _DetUUID())
    cur = BASE26
    cplans = []
    for i in range(2):
        nxt = str(tmp_path / f"chain{i + 1}.rvt")
        wm = L.survey_host(cur).watermark
        r = L.load_family_into_project(cur, nxt, product=_factory(i)(wm + 1),
                                       place=False, validate=False)
        assert r.ok, r.stop_reason
        cplans.append(r.plan)
        cur = nxt
    monkeypatch.setattr(uuid, "uuid4", _DetUUID())
    bout = str(tmp_path / "batch.rvt")
    b = L.load_families_into_project(BASE26, bout, [_factory(0), _factory(1)], validate=False)
    assert b.ok, b.stop_reason
    bplans = [r.plan for r in b.loads]
    assert [(p.guid, p.fam_doc_guid, p.host_family_id, p.symbol_id, sorted(p.twin_of.values()))
            for p in cplans] == \
           [(p.guid, p.fam_doc_guid, p.host_family_id, p.symbol_id, sorted(p.twin_of.values()))
            for p in bplans]

    def streams(p):
        return {e.path: e.data for e in read_entries(p) if e.entry_type == "stream"}
    cs, bs = streams(cur), streams(bout)
    assert set(cs) == set(bs)
    differ = sorted(k for k in cs if cs[k] != bs[k])
    part = [k for k in cs if k.startswith("Partitions/")]
    assert len(part) == 1
    assert set(differ) <= {"BasicFileInfo", part[0]}, differ
    for k in ("Global/ElemTable", "Global/ContentDocuments", "Global/Latest",
              "Global/History", "Global/PartitionTable", "Formats/Latest"):
        assert cs[k] == bs[k], k

    def walk(p):
        with open_rvt(p) as f:
            lg = f.logical(f.partition_streams()[0])
        return StreamWalker(lg, inflate=True, keep_data=True)
    wc, wb = walk(cur), walk(bout)
    assert not wc.errors and not wb.errors
    assert [(u.guid, u.n_blocks) for u in wc.units] == [(u.guid, u.n_blocks) for u in wb.units]
    kc = sorted(wc.blocks, key=lambda x: x.hdr_offset)
    kb = sorted(wb.blocks, key=lambda x: x.hdr_offset)
    assert len(kc) == len(kb)
    for a, c in zip(kc, kb):
        assert (a.unit, a.seq, a.n_records, a.flags, a.data) == \
               (c.unit, c.seq, c.n_records, c.flags, c.data)
    assert wc.end_offset == wb.end_offset
    assert wc.end_record[:10] == wb.end_record[:10]           # the end record proper
    assert len(wb.end_record) <= len(wc.end_record)           # batch re-frames once, not N times

    def bfi(p):
        e = next(e for e in read_entries(p) if e.entry_type == "stream" and e.path == "BasicFileInfo")
        return identity_report(e.data)
    rc, rb = bfi(cur), bfi(bout)
    assert {k for k in set(rc) | set(rb) if rc.get(k) != rb.get(k)} <= {"last_save_path"}


def test_authoring_failure_stops_the_batch_there(tmp_path):
    """Chain semantics: family 2 cannot be built -> family 1 is written and
    loaded, family 2 (and after) are reported not-ok, stop_reason names it."""
    from rvt.famgen import loader as L

    def broken(start_id):
        raise ValueError("no catalog facts for this rating")
    out = str(tmp_path / "partial.rvt")
    res = L.load_families_into_project(BASE26, out, [_factory(0), broken, _factory(2)],
                                       validate=False)
    assert not res.ok
    assert res.n_loaded == 1 and res.culprit == 1
    assert res.loads[0].ok and res.loads[0].plan is not None
    assert not res.loads[1].ok and "no catalog facts" in res.loads[1].stop_reason
    assert len(res.loads) == 2                      # family 3 never attempted
    assert "family 2/3" in res.stop_reason and "ValueError" in res.stop_reason
    assert os.path.isfile(out)


def test_nothing_loadable_writes_no_file(tmp_path):
    from rvt.famgen import loader as L

    def broken(start_id):
        raise ValueError("boom")
    out = str(tmp_path / "none.rvt")
    res = L.load_families_into_project(BASE26, out, [broken], validate=False)
    assert not res.ok and res.n_loaded == 0 and res.culprit == 0
    assert res.out_path is None and not os.path.exists(out)
    assert "family 1/1" in res.stop_reason


def test_write_step_failure_is_attributed_and_writes_no_file(tmp_path, monkeypatch):
    """A per-family step of the SHARED host write failing (here: family 2's
    unit splice) writes no file, blames that family (``culprit``), and marks
    the others 'not written' -- the caller can retry without it."""
    from rvt.famgen import loader as L, factory as F
    real = F.splice_save_unit
    calls = {"n": 0}

    def flaky_splice(logical, unit_bytes):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("walker error on this unit")
        return real(logical, unit_bytes)
    monkeypatch.setattr(F, "splice_save_unit", flaky_splice)
    out = str(tmp_path / "w.rvt")
    res = L.load_families_into_project(BASE26, out, [_factory(i) for i in range(3)],
                                       validate=False)
    assert not res.ok and res.out_path is None and res.culprit == 1
    assert not os.path.exists(out) and not os.path.exists(out + ".pass1.tmp")
    assert "family 2/3" in res.stop_reason and "unit splice failed" in res.stop_reason
    assert [r.ok for r in res.loads] == [False, False, False]
    assert res.loads[1].stop_reason == res.stop_reason
    assert res.loads[0].stop_reason.startswith("not written")
    assert res.shared["write_error"] == res.stop_reason


def test_stage_load_keeps_the_prefix_before_a_write_time_culprit(tmp_path, monkeypatch):
    """The reviewer's scenario on #256: families 1..k-1 fine, family k breaks
    the shared write.  The front door retries with the prefix before k --
    k-1 families delivered, two host passes, blocker names family k."""
    from rvt.frontdoor import build as B, prompt_intent as PP
    from rvt.frontdoor.base import resolve_base
    from rvt.famgen import factory as F
    R = B.load_ifc_room_module()
    model, _parsed = PP.prompt_to_intent("an electrical room with 3 panels")
    order = R._load_order(model)
    real = F.splice_save_unit
    calls = {"n": 0}

    def flaky_splice(logical, unit_bytes):
        calls["n"] += 1
        if calls["n"] == 3:                    # family 3's unit, first pass
            raise RuntimeError("walker error on this unit")
        return real(logical, unit_bytes)
    monkeypatch.setattr(F, "splice_save_unit", flaky_splice)
    stages = tmp_path / "_stages"
    stages.mkdir()
    rec = B.stage_load_batched(model, resolve_base(None).path, str(stages), R)
    assert rec["n_loaded"] == 2 and rec["n_planned"] == 3
    assert rec["host_passes"] == 2
    assert list(rec["loaded"]) == order[:2]
    assert rec["blocker"].startswith(f"{order[2]}: ") and "unit splice failed" in rec["blocker"]
    assert [(e["tag"], e["ok"]) for e in rec["loads"]] == \
        [(order[0], True), (order[1], True), (order[2], False)]
    assert os.path.isfile(rec["_current"]) and rec["_current"].endswith("stage_L_loaded.rvt")


def test_stage_load_sheds_the_last_family_when_the_culprit_is_unknown(tmp_path, monkeypatch):
    """A host-write crash the loader cannot pin on one family: shed the last
    family and try again (never drop the whole batch)."""
    from rvt.frontdoor import build as B, prompt_intent as PP
    from rvt.frontdoor.base import resolve_base
    from rvt.famgen import loader as L
    R = B.load_ifc_room_module()
    model, _parsed = PP.prompt_to_intent("an electrical room with 3 panels")
    order = R._load_order(model)
    real = L._commit_and_write

    def crash_at_three(host_rvt, out_path, host, authored, new_latest, cd_new):
        if len(authored) == 3:
            raise RuntimeError("disk hiccup")
        return real(host_rvt, out_path, host, authored, new_latest, cd_new)
    monkeypatch.setattr(L, "_commit_and_write", crash_at_three)
    stages = tmp_path / "_stages"
    stages.mkdir()
    rec = B.stage_load_batched(model, resolve_base(None).path, str(stages), R)
    assert rec["n_loaded"] == 2 and rec["host_passes"] == 2
    assert list(rec["loaded"]) == order[:2]
    assert rec["blocker"].startswith(f"{order[2]}: host write failed: RuntimeError: disk hiccup")
    assert [e["ok"] for e in rec["loads"]] == [True, True, False]


def test_single_loader_report_shape_is_unchanged(tmp_path):
    """The single loader now runs on the shared helpers; its proofs keep the
    historical keys (tests/tools read them)."""
    from rvt.famgen import loader as L
    out = str(tmp_path / "single.rvt")
    res = L.load_family_into_project(BASE26, out, place=False, validate=True)
    assert res.ok, res.stop_reason
    for k in ("plan", "roundtrip_gate", "embedded_adocument", "save_unit",
              "adocument_registrations", "adocument_reencode", "content_documents",
              "pass1_commit", "pass2_partition_splice", "verify_written"):
        assert k in res.proofs, k
    assert isinstance(res.proofs["adocument_registrations"], dict)
    assert isinstance(res.proofs["pass2_partition_splice"], dict)
    v = res.proofs["verify_written"]
    for k in ("container", "structure_layer", "partition", "elemtable", "adocument",
              "family_documents", "provenance_ours", "validate", "ok"):
        assert k in v, k
    assert v["partition"]["our_unit_index"] is not None
    assert v["elemtable"]["our_host_ids_present"] is True
    assert v["adocument"]["clean"] and v["adocument"]["content_table_record"]
    assert v["family_documents"]["ok"] and v["family_documents"]["total_host_families"] >= 1
    assert "per_plan" not in v and "file_ok" not in v
    assert res.acceptance and res.acceptance[0].startswith("H1:")


def test_batch_on_the_2025_base_validates_under_its_own_release(tmp_path):
    from rvt.famgen import loader as L
    from rvt.famload import four_registry_census
    from rvt.frontdoor import release_ctx as RC
    out = str(tmp_path / "b25.rvt")
    res = L.load_families_into_project(BASE25, out, [_factory(0), _factory(1)], validate=True)
    assert res.ok, res.stop_reason
    assert res.n_loaded == 2
    assert V.detect_release(out) == 2025
    vw = res.shared["verify_written"]
    assert vw["validate"]["verdict"] == "VALID" and vw["validate"]["n_errors"] == 0
    with RC.host_release_context(out):
        census = four_registry_census(out)
    assert census["coherent"] is True, census
    assert census["save_units"] == four_registry_census(BASE25)["save_units"] + 2


# ---------------------------------------------------------------------------
# the front door: stage timings + one host pass for a multi-family prompt
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fd_job(tmp_path_factory):
    import rvt.frontdoor as FD
    out = str(tmp_path_factory.mktemp("fd") / "room2")
    r = FD.author(prompt="an electrical room with 2 panels", out=out, no_handoff=True)
    return r


def test_manifest_stages_carry_seconds(fd_job):
    r = fd_job
    assert r.ok, (r.status, r.errors)
    stages = r.manifest["build"]["stages"]
    assert stages, "build.stages must reach the manifest"
    names = [s["stage"] for s in stages]
    for want in ("F", "L", "W", "E", "V"):
        assert want in names, names
    for s in stages:
        if s["stage"] == "release-context":
            continue
        assert isinstance(s.get("seconds"), (int, float)), s
        assert s["seconds"] >= 0
    v = next(s for s in stages if s["stage"] == "V")
    assert set(v["gates"]) >= {"validate", "census", "identity", "status_gate"}
    total = r.manifest["build"]["seconds"]
    assert sum(s["seconds"] for s in stages if s["stage"] != "release-context") <= total + 1.0


def test_multi_family_prompt_loads_in_one_host_pass(fd_job):
    r = fd_job
    build = r.manifest["build"]
    lstage = next(s for s in build["stages"] if s["stage"] == "L")
    assert lstage["host_passes"] == 1
    assert lstage["n_loaded"] == lstage["n_planned"] == 2
    assert lstage["mode"].startswith("batched")
    load = build["load"]
    assert load["n_loaded"] == 2 and not load.get("blocker")
    assert [e["ok"] for e in load["loads"]] == [True, True]
    assert load["loads"][1]["host_watermark"] > load["loads"][0]["symbol_id"]
    # one load intermediate, not one per family (stage P's identity-stamped
    # base and the walls stage are the only other intermediates)
    stages_dir = os.path.join(r.manifest["out_dir"] if os.path.isabs(r.manifest["out_dir"])
                              else os.path.join(ROOT, r.manifest["out_dir"]), "_stages")
    rvts = sorted(f for f in os.listdir(stages_dir) if f.endswith(".rvt"))
    assert rvts == ["stage_L_loaded.rvt", "stage_P_identity.rvt", "stage_W_walls.rvt"], rvts
    # and the deliverable is whole: 2 rfa + 2 loaded + 2 placed + walls, VALID 0 errors
    kinds = [c["kind"] for c in build["elements_created"]]
    assert kinds.count("family(.rfa)") == 2 and kinds.count("loaded-family") == 2
    assert kinds.count("equipment-instance") == 2 and kinds.count("wall") == 4
    g = build["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID" and g["validate"]["n_errors"] == 0
    assert g["census"].get("coherent") is not False and g["self_checks_ok"] is True


def test_stage_load_degrades_to_the_deepest_good_prefix(tmp_path, monkeypatch):
    """The front door's degrade policy lives in ``stage_load_batched``: a
    family that cannot be built stops the load THERE, the families before it
    are the deliverable (one host pass), the blocker names the family."""
    from rvt.frontdoor import build as B
    R = B.load_ifc_room_module()
    real = R.build_product

    def flaky(plan, **kw):
        if plan.tag == order[1]:
            raise ValueError("no catalog facts for this rating")
        return real(plan, **kw)
    from rvt.frontdoor import prompt_intent as PP
    model, _parsed = PP.prompt_to_intent("an electrical room with 3 panels")
    order = R._load_order(model)
    assert len(order) == 3
    monkeypatch.setattr(R, "build_product", flaky)
    stages = tmp_path / "_stages"
    stages.mkdir()
    from rvt.frontdoor.base import resolve_base
    base = resolve_base(None)
    rec = B.stage_load_batched(model, base.path, str(stages), R)
    assert rec["n_loaded"] == 1 and rec["n_planned"] == 3
    assert rec["host_passes"] == 1
    assert rec["blocker"].startswith(f"{order[1]}: ") and "no catalog facts" in rec["blocker"]
    assert list(rec["loaded"]) == [order[0]]
    assert [e["tag"] for e in rec["loads"]] == [order[0], order[1]]
    assert rec["loads"][0]["ok"] is True and rec["loads"][1]["ok"] is False
    assert rec["_current"].endswith("stage_L_loaded.rvt") and os.path.isfile(rec["_current"])
    assert set(rec["_loaded"][order[0]]) >= {"symbol_id", "family_id", "content_guid", "product"}


def test_surface_bench_reads_the_breakdown(fd_job):
    import surface_bench as SB
    r = fd_job
    res_json = {"manifest": {"json": os.path.join(
        r.manifest["out_dir"] if os.path.isabs(r.manifest["out_dir"])
        else os.path.join(ROOT, r.manifest["out_dir"]), "manifest.json")}}
    bd = SB.stage_breakdown(res_json, envelope={"go": {"job_seconds": 3.21}})
    assert bd["job_seconds"] == 3.21
    assert isinstance(bd["build_seconds"], (int, float))
    lrow = next(s for s in bd["stages"] if s["stage"] == "L")
    assert lrow["host_passes"] == 1 and isinstance(lrow["seconds"], (int, float))
    text = SB._fmt_breakdown(bd)
    assert text.startswith("job 3.2s = ") and "L " in text and "(1 pass, 2/2)" in text
    assert "go-author-6panels" in SB.JOBS and "go-author-6panels" in SB.JOB_ORDER
