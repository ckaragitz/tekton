#!/usr/bin/env python3
"""coverage.py — the CRUD x CATEGORY coverage harness: battle-hardening as a
MEASURED NUMBER, not a claim.

The matrix (``docs/coverage/matrix.json``) enumerates ``{category} x {verb}``
(create / read / modify / move / retype / delete) for every element category
the writer has — or should have.  Each cell names its implementing function,
its proof generator (a driver script that deterministically regenerates the
proof .rvt), its proof file(s), and (for READ cells) a read probe against a
real corpus file.  This runner turns that definition into measured statuses:

    CERTIFIED   the proof file validates with ZERO errors AND the orchestrator's
                ledger (docs/coverage/viewer-certified.json) says Autodesk's
                own reader accepted it (viewer.autodesk.com PASS)
    VALIDATES   proof file validates with ZERO errors (rvt.validate all
                layers), not yet viewer-certified
    REGRESSED   ledger-certified path whose CURRENT bytes now FAIL validation
                (alarm: a certified proof drifted)
    FAILS       proof file exists but the validator reports errors
    UNPROVEN    an implementing function exists but no proof file (or the
                proof file is absent on disk)
    MISSING     no implementing function at all
    BLOCKED     declared blocked by its stream (reason in the note)
    NA          verb does not apply to the category (excluded from %)

Usage (run from the repo root):

    .venv/bin/python tools/coverage.py run                # regenerate + validate + report
    .venv/bin/python tools/coverage.py run --validate-only   # no regeneration
    .venv/bin/python tools/coverage.py run --cells family_instances:create columns_beams:create
    .venv/bin/python tools/coverage.py run --force-regen   # also regenerate ledger-certified files
    .venv/bin/python tools/coverage.py report             # re-render matrix.md from the last results
    .venv/bin/python tools/coverage.py list               # print the cell inventory

Regeneration policy: a generator (a make_*.py driver) is run once per session;
before running, its expected outputs are backed up and RESTORED if the driver
fails, so a broken regenerator can never destroy a good proof.  Generators
that co-produce a ledger-CERTIFIED file are FROZEN by default (their outputs
are validated in place, never overwritten) — pass --force-regen to override.
Exit status: 0 unless a cell REGRESSED or a generator crashed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

DEFAULT_MATRIX = os.path.join(ROOT, "docs", "coverage", "matrix.json")
DEFAULT_LEDGER = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
DEFAULT_MD = os.path.join(ROOT, "docs", "coverage", "matrix.md")
PYTHON = os.path.join(ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

STATUSES = ("CERTIFIED", "VALIDATES", "REGRESSED", "FAILS", "UNPROVEN",
            "MISSING", "BLOCKED", "NA")
PROVEN = ("CERTIFIED", "VALIDATES")
GLYPH = {
    "CERTIFIED": "🏆 CERT",
    "VALIDATES": "✅ VAL",
    "REGRESSED": "🚨 REGR",
    "FAILS": "💥 FAIL",
    "UNPROVEN": "⚠️ UNPR",
    "MISSING": "❌ MISS",
    "BLOCKED": "⛔ BLOK",
    "NA": "➖",
}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def rel(path: str) -> str:
    """Repo-relative POSIX path (matrix / ledger paths are all repo-relative)."""
    try:
        r = os.path.relpath(os.path.abspath(os.path.join(ROOT, path)), ROOT)
    except ValueError:
        r = path
    return r.replace(os.sep, "/")


def abspath(path: str) -> str:
    return os.path.join(ROOT, path) if not os.path.isabs(path) else path


def load_matrix(path: str = DEFAULT_MATRIX) -> dict:
    with open(path) as fh:
        m = json.load(fh)
    _check_matrix(m)
    return m


def _check_matrix(m: dict) -> None:
    """Structural sanity: every category has exactly one cell per verb."""
    verbs = list(m["verbs"])
    cats = [c["key"] for c in m["categories"]]
    seen: Dict[Tuple[str, str], int] = {}
    for cell in m["cells"]:
        k = (cell["category"], cell["verb"])
        if cell["category"] not in cats:
            raise ValueError(f"cell has unknown category {cell['category']!r}")
        if cell["verb"] not in verbs:
            raise ValueError(f"cell has unknown verb {cell['verb']!r}")
        seen[k] = seen.get(k, 0) + 1
    dup = [k for k, n in seen.items() if n > 1]
    if dup:
        raise ValueError(f"duplicate cells: {dup}")
    missing = [(c, v) for c in cats for v in verbs if (c, v) not in seen]
    if missing:
        raise ValueError(f"matrix missing cells: {missing[:8]}{' ...' if len(missing) > 8 else ''}")
    gens = m.get("generators") or {}
    for cell in m["cells"]:
        g = cell.get("generator")
        if g and g not in gens:
            raise ValueError(f"cell {cell['category']}:{cell['verb']} names unknown generator {g!r}")


def load_ledger(path: str = DEFAULT_LEDGER) -> Dict[str, dict]:
    """Read the orchestrator's viewer-certified ledger -> {repo-rel path: entry}."""
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        data = json.load(fh)
    entries = data.get("certified") or []
    return {rel(e["file"]): e for e in entries if e.get("file")}


