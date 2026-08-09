#!/usr/bin/env python3
"""revit_kit.py -- THE REGENERABLE DESKTOP-REVIT CHECK KIT (v2, issue #118).

The open cell (CLAUDE.md §5, genesis-audit VERDICTS #48): OUR generated
families + placed instances on OUR composed base fail Autodesk's audit while
every byte instrument calls them lawful.  The decisive next signal is desktop
Revit's own error dialog / journal (#16).  v1 of the kit shipped two stale
probe copies (H12 = the pre-blob all-native-copy probe whose only defect was
the empty 0x0f3f blob, VERDICTS #36; BXhf_f1i1 = a batch-38-era file that
predates the blob fix).  v2 builds the REAL product shapes, on a fresh clone,
through the front door on the pinned certified base, and writes a manifest
that resolves any element id a dialog or journal names:

    K0_CTRL_G_ABPD.rvt          byte-identical copy of the pinned base (control)
    K1_shell_walls.rvt          the room shell: 4 walls, no loaded family
    K2_equipment_1fam_1inst.rvt one generated family loaded + one placed instance
    K3_room_combined.rvt        K1 + K2 in one file (the stamped product shape)
    families/*.rfa              the generated family K2/K3 load, standalone

    .venv/bin/python tools/revit_kit.py build  [--out experiments/terminal/kit2] [--no-publish]
    .venv/bin/python tools/revit_kit.py verify [--kit experiments/terminal/kit2]
    .venv/bin/python tools/revit_kit.py lookup ID [ID ...] [--kit experiments/terminal/kit2]

``build`` writes the files, ``manifest.json`` (sha256, role, census, expected
reading, and per K1-K3 every build-added element id -> class / save unit /
family) and ``REVIT-CHECK-KIT.md`` into the kit dir, and (unless
``--no-publish``) regenerates ``experiments/terminal/REVIT-CHECK-KIT.md``.
Every kit file is a PROOF-ONLY dev probe under experiments/ (git-ignored
binaries; only json/md are tracked).  Nothing here reads an Autodesk
directory; the human copies the journal out by hand.

Exit codes: 0 = kit built and every self-check holds, 1 = a check failed
(the kit is still written -- deliverable rule), 2 = usage / missing base.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "lib", "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rvt.frontdoor.base import PIN, BaseError, resolve_base, sha256_of  # noqa: E402
from rvt.validate import UNIT_FOOTER_BLOB_LEN as BLOB_LEN               # noqa: E402

KIT_VERSION = 2
DEFAULT_OUT = os.path.join(ROOT, "experiments", "terminal", "kit2")
PUBLISHED_MD = os.path.join(ROOT, "experiments", "terminal", "REVIT-CHECK-KIT.md")
#: the fresh-clone location of the pinned base (resolve_base() finds it there)
PINNED_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
#: kit v2 is DEFINED on this base; asserted equal to the engine's pin at build
#: time -- if the pin ever moves, bump KIT_VERSION together with this literal.
PINNED_SHA256 = "84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50"
PROMPT = "an electrical room with 1 panel"

K0, K1, K2, K3 = ("K0_CTRL_G_ABPD.rvt", "K1_shell_walls.rvt",
                  "K2_equipment_1fam_1inst.rvt", "K3_room_combined.rvt")

#: host classes whose totals the kit reports per file
CLASSES_OF_INTEREST = ("SWall", "Family", "FamilySymbol", "FamSymSurrogate",
                       "FamilySurrogate", "FamilyInstance")
#: the structural classes a build may ADD; anything else added is a check
#: failure, except ParamElemFamily whose count follows the family's parameters
STRUCTURAL = frozenset(CLASSES_OF_INTEREST)
_ONE_FAMILY = {"Family": 1, "FamilySymbol": 1, "FamSymSurrogate": 1,
               "FamilySurrogate": 1, "FamilyInstance": 1}

#: one row per project file: which front-door job/role produces it, and the
#: exact shape it must have (added structural classes, added save units,
#: total SWall in the host document)
KIT_SPEC: Dict[str, Dict[str, Any]] = {
    K0: {"role": "control", "job": None,
         "expect": {"added": {}, "added_units": 0, "swall": 0},
         "expected": "CERTIFIED base, byte-identical to the plugin's pinned G_ABPD ({verdict}). "
                     "Must open clean; if it does not, the Revit install / release is the "
                     "problem and nothing else in the kit can be read."},
    # K1 is its OWN walls-only job (stages "WV": no family generation / load /
    # placement).  Since #244 the strict split's "shell" role = walls + the
    # LOADED family (the WF_fix-certified shape), which would put a family
    # document into K1 and break the single-variable ladder K1 -> K2 (#248).
    K1: {"role": "combined", "job": "walls",
         "expect": {"added": {"SWall": 4}, "added_units": 0, "swall": 4},
         "expected": "Walls-only species on the composed base -- the certified render lane. "
                     "Expected to open clean with 4 walls visible in 3D; a dialog here would "
                     "be NEW information (walls were never the failing axis)."},
    K2: {"role": "equipment", "job": "split",
         "expect": {"added": _ONE_FAMILY, "added_units": 1, "swall": 0},
         "expected": "THE OPEN CELL, minimal: exactly one generated family document (save "
                     "unit 1, 64-B blob present) + one placed instance, no walls. The cloud "
                     "viewer rejects this shape (VERDICTS #48). Whatever dialog / journal "
                     "line Revit shows here IS the fix spec -- capture it verbatim."},
    K3: {"role": "combined", "job": "combined",
         "expect": {"added": {**_ONE_FAMILY, "SWall": 4}, "added_units": 1, "swall": 4},
         "expected": "K1 + K2 in one file: the stamped product shape (PROOF-ONLY: walls+"
                     "families combination). Same dialog as K2 => one shared cause; a "
                     "different / extra dialog => the combination adds a second defect."},
}
RFA_EXPECTED = ("The generated family K2/K3 embed, as a standalone .rfa. Insert > Load "
                "Family it into the opened K1 (or File > Open it). Loads clean => the "
                "defect is in how the project EMBEDS/places it, not the family body; "
                "a dialog => the family document itself is what Revit objects to.")

RETIRED = {
    "H12": ("retired: the all-native-copy probe's ONLY defect was its empty 0x0f3f unit "
            "footer blob -- E1 (= H12 + the donor's 64-B blob, one stream changed) and "
            "E1b (random 64 B) both PASSED in genesis-audit VERDICTS #36. Opening it in "
            "desktop Revit would re-discover a law already fixed in core."),
    "BXhf_f1i1": ("retired: a batch-38-era G_ABPD probe built before the blob fix (empty "
                  "blob on its family unit) -- it fails for the solved reason, not the "
                  "open one."),
}


# ---------------------------------------------------------------------------
# small utils
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[revit_kit] {msg}", flush=True)


def relp(path: str, start: str = ROOT) -> str:
    try:
        return os.path.relpath(path, start).replace(os.sep, "/")
    except ValueError:                                   # other drive (Windows)
        return path


def jdump(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, default=str)
        f.write("\n")


# ---------------------------------------------------------------------------
# read-only inspection of one container
# ---------------------------------------------------------------------------

def _watermark(et) -> int:
    """Highest issued ElementId: max(ElemTable footer last_id, max row id)."""
    return max([int(et.footer.last_id)] + [int(r.id) for r in et.records])


def elemtable_of(path: str):
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    with open_rvt(path) as f:
        return parse_elemtable(inflate_global_stream(f.raw("Global/ElemTable")).payload,
                               os.path.basename(path))


def watermark_of(path: str) -> int:
    return _watermark(elemtable_of(path))


def blob_lengths(path: str) -> List[int]:
    """0x0f3f footer blob length per save unit, in FamilyIndex's global unit
    order (partition streams in container order, units in stream order)."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out: List[int] = []
    with open_rvt(path) as f:
        for pn in f.partition_streams():
            w = StreamWalker(f.logical(pn), inflate=False, keep_data=False)
            out.extend(len(u.footer_blob) for u in w.units)
    return out


