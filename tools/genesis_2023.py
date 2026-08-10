#!/usr/bin/env python
"""genesis_2023.py -- THE 2023 REDUCTION LADDER (genesis-2023-reduce stream).

Re-runs the CERTIFIED 2026 genesis recipe (rstbasic -> R-rungs -> K3 -> K4;
the same lineage the 2025 ladder re-ran in one certification round,
tools/genesis_2025.py) on Autodesk's Revit-2023 rst basic sample, producing
the 2023 family-free base candidate ``B2023_K4.rvt``.

2023 IS ONE LAYER DEEPER THAN 2025/2024: besides the per-release framing
ordinals (six, resolved by name -- ``rvt.versions``), the RECORD LAYER
differs.  2023 element ids are 32-bit (the file's own schema declares it:
``Identifier`` v1 ``m_id`` i32; 2024+ is v2 ``m_id64`` i64), so record
framing headers are 8/12 bytes, in-body ElementId values are 4 bytes and
the ElemTable rows/footer are narrower with a different field order.  That
whole layer lives in ``rvt.versions.records32`` (this stream's finding +
module); :func:`context_2023` composes it with ``rvt.versions.reading`` and
the module-local framing-tag patches the 2025 campaign proved necessary
(genesis_2025.py ``_LOCAL_TAG_PATCHES``), plus the ADocument decoder bound
to the 2023 schema.

The ladder (each rung: tools/rvt_validate.py 0 errors +
``rvt.reduce_law.assert_edit_free`` + the FOUR-registry census):

  R5_2023   sample minus annotation / detail-line / schedule content (maxgc)
  R6_2023   + every view but one 3D + one plan, sheets/viewports/companions
  R7_2023   + unused symbols / types / materials / patterns / assets
  R8_2023   + design options, phases beyond the pinned, links, topologies
  R9_2023   + the family layer's host elements + placed model (deepest R)
  K3_2023   R9_2023 with loadable-family USAGE fields nulled (the
            M3-certified MODIFY path -- families + documents still present;
            reported via reduce_law.check_reduction, not edit-free by design)
  B2023_K4  K3_2023 minus the loadable-family layer AND all embedded family
            documents, FOUR-registry coherent (units + ContentDocuments +
            ContentTable + FamilyMgr) -- the 2023 family-free base candidate

Usage (repo root):
  .venv/bin/python tools/genesis_2023.py ladder      # R5..R9
  .venv/bin/python tools/genesis_2023.py k3k4        # K3_2023 + B2023_K4
  .venv/bin/python tools/genesis_2023.py formats     # 2023 format-data pins
  .venv/bin/python tools/genesis_2023.py stage       # probes.json + batch
  .venv/bin/python tools/genesis_2023.py all

The viewer is signed out: nothing here uploads.  ``stage`` writes the batch
+ probes.json for the orchestrator's certification queue (control = the
untouched 2023 sample, Autodesk's own file -- certified by construction;
it also answers "does the viewer read 2023 uploads at all?").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from collections import Counter
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import versions                                            # noqa: E402
from rvt.versions import records32                                  # noqa: E402
from rvt import reduce_law                                          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt import reduce as RED                                       # noqa: E402
from rvt.reduce import delete_elements                              # noqa: E402

import rvt_reduce as RR                                             # noqa: E402
import genesis_triage as GT                                         # noqa: E402

SRC = os.path.join(ROOT, "samples", "2023", "rstbasicsampleproject.rvt")
SAMPLES_2023 = os.path.join(ROOT, "samples", "2023")
OUT = os.path.join(ROOT, "experiments", "genesis2023")
RUNGS = os.path.join(OUT, "reduce")
FORMAT_MD = os.path.join(ROOT, "docs", "writer", "format-2023.md")
FACTS_JSON = os.path.join(OUT, "format_facts_2023.json")

RUNG_ORDER = ["R5_2023", "R6_2023", "R7_2023", "R8_2023", "R9_2023",
              "K3_2023", "B2023_K4"]

# ---------------------------------------------------------------------------
# the 2023 emit context: records32 + versions.reading + module-LOCAL tag copies
# ---------------------------------------------------------------------------
# rvt.versions.reading patches rvt.partitions; rvt.versions.records32.ids32
# patches the whole 32-bit-id record layer (framing walks, in-body ids, the
# ElemTable wire codec, the emit paths).  These four modules ALSO keep their
# OWN copies of the framing ordinals (from-imports or local literals) that
# the partitions patch cannot reach -- the exact list the 2025 campaign
# proved necessary (tools/genesis_2025.py _LOCAL_TAG_PATCHES, verified by
# grep again on 2026-08-04 for this stream).
def _cd_separator(o: Dict[str, int]) -> bytes:
    return struct.pack("<HiHi", o["CONTAINER_CLASS"], -1, o["UNIT_INNER_CLASS"], -1)


def _cd_end_record(o: Dict[str, int]) -> bytes:
    return struct.pack("<HiiI", o["CONTAINER_CLASS"], 0, -1, 0)


_LOCAL_TAG_PATCHES = (
    # the block header/trailer rows (rvt.reduce / manipulate / commit / writer)
    # retired with #467: those modules read rvt.partitions at CALL time, so
    # versions.reading alone re-points them
    ("rvt.famgen.factory", "CD_SEPARATOR", _cd_separator),
    ("rvt.famgen.factory", "CD_END_RECORD", _cd_end_record),
)


@contextmanager
def context_2023(src: str = SRC):
    """records32.ids32 (the 32-bit record layer) + versions.reading(src) +
    every module-local framing-tag copy patched + rvt.adocument's cached
    decoder bound to the file's own (2023) schema.  Restores everything on
    exit; yields the active ordinals."""
    import importlib
    from rvt import adocument as adoc
    from rvt.adocument import ADocumentDecoder
    sch = versions.schema_of(src)
    if not records32.is_ids32(sch):
        raise SystemExit(f"{src} does not declare Identifier v1 (32-bit ids) "
                         "-- wrong sample for the 2023 ladder")
    with records32.ids32():
        with versions.reading(src, schema=sch) as ords:
            prev: List[Tuple[Any, str, Any]] = []
            for mod_name, attr, spec in _LOCAL_TAG_PATCHES:
                mod = importlib.import_module(mod_name)
                prev.append((mod, attr, getattr(mod, attr)))
                val = spec(ords) if callable(spec) else ords[spec]
                setattr(mod, attr, val)
            # tools/rvt_reduce.py binds scan_stream_ids at import time
            # (module-level from-import), so the records32 patch of
            # rvt.reduce.scan_stream_ids does not reach it.  The i64 scan
            # silently finds ~nothing in a 2023 stream, which would zero the
            # latest_dangling evidence metric (a lying instrument, the
            # silent-miss defect class) -- rebind it to the i32 scan.
            prev.append((RR, "scan_stream_ids", RR.scan_stream_ids))
            RR.scan_stream_ids = records32.scan_stream_ids32
            prev.append((adoc, "_DECODER", adoc._DECODER))
            adoc._DECODER = ADocumentDecoder(sch)
            try:
                yield ords
            finally:
                for mod, attr, val in reversed(prev):
                    setattr(mod, attr, val)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    """genesis_triage.census under the active 2023 context: class census +
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