def cell_key(cell: dict) -> str:
    return f"{cell['category']}:{cell['verb']}"


def proof_paths(cell: dict) -> List[str]:
    out: List[str] = []
    if cell.get("proof_file"):
        out.append(cell["proof_file"])
    for p in cell.get("extra_proofs") or []:
        if p and p not in out:
            out.append(p)
    return [rel(p) for p in out]


# ---------------------------------------------------------------------------
# generators
# ---------------------------------------------------------------------------
class GeneratorRun:
    def __init__(self, key: str, spec: dict):
        self.key = key
        self.spec = spec
        self.status = "not-run"        # ran-ok | ran-failed | frozen | skipped | not-run
        self.seconds = 0.0
        self.returncode: Optional[int] = None
        self.tail = ""
        self.restored = False
        self.reason = ""

    def to_json(self) -> dict:
        return {"generator": self.key, "status": self.status,
                "seconds": round(self.seconds, 1), "returncode": self.returncode,
                "restored_backup": self.restored, "reason": self.reason,
                "output_tail": self.tail}


def _generator_frozen(spec: dict, ledger: Dict[str, dict]) -> Optional[str]:
    outs = [rel(o) for o in spec.get("outputs") or []]
    hit = [o for o in outs if o in ledger]
    if hit:
        return f"co-produces ledger-certified file(s): {', '.join(hit)}"
    return None


def run_generator(key: str, spec: dict, ledger: Dict[str, dict], *,
                  force: bool = False, timeout: int = 1800,
                  log=print) -> GeneratorRun:
    """Run one proof generator with backup/restore protection."""
    gr = GeneratorRun(key, spec)
    frozen = _generator_frozen(spec, ledger)
    if frozen and not force:
        gr.status = "frozen"
        gr.reason = frozen
        return gr
    cmd = list(spec.get("cmd") or [])
    if not cmd:
        gr.status = "skipped"
        gr.reason = "no command"
        return gr
    if cmd[0] in ("python", "python3"):
        cmd[0] = PYTHON
    elif cmd[0] == "-m":
        cmd = [PYTHON] + cmd
    else:
        cmd = [PYTHON, cmd[0]] + cmd[1:]
    outputs = [abspath(o) for o in spec.get("outputs") or []]
    backup_dir = tempfile.mkdtemp(prefix=f"cov-{key}-")
    backups: Dict[str, str] = {}
    for o in outputs:
        if os.path.exists(o):
            b = os.path.join(backup_dir, os.path.basename(o))
            shutil.copy2(o, b)
            backups[o] = b
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    t0 = time.time()
    log(f"  [gen] {key}: {' '.join(os.path.basename(c) for c in cmd)} "
        f"(est {spec.get('est_seconds', '?')}s)")
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=timeout)
        gr.returncode = proc.returncode
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        gr.tail = out[-1500:]
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired as e:
        gr.returncode = None
        gr.tail = f"TIMEOUT after {timeout}s"
        ok = False
    gr.seconds = time.time() - t0
    missing = [o for o in outputs if not os.path.exists(o)]
    if ok and missing:
        ok = False
        gr.reason = f"declared outputs missing after run: {[rel(m) for m in missing]}"
    if not ok:
        # restore every backed-up output so a broken regenerator never
        # destroys a good proof file
        for o, b in backups.items():
            shutil.copy2(b, o)
        gr.restored = bool(backups)
        gr.status = "ran-failed"
        if not gr.reason:
            gr.reason = f"generator exited {gr.returncode}"
        log(f"    -> FAILED ({gr.reason}); outputs restored from backup" if gr.restored
            else f"    -> FAILED ({gr.reason})")
    else:
        gr.status = "ran-ok"
        log(f"    -> ok in {gr.seconds:.0f}s")
    shutil.rmtree(backup_dir, ignore_errors=True)
    return gr


