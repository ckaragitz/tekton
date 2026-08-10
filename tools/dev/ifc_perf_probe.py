#!/usr/bin/env python3
"""tools/dev/ifc_perf_probe.py -- large-IFC read-path baseline (issue #160, PG6 / O10).

Generates ``perf_<n>.ifc`` (n products) with OUR OWN emitter
(:func:`rvt.frontdoor.ifc_out.write_intent_ifc` fed a synthetic intent model:
one four-wall room shell + n electrical products in a grid, each with its
tagging-contract pset -- our bytes, written to a scratch dir, never committed)
and times ``open`` + ``rvt.ifc.intent.resolve_intent`` on each file under
both IFC read backends: the stdlib-only ``rvt.ifc.steplite`` shim
(``RVT_STEPLITE_FORCE=1``) and the real ``ifcopenshell`` wheel when it is
installed.  Every (backend, n) reading is taken in a FRESH child interpreter
so import state, caches and maxrss are that run's own.

  .venv/bin/python tools/dev/ifc_perf_probe.py                       # n=100,500,2000
  .venv/bin/python tools/dev/ifc_perf_probe.py --n 100,500,2000,10000 --json out/ifc_perf.json
  .venv/bin/python tools/dev/ifc_perf_probe.py --generate-only --dir /tmp/x   # just write the files
  # before/after on ONE machine: git worktree add /tmp/main origin/main, then
  .venv/bin/python tools/dev/ifc_perf_probe.py --src /tmp/main/src --label before --json before.json
  .venv/bin/python tools/dev/ifc_perf_probe.py --label after --json after.json

Output: one JSON document ``{"machine": ..., "src": ..., "files": {n: {path, bytes,
products}}, "runs": [{backend, n, open_s, read_slice_s, resolve_s, maxrss_mb,
equipment, walls, ok, error}]}`` on stdout (and ``--json``).  ``read_slice_s``
is the read layer alone -- get_psets + get_type + ContainedInStructure for
every product of the opened file, no resolver work -- so a change in
``rvt.ifc.intent``'s own cost cannot hide (or pose as) a reader regression;
``resolve_s`` is the whole ``resolve_intent`` (its own open included);
``maxrss_mb`` is the child's OWN peak RSS in MiB (VmHWM, ``ru_maxrss`` only as
the fallback -- see the child code for why).
Stdlib + the engine only; the ifcopenshell rows say ``"skipped"`` when the
wheel is absent (never a runtime dependency -- CLAUDE.md section 2).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

DEFAULT_SIZES = (100, 500, 2000)

#: product kinds the synthetic model cycles through: (kind, tag prefix, IFC
#: class, frame, dims w/d/h in metres, extra contract cells)
_KINDS = (
    ("distribution_panelboard", "DP", "IfcElectricDistributionBoard", "upright",
     (0.51, 0.15, 1.07), {"Voltage": "208Y/120 V", "BusRating": 225,
                          "MainsType": "Main lugs only", "NumberOfCircuits": 42,
                          "Mounting": "Surface"}),
    ("transformer", "TX", "IfcTransformer", "yaw",
     (0.79, 0.58, 1.02), {"RatingkVA": 75, "Primary": "480 V", "Secondary": "208Y/120 V",
                          "Manufacturer": "tekton", "ModelLabel": "TX-75"}),
    ("receptacle_device", "RC", "IfcOutlet", "upright",
     (0.07, 0.04, 0.11), {}),
    ("switchboard", "MSB", "IfcSwitchingDevice", "yaw",
     (2.29, 0.91, 2.29), {"Voltage": "480Y/277 V", "BusRating": 2000,
                          "MainsType": "Main breaker", "Sections": 3,
                          "ShortCircuitRatingkA": 65}),
)
_BOARD_KINDS = ("distribution_panelboard", "switchboard")     # what a FedFrom may name


def synthetic_model(n: int) -> SimpleNamespace:
    """A duck-typed intent model ``write_intent_ifc`` accepts: a rectangular
    room sized to hold ``n`` products on a 1.2 m grid, one storey, and n
    equipment items cycling through :data:`_KINDS` (a receptacle carries its
    own DeviceSchedule pset; boards feed from the previous board so the
    feeder tree is non-trivial).  Deterministic for a given ``n``."""
    cols = max(1, int(n ** 0.5))
    rows = (n + cols - 1) // cols
    pitch = 1.2
    width, depth, height = cols * pitch + 2.0, rows * pitch + 2.0, 3.0
    corners = [(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)]
    walls = [SimpleNamespace(p0_m=corners[i], p1_m=corners[(i + 1) % 4], thickness_m=0.2,
                             height_m=height, base_m=0.0) for i in range(4)]
    room = SimpleNamespace(name="Perf Room", level="L1", walls=walls, info={},
                           clear={"clearWidth_m": width, "clearDepth_m": depth,
                                  "clearHeight_m": height})
    equipment: List[SimpleNamespace] = []
    last_board = None
    for i in range(n):
        kind, prefix, cls, frame, (w, d, h), extra = _KINDS[i % len(_KINDS)]
        r, c = divmod(i, cols)
        x, y = 1.0 + c * pitch, 1.0 + r * pitch
        z = 1.2 if frame == "upright" else 0.0
        tag = f"{prefix}-{i + 1}"
        contract: Dict[str, Any] = {"PanelName": tag, **extra}
        psets: Dict[str, Dict[str, Any]] = {}
        if kind == "receptacle_device":
            psets["DeviceSchedule"] = {"DeviceType": "Duplex receptacle", "Load": 180,
                                       "MountingHeight": "18", "Voltage": "120 V"}
        elif last_board is not None:
            contract["FedFrom"] = last_board
        if kind in _BOARD_KINDS:
            last_board = tag
        equipment.append(SimpleNamespace(
            kind=kind, ifc_class=cls, tag=tag, name=f"{tag} {kind.replace('_', ' ')}",
            dims_m={"w": w, "d": d, "h": h}, insertion_m=[x, y, z],
            front_normal=[0.0, -1.0, 0.0], frame_kind=frame, level="L1",
            contract=contract, psets=psets, fed_from=None))
    return SimpleNamespace(project_name=f"tekton ifc perf probe n={n}", room=room,
                           equipment=equipment, feeders=[],
                           levels=[{"id": "L1", "name": "Level 1", "elevation": 0.0,
                                    "is_building_story": True}])


def generate(n: int, out_dir: str) -> Dict[str, Any]:
    """Write ``perf_<n>.ifc`` into ``out_dir``; returns {path, bytes, products}."""
    from rvt.frontdoor.ifc_out import write_intent_ifc
    path = os.path.join(out_dir, f"perf_{n}.ifc")
    write_intent_ifc(synthetic_model(n), path, note=f"synthetic perf probe, {n} products")
    return {"path": path, "bytes": os.path.getsize(path), "products": n + 1}   # + the room shell


# ---------------------------------------------------------------------------
# the child: one (backend, file) reading in a fresh interpreter
# ---------------------------------------------------------------------------

_CHILD = r"""
import gc, json, os, resource, sys, time
sys.path.insert(0, sys.argv[1])
backend, path = sys.argv[2], sys.argv[3]
if backend == "steplite":
    os.environ["RVT_STEPLITE_FORCE"] = "1"
