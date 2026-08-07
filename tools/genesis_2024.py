#!/usr/bin/env python
"""genesis_2024.py -- THE 2024 REDUCTION LADDER (genesis-2024-reduce stream).

Re-runs the CERTIFIED genesis recipe (rstbasic -> R-rungs -> K3 -> K4) on
Autodesk's Revit-2024 rst basic sample, producing the 2024 family-free base
candidate ``B2024_K4.rvt``.  Precedent: the SAME recipe, mechanized the same
way by tools/genesis_2025.py, was viewer-certified for 2025 in ONE round
(docs/inbox/genesis-audit.md ORCHESTRATOR VERDICTS #28: control + R9_2025 +
K3_2025 + B2025_K4 all PASS) -- the certified-2026 recipe transfers
wholesale across releases.

Everything runs inside :func:`release_context` -- the GENERALIZED form of
genesis_2025's ``context_2025``: ``rvt.versions.reading(<file>)`` (the six
partition-framing ordinals resolved BY NAME from the file's OWN schema)
plus the patch set for the seven module-LOCAL copies of those ordinals the
emitting tools keep (`_LOCAL_TAG_PATCHES` -- the genesis-2025-plan SS7
"baked 2026 literal" risk, found real in seven places and re-used verbatim
here).  ``context_2024`` binds it to the 2024 sample and ASSERTS the file
really is 2024 first.  Nothing in the patch set is release-specific: the
values all come from the active ordinals, so the same helper serves 2024,
2025 and any future release (refactor proposal in
docs/inbox/genesis-2024-reduce.md -- genesis_2025.py is NOT edited).

The ladder (each rung: tools/rvt_validate.py 0 errors +
``rvt.reduce_law.assert_edit_free`` + the FOUR-registry census + a RELEASE
gate: ``versions.detect_release`` == 2024 and every partition block header
carries the 2024 SegmentMarker ordinal 0x0e7c):

  R5_2024   sample minus annotation / detail-line / schedule content (maxgc)
  R6_2024   + every view but one 3D + one plan, sheets/viewports/companions
  R7_2024   + unused symbols / types / materials / patterns / assets
  R8_2024   + design options, phases beyond the pinned, links, topologies
  R9_2024   + the family layer's host elements + placed model (deepest R)
  K3_2024   R9_2024 with loadable-family USAGE fields nulled (the
            M3-certified MODIFY path -- families + documents still present;
            reported via reduce_law.check_reduction, not edit-free by design)
  B2024_K4  K3_2024 minus the loadable-family layer AND all embedded family
            documents, FOUR-registry coherent (units + ContentDocuments +
            ContentTable + FamilyMgr) -- the 2024 family-free base candidate

Usage (repo root):
  .venv/bin/python tools/genesis_2024.py ladder      # R5..R9
  .venv/bin/python tools/genesis_2024.py k3k4        # K3_2024 + B2024_K4
  .venv/bin/python tools/genesis_2024.py formats     # 2024 format-data pins
  .venv/bin/python tools/genesis_2024.py stage       # probes.json + batch
  .venv/bin/python tools/genesis_2024.py all

The viewer belongs to the orchestrator: nothing here uploads.  ``stage``
writes the batch + probes.json for the certification queue (control = the
untouched 2024 sample, Autodesk's own file -- certified by construction;
it also answers "does the viewer read 2024 uploads at all?").
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import struct
import sys
import time
from collections import Counter
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import versions                                            # noqa: E402
from rvt import reduce_law                                          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt.reduce import delete_elements, verify_reduced              # noqa: E402

import rvt_reduce as RR                                             # noqa: E402
import genesis_triage as GT                                         # noqa: E402

YEAR = 2024
SRC = os.path.join(ROOT, "samples", "2024", "rstbasicsampleproject.rvt")
SAMPLES_2024 = os.path.join(ROOT, "samples", "2024")
OUT = os.path.join(ROOT, "experiments", "genesis2024")
RUNGS = os.path.join(OUT, "reduce")
FORMAT_MD = os.path.join(ROOT, "docs", "writer", "format-2024.md")
FACTS_JSON = os.path.join(OUT, "format_facts_2024.json")

RUNG_ORDER = ["R5_2024", "R6_2024", "R7_2024", "R8_2024", "R9_2024",
              "K3_2024", "B2024_K4"]

# ---------------------------------------------------------------------------
# the per-release emit context: versions.reading + the module-LOCAL copies
# ---------------------------------------------------------------------------
# rvt.versions.reading patches rvt.partitions (module globals looked up at
# call time).  These modules keep their OWN copies of the framing ordinals --
# from-imports or baked literals -- that the patch cannot reach.  The list is
# the one genesis_2025.py proved complete for a cross-release emit (2025
# ladder viewer-certified, verdicts #28); every value derives from the ACTIVE
# ordinals, so nothing here is per-release.
#   (module, attr, ordinal-name or callable(ords))


def _cd_separator(o: Dict[str, int]) -> bytes:
    return struct.pack("<HiHi", o["CONTAINER_CLASS"], -1, o["UNIT_INNER_CLASS"], -1)


def _cd_end_record(o: Dict[str, int]) -> bytes:
    return struct.pack("<HiiI", o["CONTAINER_CLASS"], 0, -1, 0)


_LOCAL_TAG_PATCHES = (
    ("rvt.reduce", "BLOCK_TAG", "BLOCK_TAG"),
    ("rvt.reduce", "BLOCK_TRL_TAG", "TRAILER_TAG"),
    ("rvt.manipulate", "BLOCK_TAG", "BLOCK_TAG"),
    ("rvt.manipulate", "TRAILER_TAG", "TRAILER_TAG"),
    ("rvt.commit", "BLOCK_TRL_TAG", "TRAILER_TAG"),
    ("rvt.writer", "BLOCK_TRL_TAG", "TRAILER_TAG"),
    ("rvt.famgen.factory", "CD_SEPARATOR", _cd_separator),
    ("rvt.famgen.factory", "CD_END_RECORD", _cd_end_record),
)


@contextmanager
def release_context(src: str):
    """versions.reading(src) + every module-local framing-tag copy patched +
    rvt.adocument's cached decoder bound to the file's OWN schema.  Restores
    everything on exit; yields the active ordinals.

    GENERAL: works for any release, because every patched value derives from
    the ordinals ``versions.reading`` resolves by name from ``src``'s own
    ``Formats/Latest`` (this is genesis_2025.context_2025 with the source
    file as the only parameter -- proposed as the shared helper both ladders
    should import; see docs/inbox/genesis-2024-reduce.md)."""
    import importlib
    from rvt import adocument as adoc
    from rvt.adocument import ADocumentDecoder
    with versions.reading(src) as ords:
        prev: List[Tuple[Any, str, Any]] = []
        for mod_name, attr, spec in _LOCAL_TAG_PATCHES:
            mod = importlib.import_module(mod_name)
            prev.append((mod, attr, getattr(mod, attr)))
            val = spec(ords) if callable(spec) else ords[spec]
            setattr(mod, attr, val)
        prev.append((adoc, "_DECODER", adoc._DECODER))
        adoc._DECODER = ADocumentDecoder(versions.schema_of(src))
        try:
            yield ords
        finally:
            for mod, attr, val in reversed(prev):
                setattr(mod, attr, val)


@contextmanager
def context_2024(src: str = SRC):
    """The 2024-pinned entry point: :func:`release_context` on a file that is
    ASSERTED to be Revit 2024 first (so the ladder can never silently run on
    the wrong release's sample)."""
    yr = versions.detect_release(src)
    if yr != YEAR:
        raise versions.VersionError(
            f"context_2024: {src} detects as Revit {yr}, not {YEAR}")
    with release_context(src) as ords:
        if ords != dict(versions.KNOWN_RELEASES[YEAR].framing):
            raise versions.VersionError(
                f"context_2024: active ordinals {ords} != the pinned 2024 "
                f"framing table")
        yield ords


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_report(name: str, rep: dict) -> str:
    os.makedirs(RUNGS, exist_ok=True)
    p = os.path.join(RUNGS, f"{name}.json")
    with open(p, "w") as fh:
        json.dump(rep, fh, indent=1,
                  default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    return p


def law_gate_reduction(before_doc: Document, after_path: str, *,
                       before_label: str, after_label: str) -> dict:
    """THE GUARD on a reduction rung: rvt.reduce_law.assert_edit_free.
    Raises SurvivorEditedError on any edited survivor / added id."""
    after_doc = Document.from_file(after_path)
    rep = reduce_law.assert_edit_free(before_doc, after_doc,
                                      before_label=before_label,
                                      after_label=after_label)
    return {"verdict": rep.verdict, "ok": rep.ok, "removed": rep.removed,
            "added": len(rep.added), "common": rep.common,
            "survivors_edited": len(rep.survivors_edited),
            "summary": rep.summary()}


def four_registry_census(path: str) -> dict:
    """genesis_triage.census under the active 2024 context: class census +
    save_units / ContentDocuments entries / ContentTable records / FamilyMgr
    entries+GUIDs -- the four document registries the reader wants coherent."""
    cen = GT.census(path)
    su, cd, ct = cen.get("save_units"), cen.get("contentdocs_entries"), cen.get("contenttable_records")
    fm_guids = cen.get("familymgr_doc_guids")
    cen["four_registry_coherent"] = (
        su is not None and cd is not None and ct is not None
        and (su - 1) == cd == ct
        and (fm_guids is None or fm_guids == cd))
    return cen


def release_gate(path: str) -> dict:
    """The per-rung RELEASE proof: (a) ``versions.detect_release`` reads the
    emitted file as 2024 (BasicFileInfo Format year); (b) on disk, the
    complete set of partition block-header tags is exactly the 2024
    SegmentMarker ordinal {0x0e7c} -- no 2026 (or 2025) tag survived the
    emit.  Runs under its own reading() so it is context-independent."""
    want = versions.KNOWN_RELEASES[YEAR].framing["BLOCK_TAG"]
    detected = versions.detect_release(path)
    with versions.reading(path):
        from rvt.partitions import StreamWalker
        with open_rvt(path) as f:
            raw = f.logical(f.partition_streams()[0])
            w = StreamWalker(raw, inflate=False, keep_data=False)
            tags = {struct.unpack_from("<H", raw, b.hdr_offset)[0]
                    for b in w.blocks}
            rep = {"detected_release": detected,
                   "block_header_tags": sorted(hex(t) for t in tags),
                   "blocks": len(w.blocks), "units": len(w.units),
                   "walker_errors": len(w.errors)}
    rep["ok"] = (detected == YEAR and tags == {want}
                 and rep["walker_errors"] == 0)
    return rep


def _validator(path: str) -> dict:
    return RR._run_validator(path)


# ---------------------------------------------------------------------------
# the R-ladder (maxgc, the certified 2026 seeds re-run on the 2024 sample)
# ---------------------------------------------------------------------------
def run_r_ladder(stages: Iterable[str] = ("R5", "R6", "R7", "R8", "R9")) -> List[dict]:
    os.makedirs(RUNGS, exist_ok=True)
    results = []
    with context_2024(SRC):
        st = RR.build_state_v2(SRC)
        sample_doc = st["doc"]
        for stage in stages:
            name = f"{stage}_{YEAR}"
            t0 = time.time()
            seed = RR._protect_history(st, RR.stage_seed_v2(stage, st))
            delete, kept, ev = RR.maxgc(st, seed)
            out = os.path.join(RUNGS, f"{name}.rvt")
            rrep = delete_elements(SRC, out, delete)
            v = verify_reduced(out, delete)
            val = _validator(out)
            law = law_gate_reduction(sample_doc, out,
                                     before_label=f"rstbasic-{YEAR} (sample)",
                                     after_label=name)
            cen = four_registry_census(out)
            rel = release_gate(out)
            res = {
                "rung": name, "ladder": str(YEAR), "release": YEAR,
                "recipe": f"the certified 2026 {stage} seed (rvt_reduce.stage_seed_v2) "
                          f"re-run on samples/2024/rstbasicsampleproject.rvt under "
                          f"rvt.versions.reading + context_2024",
                "parent": relp(SRC), "parent_rung": "sample",
                "out": relp(out), "file_size": os.path.getsize(out),
                "seed": len(seed), "seed_kept_pinned": len(kept),
                "deleted": len(delete),
                "surviving_elements": rrep.elemtable_count_after,
                "deleted_by_class": Counter(
                    st["cls_of"].get(e, "?") for e in delete).most_common(40),
                "structural_ok": bool(v["ok"]),
                "validator": val,
                "reduce_law": law,
                "census": cen,
                "release_gate": rel,
                "latest_dangling": len(st["ext"]["Global/Latest"] & delete),
                "seconds": round(time.time() - t0, 1),
            }
            write_report(name, res)
            log(f"[{name}] deleted {len(delete):,} / kept "
                f"{rrep.elemtable_count_after:,} | {res['file_size']:,} B | "
                f"structural={v['ok']} validator_ok={val['ok']} (errors "
                f"{val['errors']}) | law={law['verdict']} | units "
                f"{cen.get('save_units')} CD {cen.get('contentdocs_entries')} "
                f"CT {cen.get('contenttable_records')} FM "
                f"{cen.get('familymgr_doc_guids')} | release "
                f"{rel['detected_release']} tags {rel['block_header_tags']} | "
                f"{res['seconds']}s")
            if not (v["ok"] and val["ok"] and val["errors"] == 0 and law["ok"]
                    and rel["ok"]):
                res["FAILED_SELF_CHECK"] = True
                write_report(name, res)
                raise SystemExit(f"[{name}] SELF-CHECK FAILED -- ladder stops: "
                                 f"{val.get('error_messages')} release_gate={rel}")
            results.append(res)
    return results


# ---------------------------------------------------------------------------
# K3_2024 (modify: loadable-family usage nulls) + B2024_K4 (family-free base)
# ---------------------------------------------------------------------------
def run_k3_k4() -> List[dict]:
    r9 = os.path.join(RUNGS, f"R9_{YEAR}.rvt")
    if not os.path.exists(r9):
        raise SystemExit(f"R9_{YEAR}.rvt missing -- run the ladder first")
    results = []
    with context_2024(SRC):
        st9 = RR.build_state_v2(r9)
        r9_doc = st9["doc"]

        # ---- K3_2024: usage nulls (the M3-certified MODIFY path) ----------
        t0 = time.time()
        lay = GT.family_layer(st9)
        F = lay["ids"]
        k3 = os.path.join(RUNGS, f"K3_{YEAR}.rvt")
        pol = reduce_law.law_policy().permits("neutralise-referrers", "research-probe")
        nrep = GT.neutralise_referrers(st9, F, k3, name=f"K3_{YEAR}")
        val3 = _validator(k3)
        cen3 = four_registry_census(k3)
        rel3 = release_gate(k3)
        k3_doc = Document.from_file(k3)
        # the law instrument, non-raising: K3 is a MODIFY rung by design
        # (exactly the certified K3 recipe -- viewer-certified for 2026
        # round 5 AND for 2025 in verdicts #28); every edit must be one of
        # the neutralised referrers, nothing added/removed.
        chk = reduce_law.check_reduction(r9_doc, k3_doc,
                                         before_label=f"R9_{YEAR}",
                                         after_label=f"K3_{YEAR}")
        edited_ids = {e.id for e in chk.survivors_edited}
        neutralised_ids = {e["id"] for e in nrep["edits"] if e.get("n_edits")}
        law3 = {
            "kind": "modify (usage-null), NOT a reduction -- reduce_law policy: "
                    f"{pol.reason[:120]}",
            "verdict": chk.verdict, "removed": chk.removed, "added": len(chk.added),
            "survivors_edited": len(chk.survivors_edited),
            "edits_are_exactly_the_neutralised_referrers":
                edited_ids == neutralised_ids,
            "edited_not_neutralised": sorted(edited_ids - neutralised_ids)[:10],
            "neutralised_not_edited": sorted(neutralised_ids - edited_ids)[:10],
            "edit_classes": Counter(e.class_name for e in chk.survivors_edited
                                    ).most_common(30),
        }
        rep3 = {
            "rung": f"K3_{YEAR}", "kind": "modify (usage-null)",
            "parent": relp(r9), "parent_rung": f"R9_{YEAR}", "out": relp(k3),
            "file_size": os.path.getsize(k3),
            "recipe": f"genesis_triage K3 re-run on R9_{YEAR}: every USAGE field "
                      "naming the loadable-family layer nulled (level/grid/"
                      "section/callout/viewport head symbols, struct default "
                      "column, copy-monitor map, area-report fonts...); the "
                      "layer + its embedded documents stay.  The M3-certified "
                      "modify path; the viewer certifies the STATE (2026 "
                      "precedent: K3 PASS round 5; 2025 precedent: K3_2025 "
                      "PASS verdicts #28).",
            "family_layer": {"families": lay["families"], "size": len(F),
                             "children_by_class": lay["children_by_class"],
                             "docs": lay["docs"]},
            "neutralise": {k: nrep[k] for k in
                           ("referrer_elements_edited", "edits_by_referrer_class",
                            "embedded_document_referrers_not_edited", "verify")},
            "reduce_law": law3,
            "structural_ok": bool(nrep["verify"].get("walker_errors", 1) == 0
                                  and nrep["verify"].get("crc_failures", 1) == 0
                                  and nrep["verify"].get("ecc_mismatches", 1) == 0
                                  and nrep["verify"].get("stamps_ok", False)),
            "validator": val3, "census": cen3, "release_gate": rel3,
            "seconds": round(time.time() - t0, 1),
        }
        write_report(f"K3_{YEAR}", rep3)
        log(f"[K3_{YEAR}] layer {len(F):,} elements ({len(lay['families'])} "
            f"loadable families); referrers edited "
            f"{nrep['referrer_elements_edited']}; edits==neutralised: "
            f"{law3['edits_are_exactly_the_neutralised_referrers']}; "
            f"validator_ok={val3['ok']} (errors {val3['errors']}); units "
            f"{cen3.get('save_units')} CD {cen3.get('contentdocs_entries')} "
            f"CT {cen3.get('contenttable_records')} FM "
            f"{cen3.get('familymgr_doc_guids')}; release "
            f"{rel3['detected_release']} tags {rel3['block_header_tags']}; "
            f"{rep3['seconds']}s")
        if not (rep3["structural_ok"] and val3["ok"] and val3["errors"] == 0
                and law3["edits_are_exactly_the_neutralised_referrers"]
                and chk.removed == 0 and not chk.added and rel3["ok"]):
            rep3["FAILED_SELF_CHECK"] = True
            write_report(f"K3_{YEAR}", rep3)
            raise SystemExit(f"[K3_{YEAR}] SELF-CHECK FAILED: {val3.get('error_messages')}")
        results.append(rep3)

        # ---- B2024_K4: family layer + ALL documents out, 4-registry -------
        t0 = time.time()
        _ranges, guid_of_unit = GT._unit_guid_map(k3)
        all_guids = set(guid_of_unit)
        tmp = os.path.join(RUNGS, ".B2024_K4_docs_removed.rvt")
        rrep = GT.remove_documents(k3, tmp, all_guids,
                                   reconcile_contenttable=True,
                                   reconcile_familymgr=True)
        st_tmp = RR.build_state_v2(tmp)
        L = {e for e in F if e in st_tmp["host"]}
        L |= {e for e in st_tmp["host"]
              if st_tmp["cls_of"].get(e) == "LegendComponent"}
        L = RR._protect_history(st_tmp, L)
        delete, kept, ev = RR.maxgc(st_tmp, L)
        out = os.path.join(RUNGS, "B2024_K4.rvt")
        delete_elements(tmp, out, delete)
        os.remove(tmp)
        resid = GT._residual_guid_hits(out, all_guids)
        v = verify_reduced(out, delete)
        val4 = _validator(out)
        cen4 = four_registry_census(out)
        rel4 = release_gate(out)
        law4 = law_gate_reduction(k3_doc, out, before_label=f"K3_{YEAR}",
                                  after_label="B2024_K4")
        rep4 = {
            "rung": "B2024_K4", "kind": "documents+family-layer removal",
            "parent": relp(k3), "parent_rung": f"K3_{YEAR}", "out": relp(out),
            "file_size": os.path.getsize(out),
            "recipe": f"genesis_triage K4 re-run on K3_{YEAR}: every embedded "
                      "family document removed FOUR-registry coherent (save "
                      "units spliced + ContentDocuments entries + ADocument "
                      "ContentTable records + FamilyMgr loaded-family entries) "
                      "then the loadable-family layer deleted by maxgc -- the "
                      "2024 family-free base candidate.",
            "documents_removed": len(all_guids),
            "removal": {k: rrep.get(k) for k in
                        ("units_before", "units_after", "cd_entries_before",
                         "cd_entries_after", "contenttable_records_before",
                         "contenttable_records_after", "familymgr_entries_before",
                         "familymgr_entries_after", "familymgr_doc_guids_removed",
                         "latest_payload_before", "latest_payload_after")},
            "residual_guid_bytes_in_Latest_and_ContentDocuments": sum(resid.values()),
            "layer_gc": {"seed": len(L), "deleted": len(delete),
                         "kept_pinned": len(kept),
                         "deleted_by_class": Counter(
                             st_tmp["cls_of"].get(e, "?") for e in delete
                         ).most_common(40)},
            "structural_ok": bool(v["ok"]),
            "validator": val4, "reduce_law": law4, "census": cen4,
            "release_gate": rel4,
            "seconds": round(time.time() - t0, 1),
        }
        write_report("B2024_K4", rep4)
        log(f"[B2024_K4] docs removed {len(all_guids)} (units "
            f"{rrep['units_before']}->{rrep['units_after']}, CD "
            f"{rrep['cd_entries_before']}->{rrep['cd_entries_after']}, CT "
            f"{rrep.get('contenttable_records_before')}->"
            f"{rrep.get('contenttable_records_after')}, FM "
            f"{rrep.get('familymgr_entries_before')}->"
            f"{rrep.get('familymgr_entries_after')}); layer deleted "
            f"{len(delete):,}; {rep4['file_size']:,} B; structural={v['ok']} "
            f"validator_ok={val4['ok']} (errors {val4['errors']}); law="
            f"{law4['verdict']}; residual-guid-bytes {sum(resid.values())}; "
            f"units {cen4.get('save_units')} CD {cen4.get('contentdocs_entries')} "
            f"CT {cen4.get('contenttable_records')} FM "
            f"{cen4.get('familymgr_doc_guids')} coherent="
            f"{cen4.get('four_registry_coherent')}; release "
            f"{rel4['detected_release']} tags {rel4['block_header_tags']}; "
            f"{rep4['seconds']}s")
        if not (v["ok"] and val4["ok"] and val4["errors"] == 0 and law4["ok"]
                and sum(resid.values()) == 0 and cen4.get("four_registry_coherent")
                and rel4["ok"]):
            rep4["FAILED_SELF_CHECK"] = True
            write_report("B2024_K4", rep4)
            raise SystemExit(f"[B2024_K4] SELF-CHECK FAILED: {val4.get('error_messages')}")
        results.append(rep4)
    return results


# ---------------------------------------------------------------------------
# the 2024 format-data pins (what the creation side needs, three-release now)
# ---------------------------------------------------------------------------
def _class_diff(sch_new, sch_old, label_new: str, label_old: str) -> dict:
    n_new = {c.name for c in sch_new.classes}
    n_old = {c.name for c in sch_old.classes}
    shared = n_new & n_old
    renumbered = sorted(n for n in shared
                        if sch_new.by_name[n].type_id != sch_old.by_name[n].type_id)
    return {
        f"classes_{label_new}": len(sch_new.classes),
        f"classes_{label_old}": len(sch_old.classes),
        "shared_names": len(shared),
        "renumbered_shared": len(renumbered),
        "same_ordinal_shared": len(shared) - len(renumbered),
        f"only_in_{label_new}": sorted(n_new - n_old),
        f"only_in_{label_old}": sorted(n_old - n_new),
    }


def _corpus_of(path: str) -> dict:
    import latest_map as LM
    with open_rvt(path) as f:
        payload = f.inflate("Global/Latest")
    tables = LM.find_json_tables(payload)
    bodies = b"".join(payload[t["start"]:t["end"]] for t in tables)
    return {
        "tables": [{"count": t["count"], "bytes": t["end"] - t["start"],
                    "sha256_16": t["sha256_16"]} for t in tables],
        "total_pairs": sum(t["count"] for t in tables),
        "total_bytes": len(bodies),
        "corpus_sha256": sha256_of(bodies),
    }


def collect_format_facts() -> dict:
    from rvt.schema import parse as parse_schema
    from rvt.stream_encoders import (decode_basic_file_info, decode_elemtable,
                                     decode_history)

    facts: Dict[str, Any] = {"generated_by": "tools/genesis_2024.py formats",
                             "primary_sample": relp(SRC)}
    s25_path = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
    s26_path = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

    # ---- 1. Formats/Latest: pin + class-list diffs vs 2025 AND 2026 -------
    with open_rvt(SRC) as f:
        blob24 = f.concat("Formats/Latest")
    with open_rvt(s25_path) as f:
        blob25 = f.concat("Formats/Latest")
    with open_rvt(s26_path) as f:
        blob26 = f.concat("Formats/Latest")
    sch24 = parse_schema(blob24, source=SRC)
    sch25 = parse_schema(blob25, source=s25_path)
    sch26 = parse_schema(blob26, source=s26_path)
    facts["formats_latest_2024"] = {
        "size": len(blob24), "sha256": sha256_of(blob24),
        "classes": len(sch24.classes),
        "pin_matches_rvt_versions": (
            sha256_of(blob24) == versions.KNOWN_RELEASES[YEAR].schema_sha256
            and len(blob24) == versions.KNOWN_RELEASES[YEAR].schema_size),
    }
    facts["class_diff_2025_to_2024"] = _class_diff(sch25, sch24, "2025", "2024")
    facts["class_diff_2026_to_2024"] = _class_diff(sch26, sch24, "2026", "2024")
    # byte-identical across all six 2024 samples?
    schema_hashes = {}
    for fn in sorted(os.listdir(SAMPLES_2024)):
        if not fn.endswith(".rvt"):
            continue
        with open_rvt(os.path.join(SAMPLES_2024, fn)) as f:
            schema_hashes[fn] = sha256_of(f.concat("Formats/Latest"))
    facts["formats_latest_2024"]["identical_across_six_samples"] = (
        len(set(schema_hashes.values())) == 1)
    facts["formats_latest_2024"]["per_sample_sha256"] = schema_hashes

    # ---- 2. ESSchemaStorage / Global/Latest product corpus (3 releases) ---
    corpus = {}
    for fn in sorted(os.listdir(SAMPLES_2024)):
        if not fn.endswith(".rvt"):
            continue
        corpus[fn] = _corpus_of(os.path.join(SAMPLES_2024, fn))
    shas = {v["corpus_sha256"] for v in corpus.values()}
    primary = corpus[os.path.basename(SRC)]
    facts["esschema_corpus_2024"] = {
        "byte_identical_across_six_samples": len(shas) == 1,
        "corpus_sha256": primary["corpus_sha256"],
        "total_bytes": primary["total_bytes"],
        "total_pairs": primary["total_pairs"],
        "tables": primary["tables"],
        "per_sample": corpus,
        # the same instrument on the 2025 + 2026 rst samples: counsel C4 now
        # names THREE per-release corpora
        "corpus_2025_reference": _corpus_of(s25_path),
        "corpus_2026_reference": _corpus_of(s26_path),
    }

    # ---- 3. identity / footer / version markers (3 releases) --------------
    with open_rvt(SRC) as f:
        bfi = decode_basic_file_info(f.raw("BasicFileInfo"))
        et24 = decode_elemtable(f.inflate("Global/ElemTable"))
        hist24 = decode_history(f.inflate("Global/History"))
    with open_rvt(s25_path) as f:
        et25 = decode_elemtable(f.inflate("Global/ElemTable"))
        hist25 = decode_history(f.inflate("Global/History"))
    with open_rvt(s26_path) as f:
        et26 = decode_elemtable(f.inflate("Global/ElemTable"))
        hist26 = decode_history(f.inflate("Global/History"))
    ups = {y: list(h.get("format_versions") or [])
           for y, h in ((2024, hist24), (2025, hist25), (2026, hist26))}

    def _clsname(sch, tid):
        c = sch.by_id.get(tid)
        return c.name if c is not None else None

    facts["identity_2024"] = {
        "basicfileinfo_format": bfi.get("format"),
        "basicfileinfo_build": bfi.get("build"),
        "elemtable_class_tag": {"2024": hex(et24["class_tag"]),
                                "2025": hex(et25["class_tag"]),
                                "2026": hex(et26["class_tag"]),
                                "name": _clsname(sch24, et24["class_tag"])},
        "elemtable_footer_tail_class": {
            "2024": hex(et24["footer"]["tail_class"]),
            "2025": hex(et25["footer"]["tail_class"]),
            "2026": hex(et26["footer"]["tail_class"]),
            "name": _clsname(sch24, et24["footer"]["tail_class"])},
        "history_upgrade_versions": {
            "2024_last": (ups[2024][-1] if ups[2024] else None),
            "2024_count": len(ups[2024]),
            "2025_last": (ups[2025][-1] if ups[2025] else None),
            "2025_count": len(ups[2025]),
            "2026_last": (ups[2026][-1] if ups[2026] else None),
            "2026_count": len(ups[2026]),
            "identical_across_releases": (ups[2024] == ups[2025] == ups[2026]),
        },
        "history_class_tag": {"2024": hex(hist24.get("class_tag", 0)),
                              "2025": hex(hist25.get("class_tag", 0)),
                              "2026": hex(hist26.get("class_tag", 0))},
        # the format-2025.md finding, measured from the 2024 side: the
        # ADocument CLASS's version stamp in each release's own schema
        "adocument_schema_version": {
            str(y): s.by_name["ADocument"].version for y, s in
            ((2024, sch24), (2025, sch25), (2026, sch26))},
    }

    # ---- 4. framing ordinals, by-name (re-verified) -----------------------
    facts["framing_2024"] = {k: hex(v) for k, v in
                             versions.ordinals_from_schema(sch24).items()}
    facts["framing_matches_rvt_versions_table"] = (
        versions.ordinals_from_schema(sch24) == dict(versions.KNOWN_RELEASES[YEAR].framing))
    os.makedirs(OUT, exist_ok=True)
    with open(FACTS_JSON, "w") as fh:
        json.dump(facts, fh, indent=1, default=str)
    log(f"[formats] wrote {relp(FACTS_JSON)}")
    return facts


def write_format_md(facts: dict) -> str:
    fl = facts["formats_latest_2024"]
    cd25 = facts["class_diff_2025_to_2024"]
    cd26 = facts["class_diff_2026_to_2024"]
    es = facts["esschema_corpus_2024"]
    idn = facts["identity_2024"]
    ref25 = es["corpus_2025_reference"]
    ref26 = es["corpus_2026_reference"]
    L: List[str] = []
    A = L.append
    A("# FORMAT 2024 -- the pinned Revit-2024 format data the creation side needs")
    A("")
    A("Stream: **genesis-2024-reduce** (2026-08-04).  Generated by "
      "`tools/genesis_2024.py formats`; machine-readable facts in "
      f"`{relp(FACTS_JSON)}`.  Everything below is measured from the "
      "quarantined `samples/2024/` Autodesk samples (DEV-ONLY -- learn from, "
      "never ship) under `rvt.versions.reading`.  Companion docs: "
      "`docs/writer/format-2025.md` (the 2025 pins, same instruments), "
      "`docs/inbox/versions.md` (read parity + the version model), "
      "`docs/inbox/genesis-2024-reduce.md` (the 2024 ladder record).")
    A("")
    A("## 1. `Formats/Latest` -- the 2024 schema constant")
    A("")
    A(f"* size **{fl['size']:,} B**, **{fl['classes']:,} classes**, sha256 "
      f"`{fl['sha256']}`")
    A(f"* byte-identical across all six 2024 samples: "
      f"**{fl['identical_across_six_samples']}**")
    A(f"* matches the `rvt.versions.KNOWN_RELEASES[2024]` pin: "
      f"**{fl['pin_matches_rvt_versions']}**")
    A("")
    A("## 2. Class-list diffs (names are stable, ordinals drift)")
    A("")
    A("| | 2026 | 2025 | 2024 |")
    A("|---|---:|---:|---:|")
    A(f"| classes | {cd26['classes_2026']:,} | {cd25['classes_2025']:,} | "
      f"{cd26['classes_2024']:,} |")
    A(f"| shared names with 2024 | {cd26['shared_names']:,} | "
      f"{cd25['shared_names']:,} | |")
    A(f"| shared names RENUMBERED vs 2024 | {cd26['renumbered_shared']:,} | "
      f"{cd25['renumbered_shared']:,} | |")
    A(f"| shared names with the SAME ordinal as 2024 | "
      f"{cd26['same_ordinal_shared']:,} | {cd25['same_ordinal_shared']:,} | |")
    A(f"| names only in the newer release | {len(cd26['only_in_2026'])} | "
      f"{len(cd25['only_in_2025'])} | |")
    A(f"| names only in 2024 | {len(cd26['only_in_2024'])} (vs 2026) | "
      f"{len(cd25['only_in_2024'])} (vs 2025) | |")
    A("")
    A("**Consequence (the whole version model in one line): resolve every "
      "class ordinal BY NAME from the target release's schema; never carry "
      "a 2026 (or 2025) ordinal into a 2024 file.**  The six "
      "partition-framing ordinals below are the load-bearing instance.")
    A("")
    A(f"### 2a. The {len(cd25['only_in_2025'])} classes that exist in 2025 but NOT in 2024")
    A("")
    A("A genesis constructor targeting 2024 may not emit ANY of these (nor "
      "the 2026-only set below):")
    A("")
    A(", ".join(f"`{n}`" for n in cd25["only_in_2025"]) or "(none)")
    A("")
    A(f"### 2b. The {len(cd26['only_in_2026'])} classes that exist in 2026 but NOT in 2024")
    A("")
    A("Includes the conductor catalog + numbering-format machinery "
      "`rvt.genesis` constructs for 2026 (the 2025 campaign's plan SS5a.1 "
      "list is a subset -- everything 2026-only vs 2025 is also missing "
      "in 2024):")
    A("")
    A(", ".join(f"`{n}`" for n in cd26["only_in_2026"]) or "(none)")
    A("")
    A(f"### 2c. The {len(cd26['only_in_2024'])} classes that exist in 2024 but NOT in 2026"
      f" ({len(cd25['only_in_2024'])} not in 2025)")
    A("")
    A("None of these is constructed by `rvt.genesis`; they matter only to "
      "the read side, which is schema-directed anyway.")
    A("")
    A("vs 2026: " + (", ".join(f"`{n}`" for n in cd26["only_in_2024"]) or "(none)"))
    A("")
    A("vs 2025: " + (", ".join(f"`{n}`" for n in cd25["only_in_2024"]) or "(none)"))
    A("")
    A("## 3. The `ESSchemaStorage` / product-runtime corpus (Global/Latest)")
    A("")
    A("The Autodesk Forge unit/spec/parameter-group JSON corpus inside the "
      "ADocument (`ESSchemaStorage`, AppInfo slot) -- shipped PRODUCT data, "
      "byte-identical within a release.  **Counsel C4 now covers THREE "
      "releases' corpora (2024 / 2025 / 2026), one pinned constant each:**")
    A("")
    A("| release | (typeid,json) pairs | corpus bytes | sha256 |")
    A("|---|---:|---:|---|")
    A(f"| 2024 | {es['total_pairs']:,} | {es['total_bytes']:,} | `{es['corpus_sha256']}` |")
    A(f"| 2025 (same instrument, rst) | {ref25['total_pairs']:,} | "
      f"{ref25['total_bytes']:,} | `{ref25['corpus_sha256']}` |")
    A(f"| 2026 (same instrument, rst) | {ref26['total_pairs']:,} | "
      f"{ref26['total_bytes']:,} | `{ref26['corpus_sha256']}` |")
    A("")
    A(f"* byte-identical across all six 2024 samples: "
      f"**{es['byte_identical_across_six_samples']}**")
    A(f"* per-table shape (2024): " + "; ".join(
        f"{t['count']:,} pairs / {t['bytes']:,} B (`{t['sha256_16']}`)"
        for t in es["tables"]))
    A("* the corpora differ materially release-to-release: a 2024 writer "
      "must carry the 2024 corpus, never a newer one.")
    A("")
    A("## 4. Identity / footer / version markers")
    A("")
    A(f"* `BasicFileInfo` format string: **`{idn['basicfileinfo_format']}`**, "
      f"build: **`{idn['basicfileinfo_build']}`** (the RTM 2024 sample build)")
    hz = idn["history_upgrade_versions"]
    A(f"* `Global/History` upgrade-version list: 2024 ends **{hz['2024_last']}** "
      f"({hz['2024_count']} entries); identical list across 2024/2025/2026: "
      f"**{hz['identical_across_releases']}** (2025 {hz['2025_last']}/"
      f"{hz['2025_count']}, 2026 {hz['2026_last']}/{hz['2026_count']}).  "
      "This is the format-2025.md finding measured from the 2024 side: "
      "**2662 is the ADocument schema `version` stamp in all three "
      "releases' own schemas, NOT a release marker** -- the document format "
      "version froze at 2662 before 2024; the RELEASE-authoritative marker "
      "is `BasicFileInfo` `Format:` (what `rvt.versions.detect_release` "
      "keys on).  A 2024 writer writes 2662 unchanged.")
    etc = idn["elemtable_class_tag"]
    etf = idn["elemtable_footer_tail_class"]
    A(f"* `Global/ElemTable` lead class tag: 2024 `{etc['2024']}` vs 2025 "
      f"`{etc['2025']}` vs 2026 `{etc['2026']}` (= `{etc['name']}` -- an "
      "ordinal, resolved by name)")
    A(f"* `ElemTable` footer tail class: 2024 `{etf['2024']}` vs 2025 "
      f"`{etf['2025']}` vs 2026 `{etf['2026']}` (= `{etf['name']}`)")
    hc = idn["history_class_tag"]
    A(f"* `Global/History` lead class tag: 2024 `{hc['2024']}` vs 2025 "
      f"`{hc['2025']}` vs 2026 `{hc['2026']}`")
    A("")
    A("These stream-lead tags round-trip automatically through the decoders "
      "(they preserve the decoded `class_tag`); only a from-scratch 2024 "
      "stream author needs the table above.")
    A("")
    A("## 5. Partition-framing ordinals (by-name, re-verified this run)")
    A("")
    A("| constant | class | 2024 |")
    A("|---|---|---|")
    for k, v in facts["framing_2024"].items():
        A(f"| {k} | {versions.FRAMING_CLASSES[k]} | `{v}` |")
    A("")
    A(f"Matches the precomputed `rvt.versions` table: "
      f"**{facts['framing_matches_rvt_versions_table']}**")
    A("")
    A("## 6. The module-local baked-tag patch set (unchanged from 2025)")
    A("")
    A("`rvt.versions.reading` patches `rvt.partitions`; the emit path keeps "
      "module-LOCAL copies of the framing ordinals that the patch cannot "
      "reach.  The SEVEN-entry patch set genesis_2025 proved complete "
      "(2025 ladder viewer-certified, verdicts #28) is re-used verbatim by "
      "`tools/genesis_2024.py::release_context` -- nothing in it is "
      "release-specific (every value derives from the active ordinals):")
    A("")
    A("| module | attr | why |")
    A("|---|---|---|")
    A("| `rvt.reduce` | `BLOCK_TAG` (local literal 0x0F28) | `NewBlock.frame` writes block headers |")
    A("| `rvt.reduce` | `BLOCK_TRL_TAG` (from-import) | block trailer mirror |")
    A("| `rvt.manipulate` | `BLOCK_TAG`, `TRAILER_TAG` (from-imports) | the modify path re-frames blocks |")
    A("| `rvt.commit` | `BLOCK_TRL_TAG` (from-import) | commit re-frames touched blocks |")
    A("| `rvt.writer` | `BLOCK_TRL_TAG` (module constant) | reframe_blocks |")
    A("| `rvt.famgen.factory` | `CD_SEPARATOR`, `CD_END_RECORD` (bake 0x3A3/0x3A2) | ContentDocuments grammar (2024: 0x37B/0x37A) |")
    A("| `rvt.adocument` | `_DECODER` (cached 2026-schema decoder) | ADocument decode/encode must use the file's schema |")
    A("")
    A("Proposed permanent fix (versions stream / orchestrator, unchanged "
      "from the 2025 record): fold these into `rvt.versions.activate` so "
      "`reading()` covers the emit path too; until then "
      "`genesis_2024.release_context` / `genesis_2025.context_2025` are the "
      "working recipes.")
    A("")
    txt = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(FORMAT_MD), exist_ok=True)
    with open(FORMAT_MD, "w") as fh:
        fh.write(txt)
    log(f"[formats] wrote {relp(FORMAT_MD)}")
    return FORMAT_MD


# ---------------------------------------------------------------------------
# staging: probes.json (probe_batch schema) + the gated batch
# ---------------------------------------------------------------------------
def _rung_json(name: str) -> dict:
    p = os.path.join(RUNGS, f"{name}.json")
    with open(p) as fh:
        return json.load(fh)


def global_next_batch_number() -> int:
    """The next collision-free batch number, from ALL the evidence on disk:
    every batch_<n>.json manifest AND every CTRL_*_b<n>.* control filename
    under experiments/ (rounds 18..27 left controls but no manifests in the
    standard dirs, so scanning manifests alone would re-issue 18)."""
    import probe_batch as PB
    n = max(PB.next_batch_number(PB.ACCEPTANCE), PB.next_batch_number(OUT)) - 1
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "CTRL_*_b*.*"),
                       recursive=True):
        m = re.search(r"_b(\d+)\.[A-Za-z]+$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def write_probes_manifest() -> str:
    """experiments/genesis2024/probes.json -- the declaration probe_batch
    resolves bases from (BASE_KEYS: 'base'/'parent_rung'), ordered by
    information value.  Every 2024 file is a candidate-base: NOTHING 2024 is
    viewer-certified yet; certification cascades down the lineage.  R5..R8
    are built + gated but NOT staged: the 2025 precedent (whole lineage
    certified in one round, verdicts #28) says the recipe transfers, so the
    round spends its slots on the lineage spine (R9 -> K3 -> K4); the
    intermediate rungs exist on disk for bisection if R9_2024 fails."""
    entries = []
    meta = {
        "R9_2024": {
            "tests": "Round-1 anchor of the 2024 campaign AND its deepest "
                     "R-rung in one file: views/types/options/families' host "
                     "elements gone (the certified 2026/2025 R9 shape; every "
                     "embedded doc still present, censused).  K3_2024's parent.",
            "if_PASS": "certify; the 2024 reduction mechanics (re-blocker, ECC, "
                       "ordinals) are viewer-proven; K3/K4 verdicts readable.",
            "if_FAIL": "with the sample control PASSING, the 2024 EMIT path is "
                       "defective (framing/ordinal bug) -- bisect via the "
                       "on-disk R5_2024..R8_2024 rungs before reading anything "
                       "else.",
        },
        "K3_2024": {
            "tests": "Loadable-family USAGE nulled (families + documents "
                     "still present) -- the M3-certified modify path, the "
                     "mandatory parent state of B2024_K4 (precedent: K3 PASS "
                     "2026 round 5, K3_2025 PASS verdicts #28).",
            "if_PASS": "certify; B2024_K4's verdict is readable.",
            "if_FAIL": "the 2024 reader requires head/tag defaults to name "
                       "real families -- B2024_K4 unreadable until split.",
        },
        "B2024_K4": {
            "tests": "THE 2024 FAMILY-FREE BASE CANDIDATE: zero loadable "
                     "families, zero embedded family documents, FOUR-registry "
                     "coherent, on Autodesk's own 2024 skeleton (the certified "
                     "2026 K4 recipe, 2025-transfer-proven).  PASS = the "
                     "certified 2024 base the 2024 substitution ladder builds "
                     "on.",
            "if_PASS": "certify + ledger; the 2024 campaign proceeds to the "
                       "constructor retarget + substitution ladder (the "
                       "G25-3/4 pattern at 2024).",
            "if_FAIL": "(with K3_2024 passing) the 2024 reader diverges on "
                       "the family-document question -- re-run the "
                       "KD1-equivalent control before concluding anything.",
        },
    }
    parent = {"R9_2024": None, "K3_2024": "R9_2024", "B2024_K4": "K3_2024"}
    for name in ("R9_2024", "K3_2024", "B2024_K4"):
        rep = _rung_json(name)
        v = rep.get("validator", {})
        e = {
            "name": name,
            "file": rep["out"],
            "kind": "candidate-base",
            "base": rep["parent"],
            "the_ONE_thing_it_tests": meta[name]["tests"],
            "if_PASS": meta[name]["if_PASS"],
            "if_FAIL": meta[name]["if_FAIL"],
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"),
                          "warnings": v.get("warnings")},
            "structural_ok": rep.get("structural_ok"),
            "reduce_law": (rep.get("reduce_law") or {}).get("verdict"),
            "release_detected": (rep.get("release_gate") or {}).get("detected_release"),
            "elements": (rep.get("census") or {}).get("elements"),
            "coherence": {k: (rep.get("census") or {}).get(k)
                          for k in ("save_units", "contentdocs_entries",
                                    "contenttable_records", "familymgr_doc_guids")},
            "report": f"experiments/genesis2024/reduce/{name}.json",
        }
        if parent[name]:
            e["parent_rung"] = parent[name]
        entries.append(e)
    manifest = {
        "stream": "genesis-2024-reduce (the Revit-2024 reduction ladder -- "
                  "the certified 2026 recipe at its third release)",
        "situation": (
            "The certified genesis bases are Revit 2026 (G_ABPD) and, since "
            "verdicts #28, the 2025 reduction lineage (B2025_K4); a Revit-2024 "
            "user can open NEITHER (Revit never opens newer files).  This "
            "ladder re-runs the same certified recipe (rstbasic -> R-rungs -> "
            "K3 -> K4) on Autodesk's own 2024 rst basic sample under "
            "rvt.versions.reading + the proven local-tag patch set.  NOTHING "
            "2024 is viewer-certified yet, so every file here is a "
            "candidate-base; the batch control is the UNTOUCHED 2024 sample "
            "itself (Autodesk's own bytes -- certified by construction), "
            "which simultaneously answers 'does the viewer read 2024 uploads "
            "at all?'."),
        "ordering": "reading order: control (the 2024 sample) FIRST -- if it "
                    "fails, the viewer/oracle cannot read 2024 uploads and "
                    "every other verdict is VOID; then R9_2024, K3_2024, "
                    "B2024_K4 (certification cascades; a parent FAIL voids "
                    "its children; R5..R8_2024 are on disk for bisection).",
        "base": relp(SRC),
        "known_passing_anchors": {
            "sample": relp(SRC) + " (Autodesk's own file -- certified by construction)"},
        "probes": entries,
    }
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1)
    log(f"[stage] wrote {relp(p)} ({len(entries)} candidate-bases)")
    return p