# ---------------------------------------------------------------------------
# proof validation
# ---------------------------------------------------------------------------
def validate_proof(path: str, gate: str = "rvt_validate", *, log=print) -> dict:
    """Run the gate on one proof file -> {exists, validates, error_count, ...}."""
    ap = abspath(path)
    res: Dict[str, Any] = {"path": rel(path), "gate": gate, "exists": os.path.exists(ap)}
    if not res["exists"]:
        res.update(validates=False, error_count=None)
        return res
    t0 = time.time()
    try:
        if gate == "verify_rfa":
            from rvt.families import verify_rfa
            rep = verify_rfa(ap)
            n_err = (int(rep.get("gzip_crc_failures", 0)) + int(rep.get("ecc_mismatch", 0))
                     + len(rep.get("walker_errors") or []))
            st = rep.get("decode_seq102") or {}
            if st.get("clean") != st.get("records"):
                n_err += int((st.get("records") or 0) - (st.get("clean") or 0))
            ok = bool(rep.get("ok"))
            res.update(validates=ok, error_count=(0 if ok else max(1, n_err)),
                       warning_count=0, errors=[])
        else:
            from rvt.validate import validate_file
            rep = validate_file(ap)
            errs = rep.errors
            res.update(validates=bool(rep.ok), error_count=len(errs),
                       warning_count=len(rep.warnings),
                       errors=[f"{f.layer}/{f.where}: {f.message}" for f in errs[:6]])
    except Exception as e:  # a crash of the gate is a failed validation, not silence
        res.update(validates=False, error_count=-1, errors=[f"gate crashed: {e!r}"])
    res["seconds"] = round(time.time() - t0, 1)
    log(f"  [val] {'OK  ' if res['validates'] else 'FAIL'} {res['path']}  "
        f"errors={res['error_count']} ({res['seconds']}s)")
    return res


# ---------------------------------------------------------------------------
# read probes
# ---------------------------------------------------------------------------
_DOC_CACHE: Dict[str, Any] = {}


def _document(template: str, templates: Dict[str, str]):
    path = templates.get(template, template)
    ap = abspath(path)
    if ap not in _DOC_CACHE:
        from rvt.mutate import Document
        _DOC_CACHE[ap] = Document.from_file(ap)
    return _DOC_CACHE[ap]


def _resolve_callable(target: str, doc):
    """'doc:levels' -> bound Document method; 'pkg.mod:func' -> func(doc)."""
    where, _, name = target.partition(":")
    if where == "doc":
        fn = getattr(doc, name)
        return fn()
    mod = importlib.import_module(where)
    fn = getattr(mod, name)
    return fn(doc)


