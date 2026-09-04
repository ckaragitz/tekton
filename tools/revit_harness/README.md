# The verdict harness — your Revit as an unattended test rig

One-time setup (the owner's Windows machine, Revit 2026 installed):

1. Install [pyRevit](https://github.com/pyrevitlabs/pyRevit/releases) (free)
   — or use RevitPythonShell if you already have it.
2. Copy this folder anywhere (it needs no tekton checkout).
3. Drop the `.rfa` files a session sends you into `inbox/`.
4. Run: `pyrevit run verdict_harness.py --revit=2026`
   (or paste-exec the file in RevitPythonShell).
5. Send back `verdicts.json`.

Per file it records: did it **open**; did every solid's geometry **expand**
(the click-the-extrusion failure class, caught with no clicking); and per
parameter, whether flexing it **drives geometry**, is **value-only**, or
**errors** — the exact ladder the P-rung and drive-chain probes need.

No dialogs, no saving, nothing modified: every flex is rolled back and every
document closed without saving. The session turns each FAIL row into a
permanent no-Revit check (`constraint_law` / `conformance`), so each run
shrinks the set of things that ever need a human again.