def _validator(path: str) -> dict:
    return RR._run_validator(path)


# ---------------------------------------------------------------------------
# the R-ladder (maxgc, the certified 2026 seeds re-run on the 2023 sample)
# ---------------------------------------------------------------------------
def run_r_ladder(stages: Iterable[str] = ("R5", "R6", "R7", "R8", "R9")) -> List[dict]:
    os.makedirs(RUNGS, exist_ok=True)
    results = []
    with context_2023(SRC):
        st = RR.build_state_v2(SRC)
        sample_doc = st["doc"]
        for stage in stages:
            name = f"{stage}_2023"
            t0 = time.time()
            seed = RR._protect_history(st, RR.stage_seed_v2(stage, st))
            delete, kept, ev = RR.maxgc(st, seed)
            out = os.path.join(RUNGS, f"{name}.rvt")
            rrep = delete_elements(SRC, out, delete)
            v = RED.verify_reduced(out, delete)
            val = _validator(out)
            law = law_gate_reduction(sample_doc, out,
                                     before_label="rstbasic-2023 (sample)",
                                     after_label=name)
            cen = four_registry_census(out)
            res = {
                "rung": name, "ladder": "2023", "release": 2023,
                "recipe": f"the certified 2026 {stage} seed (rvt_reduce.stage_seed_v2) "
                          f"re-run on samples/2023/rstbasicsampleproject.rvt under "
                          f"rvt.versions.records32.ids32 + versions.reading + context_2023",
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
                f"{cen.get('familymgr_doc_guids')} | {res['seconds']}s")
            if not (v["ok"] and val["ok"] and val["errors"] == 0 and law["ok"]):
                res["FAILED_SELF_CHECK"] = True
                write_report(name, res)
                raise SystemExit(f"[{name}] SELF-CHECK FAILED -- ladder stops: "
                                 f"{val.get('error_messages')}")
            results.append(res)
    return results


