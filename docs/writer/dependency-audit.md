# Dependency audit — what the plugin's runtime paths actually import, and what each import costs

**Stream:** perf-deps (kill the heavy dependencies).
**Date:** 2026-08-04.
**Scope:** every module the PLUGIN's runtime paths can reach — the frontdoor
author / edit / inspect flows, the IFC read paths (`rvt.ifc.intent`,
`rvt.ifc.product_facts`, `rvt.ifc.famfrom_ifc`), and the converter modules
(`rvt.convert.*`) — plus the tekton-ifc authoring skill scripts.
**Method:** every claim below is *measured*, not inferred: import closures
were taken empirically (fresh subprocess per module, diff of `sys.modules`
roots against the stdlib list); install costs were timed with
`pip install --no-cache-dir` into fresh venvs; runtime numbers come from a
simulated bare VM (fresh TMPDIR containing ONLY the unzipped
`tekton-plugin.zip`, system python, `env -i` cleared environment).
Hardware: Apple Silicon macBook, fast office network — install *times* will
be larger on a slow sandbox link; the *byte sizes* are the invariant.

## 1. The third-party inventory (everything, with costs)

| package | why it exists | wheel download | installed size | cold `pip install` (fast net) | pure python? |
|---|---|---|---|---|---|
| **ifcopenshell 0.8.5** | reading IFC (intent + product facts); *writing* IFC (tekton-ifc skill); validation | **40.4 MB** (+7.1 MB deps: shapely 1.6 MB, numpy 5.1 MB, lark, isodate, dateutil, six, typing_extensions) | **190 MB** (+34 MB numpy, +7.1 MB shapely ⇒ ~233 MB total) | **11.0 s** wall (fresh venv, no cache; minutes on a slow VM link, **impossible** on a network-less sandbox) | no (C++ core, cython/swig) |
| **numpy** | `rvt.ifc.intent`'s matrix/hull math (top-level import); `rvt.frontdoor.prompt_intent`; lazy in `rvt.provenance` / ECC paths | 5.1 MB | 34 MB | 6.9 s wall | no (binary wheel) |
| **olefile** | the CFB container (`rvt.container`, `rvt.validate`, roundtrip) | ~0.1 MB | ~0.4 MB | ~1 s | **yes — already vendored** at `skills/_shared/_vendor`, zero install |
| compoundfiles | optional fallback in `rvt.roundtrip` only (guarded) | – | – | never installed | yes |
| pytest | dev-only (never on a runtime path) | – | – | – | yes |

`pip install ifcopenshell` transitively pins **numpy + shapely + lark +
isodate + python-dateutil + six + typing_extensions** — seven packages,
~47.5 MB of downloads, ~233 MB on disk, for read paths that consume a
line-oriented text format.

## 2. The honest per-route import graph (measured closures)

Third-party roots loaded by importing each entry module (venv with
everything installed; entries marked *eager-optional* disappear when the
package is absent because the import is guarded):