def run_probe(cell: dict, templates: Dict[str, str], *, log=print) -> dict:
    """Execute a READ cell's probe against a real corpus file."""
    probe = cell.get("probe") or {}
    kind = probe.get("kind")
    tpl = probe.get("template", "rme")
    res: Dict[str, Any] = {"kind": kind, "template": tpl}
    t0 = time.time()
    try:
        doc = _document(tpl, templates)
        if kind == "class_decode":
            counts, decoded, dirty = {}, 0, 0
            need = int(probe.get("min", 1))
            ndec = int(probe.get("decode", 3))
            for cls in probe.get("classes") or []:
                ids = list(doc.ids_of_class(cls))
                counts[cls] = len(ids)
                for eid in ids[:ndec]:
                    ok = False
                    for seq in (102, 101):
                        try:
                            if doc.value(eid, seq) is not None:
                                ok = True
                                break
                        except Exception:
                            pass
                    decoded += 1
                    if not ok:
                        dirty += 1
            total = sum(counts.values())
            passed = total >= need and dirty == 0
            res.update(passed=passed, counts=counts, decoded=decoded, dirty=dirty,
                       detail=f"{total} elements ({', '.join(f'{k}={v}' for k, v in counts.items())}); "
                              f"{decoded} decoded, {dirty} unreadable")
        elif kind == "category_decode":
            want = set(int(c) for c in probe.get("categories") or [])
            counts = {c: 0 for c in want}
            for eid in doc.et_by_id:
                try:
                    cat = doc.category_of(eid)
                except Exception:
                    continue
                if cat in want:
                    counts[cat] += 1
            total = sum(counts.values())
            need = int(probe.get("min", 1))
            res.update(passed=total >= need, counts={str(k): v for k, v in counts.items()},
                       detail=f"{total} elements by category ({', '.join(f'{k}={v}' for k, v in counts.items())})")
        elif kind == "callable":
            val = _resolve_callable(probe["target"], doc)
            try:
                n = len(val)
            except Exception:
                n = 1 if val else 0
            need = int(probe.get("min", 1))
            res.update(passed=n >= need, count=n,
                       detail=f"{probe['target']} -> {n} item(s)")
        else:
            res.update(passed=False, detail=f"unknown probe kind {kind!r}")
    except Exception as e:
        res.update(passed=False, detail=f"probe crashed: {e!r}")
    res["seconds"] = round(time.time() - t0, 1)
    log(f"  [probe] {'OK  ' if res.get('passed') else 'FAIL'} {cell_key(cell)}  {res.get('detail')}")
    return res


# ---------------------------------------------------------------------------
# status resolution
# ---------------------------------------------------------------------------
_RANK = {"CERTIFIED": 5, "VALIDATES": 4, "REGRESSED": 3, "FAILS": 2, "MISSING": 1}


def resolve_status(cell: dict, proofs: List[dict], ledger: Dict[str, dict],
                   probe_res: Optional[dict]) -> Tuple[str, dict]:
    """Compute a cell's status from its evidence.  Returns (status, detail)."""
    detail: Dict[str, Any] = {}
    if cell.get("na"):
        return "NA", {"reason": cell.get("na")}
    if cell.get("blocked"):
        return "BLOCKED", {"reason": cell.get("blocked")}
    probe_status: Optional[str] = None
    if cell["verb"] == "read" and probe_res is not None:
        detail["probe"] = probe_res
        if probe_res.get("passed"):
            probe_status = "VALIDATES"
        else:
            probe_status = "FAILS" if cell.get("function") else "MISSING"
        if not proofs:
            return probe_status, detail
    if not proofs:
        return ("UNPROVEN" if cell.get("function") else "MISSING"), detail
    best, best_rank, per = None, -1, []
    for p in proofs:
        certified = p["path"] in ledger
        if not p.get("exists"):
            st = "MISSING"
        elif p.get("validates"):
            st = "CERTIFIED" if certified else "VALIDATES"
        else:
            st = "REGRESSED" if certified else "FAILS"
        per.append({"path": p["path"], "status": st, "error_count": p.get("error_count"),
                    "viewer_certified": certified})
        if _RANK[st] > best_rank:
            best_rank, best = _RANK[st], st
    detail["proofs"] = per
    if best == "MISSING":  # proof file(s) declared but none on disk
        best = "UNPROVEN" if cell.get("function") else "MISSING"
    if probe_status is not None:
        # a READ cell may carry both a corpus probe and proof files: best wins
        order = {"CERTIFIED": 5, "VALIDATES": 4, "REGRESSED": 3, "FAILS": 2,
                 "UNPROVEN": 1, "MISSING": 0}
        if order.get(probe_status, 0) > order.get(best, 0):
            best = probe_status
    return best or "UNPROVEN", detail