# ---------------------------------------------------------------------------
# K3_2023 (modify: loadable-family usage nulls) + B2023_K4 (family-free base)
# ---------------------------------------------------------------------------
def run_k3_k4() -> List[dict]:
    r9 = os.path.join(RUNGS, "R9_2023.rvt")
    if not os.path.exists(r9):
        raise SystemExit("R9_2023.rvt missing -- run the ladder first")
    results = []
    with context_2023(SRC):
        st9 = RR.build_state_v2(r9)
        r9_doc = st9["doc"]

        # ---- K3_2023: usage nulls (the M3-certified MODIFY path) ----------
        t0 = time.time()
        lay = GT.family_layer(st9)
        F = lay["ids"]
        k3 = os.path.join(RUNGS, "K3_2023.rvt")
        pol = reduce_law.law_policy().permits("neutralise-referrers", "research-probe")
        nrep = GT.neutralise_referrers(st9, F, k3, name="K3_2023")
        val3 = _validator(k3)
        cen3 = four_registry_census(k3)
        k3_doc = Document.from_file(k3)
        # the law instrument, non-raising: K3 is a MODIFY rung by design
        # (exactly the 2026 K3 recipe, viewer-certified there; re-proven for
        # 2025 in one round); every edit must be one of the neutralised
        # referrers, nothing added/removed.
        chk = reduce_law.check_reduction(r9_doc, k3_doc,
                                         before_label="R9_2023", after_label="K3_2023")
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
            "rung": "K3_2023", "kind": "modify (usage-null)",
            "parent": relp(r9), "parent_rung": "R9_2023", "out": relp(k3),
            "file_size": os.path.getsize(k3),
            "recipe": "genesis_triage K3 re-run on R9_2023: every USAGE field "
                      "naming the loadable-family layer nulled (level/grid/"
                      "section/callout/viewport head symbols, struct default "
                      "column, copy-monitor map, area-report fonts...); the "
                      "layer + its embedded documents stay.  The M3-certified "
                      "modify path (2026 precedent: K3 viewer PASS, round 5; "
                      "2025 precedent: K3_2025 PASS, round 1).",
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
            "validator": val3, "census": cen3,
            "seconds": round(time.time() - t0, 1),
        }
        write_report("K3_2023", rep3)
        log(f"[K3_2023] layer {len(F):,} elements ({len(lay['families'])} "
            f"loadable families); referrers edited "
            f"{nrep['referrer_elements_edited']}; edits==neutralised: "
            f"{law3['edits_are_exactly_the_neutralised_referrers']}; "
            f"validator_ok={val3['ok']} (errors {val3['errors']}); units "
            f"{cen3.get('save_units')} CD {cen3.get('contentdocs_entries')} "
            f"CT {cen3.get('contenttable_records')} FM "
            f"{cen3.get('familymgr_doc_guids')}; {rep3['seconds']}s")
        if not (rep3["structural_ok"] and val3["ok"] and val3["errors"] == 0
                and law3["edits_are_exactly_the_neutralised_referrers"]
                and chk.removed == 0 and not chk.added):
            rep3["FAILED_SELF_CHECK"] = True
            write_report("K3_2023", rep3)
            raise SystemExit(f"[K3_2023] SELF-CHECK FAILED: {val3.get('error_messages')}")
        results.append(rep3)

        # ---- B2023_K4: family layer + ALL documents out, 4-registry -------
        t0 = time.time()
        _ranges, guid_of_unit = GT._unit_guid_map(k3)
        all_guids = set(guid_of_unit)
        tmp = os.path.join(RUNGS, ".B2023_K4_docs_removed.rvt")
        rrep = GT.remove_documents(k3, tmp, all_guids,
                                   reconcile_contenttable=True,
                                   reconcile_familymgr=True)
        st_tmp = RR.build_state_v2(tmp)
        L = {e for e in F if e in st_tmp["host"]}
        L |= {e for e in st_tmp["host"]
              if st_tmp["cls_of"].get(e) == "LegendComponent"}
        L = RR._protect_history(st_tmp, L)
        delete, kept, ev = RR.maxgc(st_tmp, L)
        out = os.path.join(RUNGS, "B2023_K4.rvt")
        delete_elements(tmp, out, delete)
        os.remove(tmp)
        resid = GT._residual_guid_hits(out, all_guids)
        v = RED.verify_reduced(out, delete)
        val4 = _validator(out)
        cen4 = four_registry_census(out)
        law4 = law_gate_reduction(k3_doc, out, before_label="K3_2023",
                                  after_label="B2023_K4")
        rep4 = {
            "rung": "B2023_K4", "kind": "documents+family-layer removal",
            "parent": relp(k3), "parent_rung": "K3_2023", "out": relp(out),
            "file_size": os.path.getsize(out),
            "recipe": "genesis_triage K4 re-run on K3_2023: every embedded "
                      "family document removed FOUR-registry coherent (save "
                      "units spliced + ContentDocuments entries + ADocument "
                      "ContentTable records + FamilyMgr loaded-family entries) "
                      "then the loadable-family layer deleted by maxgc -- the "
                      "2023 family-free base candidate.",
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
            "seconds": round(time.time() - t0, 1),
        }
        write_report("B2023_K4", rep4)
        log(f"[B2023_K4] docs removed {len(all_guids)} (units "
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
            f"{cen4.get('four_registry_coherent')}; {rep4['seconds']}s")
        if not (v["ok"] and val4["ok"] and val4["errors"] == 0 and law4["ok"]
                and sum(resid.values()) == 0 and cen4.get("four_registry_coherent")):
            rep4["FAILED_SELF_CHECK"] = True
            write_report("B2023_K4", rep4)
            raise SystemExit(f"[B2023_K4] SELF-CHECK FAILED: {val4.get('error_messages')}")
        results.append(rep4)
    return results