def validate(path: str) -> Dict[str, Any]:
    from rvt.validate import validate_file
    fam = os.path.splitext(path)[1].lower() in (".rfa", ".rft")
    rep = validate_file(path, family=fam)
    return {"ok": bool(rep.ok), "errors": len(rep.errors), "warnings": len(rep.warnings),
            "error_messages": [f"[{x.layer}] {x.where}: {x.message}" for x in rep.errors],
            "mode": "family" if fam else "project"}


def _int_refs(v: Any, lo: int, depth: int = 0):
    """Every int > ``lo`` anywhere inside a decoded value (bounded walk)."""
    if isinstance(v, bool):
        return
    if isinstance(v, int):
        if v > lo:
            yield v
    elif isinstance(v, dict) and depth < 8:
        for x in v.values():
            yield from _int_refs(x, lo, depth + 1)
    elif isinstance(v, (list, tuple)) and depth < 8:
        for x in v[:512]:
            yield from _int_refs(x, lo, depth + 1)


def inspect_rvt(path: str, *, base_watermark: int, base_units: int = 1,
                tags: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """Census + the added-element map of one built project file (read-only).

    ``added_elements``: every host-document element whose id is above the
    base watermark -> class, save unit 0, owning family (by reference closure
    over the added set: ParamElemFamily/FamilySurrogate -> Family,
    FamilySymbol.m_familyId -> Family, FamSymSurrogate -> symbol -> Family,
    FamilyInstance -> symbol -> Family), build tag when known.
    ``family_documents``: every GUID-carrying save unit -> host Family name,
    blob length, and its own element id -> class map (a famdoc has its OWN id
    space, so a journal id may resolve there instead of the host)."""
    from rvt.families import FamilyIndex, family_documents
    tags = tags or {}
    fi = FamilyIndex.open(path)
    et = elemtable_of(path)
    et_ids = {int(r.id) for r in et.records}
    u0 = fi.unit_records(0)
    recs102 = u0[102]
    host_ids = set(recs102) & et_ids

    def cls_of(unit_recs, eid):
        for seq in [102] + sorted(s for s in unit_recs if s != 102):
            r = unit_recs.get(seq, {}).get(eid)
            if r is not None:
                return fi.class_name(r.class_id)
        return None

    totals = Counter(fi.class_name(recs102[e].class_id) for e in host_ids)
    added_ids = sorted(i for i in et_ids if i > base_watermark)
    added = [{"id": e, "class": cls_of(u0, e), "unit": 0} for e in added_ids]

    # host families we added (name, famdoc unit, symbols) via the shared census
    fams = {d["family_id"]: d for d in family_documents(fi) if d["family_id"] > base_watermark}
    owner: Dict[int, int] = {f: f for f in fams}
    for d in fams.values():
        for s in d["symbols"]:
            owner[s["symbol_id"]] = d["family_id"]
    added_set = set(added_ids)
    refs = {row["id"]: {i for i in _int_refs(fi.value(0, row["id"]), base_watermark)
                       if i in added_set and i != row["id"]}
            for row in added if row["id"] not in owner and row["id"] in recs102}
    changed = True
    while changed:
        changed = False
        for eid, rr in refs.items():
            hit = next((r for r in sorted(rr) if r in owner), None) if eid not in owner else None
            if hit is not None:
                owner[eid] = owner[hit]
                changed = True
    for row in added:
        fam = fams.get(owner.get(row["id"]))
        row["family"] = fam["family_name"] if fam else None
        row["family_id"] = fam["family_id"] if fam else None
        row["family_unit"] = fam["unit"] if fam else None
        v = fi.value(0, row["id"]) if row["id"] in recs102 else None
        if v and v.get("m_name"):
            row["name"] = str(v["m_name"])
        if row["id"] in tags:
            row["tag"] = tags[row["id"]]

    blobs = blob_lengths(path)
    units = [{"index": u.index, "guid": u.guid, "blocks": u.n_blocks, "blob_len": blobs[u.index]}
             for u in fi.units]
    name_by_unit = {d["unit"]: d["family_name"] for d in fams.values() if d["unit"] is not None}
    famdocs: List[Dict[str, Any]] = []
    for u in units:
        if not u["guid"]:
            continue
        urecs = fi.unit_records(u["index"])
        elems = [{"id": e, "class": cls_of(urecs, e)}
                 for e in sorted({e for seq in urecs.values() for e in seq})]
        famdocs.append({"unit": u["index"], "guid": u["guid"], "blob_len": u["blob_len"],
                        "blocks": u["blocks"], "family": name_by_unit.get(u["index"]),
                        "added": u["index"] >= base_units, "n_elements": len(elems),
                        "classes": dict(Counter(e["class"] or "?" for e in elems)),
                        "elements": elems})
    return {
        "watermark": _watermark(et),
        "elemtable_rows": len(et.records),
        "host_records": len(host_ids),
        "classes": {c: totals.get(c, 0) for c in CLASSES_OF_INTEREST},
        "added_classes": dict(sorted(Counter(r["class"] or "?" for r in added).items())),
        "save_units": units,
        "added_save_units": sum(1 for u in units if u["index"] >= base_units),
        "added_elements": added,
        "family_documents": famdocs,
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

#: the three front-door jobs the kit files come from (K1 walls-only, K2 the
#: strict split's equipment half, K3 the combined product shape)
JOBS: Dict[str, Dict[str, Any]] = {
    "walls": {"strict": False, "stages": "WV"},
    "split": {"strict": True},
    "combined": {"strict": False},
}


def _author(out_dir: str, *, base: str, strict: bool, stages: Optional[str] = None):
    import rvt.frontdoor as FD
    kw: Dict[str, Any] = {"stages": stages} if stages else {}
    r = FD.author(prompt=PROMPT, out=out_dir, base=base, strict=strict, no_handoff=True, **kw)
    if not r.ok:
        label = f"stages={stages}" if stages else ("strict" if strict else "combined")
        raise RuntimeError(f"front door build failed ({label}): {r.status}; {r.errors}")
    return r


def _tags_from(manifest: Dict[str, Any]) -> Dict[int, str]:
    """elem id -> build tag (walls, instances, loaded family/symbol ids)."""
    out: Dict[int, str] = {}
    for row in manifest["build"].get("elements_created") or []:
        for k in ("elem_id", "symbol_id", "family_id", "symbol", "family"):
            if isinstance(row.get(k), int) and row.get("tag"):
                out.setdefault(row[k], str(row["tag"]))
    return out


def build_kit(out_dir: str = DEFAULT_OUT, *, publish_md: Optional[str] = PUBLISHED_MD,
              base_path: Optional[str] = None, keep_build: bool = False) -> Dict[str, Any]:
    """Build K0-K3 + families into ``out_dir``; write manifest.json and
    REVIT-CHECK-KIT.md there (and to ``publish_md`` when given).  Returns the
    manifest (with ``checks`` = the self-check problems, empty when good)."""
    t0 = time.time()
    if PIN.base_sha256.lower() != PINNED_SHA256:
        raise BaseError(f"the genesis pin moved ({PIN.base_sha256[:16]}...): kit v{KIT_VERSION} "
                        f"is defined on {PINNED_SHA256[:16]}... -- bump KIT_VERSION + PINNED_SHA256")
    base = resolve_base(base_path)                    # located + sha-verified against the pin
    out_dir = os.path.abspath(out_dir)
    fam_dir = os.path.join(out_dir, "families")
    work = os.path.join(out_dir, "_build")
    for d in (fam_dir, work):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(fam_dir)

    # -- K0: the byte-identical control ------------------------------------
    k0 = os.path.join(out_dir, K0)
    shutil.copyfile(base.path, k0)
    base_wm = watermark_of(k0)
    base_units = len(blob_lengths(k0))
    log(f"K0 <- {relp(base.path)} sha256 {base.sha256[:16]}... watermark {base_wm}")

    # -- K1: walls-only job; K2: the strict split's equipment half; K3: combined --
    log(f"building on K0 through rvt.frontdoor.author: {PROMPT!r} "
        "(walls-only, strict split, then combined)")
    jobs = {name: _author(os.path.join(work, name), base=k0, **spec)
            for name, spec in JOBS.items()}
    for name, spec in KIT_SPEC.items():
        if spec["job"]:
            built = jobs[spec["job"]].manifest["build"]["files"][spec["role"]]["path"]
            shutil.copyfile(built, os.path.join(out_dir, name))
    fam_rows: Dict[str, Dict[str, Any]] = {}
    for r in jobs.values():
        for row in r.manifest["build"].get("family_files") or []:
            p = row.get("path")
            if p and os.path.isfile(p) and os.path.basename(p) not in fam_rows:
                shutil.copyfile(p, os.path.join(fam_dir, os.path.basename(p)))
                fam_rows[os.path.basename(p)] = row
    if not keep_build:
        shutil.rmtree(work, ignore_errors=True)

    # -- inspect + validate everything (the kit's own gate on the bytes it ships)
    files: List[Dict[str, Any]] = []
    for name, spec in KIT_SPEC.items():
        p = os.path.join(out_dir, name)
        log(f"inspecting {name}")
        job = jobs.get(spec["job"]) if spec["job"] else None
        insp = inspect_rvt(p, base_watermark=base_wm, base_units=base_units,
                           tags=_tags_from(job.manifest) if job else None)
        entry: Dict[str, Any] = {
            "name": name, "kind": "rvt", "role": spec["role"],
            "sha256": sha256_of(p), "bytes": os.path.getsize(p),
            "expected": spec["expected"].format(verdict=(PIN.certification.get("verdict") or "certified")),
            "validation": validate(p),
            "stamps": list(job.as_json().get("stamps") or []) if job else [],
            "added_elements": insp.pop("added_elements"),
            "family_documents": insp.pop("family_documents"),
            "census": insp,
        }
        if job is None:
            entry["source"] = relp(base.path)
            entry["byte_identical_to_pin"] = entry["sha256"] == PINNED_SHA256
        files.append(entry)
    for fname, row in fam_rows.items():
        p = os.path.join(fam_dir, fname)
        files.append({"name": f"families/{fname}", "kind": "rfa", "role": "family",
                      "tag": row.get("tag"), "catalog": row.get("catalog"),
                      "variant": row.get("variant"), "sha256": sha256_of(p),
                      "bytes": os.path.getsize(p), "expected": RFA_EXPECTED,
                      "validation": validate(p), "census": {"blob_lengths": blob_lengths(p)}})

    # -- the id index: any id a dialog names -> where it lives -------------------
    id_index: Dict[str, List[Dict[str, Any]]] = {}
    for e in files:
        for row in e.get("added_elements") or []:
            id_index.setdefault(str(row["id"]), []).append(
                {"file": e["name"], "unit": 0, "class": row["class"],
                 "family": row.get("family"), "tag": row.get("tag")})
        for fd in e.get("family_documents") or []:
            for el in fd["elements"]:
                id_index.setdefault(str(el["id"]), []).append(
                    {"file": e["name"], "unit": fd["unit"], "unit_guid": fd["guid"],
                     "class": el["class"], "family": fd.get("family")})

    manifest: Dict[str, Any] = {
        "schema": f"tekton.revit-check-kit/{KIT_VERSION}",
        "kit_version": KIT_VERSION,
        "tool": "tools/revit_kit.py",
        "issue": "#118 (kit v2); serves #16 (the desktop-Revit round)",
        "honesty": "PROOF-ONLY dev probes under experiments/; never a deliverable",
        "volatility": ("K2/K3/.rfa sha256 and famdoc GUIDs differ per build (famgen mints "
                       "fresh GUIDs, cf. #9); element ids and classes are stable. Read the "
                       "manifest.json that travelled WITH the files; `verify` catches a mismatch."),
        "base": {"path": relp(base.path), "source": base.source, "sha256": base.sha256,
                 "pinned_sha256": PINNED_SHA256, "watermark": base_wm,
                 "save_units": base_units, "release": int(PIN.revit_release),
                 "verdict": PIN.certification.get("verdict")},
        "prompt": PROMPT,
        "built_through": "rvt.frontdoor.author(prompt, base=K0, stages='WV') -> K1 (walls "
                         "only); strict=True -> K2 (the split's equipment half); "
                         "strict=False -> K3",
        "build_seconds": {k: r.seconds for k, r in jobs.items()},
        "files": files,
        "id_index": id_index,
    }
    manifest["checks"] = check_kit(manifest)
    manifest["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(out_dir, "manifest.json"), manifest)
    md = render_kit_md(manifest)
    for target in filter(None, (os.path.join(out_dir, "REVIT-CHECK-KIT.md"), publish_md)):
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
    if publish_md:
        log(f"published {relp(publish_md)}")
    log(f"kit written to {relp(out_dir)} in {manifest['seconds']} s; "
        f"checks: {manifest['checks'] or 'ALL HOLD'}")
    return manifest


# ---------------------------------------------------------------------------
# self-checks (shared by the CLI and tests/test_revit_kit.py)
# ---------------------------------------------------------------------------

def _file(manifest: Dict[str, Any], name: str) -> Dict[str, Any]:
    for e in manifest["files"]:
        if e["name"] == name:
            return e
    raise KeyError(name)


def check_kit(manifest: Dict[str, Any]) -> List[str]:
    """The kit's shape laws (KIT_SPEC + blob + validator); returns the list of
    violated ones (empty = good)."""
    names = {e["name"] for e in manifest["files"]}
    bad = [f"{n} missing" for n in KIT_SPEC if n not in names]
    if bad:
        return bad
    if _file(manifest, K0)["sha256"] != PINNED_SHA256:
        bad.append("K0 is not byte-identical to the pinned G_ABPD")
    for e in manifest["files"]:
        v = e["validation"]
        if not v["ok"] or v["errors"]:
            bad.append(f"{e['name']}: validator {v['errors']} error(s): {v['error_messages'][:3]}")
    for name, spec in KIT_SPEC.items():
        e, want = _file(manifest, name), spec["expect"]
        got = {c: n for c, n in e["census"]["added_classes"].items() if c != "ParamElemFamily"}
        if got != want["added"]:
            bad.append(f"{name}: added structural classes {got} != {want['added']}")
        unexpected = set(got) - STRUCTURAL
        if unexpected:
            bad.append(f"{name}: unexpected added classes {sorted(unexpected)}")
        if e["census"]["classes"]["SWall"] != want["swall"]:
            bad.append(f"{name}: SWall total {e['census']['classes']['SWall']} != {want['swall']}")
        added_docs = [d for d in e["family_documents"] if d["added"]]
        if e["census"]["added_save_units"] != want["added_units"] or len(added_docs) != want["added_units"]:
            bad.append(f"{name}: added save units {e['census']['added_save_units']} != {want['added_units']}")
        for u in e["census"]["save_units"]:
            if u["blob_len"] != BLOB_LEN:
                bad.append(f"{name}: unit {u['index']} 0x0f3f blob {u['blob_len']} B != {BLOB_LEN}")
        if want["added"] and not e["added_elements"]:
            bad.append(f"{name}: added-element id map empty")
    if not any(e["kind"] == "rfa" for e in manifest["files"]):
        bad.append("no families/*.rfa in the kit")
    if not manifest["id_index"]:
        bad.append("id_index empty")
    return bad


# ---------------------------------------------------------------------------
# the markdown
# ---------------------------------------------------------------------------

def render_kit_md(manifest: Dict[str, Any]) -> str:
    files = manifest["files"]
    rvts = [e for e in files if e["kind"] == "rvt"]
    rfas = [e for e in files if e["kind"] == "rfa"]
    base = manifest["base"]
    rel = base["release"]
    rfa_name = rfas[0]["name"] if rfas else "families/<the .rfa>"

    lines: List[str] = []
    w = lines.append
    w("# REVIT CHECK KIT v2 -- one desktop-Revit session, four project files + one family, ~15 minutes")
    w("")
    w("Generated by `tools/revit_kit.py build` (issue #118; serves #16). **Regenerable "
      "anywhere** -- a fresh clone rebuilds every file below in well under a minute:")
    w("")
    w("```bash")
    w(".venv/bin/python tools/revit_kit.py build --out experiments/terminal/kit2")
    w(".venv/bin/python tools/revit_kit.py lookup <element-id>      # resolve an id a dialog/journal names")
    w("```")
    w("")
    w("**Why you are being asked.** Autodesk's cloud viewer rejects our generated "
      "family + placed instance on our composed base with an opaque \"Processing "
      "failed\"; 26 single-variable viewer rounds (docs/inbox/genesis-audit.md "
      "#31-#48) exonerated every axis our byte instruments can measure. Desktop Revit "
      "shows the SPECIFIC dialog and writes a journal line naming the element or "
      "table it objects to. One open attempt per file below is worth more than ten "
      "more cloud probes.")
    w("")
    w("**What changed since v1.** The two v1 files are retired, do not open them:")
    for k, why in RETIRED.items():
        w(f"- `{k}` -- {why}")
    w("The v2 files are the real product shapes, built through the front door on the "
      "pinned certified base, every unit carrying the 64-byte blob, every file "
      "validating 0 errors.")
    w("")
    w("## Files (open in THIS order)")
    w("")
    w("| # | file | what it is | walls | placed instances | added family docs | validator |")
    w("|---|---|---|---|---|---|---|")
    for i, e in enumerate(rvts):
        v, cz = e["validation"], e["census"]["classes"]
        w(f"| {i} | `{e['name']}` | {e['role']} | {cz['SWall']} | {cz['FamilyInstance']} "
          f"| {e['census']['added_save_units']} | {v['errors']} errors / {v['warnings']} warnings |")
    for j, e in enumerate(rfas, start=len(rvts)):
        v = e["validation"]
        w(f"| {j} | `{e['name']}` | standalone generated family ({e.get('tag') or '?'}) "
          f"| - | - | - | {v['errors']} errors / {v['warnings']} warnings |")
    w("")
    w(f"`{K0}` is byte-identical to the pinned base (sha256 `{base['pinned_sha256']}`); "
      f"the other files were built ON it, so every element id above the base watermark "
      f"**{base['watermark']}** was authored by tekton. `manifest.json` beside these files "
      "lists, per file, every such id -> class -> save unit -> family, and an `id_index` "
      "across the whole kit. Always keep the `manifest.json` that came WITH the files you "
      "open: family-document GUIDs and K2/K3 hashes differ per build.")
    w("")
    w("Expected reading per file:")
    w("")
    for e in rvts + rfas[:1]:
        w(f"- `{e['name']}` -- {e['expected']}")
    w("")
    w(f"## What to do (Revit {rel}; a newer release is fine and will offer to upgrade; "
      "an OLDER release cannot open these -- stop there)")
    w("")
    w("For EACH project file, in the order above:")
    w("")
    w("1. File > Open > browse to the file and **tick `Audit`** in the Open dialog before "
      "clicking Open. Audit makes Revit run its full consistency pass and say what it repaired.")
    w("2. **Screenshot every dialog that appears, in order, before clicking anything.** "
      "If a dialog has `Show`, `More Info`, `Expand` or `Details`, open it and screenshot "
      "that too. Then click through (OK / Close / Continue -- never `Delete` unless it is the only way on, and say so).")
    w("3. If a dialog names an **element id**: note it, then once the file is open use "
      "Manage > Inquiry > **Select by ID**, paste the id, and screenshot what gets selected "
      "(Properties palette open). `tools/revit_kit.py lookup <id>` (or `manifest.json` "
      "`id_index`) tells us which of our elements that is -- host element or inside the "
      "family document.")
    w("4. If it opens: Manage > Inquiry > **Review Warnings** -> Export the list (or screenshot it in full). "
      "Open the default 3D view: K1/K3 should show four walls; K2/K3 a panelboard box near x = -15 ft. Screenshot.")
    w("5. File > Save As under a new name; screenshot any dialog (a save-time audit failure is as informative as an open-time one).")
    w(f"6. With `{K1}` open and clean: Insert > **Load Family** > `{rfa_name}`; "
      "screenshot any dialog; if it loads, place one instance from the Project Browser and Save As again.")
    w("7. **Always attach the newest journal**, whatever happened (clean open, dialog, or crash): "
      f"after closing Revit, open `%LOCALAPPDATA%\\Autodesk\\Revit\\Autodesk Revit {rel}\\Journals` "
      "in Explorer, sort by date, and **copy the newest `journal.*.txt` out by hand** to the folder "
      "you send back. Never point a script or tool at that directory (or any Autodesk directory) -- copy the file out, then we read the copy.")
    w("8. If Revit CRASHES: screenshot the crash reporter, do not send the report to Autodesk, and grab the journal as in step 7 (it names the failing subsystem, cf. docs/inbox/rfa-revit-api-compat.md Iteration 3).")
    w("")
    w("## What each outcome tells us")
    w("")
    w("| outcome | reading |")
    w("|---|---|")
    w(f"| `{K0}` shows any dialog | STOP: the control failed -- wrong Revit release or a broken install; nothing else in the round can be read |")
    w(f"| `{K0}` + `{K1}` clean, `{K2}` dialog | the expected split: the dialog / journal line for K2 names the audit's objection to our generated family document or its placement -- that text is the fix spec (verdict #49) |")
    w(f"| `{K1}` dialog too | NEW: walls on the composed base are certified in the cloud viewer; a desktop-only objection to the shell would be a second, independent finding -- capture it separately |")
    w(f"| `{K2}` and `{K3}` same dialog | one shared root cause (the family document / instance); the walls+families combination adds nothing |")
    w(f"| `{K3}` dialog differs from `{K2}` | the combination carries an ADDITIONAL defect beyond the open cell -- both texts matter |")
    w(f"| `{K2}`/`{K3}` open clean with Audit ticked | desktop Revit accepts what the cloud viewer rejects: the defect is a viewer-side ingest rule; record it, ship stamped, chase the viewer separately |")
    w(f"| `{K2}` opens but Review Warnings lists entries | export them: a warning naming a family/symbol/instance id is nearly as good as a dialog |")
    w("| the `.rfa` fails Insert > Load Family | the family document body itself is what Revit objects to (compare #52's journal method); if it loads clean while K2 fails, the defect is in the EMBED/placement, not the body |")
    w("| Revit crashes on K2/K3 | the journal's last `DBG_WARN` / assertion line localises the subsystem -- attach it |")
    w("")
    w("## Send back")
    w("")
    w("The screenshots, the exported warnings (if any), the copied journal file(s), the kit's `manifest.json`, "
      "and one line per file: `opened clean` / `dialog: <first words>` / `corrupt: <detail line>` / `crash`. "
      "The receiving session records it as the next `## ORCHESTRATOR VERDICTS` entry in docs/inbox/genesis-audit.md and on issue #16.")
    w("")
    w("## Safety / provenance")
    w("")
    w("Every file here is a **PROOF-ONLY dev probe** (git-ignored under experiments/), built by our own "
      "writer on our composed genesis base; the family is generated from manufacturer facts, no third-party geometry. "
      "Do not redistribute; delete after the check. Nothing here touches your firm's models or your Autodesk "
      "account beyond opening local files. The kit never reads or asks you to expose any Autodesk installation directory.")
    w("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# verify / lookup
# ---------------------------------------------------------------------------

def load_manifest(kit_dir: str) -> Dict[str, Any]:
    with open(os.path.join(kit_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def verify_kit(kit_dir: str = DEFAULT_OUT) -> List[str]:
    """Re-check an existing kit dir against its manifest (sha256 per file,
    K0 against the pin) plus the recorded shape checks."""
    m = load_manifest(kit_dir)
    bad = check_kit(m)
    for e in m["files"]:
        p = os.path.join(kit_dir, e["name"])
        if not os.path.isfile(p):
            bad.append(f"{e['name']} absent from {relp(kit_dir)}")
        elif sha256_of(p) != e["sha256"]:
            bad.append(f"{e['name']} sha256 differs from manifest (rebuilt or corrupted copy)")
    return bad


def lookup(kit_dir: str, ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    idx = load_manifest(kit_dir)["id_index"]
    return {str(i): idx.get(str(i), []) for i in ids}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="revit_kit", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build K0-K3 + families, manifest.json, REVIT-CHECK-KIT.md")
    b.add_argument("--out", default=DEFAULT_OUT, help="kit directory (default experiments/terminal/kit2)")
    b.add_argument("--no-publish", action="store_true",
                   help="do not regenerate experiments/terminal/REVIT-CHECK-KIT.md")
    b.add_argument("--keep-build", action="store_true", help="keep the front-door job dirs under <out>/_build")
    v = sub.add_parser("verify", help="re-check an existing kit dir against its manifest")
    v.add_argument("--kit", default=DEFAULT_OUT)
    lk = sub.add_parser("lookup", help="resolve element id(s) a Revit dialog/journal names")
    lk.add_argument("ids", nargs="+")
    lk.add_argument("--kit", default=DEFAULT_OUT)
    a = ap.parse_args(argv)

    if a.cmd == "build":
        try:
            m = build_kit(a.out, publish_md=None if a.no_publish else PUBLISHED_MD,
                          keep_build=a.keep_build)
        except BaseError as e:
            log(f"ERROR {e}")
            return 2
        for e in m["files"]:
            v = e["validation"]
            log(f"  {e['name']:<44} sha256 {e['sha256'][:12]}  {v['errors']} errors / "
                f"{v['warnings']} warnings  " + (
                    f"added {e['census']['added_classes']} units+{e['census']['added_save_units']}"
                    if e["kind"] == "rvt" else f"({e.get('tag')})"))
        log(f"id_index: {len(m['id_index'])} ids")
        return int(bool(m["checks"]))
    if not os.path.isfile(os.path.join(a.kit, "manifest.json")):
        log(f"ERROR no manifest.json in {a.kit} -- run `revit_kit.py build --out {a.kit}` first")
        return 2
    if a.cmd == "verify":
        bad = verify_kit(a.kit)
        log(f"PROBLEMS: {bad}" if bad else
            "VERIFIED: every file matches its manifest and every shape law holds")
        return int(bool(bad))
    res = lookup(a.kit, a.ids)
    for i, hits in res.items():
        if not hits:
            print(f"{i}: not a kit-added element (base element <= watermark, or unknown)")
        for h in hits:
            print(f"{i}: {h['file']} unit {h['unit']}"
                  + (f" ({h['unit_guid']})" if h.get("unit_guid") else " (host)")
                  + f" class {h['class']}"
                  + (f" family {h['family']!r}" if h.get("family") else "")
                  + (f" tag {h['tag']}" if h.get("tag") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