# ---------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------
def select_cells(matrix: dict, cells: Optional[List[str]] = None,
                 categories: Optional[List[str]] = None) -> List[dict]:
    out = matrix["cells"]
    if categories:
        cats = set(categories)
        out = [c for c in out if c["category"] in cats]
    if cells:
        keys = set(cells)
        out = [c for c in out if cell_key(c) in keys]
        found = {cell_key(c) for c in out}
        unknown = keys - found
        if unknown:
            raise ValueError(f"unknown cells: {sorted(unknown)}")
    return out


def run(matrix: dict, *, ledger: Optional[Dict[str, dict]] = None,
        cells: Optional[List[str]] = None, categories: Optional[List[str]] = None,
        validate_only: bool = False, force_regen: bool = False,
        skip_probes: bool = False, timeout: int = 1800,
        log=print) -> dict:
    """Run the harness over the selected cells; returns the results block and
    mutates ``matrix`` in place (per-cell ``result`` + top-level summary)."""
    ledger = load_ledger() if ledger is None else ledger
    templates = matrix.get("templates") or {}
    generators = matrix.get("generators") or {}
    sel = select_cells(matrix, cells, categories)
    now = _dt.datetime.now().isoformat(timespec="seconds")

    # 1. which proof files / generators are in play
    needed_paths: List[str] = []
    for c in sel:
        for p in proof_paths(c):
            if p not in needed_paths:
                needed_paths.append(p)
    gen_keys: List[str] = []
    for c in sel:
        g = c.get("generator")
        if g and g not in gen_keys:
            gen_keys.append(g)
        for g in c.get("extra_generators") or []:
            if g and g not in gen_keys:
                gen_keys.append(g)

    # 2. regenerate
    gen_runs: Dict[str, GeneratorRun] = {}
    if not validate_only:
        for g in gen_keys:
            gen_runs[g] = run_generator(g, generators[g], ledger,
                                        force=force_regen, timeout=timeout, log=log)
    else:
        for g in gen_keys:
            gr = GeneratorRun(g, generators[g])
            gr.status = "skipped"
            gr.reason = "--validate-only"
            gen_runs[g] = gr

    # 3. validate every proof file once
    proof_results: Dict[str, dict] = {}
    for p in needed_paths:
        gate = "verify_rfa" if p.lower().endswith(".rfa") else "rvt_validate"
        proof_results[p] = validate_proof(p, gate, log=log)

    # 4. read probes
    probe_results: Dict[str, dict] = {}
    if not skip_probes:
        for c in sel:
            if c["verb"] == "read" and c.get("probe") and not c.get("na") and not c.get("blocked"):
                probe_results[cell_key(c)] = run_probe(c, templates, log=log)

    # 5. resolve statuses
    for c in sel:
        proofs = [proof_results[p] for p in proof_paths(c) if p in proof_results]
        pres = probe_results.get(cell_key(c))
        status, detail = resolve_status(c, proofs, ledger, pres)
        g = c.get("generator")
        regen = None
        if g and g in gen_runs:
            regen = {"generator": g, "status": gen_runs[g].status,
                     "reason": gen_runs[g].reason}
        c["result"] = {
            "status": status,
            "validates": (proofs[0]["validates"] if proofs else
                          (pres.get("passed") if pres is not None else None)),
            "error_count": (proofs[0].get("error_count") if proofs else None),
            "viewer_certified": any(p["path"] in ledger for p in proofs) if proofs else False,
            "regeneration": regen,
            "detail": detail,
            "last_run": now,
        }

    prev = matrix.get("summary") or {}
    summary = summarize(matrix)
    mode = "validate-only" if validate_only else ("force-regen" if force_regen else "regen")
    summary["run"] = {
        "at": now,
        "mode": mode,
        "cells_selected": len(sel),
        "generators": {g: gr.to_json() for g, gr in gen_runs.items()},
        "proof_files_validated": len(proof_results),
        "probes_run": len(probe_results),
    }
    # keep the most recent REGENERATION record visible across later
    # validate-only sweeps (a driver's pass/fail is evidence too)
    if mode in ("regen", "force-regen"):
        summary["last_regen"] = {"at": now,
                                 "generators": summary["run"]["generators"]}
    elif prev.get("last_regen"):
        summary["last_regen"] = prev["last_regen"]
    matrix["summary"] = summary
    return summary