# ---------------------------------------------------------------------------
# the 2023 format-data pins (the measurements a 2023 creation side would need)
# ---------------------------------------------------------------------------
def collect_format_facts() -> dict:
    import latest_map as LM
    from rvt.schema import parse as parse_schema
    from rvt.stream_encoders import (decode_basic_file_info, decode_history)

    facts: Dict[str, Any] = {"generated_by": "tools/genesis_2023.py formats",
                             "primary_sample": relp(SRC)}
    ref = {2026: os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt"),
           2025: os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt"),
           2024: os.path.join(ROOT, "samples", "2024", "rstbasicsampleproject.rvt")}

    # ---- 1. Formats/Latest: pin + THREE-way class-list diff ---------------
    with open_rvt(SRC) as f:
        blob23 = f.concat("Formats/Latest")
    sch23 = parse_schema(blob23, source=SRC)
    n23 = {c.name for c in sch23.classes}
    facts["formats_latest_2023"] = {
        "size": len(blob23), "sha256": sha256_of(blob23),
        "classes": len(sch23.classes),
        "pin_matches_rvt_versions": (
            sha256_of(blob23) == versions.KNOWN_RELEASES[2023].schema_sha256
            and len(blob23) == versions.KNOWN_RELEASES[2023].schema_size),
    }
    diffs = {}
    for yr, path in ref.items():
        with open_rvt(path) as f:
            blob = f.concat("Formats/Latest")
        sch = parse_schema(blob, source=path)
        names = {c.name for c in sch.classes}
        shared = n23 & names
        renumbered = sorted(n for n in shared
                            if sch23.by_name[n].type_id != sch.by_name[n].type_id)
        diffs[str(yr)] = {
            "classes_other": len(sch.classes), "classes_2023": len(sch23.classes),
            "shared_names": len(shared),
            "renumbered_shared": len(renumbered),
            "same_ordinal_shared": len(shared) - len(renumbered),
            "only_in_other": sorted(names - n23), "only_in_2023": sorted(n23 - names),
        }
    facts["class_diff_vs_2023"] = diffs
    # byte-identical across all six 2023 samples?
    schema_hashes = {}
    for fn in sorted(os.listdir(SAMPLES_2023)):
        if not fn.endswith(".rvt"):
            continue
        with open_rvt(os.path.join(SAMPLES_2023, fn)) as f:
            schema_hashes[fn] = sha256_of(f.concat("Formats/Latest"))
    facts["formats_latest_2023"]["identical_across_six_samples"] = (
        len(set(schema_hashes.values())) == 1)
    facts["formats_latest_2023"]["per_sample_sha256"] = schema_hashes

    # ---- 2. THE RECORD-LAYER DELTA (what 2024 changed) --------------------
    idc23 = sch23.by_name["Identifier"]
    facts["record_layer_2023"] = {
        "identifier_version": idc23.version,
        "identifier_field": [(f.name, f.kind) for f in idc23.fields],
        "element_id_bits": 32,
        "record_header_bytes": {"seq101": records32.RAW_HDR_101,
                                "seq102_103": records32.RAW_HDR_10X},
        "elemtable_row_bytes": records32.REC_SIZE32,
        "elemtable_row_order": "original_id, id, ce, me, ue, partition, owner",
        "elemtable_footer_bytes": records32.FOOTER_LEN32,
        "owner_invalid_wire": hex(records32.INVALID_OWNER32),
        "elemtable_class_version": sch23.by_name["ElemTable"].version,
        "elemrec_field_order": [f.name for f in sch23.by_name["ElemRec"].fields],
    }

    # ---- 3. ESSchemaStorage / Global/Latest product corpus (C4, 4 releases)
    corpus = {}
    for fn in sorted(os.listdir(SAMPLES_2023)):
        if not fn.endswith(".rvt"):
            continue
        with open_rvt(os.path.join(SAMPLES_2023, fn)) as f:
            payload = f.inflate("Global/Latest")
        tables = LM.find_json_tables(payload)
        bodies = b"".join(payload[t["start"]:t["end"]] for t in tables)
        corpus[fn] = {
            "tables": [{"count": t["count"], "bytes": t["end"] - t["start"],
                        "sha256_16": t["sha256_16"]} for t in tables],
            "total_pairs": sum(t["count"] for t in tables),
            "total_bytes": len(bodies),
            "corpus_sha256": sha256_of(bodies),
        }
    shas = {v["corpus_sha256"] for v in corpus.values()}
    facts["esschema_corpus_2023"] = {
        "byte_identical_across_six_samples": len(shas) == 1,
        "corpus_sha256": corpus[os.path.basename(SRC)]["corpus_sha256"],
        "total_bytes": corpus[os.path.basename(SRC)]["total_bytes"],
        "total_pairs": corpus[os.path.basename(SRC)]["total_pairs"],
        "tables": corpus[os.path.basename(SRC)]["tables"],
        "per_sample": corpus,
        "reference_corpora": {},
    }
    for yr, path in ref.items():
        with open_rvt(path) as f:
            payload = f.inflate("Global/Latest")
        t = LM.find_json_tables(payload)
        b = b"".join(payload[x["start"]:x["end"]] for x in t)
        facts["esschema_corpus_2023"]["reference_corpora"][str(yr)] = {
            "total_pairs": sum(x["count"] for x in t),
            "total_bytes": len(b), "corpus_sha256": sha256_of(b),
        }

    # ---- 4. identity / footer / version markers (incl. the 2662 check) ----
    from rvt.stream_encoders import decode_elemtable
    import rvt.stream_encoders as SE
    with context_2023(SRC):
        with open_rvt(SRC) as f:
            bfi = decode_basic_file_info(f.raw("BasicFileInfo"))
            # module-attr lookup so the records32 patch is in force
            et = SE.decode_elemtable(f.inflate("Global/ElemTable"))
            hist = decode_history(f.inflate("Global/History"))
    with open_rvt(ref[2026]) as f:
        et26 = decode_elemtable(f.inflate("Global/ElemTable"))
        hist26 = decode_history(f.inflate("Global/History"))
    ups23 = list(hist.get("format_versions") or [])
    ups26 = list(hist26.get("format_versions") or [])

    def _clsname(sch, tid):
        c = sch.by_id.get(tid)
        return c.name if c is not None else None

    facts["identity_2023"] = {
        "basicfileinfo_format": bfi.get("format"),
        "basicfileinfo_build": bfi.get("build"),
        "elemtable_class_tag": {"2023": hex(et["class_tag"]),
                                "2026": hex(et26["class_tag"]),
                                "name": _clsname(sch23, et["class_tag"])},
        "elemtable_footer_tail_class": {
            "2023": hex(et["footer"]["tail_class"]),
            "2026": hex(et26["footer"]["tail_class"]),
            "name": _clsname(sch23, et["footer"]["tail_class"])},
        "history_upgrade_versions": {"2023_last": (ups23[-1] if ups23 else None),
                                     "2023_count": len(ups23),
                                     "2026_last": (ups26[-1] if ups26 else None),
                                     "2026_count": len(ups26)},
        "history_class_tag": {"2023": hex(hist.get("class_tag", 0)),
                              "2026": hex(hist26.get("class_tag", 0))},
        "adocument_schema_version": {
            "2023": sch23.by_name["ADocument"].version,
        },
    }

    # ---- 5. framing ordinals, by-name (re-verified) -----------------------
    facts["framing_2023"] = {k: hex(v) for k, v in
                            versions.ordinals_from_schema(sch23).items()}
    facts["framing_matches_rvt_versions_table"] = (
        versions.ordinals_from_schema(sch23) == dict(versions.KNOWN_RELEASES[2023].framing))
    os.makedirs(OUT, exist_ok=True)
    with open(FACTS_JSON, "w") as fh:
        json.dump(facts, fh, indent=1, default=str)
    log(f"[formats] wrote {relp(FACTS_JSON)}")
    return facts


