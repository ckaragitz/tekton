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
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "lib", "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KIT_VERSION = 2
DEFAULT_OUT = os.path.join(ROOT, "experiments", "terminal", "kit2")
PUBLISHED_MD = os.path.join(ROOT, "experiments", "terminal", "REVIT-CHECK-KIT.md")
PINNED_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
PINNED_SHA256 = "84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50"
BASE_WATERMARK = 1472524          # G_ABPD's highest issued ElementId (== rst == K4)
BLOB_LEN = 64                     # the 0x0f3f unit footer blob law (VERDICTS #36)
PROMPT = "an electrical room with 1 panel"

K0, K1, K2, K3 = ("K0_CTRL_G_ABPD.rvt", "K1_shell_walls.rvt",
                  "K2_equipment_1fam_1inst.rvt", "K3_room_combined.rvt")

#: classes whose counts the kit reports per file (total in host doc + added)
CLASSES_OF_INTEREST = ("SWall", "Family", "FamilySymbol", "FamSymSurrogate",
                       "FamilySurrogate", "FamilyInstance")

EXPECTED = {
    K0: ("CERTIFIED base, byte-identical to the plugin's pinned G_ABPD (viewer "
         "verdict #24). Must open clean; if it does not, the Revit install / "
         "release is the problem and nothing else in the kit can be read."),
    K1: ("Walls-only species on the composed base -- the certified render lane. "
         "Expected to open clean with 4 walls visible in 3D; a dialog here would "
         "be NEW information (walls were never the failing axis)."),
    K2: ("THE OPEN CELL, minimal: exactly one generated family document (save "
         "unit 1, 64-B blob present) + one placed instance, no walls. The cloud "
         "viewer rejects this shape (VERDICTS #48). Whatever dialog / journal "
         "line Revit shows here IS the fix spec -- capture it verbatim."),
    K3: ("K1 + K2 in one file: the stamped product shape (PROOF-ONLY: walls+"
         "families combination). Same dialog as K2 => one shared cause; a "
         "different / extra dialog => the combination adds a second defect."),
    "rfa": ("The generated family K2/K3 embed, as a standalone .rfa. Insert > Load "
            "Family it into the opened K1 (or File > Open it). Loads clean => the "
            "defect is in how the project EMBEDS/places it, not the family body; "
            "a dialog => the family document itself is what Revit objects to."),
}


# ---------------------------------------------------------------------------
# small utils
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[revit_kit] {msg}", flush=True)


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def relp(path: str, start: str = ROOT) -> str:
    try:
        return os.path.relpath(path, start).replace(os.sep, "/")
    except ValueError:                                   # other drive (Windows)
        return path


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, default=str)
        f.write("\n")


# ---------------------------------------------------------------------------
# read-only inspection of one container
# ---------------------------------------------------------------------------

def elemtable_of(path: str):
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    with open_rvt(path) as f:
        return parse_elemtable(inflate_global_stream(f.raw("Global/ElemTable")).payload,
                               os.path.basename(path))


def watermark_of(path: str) -> int:
    """Highest issued ElementId: max(ElemTable footer last_id, max row id)."""
    et = elemtable_of(path)
    return max([int(et.footer.last_id)] + [int(r.id) for r in et.records])