# ---------------------------------------------------------------------------
# summary + report
# ---------------------------------------------------------------------------
def summarize(matrix: dict) -> dict:
    rows: Dict[str, dict] = {}
    total = {s: 0 for s in STATUSES}
    for c in matrix["cells"]:
        st = ((c.get("result") or {}).get("status")
                or ("NA" if c.get("na") else "UNRUN"))
        r = rows.setdefault(c["category"], {"cells": {}, "counts": {s: 0 for s in STATUSES},
                                            "proven": 0, "applicable": 0})
        r["cells"][c["verb"]] = st
        if st in total:
            total[st] += 1
            r["counts"][st] += 1
        if st != "NA":
            r["applicable"] += 1
            if st in PROVEN:
                r["proven"] += 1
    for r in rows.values():
        r["pct"] = round(100.0 * r["proven"] / r["applicable"], 1) if r["applicable"] else 0.0
    applicable = sum(r["applicable"] for r in rows.values())
    proven = sum(r["proven"] for r in rows.values())
    certified = total.get("CERTIFIED", 0)
    regenerable = 0
    proven_cells = 0
    for c in matrix["cells"]:
        st = ((c.get("result") or {}).get("status")) or ""
        if st in PROVEN:
            proven_cells += 1
            if c.get("generator") or c.get("extra_generators"):
                regenerable += 1
    return {
        "overall_pct": round(100.0 * proven / applicable, 1) if applicable else 0.0,
        "certified_pct": round(100.0 * certified / applicable, 1) if applicable else 0.0,
        "proven": proven,
        "applicable": applicable,
        "counts": total,
        "regenerable_pct": round(100.0 * regenerable / proven_cells, 1) if proven_cells else 0.0,
        "rows": {k: {"pct": v["pct"], "proven": v["proven"],
                     "applicable": v["applicable"], "counts": v["counts"]}
                 for k, v in rows.items()},
    }


