"""tekton verdict harness -- turn a Revit desktop into an unattended test rig.

WHY THIS EXISTS.  tekton's own instruments catch internal contradictions
(constraint_law), corpus divergence (conformance) and structural damage
(rvt_validate) with no Revit at all -- but hard rule 4 stands: only Autodesk's
reader decides whether a family OPENS and BEHAVES.  Revit runs only on the
owner's Windows machine and APS is banned (hard rule 7), so that machine is
the arbiter.  This script makes it an arbiter that needs NO CLICKING: drop
.rfa files in a folder, run once, read verdicts.json.

WHAT IT DOES (inside Revit, via pyRevit or RevitPythonShell):
  for every .rfa in the inbox folder:
    1. open the family document                (verdict: opens)
    2. enumerate its parameters                (names, storage types)
    3. select-test: expand every element's geometry
                                               (verdict: geometry_readable --
                                                the click-the-extrusion bug
                                                class, caught headlessly)
    4. FLEX every modifiable family parameter: set value*1.1, regenerate,
       diff every solid's bounding box, set it back
                                               (verdict per parameter: drives
                                                geometry / value-only / error)
    5. close without saving; write one row to verdicts.json

HOW TO RUN (once):
  * pyRevit:  pyrevit run tools/revit_harness/verdict_harness.py --revit=2026
  * or RevitPythonShell / a Dynamo Python node: exec(open(r"...\verdict_harness.py").read())
  * folders default beside this file: inbox/ (drop .rfa here), verdicts.json out.

The session reads verdicts.json back (the owner uploads it, or it syncs);
every FAIL row becomes a law in constraint_law/conformance so the same
species can never ship again.  That is the loop: tekton authors -> harness
verdicts -> failure becomes a permanent no-Revit check.

This file runs INSIDE Revit's Python (IronPython or CPython3 per pyRevit);
it imports nothing from tekton and touches no Autodesk install directory --
it only drives the running Revit session's own API.
"""
import json
import os
import time
import traceback

try:                                     # Revit API (present only inside Revit)
    import clr                                                     # noqa: F401
    from Autodesk.Revit.DB import (BuiltInParameterGroup,          # noqa: F401
                                   FilteredElementCollector, GenericForm,
                                   Options, StorageType, Transaction)
    from pyrevit import HOST_APP
    _APP = HOST_APP.app
except Exception:                        # imported outside Revit: explain, don't crash
    _APP = None

HERE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.environ.get("TEKTON_HARNESS_INBOX", os.path.join(HERE, "inbox"))
OUT = os.environ.get("TEKTON_HARNESS_OUT", os.path.join(HERE, "verdicts.json"))
FLEX_FACTOR = 1.1
BBOX_TOL_FT = 1e-6


def _bboxes(doc):
    out = {}
    opts = Options()
    for el in FilteredElementCollector(doc).OfClass(GenericForm):
        bb = el.get_BoundingBox(None)
        if bb is not None:
            out[el.Id.IntegerValue] = (bb.Min.X, bb.Min.Y, bb.Min.Z,
                                       bb.Max.X, bb.Max.Y, bb.Max.Z)
        g = el.get_Geometry(opts)        # the select-test: force expansion
        if g is not None:
            for _ in g:
                break
    return out


def _moved(a, b):
    if set(a) != set(b):
        return True
    for k in a:
        if any(abs(x - y) > BBOX_TOL_FT for x, y in zip(a[k], b[k])):
            return True
    return False


def _flex(doc, fam_mgr, param):
    """Flex ONE parameter: x1.1, regen, bbox diff, restore.  Returns verdict."""
    if param.IsReadOnly or param.StorageType != StorageType.Double:
        return "not-flexable"
    cur = fam_mgr.CurrentType
    old = cur.AsDouble(param)
    if old is None or old == 0:
        return "value-only (no current value to flex)"
    before = _bboxes(doc)
    t = Transaction(doc, "tekton flex " + param.Definition.Name)
    t.Start()
    try:
        fam_mgr.Set(param, old * FLEX_FACTOR)
        doc.Regenerate()
        after = _bboxes(doc)
        verdict = "DRIVES geometry" if _moved(before, after) else "value-only"
        fam_mgr.Set(param, old)
        doc.Regenerate()
        t.Commit()
        return verdict
    except Exception as exc:                                       # noqa: BLE001
        t.RollBack()
        return "ERROR: %s: %s" % (type(exc).__name__, exc)


def run():
    if _APP is None:
        print(__doc__)
        print("!! Not running inside Revit -- start this through pyRevit / "
              "RevitPythonShell on the machine with Revit installed.")
        return 2
    os.makedirs(INBOX, exist_ok=True)
    rows = []
    for fname in sorted(os.listdir(INBOX)):
        if not fname.lower().endswith(".rfa"):
            continue
        row = {"file": fname, "opened": False, "geometry_readable": False,
               "parameters": {}, "error": None, "seconds": None}
        t0 = time.time()
        doc = None
        try:
            doc = _APP.OpenDocumentFile(os.path.join(INBOX, fname))
            row["opened"] = True
            _bboxes(doc)                       # select-test every form
            row["geometry_readable"] = True
            # per-view census: how many solids each view actually shows.
            # This is the "why can't I see the whole item in plan" question
            # answered without anyone's eyes (steer #765): a plan view whose
            # count is far below the 3D view's names the display bug and,
            # via each element's id, WHICH parts vanish.
            try:
                from Autodesk.Revit.DB import View
                census = {}
                for v in FilteredElementCollector(doc).OfClass(View):
                    if getattr(v, "IsTemplate", False):
                        continue
                    ids = [e.Id.IntegerValue for e in
                           FilteredElementCollector(doc, v.Id).OfClass(GenericForm)]
                    census["%s:%s" % (v.ViewType, v.Name)] = {
                        "solids_visible": len(ids), "ids": ids[:400]}
                row["view_census"] = census
            except Exception as exc:                               # noqa: BLE001
                row["view_census"] = "ERROR: %s" % exc
            fm = doc.FamilyManager
            for p in fm.GetParameters():
                row["parameters"][p.Definition.Name] = _flex(doc, fm, p)
        except Exception as exc:                                   # noqa: BLE001
            row["error"] = "%s: %s" % (type(exc).__name__, exc)
            row["traceback"] = traceback.format_exc()[-1500:]
        finally:
            if doc is not None:
                try:
                    doc.Close(False)
                except Exception:                                  # noqa: BLE001
                    pass
        row["seconds"] = round(time.time() - t0, 2)
        rows.append(row)
        print("%-40s opened=%s geom=%s params=%d err=%s" % (
            fname, row["opened"], row["geometry_readable"],
            len(row["parameters"]), (row["error"] or "-")[:60]))
    with open(OUT, "w") as fh:
        json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "revit": str(getattr(_APP, "VersionNumber", "?")),
                   "rows": rows}, fh, indent=1)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    # plain python AND pyRevit/RevitPythonShell (both exec the script as
    # __main__); an unconditional module-level run() fired on any IMPORT of
    # this file too (#770 review) -- the guard covers every real entry.
    raise SystemExit(run())
