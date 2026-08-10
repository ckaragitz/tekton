#!/usr/bin/env python
"""genesis_2025.py -- THE 2025 REDUCTION LADDER (genesis-2025-reduce stream).

Re-runs the CERTIFIED 2026 genesis recipe (rstbasic -> R-rungs -> K3 -> K4,
docs/writer/genesis-2025-plan.md G25-1/G25-2) on Autodesk's Revit-2025 rst
basic sample, producing the 2025 family-free base candidate ``B2025_K4.rvt``.

Everything runs inside ``rvt.versions.reading(<2025 file>)`` so the six
partition-framing ordinals resolve from the file's OWN schema -- plus the
:func:`context_2025` patch set for the module-local copies of those ordinals
the emitting tools keep (the plan's SS7 "baked 0x0f28-era literal" risk,
found real in FOUR places -- see ``_LOCAL_TAG_PATCHES``).

The ladder (each rung: tools/rvt_validate.py 0 errors +
``rvt.reduce_law.assert_edit_free`` + the FOUR-registry census):

  R5_2025   sample minus annotation / detail-line / schedule content (maxgc)
  R6_2025   + every view but one 3D + one plan, sheets/viewports/companions
  R7_2025   + unused symbols / types / materials / patterns / assets
  R8_2025   + design options, phases beyond the pinned, links, topologies
  R9_2025   + the family layer's host elements + placed model (deepest R)
  K3_2025   R9_2025 with loadable-family USAGE fields nulled (the
            M3-certified MODIFY path -- families + documents still present;
            reported via reduce_law.check_reduction, not edit-free by design)
  B2025_K4  K3_2025 minus the loadable-family layer AND all embedded family
            documents, FOUR-registry coherent (units + ContentDocuments +
            ContentTable + FamilyMgr) -- the 2025 family-free base candidate

Usage (repo root):
  .venv/bin/python tools/genesis_2025.py ladder      # R5..R9
  .venv/bin/python tools/genesis_2025.py k3k4        # K3_2025 + B2025_K4
  .venv/bin/python tools/genesis_2025.py formats     # 2025 format-data pins
  .venv/bin/python tools/genesis_2025.py stage       # probes.json + batch
  .venv/bin/python tools/genesis_2025.py all

The viewer is signed out: nothing here uploads.  ``stage`` writes the batch
+ probes.json for the orchestrator's certification queue (control = the
untouched 2025 sample, Autodesk's own file -- certified by construction;
it also answers plan risk #1 "does the viewer accept 2025 uploads?").
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
from rvt import reduce_law                                          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt.reduce import delete_elements, verify_reduced              # noqa: E402

import rvt_reduce as RR                                             # noqa: E402
import genesis_triage as GT                                         # noqa: E402

SRC = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
SAMPLES_2025 = os.path.join(ROOT, "samples", "2025")
OUT = os.path.join(ROOT, "experiments", "genesis2025")
RUNGS = os.path.join(OUT, "reduce")
FORMAT_MD = os.path.join(ROOT, "docs", "writer", "format-2025.md")
FACTS_JSON = os.path.join(OUT, "format_facts_2025.json")

RUNG_ORDER = ["R5_2025", "R6_2025", "R7_2025", "R8_2025", "R9_2025",
              "K3_2025", "B2025_K4"]

# ---------------------------------------------------------------------------
# the 2025 emit context: versions.reading + the module-LOCAL tag copies
# ---------------------------------------------------------------------------
# rvt.versions.reading patches rvt.partitions (module globals looked up at
# call time).  These four modules keep their OWN copies of the framing
# ordinals -- from-imports or local literals -- that the patch cannot reach.
# Verified by grep on 2026-08-04 (the exact risk genesis-2025-plan.md SS7
# names): rvt/reduce.py:59 ``BLOCK_TAG = 0x0F28`` (used by NewBlock.frame),
# rvt/reduce.py:56 + rvt/commit.py:37 ``from .writer import BLOCK_TRL_TAG``,
# rvt/manipulate.py:76 ``from .partitions import BLOCK_TAG, TRAILER_TAG``,
# rvt/famgen/factory.py:1469-1471 CD_SEPARATOR / CD_END_RECORD baking the
# 2026 ContentMarker/ContentKey ordinals (0x3A3/0x3A2).
#   (module, attr, ordinal-name or callable(ords))
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
def context_2025(src: str = SRC):
    """versions.reading(src) + every module-local framing-tag copy patched +
    rvt.adocument's cached decoder bound to the file's own (2025) schema.
    Restores everything on exit; yields the active ordinals."""
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
    """genesis_triage.census under the active 2025 context: class census +
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
# the R-ladder (maxgc, the certified 2026 seeds re-run on the 2025 sample)
# ---------------------------------------------------------------------------
def run_r_ladder(stages: Iterable[str] = ("R5", "R6", "R7", "R8", "R9")) -> List[dict]:
    os.makedirs(RUNGS, exist_ok=True)
    results = []
    with context_2025(SRC):
        st = RR.build_state_v2(SRC)
        sample_doc = st["doc"]
        for stage in stages:
            name = f"{stage}_2025"
            t0 = time.time()
            seed = RR._protect_history(st, RR.stage_seed_v2(stage, st))
            delete, kept, ev = RR.maxgc(st, seed)
            out = os.path.join(RUNGS, f"{name}.rvt")
            rrep = delete_elements(SRC, out, delete)
            v = verify_reduced(out, delete)
            val = _validator(out)
            law = law_gate_reduction(sample_doc, out,
                                     before_label="rstbasic-2025 (sample)",
                                     after_label=name)
            cen = four_registry_census(out)
            res = {
                "rung": name, "ladder": "2025", "release": 2025,
                "recipe": f"the certified 2026 {stage} seed (rvt_reduce.stage_seed_v2) "
                          f"re-run on samples/2025/rstbasicsampleproject.rvt under "
                          f"rvt.versions.reading + context_2025",
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
# K3_2025 (modify: loadable-family usage nulls) + B2025_K4 (family-free base)
# ---------------------------------------------------------------------------
def run_k3_k4() -> List[dict]:
    r9 = os.path.join(RUNGS, "R9_2025.rvt")
    if not os.path.exists(r9):
        raise SystemExit("R9_2025.rvt missing -- run the ladder first")
    results = []
    with context_2025(SRC):
        st9 = RR.build_state_v2(r9)
        r9_doc = st9["doc"]

        # ---- K3_2025: usage nulls (the M3-certified MODIFY path) ----------
        t0 = time.time()
        lay = GT.family_layer(st9)
        F = lay["ids"]
        k3 = os.path.join(RUNGS, "K3_2025.rvt")
        pol = reduce_law.law_policy().permits("neutralise-referrers", "research-probe")
        nrep = GT.neutralise_referrers(st9, F, k3, name="K3_2025")
        val3 = _validator(k3)
        cen3 = four_registry_census(k3)
        k3_doc = Document.from_file(k3)
        # the law instrument, non-raising: K3 is a MODIFY rung by design
        # (exactly the 2026 K3 recipe, viewer-certified there); every edit
        # must be one of the neutralised referrers, nothing added/removed.
        chk = reduce_law.check_reduction(r9_doc, k3_doc,
                                         before_label="R9_2025", after_label="K3_2025")
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
            "rung": "K3_2025", "kind": "modify (usage-null)",
            "parent": relp(r9), "parent_rung": "R9_2025", "out": relp(k3),
            "file_size": os.path.getsize(k3),
            "recipe": "genesis_triage K3 re-run on R9_2025: every USAGE field "
                      "naming the loadable-family layer nulled (level/grid/"
                      "section/callout/viewport head symbols, struct default "
                      "column, copy-monitor map, area-report fonts...); the "
                      "layer + its embedded documents stay.  The M3-certified "
                      "modify path; the viewer certifies the STATE (2026 "
                      "precedent: K3 viewer PASS, round 5).",
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
        write_report("K3_2025", rep3)
        log(f"[K3_2025] layer {len(F):,} elements ({len(lay['families'])} "
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
            write_report("K3_2025", rep3)
            raise SystemExit(f"[K3_2025] SELF-CHECK FAILED: {val3.get('error_messages')}")
        results.append(rep3)

        # ---- B2025_K4: family layer + ALL documents out, 4-registry -------
        t0 = time.time()
        _ranges, guid_of_unit = GT._unit_guid_map(k3)
        all_guids = set(guid_of_unit)
        tmp = os.path.join(RUNGS, ".B2025_K4_docs_removed.rvt")
        rrep = GT.remove_documents(k3, tmp, all_guids,
                                   reconcile_contenttable=True,
                                   reconcile_familymgr=True)
        st_tmp = RR.build_state_v2(tmp)
        L = {e for e in F if e in st_tmp["host"]}
        L |= {e for e in st_tmp["host"]
              if st_tmp["cls_of"].get(e) == "LegendComponent"}
        L = RR._protect_history(st_tmp, L)
        delete, kept, ev = RR.maxgc(st_tmp, L)
        out = os.path.join(RUNGS, "B2025_K4.rvt")
        delete_elements(tmp, out, delete)
        os.remove(tmp)
        resid = GT._residual_guid_hits(out, all_guids)
        v = verify_reduced(out, delete)
        val4 = _validator(out)
        cen4 = four_registry_census(out)
        law4 = law_gate_reduction(k3_doc, out, before_label="K3_2025",
                                  after_label="B2025_K4")
        rep4 = {
            "rung": "B2025_K4", "kind": "documents+family-layer removal",
            "parent": relp(k3), "parent_rung": "K3_2025", "out": relp(out),
            "file_size": os.path.getsize(out),
            "recipe": "genesis_triage K4 re-run on K3_2025: every embedded "
                      "family document removed FOUR-registry coherent (save "
                      "units spliced + ContentDocuments entries + ADocument "
                      "ContentTable records + FamilyMgr loaded-family entries) "
                      "then the loadable-family layer deleted by maxgc -- the "
                      "2025 family-free base candidate.",
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
        write_report("B2025_K4", rep4)
        log(f"[B2025_K4] docs removed {len(all_guids)} (units "
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
            write_report("B2025_K4", rep4)
            raise SystemExit(f"[B2025_K4] SELF-CHECK FAILED: {val4.get('error_messages')}")
        results.append(rep4)
    return results


# ---------------------------------------------------------------------------
# the 2025 format-data pins (plan G25-0 measurements the creation side needs)
# ---------------------------------------------------------------------------
def collect_format_facts() -> dict:
    import latest_map as LM
    from rvt.schema import parse as parse_schema
    from rvt.stream_encoders import (decode_basic_file_info, decode_elemtable,
                                     decode_history)

    facts: Dict[str, Any] = {"generated_by": "tools/genesis_2025.py formats",
                             "primary_sample": relp(SRC)}

    # ---- 1. Formats/Latest: pin + class-list diff vs 2026 -----------------
    with open_rvt(SRC) as f:
        blob25 = f.concat("Formats/Latest")
    s26_path = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
    with open_rvt(s26_path) as f:
        blob26 = f.concat("Formats/Latest")
    sch25 = parse_schema(blob25, source=SRC)
    sch26 = parse_schema(blob26, source=s26_path)
    n25 = {c.name for c in sch25.classes}
    n26 = {c.name for c in sch26.classes}
    only26 = sorted(n26 - n25)
    only25 = sorted(n25 - n26)
    shared = n25 & n26
    renumbered = sorted(n for n in shared
                        if sch25.by_name[n].type_id != sch26.by_name[n].type_id)
    facts["formats_latest_2025"] = {
        "size": len(blob25), "sha256": sha256_of(blob25),
        "classes": len(sch25.classes),
        "pin_matches_rvt_versions": (
            sha256_of(blob25) == versions.KNOWN_RELEASES[2025].schema_sha256
            and len(blob25) == versions.KNOWN_RELEASES[2025].schema_size),
    }
    facts["class_diff_2026_to_2025"] = {
        "classes_2026": len(sch26.classes), "classes_2025": len(sch25.classes),
        "shared_names": len(shared),
        "renumbered_shared": len(renumbered),
        "same_ordinal_shared": len(shared) - len(renumbered),
        "only_in_2026": only26, "only_in_2025": only25,
    }
    # byte-identical across all six 2025 samples?
    schema_hashes = {}
    for fn in sorted(os.listdir(SAMPLES_2025)):
        if not fn.endswith(".rvt"):
            continue
        with open_rvt(os.path.join(SAMPLES_2025, fn)) as f:
            schema_hashes[fn] = sha256_of(f.concat("Formats/Latest"))
    facts["formats_latest_2025"]["identical_across_six_samples"] = (
        len(set(schema_hashes.values())) == 1)
    facts["formats_latest_2025"]["per_sample_sha256"] = schema_hashes

    # ---- 2. ESSchemaStorage / Global/Latest product corpus ----------------
    corpus = {}
    for fn in sorted(os.listdir(SAMPLES_2025)):
        if not fn.endswith(".rvt"):
            continue
        with open_rvt(os.path.join(SAMPLES_2025, fn)) as f:
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
    facts["esschema_corpus_2025"] = {
        "byte_identical_across_six_samples": len(shas) == 1,
        "corpus_sha256": corpus[os.path.basename(SRC)]["corpus_sha256"],
        "total_bytes": corpus[os.path.basename(SRC)]["total_bytes"],
        "total_pairs": corpus[os.path.basename(SRC)]["total_pairs"],
        "tables": corpus[os.path.basename(SRC)]["tables"],
        "per_sample": corpus,
        "corpus_2026_reference": {"total_bytes_rst": None, "note": ""},
    }
    # the 2026 reference corpus, measured the same way (rst sample)
    with open_rvt(s26_path) as f:
        payload26 = f.inflate("Global/Latest")
    t26 = LM.find_json_tables(payload26)
    b26 = b"".join(payload26[t["start"]:t["end"]] for t in t26)
    facts["esschema_corpus_2025"]["corpus_2026_reference"] = {
        "total_pairs": sum(t["count"] for t in t26),
        "total_bytes": len(b26), "corpus_sha256": sha256_of(b26),
    }

    # ---- 3. identity / footer / version markers ---------------------------
    with open_rvt(SRC) as f:
        bfi = decode_basic_file_info(f.raw("BasicFileInfo"))
        et = decode_elemtable(f.inflate("Global/ElemTable"))
        hist = decode_history(f.inflate("Global/History"))
    with open_rvt(s26_path) as f:
        et26 = decode_elemtable(f.inflate("Global/ElemTable"))
        hist26 = decode_history(f.inflate("Global/History"))
    ups25 = list(hist.get("format_versions") or [])
    ups26 = list(hist26.get("format_versions") or [])
    tail25 = et["footer"]["tail_class"]
    tail26 = et26["footer"]["tail_class"]

    def _clsname(sch, tid):
        c = sch.by_id.get(tid)
        return c.name if c is not None else None

    facts["identity_2025"] = {
        "basicfileinfo_format": bfi.get("format"),
        "basicfileinfo_build": bfi.get("build"),
        "elemtable_class_tag": {"2025": hex(et["class_tag"]),
                                "2026": hex(et26["class_tag"]),
                                "name": _clsname(sch25, et["class_tag"])},
        "elemtable_footer_tail_class": {"2025": hex(tail25), "2026": hex(tail26),
                                        "name": _clsname(sch25, tail25)},
        "history_upgrade_versions": {"2025_last": (ups25[-1] if ups25 else None),
                                     "2025_count": len(ups25),
                                     "2026_last": (ups26[-1] if ups26 else None),
                                     "2026_count": len(ups26)},
        "history_class_tag": {"2025": hex(hist.get("class_tag", 0)),
                              "2026": hex(hist26.get("class_tag", 0))},
    }

    # ---- 4. framing ordinals, by-name (re-verified) -----------------------
    facts["framing_2025"] = {k: hex(v) for k, v in
                            versions.ordinals_from_schema(sch25).items()}
    facts["framing_matches_rvt_versions_table"] = (
        versions.ordinals_from_schema(sch25) == dict(versions.KNOWN_RELEASES[2025].framing))
    os.makedirs(OUT, exist_ok=True)
    with open(FACTS_JSON, "w") as fh:
        json.dump(facts, fh, indent=1, default=str)
    log(f"[formats] wrote {relp(FACTS_JSON)}")
    return facts


def write_format_md(facts: dict) -> str:
    fl = facts["formats_latest_2025"]
    cd = facts["class_diff_2026_to_2025"]
    es = facts["esschema_corpus_2025"]
    idn = facts["identity_2025"]
    ref26 = es["corpus_2026_reference"]
    L: List[str] = []
    A = L.append
    A("# FORMAT 2025 -- the pinned Revit-2025 format data the creation side needs")
    A("")
    A("Stream: **genesis-2025-reduce** (2026-08-04).  Generated by "
      "`tools/genesis_2025.py formats`; machine-readable facts in "
      f"`{relp(FACTS_JSON)}`.  Everything below is measured from the "
      "quarantined `samples/2025/` Autodesk samples (DEV-ONLY -- learn from, "
      "never ship) under `rvt.versions.reading`.  Companion docs: "
      "`docs/writer/genesis-2025-plan.md` (the campaign), "
      "`docs/inbox/versions.md` (read parity + the version model), "
      "`docs/inbox/genesis-2025-reduce.md` (the 2025 ladder record).")
    A("")
    A("## 1. `Formats/Latest` -- the 2025 schema constant")
    A("")
    A(f"* size **{fl['size']:,} B**, **{fl['classes']:,} classes**, sha256 "
      f"`{fl['sha256']}`")
    A(f"* byte-identical across all six 2025 samples: "
      f"**{fl['identical_across_six_samples']}**")
    A(f"* matches the `rvt.versions.KNOWN_RELEASES[2025]` pin: "
      f"**{fl['pin_matches_rvt_versions']}**")
    A("")
    A("## 2. Class-list diff 2026 -> 2025 (names are stable, ordinals drift)")
    A("")
    A(f"| | 2026 | 2025 |\n|---|---:|---:|")
    A(f"| classes | {cd['classes_2026']:,} | {cd['classes_2025']:,} |")
    A(f"| shared names | {cd['shared_names']:,} | |")
    A(f"| shared names RENUMBERED (ordinal differs) | {cd['renumbered_shared']:,} | |")
    A(f"| shared names with the SAME ordinal | {cd['same_ordinal_shared']:,} | |")
    A(f"| names only in 2026 | {len(cd['only_in_2026'])} | |")
    A(f"| names only in 2025 | | {len(cd['only_in_2025'])} |")
    A("")
    A("**Consequence (the whole version model in one line): resolve every "
      "class ordinal BY NAME from the target release's schema; never carry "
      "a 2026 ordinal into a 2025 file.**  The six partition-framing "
      "ordinals below are the load-bearing instance.")
    A("")
    A(f"### 2a. The {len(cd['only_in_2026'])} classes that exist in 2026 but NOT in 2025")
    A("")
    A("A genesis constructor may not emit ANY of these into a 2025 file "
      "(the conductor catalog + numbering-format machinery are the ones "
      "`rvt.genesis` actually constructs -- plan SS5a.1):")
    A("")
    A(", ".join(f"`{n}`" for n in cd["only_in_2026"]) or "(none)")
    A("")
    A(f"### 2b. The {len(cd['only_in_2025'])} classes that exist in 2025 but NOT in 2026")
    A("")
    A("None of these is constructed by `rvt.genesis` (plan SS5); they matter "
      "only to the read side, which is schema-directed anyway:")
    A("")
    A(", ".join(f"`{n}`" for n in cd["only_in_2025"]) or "(none)")
    A("")
    A("## 3. The `ESSchemaStorage` / product-runtime corpus (Global/Latest)")
    A("")
    A("The Autodesk Forge unit/spec/parameter-group JSON corpus inside the "
      "ADocument (`ESSchemaStorage`, AppInfo slot) -- shipped PRODUCT data, "
      "byte-identical within a release (counsel C4 applies per release):")
    A("")
    A("| release | (typeid,json) pairs | corpus bytes | sha256 |")
    A("|---|---:|---:|---|")
    A(f"| 2025 | {es['total_pairs']:,} | {es['total_bytes']:,} | `{es['corpus_sha256']}` |")
    A(f"| 2026 (same instrument, rst) | {ref26['total_pairs']:,} | "
      f"{ref26['total_bytes']:,} | `{ref26['corpus_sha256']}` |")
    A("")
    A(f"* byte-identical across all six 2025 samples: "
      f"**{es['byte_identical_across_six_samples']}**")
    A(f"* per-table shape (2025): " + "; ".join(
        f"{t['count']:,} pairs / {t['bytes']:,} B (`{t['sha256_16']}`)"
        for t in es["tables"]))
    A("")
    A("## 4. Identity / footer / version markers")
    A("")
    A(f"* `BasicFileInfo` format string: **`{idn['basicfileinfo_format']}`**, "
      f"build: **`{idn['basicfileinfo_build']}`** (the 2025 samples are "
      "Autodesk 'Development Build' releases)")
    hz = idn["history_upgrade_versions"]
    A(f"* `Global/History` upgrade-version list: 2025 ends **{hz['2025_last']}** "
      f"({hz['2025_count']} entries) -- IDENTICAL to 2026 ({hz['2026_last']}, "
      f"{hz['2026_count']} entries) AND to 2024 (measured directly).  "
      "**CORRECTION to the KNOWLEDGE.md gloss '2662 = Revit 2026': 2662 is the "
      "ADocument schema `version` stamp in the 2024, 2025 AND 2026 schemas** "
      "(verified from each release's own `Formats/Latest`) -- the document "
      "format version froze at 2662 before 2024; the History terminal value "
      "is therefore NOT a release marker, and writing 2662 is correct for "
      "all three creation targets.  The RELEASE-authoritative marker is "
      "`BasicFileInfo` `Format:` (what `rvt.versions.detect_release` keys on).")
    etc = idn["elemtable_class_tag"]
    etf = idn["elemtable_footer_tail_class"]
    A(f"* `Global/ElemTable` lead class tag: 2025 `{etc['2025']}` vs 2026 "
      f"`{etc['2026']}` (= `{etc['name']}` -- an ordinal, resolved by name)")
    A(f"* `ElemTable` footer tail class: 2025 `{etf['2025']}` vs 2026 "
      f"`{etf['2026']}` (= `{etf['name']}`)")
    hc = idn["history_class_tag"]
    A(f"* `Global/History` lead class tag: 2025 `{hc['2025']}` vs 2026 `{hc['2026']}`")
    A("")
    A("These stream-lead tags round-trip automatically through the decoders "
      "(they preserve the decoded `class_tag`); only a from-scratch 2025 "
      "stream author needs the table above.")
    A("")
    A("## 5. Partition-framing ordinals (by-name, re-verified this run)")
    A("")
    A("| constant | class | 2025 |")
    A("|---|---|---|")
    for k, v in facts["framing_2025"].items():
        A(f"| {k} | {versions.FRAMING_CLASSES[k]} | `{v}` |")
    A("")
    A(f"Matches the precomputed `rvt.versions` table: "
      f"**{facts['framing_matches_rvt_versions_table']}**")
    A("")
    A("## 6. The module-local baked-tag patch set (plan SS7 risk, found REAL)")
    A("")
    A("`rvt.versions.reading` patches `rvt.partitions`; these module-LOCAL "
      "copies of the framing ordinals had to be patched too "
      "(`tools/genesis_2025.py context_2025`) before any 2025 emit:")
    A("")
    A("| module | attr | why |")
    A("|---|---|---|")
    A("| `rvt.reduce` | `BLOCK_TAG` (local literal 0x0F28) | `NewBlock.frame` writes block headers |")
    A("| `rvt.reduce` | `BLOCK_TRL_TAG` (from-import) | block trailer mirror |")
    A("| `rvt.manipulate` | `BLOCK_TAG`, `TRAILER_TAG` (from-imports) | the modify path re-frames blocks |")
    A("| `rvt.commit` | `BLOCK_TRL_TAG` (from-import) | commit re-frames touched blocks |")
    A("| `rvt.writer` | `BLOCK_TRL_TAG` (module constant) | reframe_blocks |")
    A("| `rvt.famgen.factory` | `CD_SEPARATOR`, `CD_END_RECORD` (bake 0x3A3/0x3A2) | ContentDocuments grammar (2025: 0x391/0x390) |")
    A("| `rvt.adocument` | `_DECODER` (cached 2026-schema decoder) | ADocument decode/encode must use the file's schema |")
    A("")
    A("Proposed permanent fix (for the versions stream / orchestrator): fold "
      "these into `rvt.versions.activate` so `reading()` covers the emit "
      "path too; until then `context_2025` is the working recipe.")
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
    """experiments/genesis2025/probes.json -- the declaration probe_batch
    resolves bases from (BASE_KEYS: 'base'/'parent_rung'), ordered by
    information value.  Every 2025 file is a candidate-base: NOTHING 2025 is
    viewer-certified yet; certification cascades down the lineage."""
    entries = []
    meta = {
        "R5_2025": {
            "tests": "Round-1 anchor of the 2025 campaign (plan G25-1): does "
                     "the viewer accept a 2025 reduction at all?  R5-equivalent "
                     "of the certified 2026 rung (annotation/schedule content "
                     "removed by maxgc).",
            "if_PASS": "certify; the 2025 reduction mechanics (re-blocker, ECC, "
                       "ordinals) are viewer-proven; R9/K3/K4 verdicts readable.",
            "if_FAIL": "with the sample control PASSING, the 2025 EMIT path is "
                       "defective (framing/ordinal bug) -- bisect against the "
                       "identity re-emit before reading anything else.",
        },
        "R9_2025": {
            "tests": "Deepest R-rung: views/types/options/families' host "
                     "elements gone (the 2026 R9 shape; all 52 embedded docs "
                     "still present, censused).  K3_2025's parent.",
            "if_PASS": "certify; K3_2025's verdict is readable.",
            "if_FAIL": "bisect R6..R8 (viewer rounds); the 2026 precedent says "
                       "this shape passes.",
        },
        "K3_2025": {
            "tests": "Loadable-family USAGE nulled (families + documents "
                     "still present) -- the M3-certified modify path, the "
                     "mandatory parent state of B2025_K4 (2026 precedent: "
                     "K3 PASS, round 5).",
            "if_PASS": "certify; B2025_K4's verdict is readable.",
            "if_FAIL": "the 2025 reader requires head/tag defaults to name "
                       "real families -- B2025_K4 unreadable until split.",
        },
        "B2025_K4": {
            "tests": "THE 2025 FAMILY-FREE BASE CANDIDATE: zero loadable "
                     "families, zero embedded family documents, FOUR-registry "
                     "coherent, on Autodesk's own 2025 skeleton (the certified "
                     "2026 K4 recipe).  PASS = the certified 2025 base every "
                     "G25-3+ substitution rung builds on.",
            "if_PASS": "certify + ledger; the 2025 campaign proceeds to the "
                       "constructor retarget + substitution ladder (G25-3/4).",
            "if_FAIL": "(with K3_2025 passing) the 2025 reader diverges from "
                       "2026 on the family-document question -- re-run the "
                       "KD1-equivalent control before concluding anything.",
        },
    }
    parent = {"R5_2025": None, "R9_2025": None,
              "K3_2025": "R9_2025", "B2025_K4": "K3_2025"}
    for name in ("R5_2025", "R9_2025", "K3_2025", "B2025_K4"):
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
            "report": f"experiments/genesis2025/reduce/{name}.json",
        }
        if parent[name]:
            e["parent_rung"] = parent[name]
        entries.append(e)
    manifest = {
        "stream": "genesis-2025-reduce (the Revit-2025 reduction ladder, "
                  "plan G25-1/G25-2)",
        "situation": (
            "THE REAL END USER RUNS REVIT 2025.  The certified genesis base "
            "G_ABPD is Revit 2026 (unopenable for him); this ladder re-runs "
            "the certified 2026 recipe (rstbasic -> R-rungs -> K3 -> K4) on "
            "Autodesk's own 2025 rst basic sample under rvt.versions.reading. "
            "NOTHING 2025 is viewer-certified yet, so every file here is a "
            "candidate-base; the batch control is the UNTOUCHED 2025 sample "
            "itself (Autodesk's own bytes -- certified by construction), "
            "which simultaneously answers plan risk #1: does the viewer "
            "accept 2025 uploads at all?"),
        "ordering": "reading order: control (the 2025 sample) FIRST -- if it "
                    "fails, the viewer/oracle cannot read 2025 uploads and "
                    "every other verdict is VOID; then R5_2025, R9_2025, "
                    "K3_2025, B2025_K4 (certification cascades; a parent FAIL "
                    "voids its children).",
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
             for n in ("R5_2025", "R9_2025", "K3_2025", "B2025_K4")]
    for f in files:
        if not os.path.exists(f):
            raise SystemExit(f"missing rung {relp(f)} -- run ladder + k3k4 first")
    # batch number: continue the GLOBAL numbering (experiments/acceptance/
    # holds batch_15/16); per-dir numbering would collide confusingly.
    n = max(PB.next_batch_number(PB.ACCEPTANCE), PB.next_batch_number(OUT))
    manifest = PB.stage_batch(
        [], candidate_bases=files, control_from=relp(SRC),
        out_dir=OUT, batch_n=n,
        note=("2025 campaign round 1 (plan G25-1/G25-2 combined): every "
              "entry a candidate-base (no 2025 file is certified yet); "
              "control = the untouched Autodesk 2025 rst sample, which also "
              "answers 'does the viewer accept 2025 uploads?'.  Read with "
              "probe_batch.read_batch_verdicts; certification cascades "
              "R5 -> R9 -> K3 -> B2025_K4."))
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