def _md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_markdown(matrix: dict) -> str:
    verbs = list(matrix["verbs"])
    cats = matrix["categories"]
    by = {(c["category"], c["verb"]): c for c in matrix["cells"]}
    s = matrix.get("summary") or summarize(matrix)
    L: List[str] = []
    ap = L.append
    run = s.get("run") or {}
    ap("# Writer coverage matrix — CRUD x category\n")
    ap("_Generated by `tools/coverage.py`; source of truth: `docs/coverage/matrix.json`._"
       f"  \n_Last run: **{run.get('at', 'never')}** (mode `{run.get('mode', '-')}`, "
       f"{run.get('cells_selected', 0)} cells, {run.get('proof_files_validated', 0)} proof "
       f"files gated, {run.get('probes_run', 0)} read probes)._\n")
    ap(f"## Headline\n")
    ap(f"**{s['overall_pct']}%** of applicable cells are PROVEN "
       f"({s['proven']}/{s['applicable']}: validates with ZERO validator errors or "
       f"viewer-certified).  \n"
       f"**{s['certified_pct']}%** are CERTIFIED by Autodesk's own reader "
       f"({s['counts'].get('CERTIFIED', 0)} cells).  \n"
       f"**{s['regenerable_pct']}%** of proven cells have a registered proof "
       f"regenerator (a `make_*.py` driver the harness reruns).\n")
    c = s["counts"]
    ap("| status | cells | meaning |\n|---|---|---|")
    legend = {
        "CERTIFIED": "proof validates AND Autodesk's viewer accepted it (ledger)",
        "VALIDATES": "proof file passes rvt.validate (all layers, 0 errors); viewer certification pending",
        "REGRESSED": "ledger-certified path whose current bytes FAIL validation",
        "FAILS": "proof file exists but the validator reports errors",
        "UNPROVEN": "implementing function exists, no passing proof file",
        "MISSING": "no implementing function",
        "BLOCKED": "declared blocked by its stream (see note)",
        "NA": "verb does not apply (excluded from percentages)",
    }
    for st in STATUSES:
        ap(f"| {GLYPH[st]} {st} | {c.get(st, 0)} | {legend[st]} |")
    ap("")
    ap("## Matrix\n")
    ap("| category | " + " | ".join(verbs) + " | proven |")
    ap("|---" * (len(verbs) + 2) + "|")
    for cat in cats:
        row = s["rows"].get(cat["key"], {})
        cells = []
        for v in verbs:
            cell = by.get((cat["key"], v))
            st = (cell.get("result") or {}).get("status") if cell else None
            if st is None:
                st = "NA" if cell and cell.get("na") else "UNRUN"
            cells.append(GLYPH.get(st, st))
        pct = f"{row.get('proven', 0)}/{row.get('applicable', 0)} ({row.get('pct', 0)}%)"
        ap(f"| **{cat['label']}** | " + " | ".join(cells) + f" | {pct} |")
    ap("")
    # generator tables
    gens = (run.get("generators") or {})
    if gens and any(gr.get("status") not in ("skipped",) for gr in gens.values()):
        ap("## Regenerators — this run\n")
        ap("| generator | status | seconds | note |\n|---|---|---|---|")
        for g, gr in gens.items():
            ap(f"| `{g}` | {gr['status']} | {gr['seconds']} | {_md_escape(gr.get('reason') or '')} |")
        ap("")
    lr = s.get("last_regen") or {}
    if lr.get("generators") and lr.get("at") != run.get("at"):
        ap(f"## Last full regeneration ({lr.get('at')})\n")
        ap("Every driver below was rerun from scratch; its outputs were then "
           "re-validated (this table records the driver, the matrix records the "
           "resulting validation).\n")
        ap("| generator | status | seconds | note |\n|---|---|---|---|")
        for g, gr in lr["generators"].items():
            ap(f"| `{g}` | {gr['status']} | {gr['seconds']} | {_md_escape(gr.get('reason') or '')} |")
        ap("")
    elif lr.get("generators"):
        pass  # same run — already printed above
    # per-cell evidence
    ap("## Cell evidence\n")
    for cat in cats:
        ap(f"### {cat['label']}\n")
        ap("| verb | status | function | proof / probe | note |\n|---|---|---|---|---|")
        for v in verbs:
            cell = by.get((cat["key"], v))
            if cell is None:
                continue
            res = cell.get("result") or {}
            st = res.get("status") or ("NA" if cell.get("na") else "UNRUN")
            fn = cell.get("function") or "—"
            if isinstance(fn, list):
                fn = "<br>".join(fn)
            ev = []
            for p in proof_paths(cell):
                pr = None
                for x in (res.get("detail") or {}).get("proofs") or []:
                    if x["path"] == p:
                        pr = x
                tag = ""
                if pr is not None:
                    tag = (f" [{pr['status']}, errors={pr['error_count']}]")
                ev.append(f"`{os.path.basename(p)}`{tag}")
            probe = (res.get("detail") or {}).get("probe")
            if probe:
                ev.append(f"probe: {_md_escape(probe.get('detail', ''))}")
            elif cell.get("probe") and not probe:
                ev.append("probe (not run)")
            note = cell.get("na") if cell.get("na") else (cell.get("blocked") or cell.get("note") or "")
            ap(f"| {v} | {GLYPH.get(st, st)} | {_md_escape(fn)} | "
               f"{_md_escape('<br>'.join(ev)) if ev else '—'} | {_md_escape(note)} |")
        ap("")
    ap("---\n_Regenerate: `.venv/bin/python tools/coverage.py run` "
       "(add `--validate-only` to skip proof regeneration)._\n")
    return "\n".join(L)


