#!/usr/bin/env python
"""Build the instbug FIX probes (instbug-fix stream).

Re-emits, through the FIXED product path (rvt.famload_fix.fixed_product_path
= the D1..D5 corpus-law fixes over rvt.famgen.loader + ifc_intent +
ConstructedSpecimens):

  BXfix_f1i1.rvt        G_ABPD + 1 panel family + 1 placed instance
  BXfix_f6i6.rvt        G_ABPD + 6 panel families + 6 placed instances
  DEMO_250v_room_v2.rvt the user's demo prompt re-run END TO END through the
                        real front door (rvt.frontdoor.run) under the fix

Every file: validator 0 errors + famload_fix.assert_fixed (D1..D5 states +
four-registry census) + a probes.json entry.  Stage for the viewer with:

  .venv/bin/python tools/probe_batch.py stage \
      experiments/instbug/fix/BXfix_f1i1.rvt \
      experiments/instbug/fix/BXfix_f6i6.rvt \
      experiments/instbug/fix/DEMO_250v_room_v2.rvt \
      --control-from experiments/genesis/subst_k4/compose/G_ABPD.rvt
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

PROMPT = "an electrical room rated for 250V with 6 panels"
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(path):
    from rvt.validate import validate_file
    r = validate_file(path)
    return {"verdict": "VALID" if r.ok else "INVALID",
            "n_errors": len(r.errors), "n_warnings": len(r.warnings),
            "errors": [f"[{f.layer}] {f.where}: {f.message}"[:220] for f in r.errors[:6]]}


def main():
    t0 = time.time()
    # pre-load every module the patch set must reach
    import ifc_intent  # noqa: F401  (tools/ifc_intent.py under its bisect alias)
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    import bisect_instance_bug as BB
    from rvt import famload_fix as FX

    out = {"prompt": PROMPT, "base": os.path.relpath(G_ABPD, ROOT), "built": {}}
    scratch = os.path.join(HERE, "_build")
    os.makedirs(scratch, exist_ok=True)

    with FX.fixed_product_path():
        model6 = BB.demo_model()

        # ---- BXfix_f1i1 --------------------------------------------------
        m1 = BB.truncate_model(model6, 1)
        c1 = os.path.join(scratch, "fix_chain1")
        if os.path.isdir(c1):
            shutil.rmtree(c1)
        l1 = BB.build_chain(G_ABPD, c1, m1)
        f1 = BB.chain_file(c1, 1, "PP-1")
        p1 = os.path.join(HERE, "BXfix_f1i1.rvt")
        e1 = BB.place_instances(m1, f1, p1, G_ABPD, l1.get("_loaded") or {})
        out["built"]["BXfix_f1i1"] = {
            "file": os.path.relpath(p1, ROOT),
            "instances": [i.get("elem_id") for i in e1.get("instances") or []]}

        # ---- BXfix_f6i6 --------------------------------------------------
        c6 = os.path.join(scratch, "fix_chain6")
        if os.path.isdir(c6):
            shutil.rmtree(c6)
        l6 = BB.build_chain(G_ABPD, c6, model6)
        f6 = BB.chain_file(c6, 6, "PP-6")
        p6 = os.path.join(HERE, "BXfix_f6i6.rvt")
        e6 = BB.place_instances(model6, f6, p6, G_ABPD, l6.get("_loaded") or {})
        out["built"]["BXfix_f6i6"] = {
            "file": os.path.relpath(p6, ROOT),
            "instances": [i.get("elem_id") for i in e6.get("instances") or []]}

        # ---- DEMO_250v_room_v2: the REAL front door, end to end ----------
        from rvt import frontdoor as FD
        demo_dir = os.path.join(HERE, "demo_v2")
        if os.path.isdir(demo_dir):
            shutil.rmtree(demo_dir)
        req = FD.AuthorRequest(prompt=PROMPT, out=demo_dir,
                               stem="DEMO_250v_room_v2", no_handoff=True,
                               quiet=True)
        r = FD.run(req)
        combined = (r.files or {}).get("combined")
        if not combined or not os.path.isfile(combined):
            raise SystemExit(f"front door did not emit the combined file: "
                             f"{r.errors[:3]} files={r.files}")
        pd = os.path.join(HERE, "DEMO_250v_room_v2.rvt")
        shutil.copyfile(combined, pd)
        out["built"]["DEMO_250v_room_v2"] = {
            "file": os.path.relpath(pd, ROOT),
            "frontdoor_status": r.status,
            "out_dir": os.path.relpath(demo_dir, ROOT)}

    # ---- gates + fix assertions (outside the patch: plain reads) ---------
    from rvt import famload_fix as FX2
    expect = {"BXfix_f1i1": (1, 1), "BXfix_f6i6": (6, 6), "DEMO_250v_room_v2": (6, 6)}
    all_ok = True
    for name, rec in out["built"].items():
        path = os.path.join(ROOT, rec["file"])
        ef, ei = expect[name]
        rec["md5"] = md5(path)
        rec["validate"] = validate(path)
        rec["fix_assertions"] = FX2.assert_fixed(path, expect_families=ef,
                                                 expect_instances=ei)
        rec["ok"] = bool(rec["validate"]["n_errors"] == 0
                         and rec["fix_assertions"]["ok"])
        all_ok = all_ok and rec["ok"]

    out["all_ok"] = all_ok
    out["seconds"] = round(time.time() - t0, 1)
    rp = os.path.join(HERE, "fix_probes.json")
    with open(rp, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(json.dumps({k: ({"ok": v.get("ok"), "file": v.get("file"),
                           "validate": v.get("validate", {}).get("verdict"),
                           "errors": v.get("validate", {}).get("n_errors"),
                           "fix_ok": (v.get("fix_assertions") or {}).get("ok")}
                          if isinstance(v, dict) else v)
                      for k, v in out["built"].items()}, indent=1))
    print("all_ok:", all_ok, "seconds:", out["seconds"], "->", rp)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