def write_format_md(facts: dict) -> str:
    fl = facts["formats_latest_2023"]
    rl = facts["record_layer_2023"]
    es = facts["esschema_corpus_2023"]
    idn = facts["identity_2023"]
    L: List[str] = []
    A = L.append
    A("# FORMAT 2023 -- the pinned Revit-2023 format data")
    A("")
    A("Stream: **genesis-2023-reduce** (2026-08-04).  Generated by "
      "`tools/genesis_2023.py formats`; machine-readable facts in "
      f"`{relp(FACTS_JSON)}`.  Everything below is measured from the "
      "quarantined `samples/2023/` Autodesk samples (DEV-ONLY -- learn from, "
      "never ship) under `rvt.versions.records32.reading32`.  Companion "
      "docs: `docs/inbox/versions.md` (the version model), "
      "`docs/inbox/genesis-2023-reduce.md` (this stream's record), "
      "`src/rvt/versions/records32.py` (the 32-bit record layer).")
    A("")
    A("## 1. THE 2023 DELTA -- element ids are 32-bit (the record layer)")
    A("")
    A("2023 is the first release in the roster whose data layer genuinely "
      "differs from 2026: **Revit 2024 widened element ids from 32 to 64 "
      "bits**.  The file's own schema declares it -- class `Identifier` is "
      f"**v{rl['identifier_version']}** with field "
      f"`{rl['identifier_field'][0][0]}` (kind {rl['identifier_field'][0][1]:#x} "
      "= i32) where 2024/2025/2026 declare v2 `m_id64` (i64).  Ripples, all "
      "measured and proven by decode parity + byte-exact round-trips:")
    A("")
    A("| layer | 2023 (32-bit era) | 2024+ |")
    A("|---|---|---|")
    A(f"| record header, seq-101 | `<iI` = {rl['record_header_bytes']['seq101']} B | `<qI` = 12 B |")
    A(f"| record header, seq-102/103 | `<iII` = {rl['record_header_bytes']['seq102_103']} B | `<qII` = 16 B |")
    A("| in-body `ElementId` / `Identifier` | i32 | i64 |")
    A(f"| `Global/ElemTable` row | {rl['elemtable_row_bytes']} B, order ({rl['elemtable_row_order']}) | 40 B, order (orig, ce, me, ue, id, owner, partition) |")
    A(f"| `ElemTable` footer | {rl['elemtable_footer_bytes']} B (u32 last_id, u8 pad) | 24 B (u64 last_id, u16 pad) |")
    A(f"| owner-invalid sentinel | `{rl['owner_invalid_wire']}` | `0xffffffffffffffff` |")
    A(f"| `ElemTable` class version | v{rl['elemtable_class_version']} (no `m_bLastElementIdOverride`) | v10 |")
    A(f"| `ElemRec` schema field order | {', '.join(rl['elemrec_field_order'])} | m_history, m_id, m_OwningElementId, m_partitionId |")
    A("")
    A("Everything else is UNCHANGED at 2023: CFB container (v4, 4096-byte "
      "sectors), page/ECC framing, gzip flavour, block framing (bar the "
      "usual per-release ordinals), the schema-stream grammar "
      "(`rvt.schema.parse` reads it to EOF -- `PARSER_DELTAS = ()` for the "
      "fourth consecutive release), the class field lists (ElementHeader "
      "v24 = 2024's, FamilyInstance v37 = 2024's), the stream roster.  The "
      "reversible patch set that puts the read/write stack into the 32-bit "
      "era is `rvt.versions.records32` (activation keyed off the schema's "
      "own Identifier declaration, NOT the release number).")
    A("")
    A("## 2. `Formats/Latest` -- the 2023 schema constant")
    A("")
    A(f"* size **{fl['size']:,} B**, **{fl['classes']:,} classes**, sha256 "
      f"`{fl['sha256']}`")
    A(f"* byte-identical across all six 2023 samples: "
      f"**{fl['identical_across_six_samples']}**")
    A(f"* matches the `rvt.versions.KNOWN_RELEASES[2023]` pin: "
      f"**{fl['pin_matches_rvt_versions']}**")
    A("")
    A("## 3. Class-list diff 2023 vs 2024 / 2025 / 2026")
    A("")
    A("| | vs 2024 | vs 2025 | vs 2026 |")
    A("|---|---:|---:|---:|")
    d24, d25, d26 = (facts["class_diff_vs_2023"][y] for y in ("2024", "2025", "2026"))
    A(f"| classes (other release) | {d24['classes_other']:,} | {d25['classes_other']:,} | {d26['classes_other']:,} |")
    A(f"| shared names | {d24['shared_names']:,} | {d25['shared_names']:,} | {d26['shared_names']:,} |")
    A(f"| shared names RENUMBERED | {d24['renumbered_shared']:,} | {d25['renumbered_shared']:,} | {d26['renumbered_shared']:,} |")
    A(f"| shared names, same ordinal | {d24['same_ordinal_shared']:,} | {d25['same_ordinal_shared']:,} | {d26['same_ordinal_shared']:,} |")
    A(f"| names only in the other | {len(d24['only_in_other'])} | {len(d25['only_in_other'])} | {len(d26['only_in_other'])} |")
    A(f"| names only in 2023 | {len(d24['only_in_2023'])} | {len(d25['only_in_2023'])} | {len(d26['only_in_2023'])} |")
    A("")
    A("**Consequence (unchanged from the version model): resolve every class "
      "ordinal BY NAME from the target release's schema.**  Classes only in "
      "2024 (i.e. added AT 2024, absent from 2023): "
      + (", ".join(f"`{n}`" for n in d24["only_in_other"]) or "(none)"))
    A("")
    A("Classes only in 2023 (dropped at 2024): "
      + (", ".join(f"`{n}`" for n in d24["only_in_2023"]) or "(none)"))
    A("")
    A("## 4. The `ESSchemaStorage` / product-runtime corpus (Global/Latest)")
    A("")
    A("The Autodesk Forge unit/spec/parameter-group JSON corpus inside the "
      "ADocument -- shipped PRODUCT data, byte-identical within a release. "
      "**Counsel C4 now spans FOUR releases** (2023/2024/2025/2026, one "
      "corpus pin each):")
    A("")
    A("| release | (typeid,json) pairs | corpus bytes | sha256 |")
    A("|---|---:|---:|---|")
    A(f"| 2023 | {es['total_pairs']:,} | {es['total_bytes']:,} | `{es['corpus_sha256']}` |")
    for yr in ("2024", "2025", "2026"):
        r = es["reference_corpora"][yr]
        A(f"| {yr} (same instrument, rst) | {r['total_pairs']:,} | "
          f"{r['total_bytes']:,} | `{r['corpus_sha256']}` |")
    A("")
    A(f"* byte-identical across all six 2023 samples: "
      f"**{es['byte_identical_across_six_samples']}**")
    A(f"* per-table shape (2023): " + "; ".join(
        f"{t['count']:,} pairs / {t['bytes']:,} B (`{t['sha256_16']}`)"
        for t in es["tables"]))
    A("")
    A("## 5. Identity / footer / version markers")
    A("")
    A(f"* `BasicFileInfo` format string: **`{idn['basicfileinfo_format']}`**, "
      f"build: **`{idn['basicfileinfo_build']}`** (a real RTM build stamp; "
      "release-authoritative, what `rvt.versions.detect_release` keys on)")
    hz = idn["history_upgrade_versions"]
    A(f"* `Global/History` upgrade-version list: 2023 ends **{hz['2023_last']}** "
      f"({hz['2023_count']} entries) vs 2026 **{hz['2026_last']}** "
      f"({hz['2026_count']} entries).  THE 2662-TERMINAL CHECK: "
      + ("**2023 ALSO ends at 2662** -- the ADocument format version froze "
         "at 2662 before 2023; the History terminal value is NOT a release "
         "marker for any of the four releases."
         if hz["2023_last"] == hz["2026_last"] else
         f"**2023 ends at {hz['2023_last']}, NOT {hz['2026_last']}** -- the "
         "first release where the History terminal DIFFERS: the freeze "
         "point is between 2023 and 2024, and a 2023 creation side must "
         f"write {hz['2023_last']}."))
    A(f"* `ADocument` schema class version (2023): "
      f"**{idn['adocument_schema_version']['2023']}**")
    etc = idn["elemtable_class_tag"]
    etf = idn["elemtable_footer_tail_class"]
    A(f"* `Global/ElemTable` lead class tag: 2023 `{etc['2023']}` vs 2026 "
      f"`{etc['2026']}` (= `{etc['name']}` -- an ordinal, resolved by name)")
    A(f"* `ElemTable` footer tail class: 2023 `{etf['2023']}` vs 2026 "
      f"`{etf['2026']}` (= `{etf['name']}`)")
    hc = idn["history_class_tag"]
    A(f"* `Global/History` lead class tag: 2023 `{hc['2023']}` vs 2026 `{hc['2026']}`")
    A("")
    A("## 6. Partition-framing ordinals (by-name, re-verified this run)")
    A("")
    A("| constant | class | 2023 |")
    A("|---|---|---|")
    for k, v in facts["framing_2023"].items():
        A(f"| {k} | {versions.FRAMING_CLASSES[k]} | `{v}` |")
    A("")
    A(f"Matches the precomputed `rvt.versions` table: "
      f"**{facts['framing_matches_rvt_versions_table']}**")
    A("")
    A("## 7. The 2023 emit context (what a 2023 write needs active)")
    A("")
    A("`tools/genesis_2023.py context_2023` composes, and each layer "
      "restores on exit:")
    A("")
    A("1. `rvt.versions.records32.ids32()` -- the 32-bit record layer "
      "(framing walks, in-body ids, ElemTable wire codec, emit paths; ~40 "
      "patch points, table in records32.py).")
    A("2. `rvt.versions.reading(src)` -- the six framing ordinals bound "
      "into `rvt.partitions`.")
    A("3. The module-local framing-tag copies (`rvt.reduce` / "
      "`rvt.manipulate` / `rvt.commit` / `rvt.writer` BLOCK/TRAILER tags; "
      "`rvt.famgen.factory` CD_SEPARATOR/CD_END_RECORD rebuilt from the "
      "active ordinals) -- the genesis_2025 `_LOCAL_TAG_PATCHES` list, "
      "re-verified for this stream.")
    A("4. The TOOL-module from-import rebind: `tools/rvt_reduce.py` binds "
      "`scan_stream_ids` at import time, so the records32 patch of "
      "`rvt.reduce.scan_stream_ids` does not reach it -- the i64 scan "
      "silently finds ~nothing in a 2023 stream, which would ZERO the "
      "`latest_dangling` evidence metric (the silent-miss defect class).  "
      "context_2023 rebinds it to `records32.scan_stream_ids32`.")
    A("5. `rvt.adocument._DECODER` bound to the 2023 schema.")
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