| route / module | hard third-party needs | notes |
|---|---|---|
| `rvt.frontdoor.build` (author `--prompt` → .rvt) | **numpy** (LAZY since the perf-coldstart stream's `rvt._lazyimp` landed — loads on first numeric use, still a hard need once geometry math runs) | *eager-optionally* drags in **ifcopenshell + shapely + lark + numpy** when ifcopenshell is installed (its own `__init__` imports numpy) — see finding F2 |
| `rvt.frontdoor.edit` / `.intent` / `.prompt_intent` | **numpy** (same lazy chain) | same eager-optional drag |
| `rvt.ifc.intent` (author `--ifc`, resolved intent) | **numpy** + (**ifcopenshell** *or* **steplite**) | ifcopenshell import is guarded `try` — absent ⇒ module still imports; reads then need the steplite fallback |
| `rvt.ifc.product_facts` (facts extractor) | **none** at import; (**ifcopenshell** *or* **steplite**) at read time | **stdlib-only** with steplite |
| `rvt.ifc.famfrom_ifc` (facts → family .rfa) | **none** (famgen chain is pure python) | stdlib-only end to end with steplite |
| `rvt.convert.merge_ifc` / `.modify_family` / `.add_to_project` | **numpy** (via frontdoor.intent chain) + (**ifcopenshell** *or* **steplite**) for the IFC leg | |
| `rvt.container` / `rvt.validate` (open/emit .rvt) | **olefile** (vendored in the plugin — zero install) | validate's numpy use is lazy (ECC paths only) |
| `rvt.famgen.*`, `rvt.mutate`, `rvt.mep`, `rvt.render.wallgeom` | none | pure python |
| tekton-ifc skill scripts (`generate_ifc.py`, `harden_ifc.py`, `bridge_lib.py`, `validate_ifc.py`) | **ifcopenshell (REAL — `.api`/`.guid`/`.validate`) + numpy** | IFC *authoring*: out of steplite's scope, by design |
| `tools/ifc_to_spec.py` (legacy front door) | ifcopenshell (incl. `.geom`) + numpy | superseded by `rvt.ifc.intent`; left untouched |

### Findings

* **F1 — ifcopenshell was the only heavy dependency on the READ paths, and
  the read paths use a narrow, text-only slice of it.** No geometry kernel
  is invoked anywhere (`ifcopenshell.geom` appears only in the legacy
  `ifc_to_spec.py`): the three-d-stage writer bakes world coordinates into
  `IfcCartesianPointList3D`, so reads are STEP text + attribute graph.
  That slice is now served by **`rvt.ifc.steplite`** (stdlib-only, one
  file) — see §3.
* **F2 — installing ifcopenshell taxes even non-IFC jobs.** `rvt.ifc.intent`
  guards its import with `try:`, but when the package IS installed the try
  *succeeds*, so every author/edit/convert flow eagerly imports the 190 MB
  package: +0.30 s per process pyc-warm, **+~4.5 s on the first process
  after install** (bytecode compile), measured on the intent route (cold
  process 4.98 s with ifcopenshell vs 1.50 s with steplite+numpy).
  On sandboxes the fix is free: *don't install ifcopenshell* — the steplite
  fallback serves the reads and its import costs **0.022 s**.
* **F3 — numpy is the remaining hard dependency of the intent/author path.**
  The perf-coldstart stream has already made the *import* lazy
  (`rvt._lazyimp` in `rvt.ifc.intent` / `rvt.frontdoor.prompt_intent`), so
  a numpy-less box imports the modules fine and fails only at first
  numeric use — but resolving an intent or authoring geometry still needs
  it.  It is 8× smaller than the ifcopenshell chain (5.1 MB wheel, 34 MB
  disk, 6.9 s cold install) and commonly preinstalled on AI-surface
  sandboxes; the product-facts/family route does not need it at all.
  Excising numpy from intent.py would be a large rewrite of working math
  (hulls, 4×4 chains, box decomposition) inside another stream's certified
  module — deliberately NOT done; documented as the floor of the author
  route.
* **F4 — olefile is solved already** (vendored, pure python, zero install).
* **F5 — IFC *authoring* (tekton-ifc skill) legitimately needs the real
  ifcopenshell** (`ifcopenshell.api`); steplite deliberately refuses to
  pretend otherwise — importing `ifcopenshell.api`/`.geom`/`.validate`
  under the shim raises `ModuleNotFoundError`, the same honest signal as an
  absent library, and `/tekton-doctor --install` remains the documented way
  to enable authoring.

## 3. The fix that landed: steplite (stdlib-only IFC read subset)

`src/rvt/ifc/steplite.py` — a ~700-line, stdlib-only ISO-10303-21 reader
covering exactly the entity subset the resolver + facts extractor consume
(tokenizer → lazy entity graph; `is_a` with the IFC4 inheritance slice;
psets with ifcopenshell's own merge semantics; unit scale; placement
chains; tessellated face sets; styles/colours; `by_type` reproducing
ifcopenshell's declaration-tree DFS ordering).  Selected by **import
fallback, not monkeypatching**: `rvt/ifc/_ifcos_shim/ifcopenshell` is a
real package appended to `sys.path` by `tekton_env.ensure_engine` ONLY when
the genuine library is absent; if a real distribution is importable the
shim loads *it* instead of itself (stand-down guarantee, tested).  Zero
edits to `rvt.ifc.intent` / `rvt.ifc.product_facts`.

**Foreign classes (issue #155, 2026-08-09).** The transcribed attribute
subset (~200 rows) is no longer the boundary of the class tree: steplite
also carries `src/rvt/ifc/ifc4_parents.py`, the full IFC4 entity →
supertype table (776 entities, our own generated text —
`tools/dev/gen_ifc4_parents.py` reads the public IFC4 declarations out of a
dev-time ifcopenshell; nothing is imported at runtime).  Any IFC4 entity a
foreign tool emits therefore lands in the same `by_type('IfcProduct')` /
`is_a('IfcElement')` closure ifcopenshell reports, in ifcopenshell's own
order (case-sensitive CamelCase subtype order, file order per class), and
serves the positional attributes of its nearest transcribed ancestor
(`GlobalId … Tag` for elements); only its own leaf attributes raise.
Rows were added for the common building classes (door / window / column /
beam / roof / stair / railing / curtain wall / plate / member / footing /
furnishing), the electrical MEP classes (outlet, junction box, protective
device, appliances, motor / generator, UPS, cable-carrier fitting),
distribution ports + `IfcRelNests` / `IfcRelConnectsPorts`, systems / zones
+ `IfcRelAssignsToGroup`, and `IfcRelVoidsElement` / `IfcRelFillsElement`;
every row's supertype and full attribute list is cross-checked against the
IFC4 declarations in the test suite whenever ifcopenshell is importable.
Measured effect: `frontdoor author --ifc usecases/chicago-plenum-electrical-room/generated.ifc`
resolved 17 products under steplite vs 18 under ifcopenshell before (the
`IfcDoor` was dropped); after, 18 = 18 and the two `intent.json` are
byte-identical (142 633 bytes) modulo `source.path`.

**Class tree per FILE_SCHEMA (issue #337, 2026-08-10).** steplite now picks
the tree per file: an `IFC4X3*` file is read through
`src/rvt/ifc/ifc4x3_add2_parents.py` (876 entities, generated the same way
with `--schema IFC4X3_ADD2`) plus an eight-row delta for what IFC4.3 changed
in the transcribed subset (`IfcBuildingElement[Type]` → `IfcBuiltElement[Type]`,
`IfcBuilding` ⊂ `IfcFacility`, `IfcProperty.Specification`,
`IfcObjectPlacement.PlacementRelTo`), so `is_a('IfcBuiltElement')`,
`by_type('IfcFacility')`, `schema == 'IFC4X3'` / `schema_identifier ==
'IFC4X3_ADD2'` answer as ifcopenshell does; the cross-check of every row
against `schema_by_name("IFC4X3_ADD2")` went from 31 differences to 0.  The
IFC4X3 table is imported on first IFC4X3 file only (+0.96 ms / +291 KiB then;
IFC4-only processes: import time unchanged, +31 KiB).  Still out of scope:
IFC2X3's own hierarchy and attribute orders (IFC2X3 / IFC4X1 / IFC4X2 files
keep the IFC4 tree; `IfcElectricDistributionPoint` etc. — #159).

**Equivalence proof** (tests/test_steplite.py, run on both reference IFCs —
`electrical-room-2500a.ifc` and `chicago-plenum-downlight.ifc`):

* every entity, every named attribute equal against ifcopenshell 0.8.5
  (2 135 + 545 attribute comparisons, zero mismatches);
* `get_psets` / `get_type` / `calculate_unit_scale` /
  `get_local_placement` / `get_inverse` / `by_type` ordering equal;
* full-pipeline **byte-equality**: `resolve_intent → intent_to_json` and
  `product_facts → to_facts_record(+full dump)` produce byte-identical JSON
  under both backends (285 KB intent JSON: `cmp` clean).

## 4. Before / after (simulated bare VM: fresh TMPDIR, unzipped plugin only, system python, cleared env)

| route | BEFORE (ifcopenshell) | AFTER (steplite) |
|---|---|---|
| product facts / IFC→family | 47.5 MB download, 233 MB disk, 11.0 s install (fast net; minutes/impossible on constrained VMs) **+** 0.9 s first process | **zero install**, 0.68 s total first process (0.19 s extract) |
| resolved intent (author `--ifc`) — first process on the box | install as above + **4.98 s** process (import-compile dominated) | numpy only (5.1 MB / 6.9 s; zero where numpy is preinstalled) + **1.50 s** process |
| resolved intent — later processes (pyc-warm) | 0.78 s | 0.77 s (parse 0.63 s vs 0.47 s: steplite's pure-python parser is ~0.16 s slower on the 687 KB room file, offset by the 0.30 s import it avoids) |
| author `--prompt` (no IFC input) | 8.8 s first / ~7.8 s warm (eager ifcopenshell import riding along) | 6.5 s first / ~6.5 s user-time warm (numpy-only venv; job dominated by the build itself) |
| `import ifcopenshell` cost | 0.297 s (pyc-warm; ~4.5 s first-ever) | 0.022 s (shim) |

Raw wheel/install numbers: `pip download ifcopenshell` = 40.4 MB + 7.1 MB
deps; installed 190 MB + 34 MB numpy + 7.1 MB shapely; `pip install
--no-cache-dir ifcopenshell` = 11.0 s wall; `numpy` alone = 5.1 MB / 34 MB /
6.9 s (Apple Silicon wheels, office network, 2026-08-04).

## 5. What still costs, and the recommended posture

1. **Ship the plugin with NO pip installs for IFC reads** (done — the
   fallback engages automatically; `preflight` reports the route available).
2. **The author/intent route needs numpy** — keep `doctor --install` for
   boxes without it; most AI-surface sandboxes preinstall numpy (F3).
3. **Never `pip install ifcopenshell` just to read IFC** — it costs 47.5 MB
   / 233 MB / minutes-on-slow-links and then taxes every process import
   (F2).  Install it only to *author* IFC (tekton-ifc skill) or to run
   `ifcopenshell.validate`.
4. Optional follow-ups (recorded, not done — outside this stream's
   territory): make `rvt.ifc.intent`'s ifcopenshell import lazy
   (function-level, like product_facts) so an installed ifcopenshell no
   longer taxes prompt-only jobs (patch sketch in
   `docs/inbox/perf-deps.md` §patches); port the legacy
   `tools/ifc_to_spec.py` off `ifcopenshell.geom` or retire it.