def stage_batch() -> dict:
    import probe_batch as PB
    write_probes_manifest()
    files = [os.path.join(RUNGS, f"{n}.rvt")
             for n in ("R9_2024", "K3_2024", "B2024_K4")]
    for f in files:
        if not os.path.exists(f):
            raise SystemExit(f"missing rung {relp(f)} -- run ladder + k3k4 first")
    n = global_next_batch_number()
    manifest = PB.stage_batch(
        [], candidate_bases=files, control_from=relp(SRC),
        out_dir=OUT, batch_n=n,
        note=("2024 campaign round 1: every entry a candidate-base (no 2024 "
              "file is certified yet); control = the untouched Autodesk 2024 "
              "rst sample, which also answers 'does the viewer read 2024 "
              "uploads?'.  The 2025 precedent (verdicts #28: the whole "
              "lineage certified in one round) motivates staging the spine "
              "only (R9 -> K3 -> B2024_K4); R5..R8_2024 are on disk for "
              "bisection.  Read with probe_batch.read_batch_verdicts; "
              "certification cascades R9 -> K3 -> B2024_K4."))
    log(f"[stage] batch {manifest['batch']} staged into {relp(OUT)}: "
        + ", ".join(manifest["reading_order"]))
    return manifest


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["ladder", "k3k4", "formats", "stage", "all"])
    ap.add_argument("--stages", default="R5,R6,R7,R8,R9",
                    help="ladder: comma list of R stages")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.cmd in ("ladder", "all"):
        run_r_ladder([s.strip() for s in args.stages.split(",") if s.strip()])
    if args.cmd in ("k3k4", "all"):
        run_k3_k4()
    if args.cmd in ("formats", "all"):
        write_format_md(collect_format_facts())
    if args.cmd in ("stage", "all"):
        stage_batch()
    log(f"[done] {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