def save_units(path: str) -> List[Dict[str, Any]]:
    """Every Partitions save unit: index, GUID, block count, 0x0f3f blob length."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out: List[Dict[str, Any]] = []
    with open_rvt(path) as f:
        for pn in f.partition_streams():
            w = StreamWalker(f.logical(pn), inflate=False, keep_data=False)
            for u in w.units:
                out.append({"stream": pn, "index": u.index,
                            "guid": str(uuid.UUID(bytes_le=u.guid)) if u.guid else None,
                            "blocks": u.n_blocks, "blob_len": len(u.footer_blob),
                            "kind": "host" if not u.guid else "famdoc"})
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
    from rvt.families import FamilyIndex
    tags = tags or {}
    fi = FamilyIndex.open(path)
    et = elemtable_of(path)
    et_ids = {int(r.id) for r in et.records}
    wm = max([int(et.footer.last_id)] + list(et_ids)) if et_ids else int(et.footer.last_id)
    u0 = fi.unit_records(0)
    recs102 = u0.get(102, {})
    host_ids = set(recs102) & et_ids if et_ids else set(recs102)

    def cls_of(unit_recs, eid):
        for seq in [102] + sorted(s for s in unit_recs if s != 102):
            r = unit_recs.get(seq, {}).get(eid)
            if r is not None:
                return fi.class_name(r.class_id), seq
        return None, None

    totals = {c: 0 for c in CLASSES_OF_INTEREST}
    for eid in host_ids:
        c = fi.class_name(recs102[eid].class_id)
        if c in totals:
            totals[c] += 1

    added_ids = sorted(i for i in et_ids if i > base_watermark)
    added: List[Dict[str, Any]] = []
    added_counts: Dict[str, int] = {}
    for eid in added_ids:
        c, seq = cls_of(u0, eid)
        added.append({"id": eid, "class": c, "seq": seq, "unit": 0, "unit_kind": "host"})
        added_counts[c or "?"] = added_counts.get(c or "?", 0) + 1

    # host Family -> name / famdoc GUID; then family attribution by ref closure
    units = save_units(path)
    guid_unit = {u["guid"]: u["index"] for u in units if u["guid"]}
    fam_name: Dict[int, str] = {}
    fam_guid: Dict[int, Optional[str]] = {}
    for row in added:
        if row["class"] == "Family":
            v = fi.value(0, row["id"]) or {}
            fam_name[row["id"]] = str(v.get("m_name") or "")
            fam_guid[row["id"]] = ((v.get("m_oFamDoc") or {}).get("value") or {}).get("m_contentDocGUID")
    owner: Dict[int, int] = {f: f for f in fam_name}
    refs: Dict[int, List[int]] = {}
    added_set = set(added_ids)
    for row in added:
        if row["id"] in owner or row["seq"] != 102:
            continue
        v = fi.value(0, row["id"])
        refs[row["id"]] = sorted({i for i in _int_refs(v, base_watermark)
                                  if i in added_set and i != row["id"]})
    changed = True
    while changed:
        changed = False
        for eid, rr in refs.items():
            if eid in owner:
                continue
            for r in rr:
                if r in owner:
                    owner[eid] = owner[r]
                    changed = True
                    break
    for row in added:
        f = owner.get(row["id"])
        row["family"] = fam_name.get(f) if f is not None else None
        row["family_id"] = f
        g = fam_guid.get(f) if f is not None else None
        row["family_unit"] = guid_unit.get(g) if g else None
        v = fi.value(0, row["id"]) if row["seq"] == 102 else None
        if v and v.get("m_name"):
            row["name"] = str(v.get("m_name"))
        if row["id"] in tags:
            row["tag"] = tags[row["id"]]
        row.pop("seq", None)

    famdocs: List[Dict[str, Any]] = []
    name_by_guid = {g: fam_name[f] for f, g in fam_guid.items() if g}
    for u in units:
        if not u["guid"]:
            continue
        urecs = fi.unit_records(u["index"])
        elems = []
        for eid in sorted({e for seq in urecs.values() for e in seq}):
            c, _s = cls_of(urecs, eid)
            elems.append({"id": eid, "class": c})
        hist: Dict[str, int] = {}
        for e in elems:
            hist[e["class"] or "?"] = hist.get(e["class"] or "?", 0) + 1
        famdocs.append({"unit": u["index"], "guid": u["guid"], "blob_len": u["blob_len"],
                        "blocks": u["blocks"], "family": name_by_guid.get(u["guid"]),
                        "added": u["index"] >= base_units,
                        "n_elements": len(elems), "classes": hist, "elements": elems})

    return {
        "watermark": wm,
        "elemtable_rows": len(et.records),
        "host_records": len(host_ids),
        "classes": totals,
        "added_classes": dict(sorted(added_counts.items())),
        "save_units": units,
        "added_save_units": sum(1 for u in units if u["index"] >= base_units),
        "added_elements": added,
        "family_documents": famdocs,
    }


def inspect_rfa(path: str) -> Dict[str, Any]:
    units = save_units(path)
    return {"save_units": units}


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _author(out_dir: str, *, base: str, strict: bool):
    import rvt.frontdoor as FD
    r = FD.author(prompt=PROMPT, out=out_dir, base=base, strict=strict, no_handoff=True)
    if not r.ok:
        raise RuntimeError(f"front door build failed ({'strict' if strict else 'combined'}): "
                           f"{r.status}; {r.errors}")
    return r


def _tags_from(manifest: Dict[str, Any]) -> Dict[int, str]:
    """elem id -> build tag (walls, instances, loaded family/symbol ids)."""
    out: Dict[int, str] = {}
    for row in (manifest.get("build") or {}).get("elements_created") or []:
        t = row.get("tag")
        for k in ("elem_id", "symbol_id", "family_id", "symbol", "family"):
            v = row.get(k)
            if isinstance(v, int) and t:
                out.setdefault(v, str(t))
    return out


def _family_rows(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in (manifest.get("build") or {}).get("family_files") or []]


def build_kit(out_dir: str = DEFAULT_OUT, *, publish_md: Optional[str] = PUBLISHED_MD,
              base_path: str = PINNED_BASE, keep_build: bool = False) -> Dict[str, Any]:
    """Build K0-K3 + families into ``out_dir``; write manifest.json and
    REVIT-CHECK-KIT.md there (and to ``publish_md`` when given).  Returns the
    manifest (with ``checks`` = the self-check problems, empty when good)."""
    t0 = time.time()
    out_dir = os.path.abspath(out_dir)
    if not os.path.isfile(base_path):
        raise FileNotFoundError(f"pinned base absent: {relp(base_path)}")
    os.makedirs(out_dir, exist_ok=True)
    fam_dir = os.path.join(out_dir, "families")
    work = os.path.join(out_dir, "_build")
    for d in (fam_dir, work):
        if os.path.isdir(d):
            shutil.rmtree(d)
    os.makedirs(fam_dir)

    # -- K0: the byte-identical control ------------------------------------
    k0 = os.path.join(out_dir, K0)
    shutil.copyfile(base_path, k0)
    base_sha = sha256_of(k0)
    base_wm = watermark_of(k0)
    base_units = len(save_units(k0))
    log(f"K0 <- {relp(base_path)} sha256 {base_sha[:16]}... watermark {base_wm}")

    # -- K1 + K2: the strict twins; K3: the combined product shape --------------
    log(f"building on K0 through rvt.frontdoor.author: {PROMPT!r} (strict, then combined)")
    r_split = _author(os.path.join(work, "split"), base=k0, strict=True)
    r_comb = _author(os.path.join(work, "combined"), base=k0, strict=False)
    bs, bc = r_split.manifest["build"]["files"], r_comb.manifest["build"]["files"]
    src = {K1: bs["shell"]["path"], K2: bs["equipment"]["path"], K3: bc["combined"]["path"]}
    for name, p in src.items():
        shutil.copyfile(p, os.path.join(out_dir, name))
    tags = {K1: _tags_from(r_split.manifest), K2: _tags_from(r_split.manifest),
            K3: _tags_from(r_comb.manifest)}
    build_seconds = {"split": r_split.seconds, "combined": r_comb.seconds}
    stamps = {K1: list(r_split.as_json().get("stamps") or []),
              K2: list(r_split.as_json().get("stamps") or []),
              K3: list(r_comb.as_json().get("stamps") or [])}

    fam_files: List[Dict[str, Any]] = []
    seen = set()
    for r in (r_split, r_comb):
        for row in _family_rows(r.manifest):
            p = row.get("path")
            if not p or not os.path.isfile(p):
                continue
            name = os.path.basename(p)
            if name in seen:
                continue
            seen.add(name)
            dst = os.path.join(fam_dir, name)
            shutil.copyfile(p, dst)
            fam_files.append({"name": f"families/{name}", "tag": row.get("tag"),
                              "catalog": row.get("catalog"), "variant": row.get("variant")})
    if not keep_build:
        shutil.rmtree(work, ignore_errors=True)

    # -- inspect + validate everything -----------------------------------------
    files: List[Dict[str, Any]] = []
    roles = {K0: "control", K1: "shell", K2: "equipment", K3: "combined"}
    for name in (K0, K1, K2, K3):
        p = os.path.join(out_dir, name)
        log(f"inspecting {name}")
        entry: Dict[str, Any] = {
            "name": name, "kind": "rvt", "role": roles[name],
            "sha256": sha256_of(p), "bytes": os.path.getsize(p),
            "expected": EXPECTED[name], "validation": validate(p),
            "stamps": stamps.get(name, []),
        }
        if name == K0:
            entry["source"] = relp(base_path)
            entry["byte_identical_to_pin"] = entry["sha256"] == PINNED_SHA256
            entry["census"] = {k: v for k, v in inspect_rvt(
                p, base_watermark=base_wm, base_units=base_units).items()
                if k not in ("added_elements", "family_documents")}
            entry["added_elements"], entry["family_documents"] = [], []
        else:
            insp = inspect_rvt(p, base_watermark=base_wm, base_units=base_units,
                               tags=tags[name])
            entry["added_elements"] = insp.pop("added_elements")
            entry["family_documents"] = insp.pop("family_documents")
            entry["census"] = insp
        files.append(entry)
    for ff in fam_files:
        p = os.path.join(out_dir, ff["name"])
        ff.update({"kind": "rfa", "role": "family", "sha256": sha256_of(p),
                   "bytes": os.path.getsize(p), "expected": EXPECTED["rfa"],
                   "validation": validate(p), "census": inspect_rfa(p)})
        files.append(ff)

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
        "schema": "tekton.revit-check-kit/2",
        "kit_version": KIT_VERSION,
        "tool": "tools/revit_kit.py",
        "issue": "#118 (kit v2); serves #16 (the desktop-Revit round)",
        "honesty": "PROOF-ONLY dev probes under experiments/; never a deliverable",
        "base": {"path": relp(base_path), "sha256": base_sha, "pinned_sha256": PINNED_SHA256,
                 "watermark": base_wm, "save_units": base_units, "release": 2026},
        "prompt": PROMPT,
        "built_through": "rvt.frontdoor.author(prompt, base=K0, strict=True) -> K1/K2; "
                         "strict=False -> K3",
        "build_seconds": build_seconds,
        "open_order": [K0, K1, K2, K3] + [f["name"] for f in fam_files[:1]],
        "retired": RETIRED,
        "files": files,
        "id_index": id_index,
    }
    manifest["checks"] = check_kit(manifest)
    manifest["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(out_dir, "manifest.json"), manifest)
    md = render_kit_md(manifest)
    with open(os.path.join(out_dir, "REVIT-CHECK-KIT.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    if publish_md:
        with open(publish_md, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        log(f"published {relp(publish_md)}")
    log(f"kit written to {relp(out_dir)} in {manifest['seconds']} s; "
        f"checks: {'ALL HOLD' if not manifest['checks'] else manifest['checks']}")
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
    """The kit's shape laws; returns the list of violated ones (empty = good)."""
    bad: List[str] = []
    names = {e["name"] for e in manifest["files"]}
    for n in (K0, K1, K2, K3):
        if n not in names:
            bad.append(f"{n} missing")
    if bad:
        return bad
    if manifest["base"]["sha256"] != PINNED_SHA256:
        bad.append(f"base sha256 {manifest['base']['sha256'][:16]} != pin {PINNED_SHA256[:16]}")
    if manifest["base"]["watermark"] != BASE_WATERMARK:
        bad.append(f"base watermark {manifest['base']['watermark']} != {BASE_WATERMARK}")
    for e in manifest["files"]:
        v = e["validation"]
        if not v["ok"] or v["errors"]:
            bad.append(f"{e['name']}: validator {v['errors']} error(s): {v['error_messages'][:3]}")
    k0 = _file(manifest, K0)
    if k0["sha256"] != PINNED_SHA256 or not k0.get("byte_identical_to_pin"):
        bad.append("K0 is not byte-identical to the pinned G_ABPD")
    k1 = _file(manifest, K1)
    if k1["census"]["classes"].get("SWall") != 4:
        bad.append(f"K1 SWall {k1['census']['classes'].get('SWall')} != 4")
    if k1["census"]["added_classes"] != {"SWall": 4}:
        bad.append(f"K1 added {k1['census']['added_classes']} != 4 SWall only")
    if k1["census"]["added_save_units"] != 0:
        bad.append(f"K1 added save units {k1['census']['added_save_units']} != 0")
    k2 = _file(manifest, K2)
    a2 = k2["census"]["added_classes"]
    for c in ("Family", "FamilySymbol", "FamSymSurrogate", "FamilyInstance"):
        if a2.get(c) != 1:
            bad.append(f"K2 added {c} {a2.get(c)} != 1")
    if k2["census"]["classes"].get("SWall"):
        bad.append(f"K2 SWall {k2['census']['classes'].get('SWall')} != 0")
    added_docs = [d for d in k2["family_documents"] if d["added"]]
    if k2["census"]["added_save_units"] != 1 or len(added_docs) != 1:
        bad.append(f"K2 added save units {k2['census']['added_save_units']} != 1")
    elif added_docs[0]["blob_len"] != BLOB_LEN:
        bad.append(f"K2 famdoc unit blob {added_docs[0]['blob_len']} B != {BLOB_LEN}")
    k3 = _file(manifest, K3)
    a3 = k3["census"]["added_classes"]
    if a3.get("SWall") != 4 or a3.get("FamilyInstance") != 1 or a3.get("Family") != 1:
        bad.append(f"K3 added {a3} != 4 SWall + 1 Family + 1 FamilyInstance")
    if k3["census"]["added_save_units"] != 1:
        bad.append(f"K3 added save units {k3['census']['added_save_units']} != 1")
    for n in (K1, K2, K3):
        e = _file(manifest, n)
        if not e["added_elements"]:
            bad.append(f"{n}: added-element id map empty")
        for d in e["family_documents"]:
            if d["blob_len"] != BLOB_LEN:
                bad.append(f"{n}: unit {d['unit']} blob {d['blob_len']} B != {BLOB_LEN}")
    if not any(e["kind"] == "rfa" for e in manifest["files"]):
        bad.append("no families/*.rfa in the kit")
    if not manifest["id_index"]:
        bad.append("id_index empty")
    return bad


