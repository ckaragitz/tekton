# eng #623 — budget refusals are attributed, and a work budget stops the 44 s lattice (2026-08-11)

*Fragment of the `ifc-assembly-rfa` stream (index: `docs/inbox/ifc-assembly-rfa.md`, left untouched),
written by engineer session eng #623 on branch `cam/623-budget-attribution` from `main` @ 1376709.
One PR, one voice; nobody else appends here (docs/inbox/README.md, #636).*

Refs #623 (this task), #583 / #609 (the reviews that found it), #582, PG1 + S-2026-08-09-g.

## The two defects, reproduced on `main` @ 1376709 first

Both come from the #583 merge reviews and both reproduce with the test file's own generators
(`_box_mesh` cubes written through `write_ifc`, `RVT_STEPLITE_FORCE=1`, fresh cloud clone, no `samples/`):

1. **Unattributed refusals.** `decompose_boxes` / `decompose_slabs` answered a bare `None` for every
   refusal, so `read_assembly` had one sentence for all of them. A 9 × 9 × 9 lattice of 100 mm cubes
   (one product, 729 shells) is refused by the box lane on a *budget* and by the slab lane on a
   *budget*, and `kept_prism` / the route caveat said:
   `not decomposable into horizontal slabs (an ambiguous slice, one Z level, or over the part budget)
   -- its section most likely runs along X or Y, which the Z-extruded part contract cannot express`.
   Wrong reason; the box lane's refusal was not mentioned at all.
2. **No work budget.** The grid pass costs `cells × triangles` solid-angle evaluations (~1 µs each
   here). `MAX_GRID_CELLS = 20000` let the 9³ lattice in (17³ = **4913 cells**) with **8748
   triangles** = 4.3e7 evaluations: **43.7 s** in `read_assembly`, **45.5 s** through
   `route.py run`, to be refused on the *box* budget afterwards and ship the very prism `main`
   ships anyway. (The 15³ lattice, 29³ = 24389 cells, was already refused by the cell budget: 5.5 s,
   4 s of it the slab lane nesting 225 rings in each of 15 slabs before refusing on the part budget.)

## What was built (territory: `assembly_parts.py` plumbing + the budget; nothing geometric)

* **`refusal: Optional[List[str]] = None`** on `decompose_boxes` and `decompose_slabs`, and one
  helper `_refuse(refusal, reason)` that every former `return None` goes through. The return
  contract is unchanged — refused is still `None`, so `is None` keeps its meaning and the existing
  tests (`max_boxes=1 … is None`, the `monkeypatch` of `AP.decompose_boxes` with `**kw`) run
  untouched; a caller that passes a list gets the reason. Reasons, box lane: `no readable
  triangles` · `not axis-aligned (…)` · `flat vertex grid` · `cell budget (i x j x k = N grid cells,
  over the M allowed)` · `work budget (N grid cells x T triangles = W inside-tests, over the B
  allowed)` · `no grid cell lies inside the body` · `box budget (more than M merged boxes)` ·
  `sliver box (w x d x h in, thinner than the 0.016 in a solid needs)`. Slab lane: `no readable
  triangles` · `one Z level (…)` · `slab budget (N Z slabs, over the M allowed)` · `ambiguous slice
  at z = … ft (regions touch at a point or an edge; the ring set is not guessed)` · `part budget (N
  solids by the slab at z = … ft, over the M allowed)` · `no slab held a solid ring`.
* **`read_assembly`** collects each lane's reason in order (`box lane: …`, `slab lane: …`), words
  the two checks that are the caller's own — the box lane's exactness law becomes `box lane: volume
  mismatch (n boxes X in3 + overlap Y in3 vs Z in3 in the mesh, off by more than 1e-06 of it)`,
  the slab post-checks keep their `dropped material` / `no closer than the single prism` wording
  behind a `slab lane:` prefix — and writes ONE `kept_prism` entry per product joined with
  `, then ` (the router already joins products with `;`). A box-lane refusal followed by a slab-lane
  success is, as before, not a kept prism and says nothing. `router.py` is **not touched**: its
  caveat line relays `kept_prism[*].reason` verbatim, so the attribution surfaces there by itself.
* **`MAX_GRID_WORK = 4_000_000`** (`cells × triangles`), checked in `decompose_boxes` right after
  the cell budget and *before a single inside-test runs*; over budget → `work budget (…)` → the slab
  lane → the prism, delivered (rule 1). Why 4e6: ~1 µs per evaluation on this VM caps the pass near
  4 s per product (the cell budget alone allowed 20000 × 8748 ≈ 175 s); the largest exact body on
  record, the desktop-verified slotted P1000 strut, is 555 cells, so even at a few thousand
  triangles it keeps ~5× headroom; every reference row below is orders of magnitude under it
  (the unyawed strut: 6 cells × 36 triangles).
* **The slab lane stops sooner on the part budget** — the one place "where it applies". The merge of
  identical neighbouring sections was already a streaming comparison against the last merged
  section; it now runs inside the slicing loop (same condition, same `_same_section`, same 1e-9
  adjacency, `raw` list gone), so the merged solid count is known as it grows — and it only grows —
  and the lane refuses at the slab that crosses `max_parts` instead of slicing and nesting every
  remaining slab first (`/simplify` folded my first per-slab special case into this one exit).
  Same verdict on exactly the same bodies, and where it succeeds the authored parts are unchanged:
  `to_parts()` + the `decomposed` records of all 13 bench IFCs below are **byte-identical** to
  `main`'s (`cmp` of the JSON dumps). The 15³ lattice's slab lane drops from 15 nested slabs to 1.

No acceptance tolerance, no ring nesting, no `fit_solid`, no lane geometry changed; `route.py`,
famgen, SKILL.md, `tests/test_ifc_assembly.py` and every hot file untouched.

## Evidence (this VM: cloud session, 4 vCPU, CPython 3.11.15, `RVT_STEPLITE_FORCE=1`)

**Lattices, `read_assembly` wall time and the reason** (`bench623.py`, same IFC bytes both trees):

| body | cells × triangles | main @ 1376709 | this branch |
|---|---|---|---|
| 9³ × 100 mm cubes, one product | 4913 × 8748 = 4.3e7 | **43.73 s**, 1 prism (box, fill 0.15); reason: `not decomposable into horizontal slabs (…) -- its section most likely runs along X or Y (…)` | **0.28 s**, the same prism; reason: `box lane: work budget (4913 grid cells x 8748 triangles = 4.3e+07 inside-tests, over the 4.0e+06 allowed), then slab lane: part budget (81 solids by the slab at z = 0.1640 ft, over the 40 allowed)` |
| 15³ | 24389 × 40500 | **5.50 s**, 1 prism; same catch-all sentence | **1.24 s**, the same prism; `box lane: cell budget (29 x 29 x 29 = 24389 grid cells, over the 20000 allowed), then slab lane: part budget (225 solids by the slab at z = 0.1640 ft, over the 40 allowed)` |

**Through the router** (`tools/route.py run --ifc lattice9.ifc --output rfa --out D --json`):

| | main @ 1376709 | this branch |
|---|---|---|
| wall (`time`), 9³ · 15³ | **45.5 s** · 9.4 s | **1.8 s** · 5.0 s |
| status | `OK (1-part generic_model .rfa measured from lattice9.ifc) by the ASSEMBLY lane, after the archetype lane failed at facts->rfa` | identical |
| caveat | `kept as a single prism (the decomposition was refused, never silently accepted): Lattice9 -- not decomposable into horizontal slabs (an ambiguous slice, one Z level, or over the part budget) -- its section most likely runs along X or Y, which the Z-extruded part contract cannot express` | `kept as a single prism (the decomposition was refused, never silently accepted): Lattice9 -- box lane: work budget (4913 grid cells x 8748 triangles = 4.3e+07 inside-tests, over the 4.0e+06 allowed), then slab lane: part budget (81 solids by the slab at z = 0.1640 ft, over the 40 allowed)` |
| output | `T.rfa` | `T.rfa`: `rvt_validate --family` **VALID (no errors), warnings 0**; `make_family.py provenance` **ok, findings []** — a fact about the file, not about Revit (rule 4); nothing certified, ledger untouched |

`route.py matrix` sha256 `7dae5d40…a25d9c1` on both trees (byte-identical).

**Reference rows from the #583/#609/#620/#621 reviews, re-measured on both trees** (`read_assembly`
on the test file's generators; parts, lane, authored ÷ mesh):

| body | main @ 1376709 | this branch |
|---|---|---|
| 900 mm strut 0.0° | 3 boxes (exact), 1.0000000 | identical |
| strut 0.2° · 0.8° | 3 slabs 1.0000061 · 3 slabs 1.0000636 | identical |
| strut with a 50 µm flange mismatch, 0° · 12° | 3 boxes 1.0000000 · 3 slabs 0.9996223 | identical |
| 8-band reducer frustum · 12-band cone | 8 slabs 0.9994424 · 12 slabs 0.9982872 | identical |
| 35 mm plate + 6 mm² pin, 7° | 1 slab (pin sliver dropped) 0.9878939 | identical |
| 70-plate rail, 10° | 1 prism (polygon 0.99, no lane attempted) 1.0101039 | identical |
| corner pair (−3.5, 3.5, 5°) × 41 triangle orders | 41 × 3 slabs 0.9999999, no kept_prism | identical |
| face pair `_FACE_PAIRS[0]` × 41 orders | 41 × 3 slabs 1.0000000, no kept_prism | identical |

`kept_prism` for every reference row: `[]` on both trees (none of them is a refusal, so no wording
moved under them); and `to_parts()` + `decomposed` for these 11 IFCs plus the two lattices dumped to
JSON on both trees compare **byte-identical** (`cmp`).

**Tests.** New module `tests/test_ifc_assembly_623.py` (8 tests, 3.0 s) + drop-in
`tests/ci_shard.d/623-budget-attribution.txt`: the 9³ lattice ⇒ one delivered prism whose reason
starts `box lane: work budget (4913 grid cells x 8748 triangles` and names `slab lane: part budget
(81 solids by the slab at`, read under a **10 s** ceiling (0.3 s measured; generous for slow CI VMs); the work
budget is the product it prints and, lifted, the same body is only over the *box* budget; the route
caveat carries both lanes' reasons and never the old sentence; every box-lane and slab-lane refusal
names itself while the bare call still returns `None`; `volume mismatch` reaches `kept_prism` only
when the slab lane refuses too; a yawed strut the slab lane rescues reports nothing (control); the
flush lug names both lanes and still says `ambiguous slice`. Against `main`'s engine the 4
attribution tests fail by behaviour, the control passes, and the 3 lattice tests are the 44 s /
old-wording case measured above. `tests/test_ifc_assembly.py` **untouched, 96 passed**.

## BRANCH STATE (eng #623)

Branch `cam/623-budget-attribution` from `main` @ 1376709; one issue, one PR (`Closes #623`).
Files: `src/rvt/ifc/assembly_parts.py` (+ its `plugin/lib` mirror via `tools/sync_plugin.py`),
`tests/test_ifc_assembly_623.py` (new), `tests/ci_shard.d/623-budget-attribution.txt` (new), this
fragment (new; the index `docs/inbox/ifc-assembly-rfa.md` is not edited). Not touched:
`src/rvt/frontdoor/router.py` (no hunk needed — the caveat relays the reason), famgen, `tools/route.py`,
SKILL.md, `tests/test_ifc_assembly.py`, any hot file.

Gates on the final tree:
* `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly_623.py tests/test_ifc_assembly.py
  tests/test_router.py tests/test_records_layout.py -q -rs`: main **232 passed / 14 skipped** (without the
  new module) → branch **240 passed / 14 skipped**, 0 failed (skips: 13 × `RVT_SKIP_LARGE`/ifcopenshell-absent,
  1 × chmod-as-root).
* Whole merged CI shard (`pytest -q -p no:cacheprovider $(tools/dev/shard_list.py --print)`): see the PR body
  for the count on the final head.
* `tools/sync_plugin.py` synced 1 file → `--check` clean (deny-audit clean, identity scan == allowlist);
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok;
  `tools/dev/shard_list.py --print | grep -c test_ifc_assembly_623` → 1; `tests/test_plugin_sync.py` 9 passed.
* `/simplify` run on the diff (applied: streamed slab merge = one part-budget exit, dead fallback dropped, reason
  prose trimmed, test table normalised; skipped as out of territory: lifting fixtures into the shared test file,
  an O(columns × T) sweep that would make the work budget moot). `/verify`: `route.py run --output rfa` on the
  9³ lattice, the 15³ lattice and the 0.2° strut → 3 × OK, **1.8 s / 5.0 s / 0.8 s** wall (main 45.5 s / 9.4 s),
  caveats as in the tables above (`box lane: work budget …` / `box lane: cell budget …` / `slab decomposition
  improved Strut (3 solids, fill 0.18 -> 1.00)`), 3 × `rvt_validate --family` VALID 0 errors 0 warnings, 3 ×
  provenance ok `[]`.

Shipped vs staged: engine + tests shipped on the branch; nothing staged for the viewer, no ledger entry,
no certification claimed. No follow-up issue needed from this change; the budget value is a documented
constant (`MAX_GRID_WORK`) with its own reason string, so a future owner-machine re-run of the P1000
hanger that ever trips it will say so in the caveat rather than silently losing the exact lane.