else:
    os.environ.pop("RVT_STEPLITE_FORCE", None)
from rvt.ifc import intent as I          # selects the read backend (rvt.ifc._fallback)
import ifcopenshell
is_lite = bool(getattr(ifcopenshell, "IS_STEPLITE", False))
if (backend == "steplite") != is_lite:
    print(json.dumps({"ok": False, "skipped": True,
                      "error": "real ifcopenshell not installed" if backend != "steplite"
                               else "steplite shim not selected"}))
    sys.exit(0)
import ifcopenshell.util.element as UE
t0 = time.perf_counter()
f = ifcopenshell.open(path)
t1 = time.perf_counter()
# the read layer ALONE (no resolver work): every product's psets (type-merged),
# type and spatial containment -- the per-product inverse lookups #160 indexes
products = f.by_type("IfcProduct")
for p in products:
    UE.get_psets(p)
    UE.get_type(p)
    getattr(p, "ContainedInStructure", None)
t_slice = time.perf_counter() - t1
f = products = p = None
gc.collect()          # entity<->file cycles: free file #1 before the resolver opens its own
t2 = time.perf_counter()
model = I.resolve_intent(path)
t3 = time.perf_counter()
def peak_rss_mb():
    # VmHWM = this image's own peak RSS.  ru_maxrss is only the fallback: on
    # Linux exec() seeds it with the PARENT's high-water mark at fork time,
    # so a child of a fat parent would report the parent's memory, not its own
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024.0, "VmHWM"
    except OSError:
        pass
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return (rss / (1024.0 * 1024.0) if sys.platform == "darwin" else rss / 1024.0), "ru_maxrss"
rss_mb, rss_src = peak_rss_mb()
walls = len(getattr(getattr(model, "room", None), "walls", None) or [])
print(json.dumps({"ok": True, "open_s": round(t1 - t0, 3), "read_slice_s": round(t_slice, 3),
                  "resolve_s": round(t3 - t2, 3),
                  "maxrss_mb": round(rss_mb, 1), "maxrss_source": rss_src,
                  "equipment": len(model.equipment), "walls": walls}))