def write_outputs(matrix: dict, matrix_path: str = DEFAULT_MATRIX,
                  md_path: str = DEFAULT_MD) -> None:
    with open(matrix_path, "w") as fh:
        json.dump(matrix, fh, indent=1, default=str)
        fh.write("\n")
    with open(md_path, "w") as fh:
        fh.write(render_markdown(matrix))


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="coverage", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="regenerate + validate + report")
    r.add_argument("--matrix", default=DEFAULT_MATRIX)
    r.add_argument("--ledger", default=DEFAULT_LEDGER)
    r.add_argument("--md", default=DEFAULT_MD)
    r.add_argument("--cells", nargs="*", help="category:verb keys to run (default: all)")
    r.add_argument("--categories", nargs="*", help="category keys to run")
    r.add_argument("--validate-only", action="store_true",
                   help="skip regeneration; validate the proof files on disk")
    r.add_argument("--force-regen", action="store_true",
                   help="also regenerate generators that co-produce ledger-certified files")
    r.add_argument("--skip-probes", action="store_true")
    r.add_argument("--timeout", type=int, default=1800, help="per-generator timeout (s)")
    r.add_argument("--no-write", action="store_true", help="do not write matrix.json/md")

    rp = sub.add_parser("report", help="re-render matrix.md from the last results")
    rp.add_argument("--matrix", default=DEFAULT_MATRIX)
    rp.add_argument("--md", default=DEFAULT_MD)

    ls = sub.add_parser("list", help="print the cell inventory")
    ls.add_argument("--matrix", default=DEFAULT_MATRIX)

    a = ap.parse_args(argv)
    if a.cmd == "list":
        m = load_matrix(a.matrix)
        for c in m["cells"]:
            print(f"{cell_key(c):40s} fn={c.get('function') or '-':45s} "
                  f"proof={c.get('proof_file') or '-'}")
        return 0
    if a.cmd == "report":
        m = load_matrix(a.matrix)
        with open(a.md, "w") as fh:
            fh.write(render_markdown(m))
        print(f"wrote {a.md}")
        return 0
    if a.cmd != "run":
        ap.print_help()
        return 2
    m = load_matrix(a.matrix)
    ledger = load_ledger(a.ledger)
    print(f"coverage run: {len(select_cells(m, a.cells, a.categories))} cells, "
          f"{len(ledger)} ledger-certified files")
    s = run(m, ledger=ledger, cells=a.cells, categories=a.categories,
            validate_only=a.validate_only, force_regen=a.force_regen,
            skip_probes=a.skip_probes, timeout=a.timeout)
    print(f"\nHEADLINE: {s['overall_pct']}% proven ({s['proven']}/{s['applicable']}), "
          f"{s['certified_pct']}% certified, counts={s['counts']}")
    if not a.no_write:
        write_outputs(m, a.matrix, a.md)
        print(f"wrote {rel(a.matrix)} and {rel(a.md)}")
    regressed = s["counts"].get("REGRESSED", 0)
    crashed = [g for g, gr in (s["run"]["generators"] or {}).items()
               if gr["status"] == "ran-failed"]
    if regressed:
        print(f"ALARM: {regressed} certified proof(s) REGRESSED")
    if crashed:
        print(f"ALARM: generators failed: {crashed}")
    return 1 if (regressed or crashed) else 0


if __name__ == "__main__":
    sys.exit(main())