# ---------------------------------------------------------------------------
# the markdown
# ---------------------------------------------------------------------------

RETIRED = {
    "H12": ("retired: the all-native-copy probe's ONLY defect was its empty 0x0f3f unit "
            "footer blob -- E1 (= H12 + the donor's 64-B blob, one stream changed) and "
            "E1b (random 64 B) both PASSED in genesis-audit VERDICTS #36. Opening it in "
            "desktop Revit would re-discover a law already fixed in core."),
    "BXhf_f1i1": ("retired: a batch-38-era G_ABPD probe built before the blob fix (empty "
                  "blob on its family unit) -- it fails for the solved reason, not the "
                  "open one."),
}


def render_kit_md(manifest: Dict[str, Any]) -> str:
    files = manifest["files"]
    rvts = [e for e in files if e["kind"] == "rvt"]
    rfas = [e for e in files if e["kind"] == "rfa"]
    base = manifest["base"]

    def cz(e, c):
        return e.get("census", {}).get("classes", {}).get(c, 0)

    def added_units(e):
        return e.get("census", {}).get("added_save_units", 0)

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
    for k, why in manifest.get("retired", RETIRED).items():
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
        v = e["validation"]
        w(f"| {i} | `{e['name']}` | {e['role']} | {cz(e, 'SWall')} | {cz(e, 'FamilyInstance')} "
          f"| {added_units(e)} | {v['errors']} errors / {v['warnings']} warnings |")
    for j, e in enumerate(rfas, start=len(rvts)):
        v = e["validation"]
        w(f"| {j} | `{e['name']}` | standalone generated family ({e.get('tag') or '?'}) "
          f"| - | - | - | {v['errors']} errors / {v['warnings']} warnings |")
    w("")
    w(f"`{K0}` is byte-identical to the pinned base (sha256 `{base['pinned_sha256']}`); "
      f"the other files were built ON it, so every element id above the base watermark "
      f"**{base['watermark']}** was authored by tekton. `manifest.json` beside these files "
      "lists, per file, every such id -> class -> save unit -> family, and an `id_index` "
      "across the whole kit.")
    w("")
    w("Expected reading per file:")
    w("")
    for e in rvts + rfas[:1]:
        w(f"- `{e['name']}` -- {e['expected']}")
    w("")
    w("## What to do (Revit 2026; a newer release is fine and will offer to upgrade; an OLDER release cannot open these -- stop there)")
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
      "Open the default 3D view: K1/K3 should show four walls; K2/K3 a panelboard box near the west wall. Screenshot.")
    w("5. File > Save As under a new name; screenshot any dialog (a save-time audit failure is as informative as an open-time one).")
    w(f"6. With `{K1}` open and clean: Insert > **Load Family** > `{(rfas[0]['name'] if rfas else 'families/<the .rfa>')}`; "
      "screenshot any dialog; if it loads, place one instance from the Project Browser and Save As again.")
    w("7. **Always attach the newest journal**, whatever happened (clean open, dialog, or crash): "
      "after closing Revit, open `%LOCALAPPDATA%\\Autodesk\\Revit\\Autodesk Revit 2026\\Journals` "
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
    w("The screenshots, the exported warnings (if any), the copied journal file(s), and one line per file: "
      "`opened clean` / `dialog: <first words>` / `corrupt: <detail line>` / `crash`. "
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
    bad = list(check_kit(m))
    for e in m["files"]:
        p = os.path.join(kit_dir, e["name"])
        if not os.path.isfile(p):
            bad.append(f"{e['name']} absent from {relp(kit_dir)}")
        elif sha256_of(p) != e["sha256"]:
            bad.append(f"{e['name']} sha256 differs from manifest (rebuilt or corrupted copy)")
    return bad


def lookup(kit_dir: str, ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    idx = load_manifest(kit_dir).get("id_index") or {}
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
        except FileNotFoundError as e:
            log(f"ERROR {e}")
            return 2
        for e in m["files"]:
            v = e["validation"]
            log(f"  {e['name']:<44} sha256 {e['sha256'][:12]}  {v['errors']} errors / "
                f"{v['warnings']} warnings  " + (
                    f"added {e['census'].get('added_classes')} units+{e['census'].get('added_save_units')}"
                    if e["kind"] == "rvt" else f"({e.get('tag')})"))
        log(f"id_index: {len(m['id_index'])} ids")
        return 0 if not m["checks"] else 1
    if a.cmd == "verify":
        bad = verify_kit(a.kit)
        log("VERIFIED: every file matches its manifest and every shape law holds"
            if not bad else f"PROBLEMS: {bad}")
        return 0 if not bad else 1
    if a.cmd == "lookup":
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
