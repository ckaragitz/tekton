# ifc-census — every `--ifc` manifest enumerates what the IFC held vs what reached the .rvt (issue #153)

Stream: `ifc-census` (eng #153, cloud engineer session started by the tech-lead session,
2026-08-09). Charter = issue #153 (Refs #108 wave 2, **PG1 honesty**). Territory:
`src/rvt/ifc/intent.py` (census computation next to `resolve_intent`, `IntentModel.census`),
`src/rvt/frontdoor/intent.py` (`summarize`), `src/rvt/frontdoor/manifest.py` (the
MANIFEST.md section + the one degradation line), NEW `tests/test_ifc_census.py`, one line at
the END of `tests/ci_shard.txt`, the conformance generator's registry + pinned expectations
(`tools/dev/make_ifc_fixtures.py`, `tests/ifc_conformance/*`), regenerated `plugin/lib/**`,
this record. NOT touched: `tools/frontdoor.py`, `src/rvt/frontdoor/matrix.py` (wording patch
below), `src/rvt/frontdoor/base.py`, `skills/tekton-ifc/**`, `src/rvt/ifc/steplite.py`
(called, never edited).

## Why

Before this change, content the resolver cannot use disappeared without a word: an
`IfcSpace`, an `IfcOpeningElement`, an `IfcDoor` under old steplite, a body item of a type
nobody tessellates. `matrix.py` admits "content outside the resolved intent does not
survive", but nothing enumerated it *per run*, so a QA engineer could not tell a faithful
conversion from a hollow one. Measured on `main` @ 935b419 before writing anything (probe in
the scratchpad, both backends): `e_space_in_storey.ifc` → the `IfcSpace` is in
`f.by_type("IfcProduct")` under **both** backends (steplite parity landed in #338) yet absent
from `equipment`, `other_products` and MANIFEST.md; `d_wall_opening_door.ifc` → the opening
and the two `IfcRelVoidsElement` / `IfcRelFillsElement` relationships vanish the same way.

## What was built

* **`rvt.ifc.intent._census(f, products, equipment, others)`** → `IntentModel.census`
  (new dataclass field, `default_factory=dict`, so the prompt route's hand-built model is
  unaffected). Pure enumeration over the same file handle `resolve_intent` already opened —
  it never changes what is resolved, and it uses only `by_type` / `is_a` / attribute reads
  that steplite serves identically to ifcopenshell:
  * `schema`, `products_total` (= `len(f.by_type("IfcProduct"))`, which covers every
    `IfcSpatialElement` / `IfcSpatialStructureElement` too), `totals {mapped, recorded, dropped}`;
  * `by_class[<IfcClass>] = {read, mapped, recorded, dropped, reason}` — the fate is read off
    the resolver's ACTUAL outcome, not re-derived: equipment of a `GENERATED_KINDS` kind and
    the room-shell proxy → **mapped** (content the build authors); other equipment and the
    clearance proxies → **recorded** (kept in intent.json, no element authored; reason names
    the kinds); `IfcBuildingStorey` → mapped (a level); `IfcSite` / `IfcBuilding` → recorded
    ("placement scaffolding"); everything else `resolve_products` passes over → **dropped**
    with the reason from `_unread_fate()` — the ONE filter `resolve_products` applies and the
    census reports (IfcSpace → #158, openings/features → #157, ports, annotations, grids,
    other spatial elements, "not an IfcElement");
  * `spatial {sites, buildings, storeys, spaces}`;
  * `body_items {total, by_type, read, unreadable, unreadable_by_type, on_unread_products,
    readable_kinds, products_left_bodiless, non_body_representations}` — leaf items of every
    product's `Body` (or unnamed) representation, `IfcMappedItem` resolved through once per
    use; for read products the counts come straight from `ProductGeometry.items`
    (`GeomItem.ifc_class`) and the new `ProductGeometry.skipped` that `_collect_items` fills at
    the moment `_item_points_tris` returns nothing, so an `IfcExtrudedAreaSolid` over an
    unsupported profile or an empty brep counts unreadable exactly like an `IfcSweptDiskSolid`
    and the census never re-derives a read decision; items on products the resolver never
    reads (a space's own volume) are `on_unread_products`, never "unreadable"; non-Body
    representations (Axis / FootPrint / Box) are tallied by identifier and never called
    unreadable body. Invariant (asserted by the test): `read + unreadable + on_unread_products
    == total == sum(by_type)`; per class `mapped + recorded + dropped == read`;
  * `relationships_consumed` (the four the resolver reads: Aggregates, ContainedInSpatial-
    Structure, DefinesByProperties, DefinesByType, with counts) and `relationships_ignored`
    = every other `IfcRelationship` class present, `[{class, count, effect}]` with the cost
    of ignoring it spelled out for the 19 known ones (`IfcRelVoidsElement` → "openings are not
    cut into their host", …) and "not read by the resolver" otherwise;
  * `legend` — one sentence per bucket so the JSON is self-explaining to a QA reader.
* `intent_to_json()` emits `"census"`; **`rvt.frontdoor.intent.summarize()`** gains
  `other_products_total`, `other_products [{name, tag, ifcClass, kind, disposition}]` and
  `census` → so `manifest.json` → `intent.summary.census` carries it on every `--ifc` run
  (and on `merge_ifc` / `add_to_project`, which reuse `summarize`).
* **`rvt.frontdoor.manifest`**: `census_gaps(census)` (exported) projects the census onto
  what must be shown; `build_manifest()` appends exactly ONE line to `build.degradations`
  when `dropped > 0 or unreadable > 0` ("IFC census: 1 of 7 products dropped (IfcSpace×1); 1
  of 5 body items unreadable (IfcSweptDiskSolid×1) -- that content does not reach the .rvt;
  delivery unchanged (a label, hard rule 1); …"); `_render_md()` adds under `## Intent` a
  `recorded, not modelled (n)` line (the `other_products` the manifest used to omit) and an
  `IFC census (…)` one-liner on every IFC run, and a **`## Not converted from the IFC`**
  section (dropped classes × count — reason; unreadable body-item types × count with the
  readable kinds named; products left without any body; relationships not read — effect)
  only when something was dropped or unreadable. `_rollup_status` is untouched: the status
  line, the stamps and the delivered files are byte-for-byte what they were, plus one
  degradation line (rule 1: a label, never a refusal).
* **Fixture `j_census_space_unreadable_body`** registered in `tools/dev/make_ifc_fixtures.py`
  (hand-authored STEP from parameters, 5,239 B, zero third-party bytes): an `IfcSpace` WITH
  its own `IfcExtrudedAreaSolid` volume aggregated into the storey, a tessellated `DP-1`
  contained in the space, an `IfcWallStandardCase` extrusion `W-1`, and a conduit `CT-1`
  (`IfcCableCarrierSegment`) whose only body item is an `IfcSweptDiskSolid` along an
  `IfcPolyline` — a genuinely unreadable type now that extrusions are read (#327).
* The generator's pinned projection (`summarize(path)`, documented as "THE one place a
  sibling issue extends when its DONE pins a new fact (#153 census …)") gains
  `census` (minus the prose `legend`) → all ten `.expected.json` re-pinned with
  `.venv/bin/python tools/dev/make_ifc_fixtures.py --update-expected` (see *Re-pins* below).
* **`tests/test_ifc_census.py`** (8 tests, appended LAST to `tests/ci_shard.txt`), stdlib /
  steplite: resolves fixture j + `inputs/ifc/electrical-room-2500a.ifc` in ONE child
  interpreter with `RVT_STEPLITE_FORCE=1` via the generator's `resolve_summaries`; asserts
  j's exact counts (7 products; totals 2/4/1; IfcSpace dropped 1 citing #158; body items
  `{IfcExtrudedAreaSolid: 2, IfcSweptDiskSolid: 1, IfcTriangulatedFaceSet: 2}`, read 3,
  unreadable 1, on_unread 1, `CT-1` bodiless), the room IFC's all-zero losses (17 products,
  111/111 tessellated items read), the bucket invariants on both, parity with a real
  ifcopenshell when importable (skip otherwise), the manifest section + exactly one census
  degradation for j and their absence for the room IFC (in-process `summarize` →
  `build_manifest(build=None)` → `_render_md`; the 17 s genesis build is the /verify run, not
  a shard test), and `intent.json` carrying `census`.

## Evidence

Census under both backends (scratchpad probe = `resolve_intent(p).census`, legend stripped,
`diff` of the JSON): **IDENTICAL** for `inputs/ifc/electrical-room-2500a.ifc`,
`e_space_in_storey`, `d_wall_opening_door`, `j_census_space_unreadable_body`; the conformance
parity test now compares the census of all ten fixtures (9 pass, `i_schema_ifc2x3` stays the
pre-existing strict xfail of #159 — its census differs by the same `IfcElectricDistributionPoint`
the equipment list already differs by).

| input | products | mapped / recorded / dropped | body items (read / unreadable / on unread) | ignored rels | section |
|---|---|---|---|---|---|
| `inputs/ifc/electrical-room-2500a.ifc` | 17 | 10 / 7 / 0 | 111 tess (111 / 0 / 0) | — | absent ("nothing dropped or unreadable") |
| `usecases/chicago-plenum-electrical-room/hardened.ifc` | 14 | 11 / 3 / 0 | 61 extr + 4 tess (65 / 0 / 0) | — | absent |
| `d_wall_opening_door` | 8 | 2 / 4 / 1 (IfcOpeningElement) | 3 extr + 2 tess (4 / 0 / 1) | IfcRelFillsElement×1, IfcRelVoidsElement×1 | present |
| `e_space_in_storey` | 7 | 4 / 2 / 1 (IfcSpace) | 4 tess (4 / 0 / 0) | — | present |
| `j_census_space_unreadable_body` | 7 | 2 / 4 / 1 (IfcSpace) | 2 extr + 1 swept disk + 2 tess (3 / 1 / 1) | — | present |

MANIFEST.md of `frontdoor author --ifc tests/ifc_conformance/j_census_space_unreadable_body.ifc`
(full genesis build, 17.7 s, exit 0, status `PROOF-ONLY (self-checks PASS; …)` as before):

```
- IFC census (IFC4): 7 products read — 2 mapped, 4 recorded only, 1 dropped; body items 3/5 read, 1 unreadable — see **Not converted from the IFC** below
## Not converted from the IFC
- the input held 7 products (IFC4); the content below did NOT reach the delivered .rvt — the file is delivered all the same (a label, never a refusal); …
- **dropped** IfcSpace ×1 — IfcSpace is not read into the intent (no room / space element is authored from it yet, #158); products contained in it still resolve their storey through it
- **unreadable body items** (1 of 5): IfcSweptDiskSolid ×1 — the resolver reads IfcTriangulatedFaceSet, IfcTriangulatedIrregularNetwork, IfcPolygonalFaceSet, IfcFacetedBrep, IfcExtrudedAreaSolid; anything else loses its geometry
- **left without any body**: 'CT-1' (IfcCableCarrierSegment, 1/1 body items unreadable) — recorded at its placement with no extents
…
- **degradation**: IFC census: 1 of 7 products dropped (IfcSpace×1); 1 of 5 body items unreadable (IfcSweptDiskSolid×1) -- that content does not reach the .rvt; delivery unchanged (a label, hard rule 1); itemised under 'Not converted from the IFC' / manifest.json intent.summary.census
```

## /verify (the product driven end to end, both backends)

`frontdoor author --ifc <input> --out out/verify/<k>_<backend> --json` for
`hardened.ifc`, `electrical-room-2500a.ifc`, fixture `j`, each under real ifcopenshell 0.8.5
and `RVT_STEPLITE_FORCE=1` — **6/6 exit 0**, status `PROOF-ONLY (self-checks PASS; …)`,
one `.rvt` delivered per run, `tools/rvt_validate.py` → `VALID (no errors); warnings=1` (the
known DataStorage decoder-gap warning) on all six; census blocks byte-identical between the
two backends per input; hardened + room: `census_gaps.show False`, no census degradation, no
`Not converted` section, one-liner "… nothing dropped or unreadable"; j: section PRESENT +
exactly one `IFC census:` degradation. **Baseline against `origin/main` @ 935b419** (same
inputs, git worktree): status string identical, `proof_only_stamps` identical, delivered
`.rvt` byte size identical (room 667,648 B; j 593,920 B), `build.degradations` room 5 → 5
(nothing added), j 2 → 3 (added = the census line only, nothing removed).

## Re-pins (deliberate, `--update-expected`) — every change explained

Checked semantically against `HEAD` (script in the scratchpad: old `expected` == new
`expected` minus `census`, header compared separately):

* `a…i` (9 files): `expected` body **identical** to the previous pin except for the added
  `census` key; `d` pins `IfcOpeningElement` dropped ×1 + `IfcRelFillsElement` /
  `IfcRelVoidsElement` ignored, `e` pins `IfcSpace` dropped ×1, all others 0 dropped / 0
  unreadable / no ignored relationships. Headers unchanged except two registry notes I own the
  wording of: `a_units_mm` (the note that parked the "pset length-measure conversion" question
  on #153 now says the census does not cover pset measures and that conversion is its own
  follow-up) and `e_space_in_storey` (notes that the census counts the space dropped ×1).
* `j_census_space_unreadable_body`: new pin.
* Instrument note (voided reading, re-run — evidence discipline): my first `--update-expected`
  ran under the system `python3` (no numpy) and pinned `{"ok": false, "error": "ImportError:
  numpy is required…"}` into all ten files; caught by the semantic check, restored from git,
  re-run with `.venv/bin/python`. Lesson for the generator's users: run `--update-expected`
  with the project venv; `--check` (stdlib) is fine under any python3.

## Patch offered to `src/rvt/frontdoor/matrix.py` (not my territory — for #5's holder)

```diff
@@ Cell(("ifc",), "ifc", STATUS_WORKS, "ifc_normalize",
-         ("normalisation into OUR tagging-contract IFC dialect; content "
-          "outside the resolved intent (finishes, annotations, non-contract "
-          "psets) does not survive the round trip",)),
+         ("normalisation into OUR tagging-contract IFC dialect; content "
+          "outside the resolved intent (finishes, annotations, non-contract "
+          "psets) does not survive the round trip -- every run's manifest "
+          "enumerates exactly what was dropped / unreadable (intent census, #153)",)),
```

## Findings / open questions

* `IfcSite` / `IfcBuilding` are classed **recorded** ("placement scaffolding") rather than
  dropped: they are consumed (composed into every placement chain) but carry no element. If a
  reviewer prefers a fifth bucket, it is a one-word change in `_census`; the DONE's four
  buckets were kept.
* Pset `IfcLengthMeasure` values (fixture `a`'s `RoomInformation` in mm) are still not
  unit-converted; the census enumerates products / bodies / relationships, not measures.
  Follow-up filed: **#348**.
* Under steplite an IFC2X3-only relationship or product class (outside the IFC4 closure) is
  matched by exact name only, so it would be missing from `by_type("IfcRelationship")` /
  `by_type("IfcProduct")` — the same #159 / #337 gap the equipment list already has; noted
  for #337 rather than editing `steplite.py`.

* `router._absorb_author_result` copies stamps and the target-version line into `RouteResult`
  but not `build.degradations`, so `route run --ifc … --to rvt` will not show the census line
  (nor any other build degradation). Router territory → follow-up **#347**.
* `CONSUMED_RELATIONSHIPS` is a hand list of what `_levels` / `_storey_of_products` /
  `get_psets` / `get_type` touch; consumption is spread across ifcopenshell utils, so there is
  no cheap single source — accepted, documented at the constant.

## /simplify pass (4 review angles) — what changed after the first cut

Reuse / altitude findings were the same pattern — a post-hoc observer re-deriving decisions
the resolver had already taken — and were fixed at the decision points, behaviour-preserving
(the ten steplite pins did not move; parity still identical):
* `_collect_items` now records every leaf it cannot read into `ProductGeometry.skipped`
  (item id, class, rep identifier) and stamps `GeomItem.ifc_class`; the census reads those
  instead of re-walking read products (only never-read products are walked, by `_leaf_items`).
* `READABLE_BODY_ITEMS` moved beside `_item_points_tris` as that ladder's legend.
* ONE filter `_unread_fate(prod)` is applied by `resolve_products` AND reported by the census
  (replaces the census-private `_drop_reason` + storey/site/building branches).
* mapped/recorded read off `Equipment.disposition`; one fate loop; `spatial` derived from
  `by_class`; reasons set once per class; `census_gaps` computed once in `build_manifest` and
  stashed as `manifest.json` → `intent.census_gaps` (the compact "what was lost" block) for
  `_render_md`; `summarize()` drops the prose `legend` (it stays in intent.json); the test
  resolves each IFC once in-process (module fixture).
Skipped on purpose: threading `readable_kinds` out of the census (kept — the JSON should be
self-explaining to a QA reader who never opens the Python) and dropping
`non_body_representations` (kept — it is what makes `total` reconcile when a file carries
Axis / FootPrint reps).

## BRANCH STATE

* Branch `cam/153-ifc-census` from `main` @ 935b419; PR opened (number in the report).
* Files: `src/rvt/ifc/intent.py`, `src/rvt/frontdoor/intent.py`,
  `src/rvt/frontdoor/manifest.py`, `tools/dev/make_ifc_fixtures.py`,
  `tests/test_ifc_census.py` (new), `tests/ci_shard.txt` (+1 line, last),
  `tests/ifc_conformance/j_census_space_unreadable_body.{ifc,expected.json}` (new),
  `tests/ifc_conformance/{a..i}.expected.json` (census key), `plugin/lib/src/rvt/**` mirrors
  (sync), this record.
* Gates: see the PR body for the pasted counts (with / without ifcopenshell,
  `make_ifc_fixtures.py --check`, `sync_plugin.py --check`, `validate_plugin.py`,
  `check_portable_paths.py`, /verify runs on hardened.ifc + electrical-room-2500a.ifc under
  both backends with `rvt_validate` 0 errors).
* Nothing staged for the viewer; no certification claim; no hot file touched.