"""


def measure(backend: str, path: str, *, timeout: float, python: str, src: str = SRC
            ) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run([python, "-c", _CHILD, src, backend, path],
                              cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout:.0f} s",
                "wall_s": round(time.perf_counter() - t0, 1)}
    last = (proc.stdout.strip().splitlines() or [""])[-1]
    try:
        rec = json.loads(last)
    except ValueError:
        rec = {"ok": False, "error": (proc.stderr or proc.stdout)[-600:].strip()}
    rec["wall_s"] = round(time.perf_counter() - t0, 1)
    return rec


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", default=",".join(map(str, DEFAULT_SIZES)),
                    help="comma-separated product counts (default %(default)s)")
    ap.add_argument("--dir", default=None, help="scratch dir for the generated IFCs (default: a temp dir)")
    ap.add_argument("--backends", default="steplite,ifcopenshell")
    ap.add_argument("--timeout", type=float, default=600.0, help="per (backend, n) child, seconds")
    ap.add_argument("--python", default=sys.executable, help="interpreter for the measured children")
    ap.add_argument("--src", default=SRC,
                    help="engine src/ dir the measured children import (default: this checkout's; "
                         "point it at a worktree of main for a before/after on one machine)")
    ap.add_argument("--json", default=None, help="also write the JSON document here")
    ap.add_argument("--generate-only", action="store_true")
    ap.add_argument("--label", default="", help="free-text tag recorded in the output (e.g. main / head)")
    args = ap.parse_args(argv)

    sizes = [int(x) for x in args.n.split(",") if x.strip()]
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    out_dir = args.dir or tempfile.mkdtemp(prefix="ifc_perf_")
    os.makedirs(out_dir, exist_ok=True)
    files = {n: generate(n, out_dir) for n in sizes}
    src = os.path.abspath(args.src)
    doc: Dict[str, Any] = {
        "label": args.label,
        "src": src,
        "machine": {"python": sys.version.split()[0], "platform": platform.platform(),
                    "cpu_count": os.cpu_count()},
        "files": files,
        "runs": [],
    }
    if not args.generate_only:
        for n in sizes:
            for backend in backends:
                rec = measure(backend, files[n]["path"], timeout=args.timeout,
                              python=args.python, src=src)
                rec.update({"backend": backend, "n": n})
                doc["runs"].append(rec)
                print(json.dumps(rec), file=sys.stderr)
        # steplite / ifcopenshell resolve ratio per n, when both ran
        ratios = {}
        for n in sizes:
            got = {r["backend"]: r for r in doc["runs"] if r["n"] == n and r.get("ok")}
            if "steplite" in got and "ifcopenshell" in got and got["ifcopenshell"]["resolve_s"]:
                ratios[n] = round(got["steplite"]["resolve_s"] / got["ifcopenshell"]["resolve_s"], 2)
        doc["resolve_ratio_steplite_over_ifcopenshell"] = ratios
    text = json.dumps(doc, indent=1)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