def write_probes_manifest() -> str:
    """experiments/genesis2023/probes.json -- the declaration probe_batch
    resolves bases from, ordered by information value.  Every 2023 file is a
    candidate-base: NOTHING 2023 is viewer-certified yet; certification
    cascades down the lineage."""
    entries = []
    meta = {
        "R9_2023": {
            "tests": "Deepest R-rung of the 2023 campaign AND the first "
                     "viewer-read of a 32-BIT-ERA file we re-emitted: "
                     "views/types/options/families' host elements gone (the "
                     "certified 2026 R9 shape; all embedded docs present, "
                     "censused).  K3_2023's parent.",
            "if_PASS": "certify; the 2023 reduction mechanics (records32 "
                       "framing, re-blocker, ECC, ordinals) are viewer-proven; "
                       "K3/K4 verdicts readable.",
            "if_FAIL": "with the sample control PASSING, the 2023 EMIT path "
                       "is defective (32-bit framing / ordinal bug) -- bisect "
                       "R5..R8 (staged locally, not in this batch) against "
                       "the identity re-emit before reading anything else.",
        },
        "K3_2023": {
            "tests": "Loadable-family USAGE nulled (families + documents "
                     "still present) -- the M3-certified modify path, the "
                     "mandatory parent state of B2023_K4 (2026 precedent: "
                     "K3 PASS round 5; 2025: K3_2025 PASS round 1).",
            "if_PASS": "certify; B2023_K4's verdict is readable.",
            "if_FAIL": "the 2023 reader requires head/tag defaults to name "
                       "real families -- B2023_K4 unreadable until split.",
        },
        "B2023_K4": {
            "tests": "THE 2023 FAMILY-FREE BASE CANDIDATE: zero loadable "
                     "families, zero embedded family documents, FOUR-registry "
                     "coherent, on Autodesk's own 2023 skeleton (the certified "
                     "2026 K4 recipe, re-proven for 2025).  PASS = the "
                     "certified 2023 base a G23 substitution campaign builds on.",
            "if_PASS": "certify + ledger; the 2023 campaign proceeds to the "
                       "constructor retarget + substitution ladder (the "
                       "genesis-2023-port stream's territory).",
            "if_FAIL": "(with K3_2023 passing) the 2023 reader diverges on "
                       "the family-document question -- re-run the "
                       "KD1-equivalent control before concluding anything.",
        },
    }
    parent = {"R9_2023": None, "K3_2023": "R9_2023", "B2023_K4": "K3_2023"}
    for name in ("R9_2023", "K3_2023", "B2023_K4"):
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
            "elements": (rep.get("census") or {}).get("elements"),
            "coherence": {k: (rep.get("census") or {}).get(k)
                          for k in ("save_units", "contentdocs_entries",
                                    "contenttable_records", "familymgr_doc_guids")},
            "report": f"experiments/genesis2023/reduce/{name}.json",
        }
        if parent[name]:
            e["parent_rung"] = parent[name]
        entries.append(e)
    manifest = {
        "stream": "genesis-2023-reduce (the Revit-2023 reduction ladder)",
        "situation": (
            "2023 is the first release whose DATA LAYER differs from the "
            "certified 2026 lineage: element ids are 32-bit (Identifier v1) "
            "-- record framing, in-body ids and the ElemTable are narrower. "
            "This ladder re-runs the certified 2026 recipe (rstbasic -> "
            "R-rungs -> K3 -> K4; re-proven on 2025 in one round) on "
            "Autodesk's own 2023 rst basic sample under rvt.versions."
            "records32 + reading.  NOTHING 2023 is viewer-certified yet, so "
            "every file here is a candidate-base; the batch control is the "
            "UNTOUCHED 2023 sample itself (Autodesk's own bytes -- certified "
            "by construction), which simultaneously answers: does the viewer "
            "read 2023 uploads at all?"),
        "ordering": "reading order: control (the 2023 sample) FIRST -- if it "
                    "fails, the viewer/oracle cannot read 2023 uploads and "
                    "every other verdict is VOID; then R9_2023, K3_2023, "
                    "B2023_K4 (certification cascades; a parent FAIL voids "
                    "its children).",
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
             for n in ("R9_2023", "K3_2023", "B2023_K4")]
    for f in files:
        if not os.path.exists(f):
            raise SystemExit(f"missing rung {relp(f)} -- run ladder + k3k4 first")
    # batch number: continue the GLOBAL numbering across EVERY campaign dir
    # (acceptance 15/16, genesis2025 17, the 2024 fleet is at 28, ...) --
    # a fixed dir list here already collided once conceptually, so scan the
    # whole experiments tree for batch_<n>.json and take max+1.
    n = PB.next_batch_number(PB.ACCEPTANCE)
    for _wbase, _wdirs, wfiles in os.walk(os.path.join(ROOT, "experiments")):
        for fn in wfiles:
            m = __import__("re").match(r"batch_(\d+)\.json$", fn)
            if m:
                n = max(n, int(m.group(1)) + 1)
    manifest = PB.stage_batch(
        [], candidate_bases=files, control_from=relp(SRC),
        out_dir=OUT, batch_n=n,
        note=("2023 campaign round 1: every entry a candidate-base (no 2023 "
              "file is certified yet); control = the untouched Autodesk 2023 "
              "rst sample, which also answers 'does the viewer read 2023 "
              "uploads?'.  2023 is the 32-bit-element-id era (records32) -- "
              "R9_2023 doubles as the first viewer-read of our 32-bit "
              "re-emit.  Read with probe_batch.read_batch_verdicts; "
              "certification cascades R9 -> K3 -> B2023_K4."))
    log(f"[stage] batch {manifest['batch']} staged into {relp(OUT)}: "
        + ", ".join(manifest["reading_order"]))
    return manifest


