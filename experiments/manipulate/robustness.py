"""robustness.py -- read-only pass of the manipulation stack over ALL SIX
sample projects (files the tools were NOT developed against included:
dach-sample-project [German locale, 139 MB], racadvanced, rstadvanced).

For every ``samples/*.rvt``:
  * ``Document.from_file`` (walks every ``Partitions/<N>`` stream -- any
    framing-walker error raises), ElemTable + schema load;
  * decode EVERY host-document element in all three seqs (101/102/103) and
    count clean / stub / error records per class;
  * byte-exact re-encode check (the manipulation precondition) on a sample
    of host elements: decode -> ``rvt.encode`` -> compare with the original
    payload;
  * a few manipulate-layer smoke calls (levels(), symbols(),
    dependency_report on host instances) with timings.

Output: experiments/manipulate/robustness.json + a printed table.
Usage:  .venv/bin/python experiments/manipulate/robustness.py [names...]
        (names = sample basenames; default = all six)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import manipulate as M                       # noqa: E402
from rvt.encode import ObjectEncoder                   # noqa: E402
from rvt.mutate import Document                        # noqa: E402

SAMPLES = ["rstbasicsampleproject", "racbasicsampleproject",
           "rmebasicsampleproject", "racadvancedsampleproject",
           "rstadvancedsampleproject", "dach-sample-project"]

REENCODE_SAMPLE = 4000        # host elements checked for byte-exact re-encode


def probe(name: str) -> dict:
    path = os.path.join(ROOT, "samples", name + ".rvt")
    rep: dict = {"file": name, "size_mb": round(os.path.getsize(path) / 2**20, 1)}
    t0 = time.time()
    try:
        doc = Document.from_file(path)
    except Exception as e:                      # pragma: no cover
        rep["load_error"] = f"{type(e).__name__}: {e}"
        rep["traceback"] = traceback.format_exc()[-2000:]
        return rep
    rep["load_s"] = round(time.time() - t0, 1)
    rep["elemtable_count"] = doc.et.count
    rep["watermark"] = doc.last_issued_id
    rep["records_per_seq"] = {s: len(doc.idx[s]) for s in (101, 102, 103)}
    rep["host_records"] = len(doc.et_by_id)

    # ---- full host-document decode --------------------------------------
    t0 = time.time()
    stat = {}
    bad_examples = defaultdict(list)
    for seq in (101, 102, 103):
        clean = stub = err = missing = 0
        err_by_class: Counter = Counter()
        for eid in doc.et_by_id:
            r = doc.idx[seq].get(eid)
            if r is None:
                missing += 1
                continue
            try:
                o = doc.dec.decode_record(r.class_id, r.payload)
            except Exception as e:                       # decoder crash
                err += 1
                cls = doc.dec.class_name(r.class_id)
                err_by_class[cls] += 1
                if len(bad_examples[seq]) < 5:
                    bad_examples[seq].append({"id": eid, "class": cls,
                                              "exc": repr(e)[:200]})
                continue
            if o.clean:
                clean += 1
            elif o.stub:
                stub += 1
            else:
                err += 1
                err_by_class[o.class_name] += 1
                if len(bad_examples[seq]) < 5:
                    bad_examples[seq].append({"id": eid, "class": o.class_name,
                                              "errors": o.errors[:2],
                                              "consumed": f"{o.consumed}/{o.total}"})
        stat[seq] = {"clean": clean, "stub": stub, "error": err,
                     "missing": missing,
                     "clean_pct": round(100.0 * clean / max(1, clean + err), 3),
                     "error_by_class": err_by_class.most_common(8)}
    rep["decode"] = stat
    rep["decode_bad_examples"] = dict(bad_examples)
    rep["decode_s"] = round(time.time() - t0, 1)

    # ---- byte-exact re-encode (manipulation precondition) ---------------
    t0 = time.time()
    enc = ObjectEncoder(decoder=doc.dec)
    exact = mismatch = skipped = 0
    mism_by_class: Counter = Counter()
    for eid in list(doc.et_by_id)[:REENCODE_SAMPLE]:
        for seq in (101, 102, 103):
            r = doc.idx[seq].get(eid)
            if r is None or r.body_size < 2:
                continue
            o = doc.dec.decode_record(r.class_id, r.payload)
            if not (o.clean or o.stub):
                skipped += 1
                continue
            try:
                got = enc.encode_object(r.class_id, o.value)
            except Exception:
                mismatch += 1
                mism_by_class[o.class_name] += 1
                continue
            if got == r.payload:
                exact += 1
            else:
                mismatch += 1
                mism_by_class[o.class_name] += 1
    rep["reencode"] = {"exact": exact, "mismatch": mismatch, "skipped_undecodable": skipped,
                       "exact_pct": round(100.0 * exact / max(1, exact + mismatch), 3),
                       "mismatch_by_class": mism_by_class.most_common(10)}
    rep["reencode_s"] = round(time.time() - t0, 1)

    # ---- manipulate-layer smoke ----------------------------------------
    t0 = time.time()
    try:
        rep["levels"] = [(x["id"], x["name"], round(x["elevation_ft"], 3))
                         for x in doc.levels()]
        rep["symbols"] = len(doc.symbols())
        n = 0
        reports = []
        for eid in doc.ids_of_class("FamilyInstance"):
            if n >= 3:
                break
            r = M.dependency_report(doc, eid)
            reports.append({"id": eid, "class": r["target_class"],
                            "dependents": len(r["dependents"]),
                            "referrers": len(r["referrers"]),
                            "capped": r.get("cascade_capped_at")})
            n += 1
        rep["dependency_reports"] = reports
    except Exception as e:                                  # pragma: no cover
        rep["manipulate_error"] = f"{type(e).__name__}: {e}"
        rep["traceback"] = traceback.format_exc()[-2000:]
    rep["manipulate_s"] = round(time.time() - t0, 1)
    return rep


def main(argv=None) -> int:
    names = list(argv or sys.argv[1:]) or SAMPLES
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "files": []}
    for n in names:
        print(f"== {n}", flush=True)
        r = probe(n)
        out["files"].append(r)
        brief = {k: r.get(k) for k in ("size_mb", "load_s", "elemtable_count",
                                       "decode", "reencode", "decode_s",
                                       "reencode_s", "manipulate_s",
                                       "load_error", "manipulate_error")
                 if r.get(k) is not None}
        print(json.dumps(brief, default=str), flush=True)
    dest = os.path.join(HERE, "robustness.json")
    if len(names) < len(SAMPLES) and os.path.exists(dest):
        with open(dest) as f:
            old = json.load(f)
        merged = {x["file"]: x for x in old.get("files", [])}
        for x in out["files"]:
            merged[x["file"]] = x
        out["files"] = [merged[k] for k in SAMPLES if k in merged]
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