# ---------------------------------------------------------------------------
# the run lock (orchestrator-mandated, 2026-08-04): two 2023 streams raced
# whole-file rung writes in reduce/ twice despite written coordination.  A
# rule a process can violate silently must be a gate the tool enforces --
# so every MUTATING command (ladder / k3k4 / stage / all) takes a pid
# lockfile inside the contested directory itself and REFUSES to run while
# a live pid holds it.  formats is read-only and needs no lock.
# ---------------------------------------------------------------------------
LOCK_PATH = os.path.join(RUNGS, ".ladder.lock")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:                     # exists, owned by someone else
        return True


@contextmanager
def ladder_lock():
    os.makedirs(RUNGS, exist_ok=True)
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                holder = int(open(LOCK_PATH).read().strip() or 0)
            except (OSError, ValueError):
                holder = 0
            if holder and _pid_alive(holder):
                raise SystemExit(
                    f"REFUSED: {relp(LOCK_PATH)} is held by LIVE pid {holder} "
                    "-- another ladder/k3k4/stage run is in flight.  Two "
                    "processes writing the same rung files produce torn "
                    ".rvt/.json outputs; wait for the holder to exit (the "
                    "lock clears itself) or investigate that pid.")
            log(f"[lock] stale lock (pid {holder or '?'} dead) -- reclaiming")
            os.unlink(LOCK_PATH)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(LOCK_PATH)
        except OSError:
            pass


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
    if args.cmd == "formats":                    # read-only: no lock needed
        write_format_md(collect_format_facts())
        log(f"[done] {time.time() - t0:.1f}s")
        return 0
    with ladder_lock():
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
