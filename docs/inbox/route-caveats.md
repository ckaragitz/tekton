# route-caveats — build degradations ride into `RouteResult.caveats` (issue #347)

Stream: eng #347 (branch `cam/347-route-caveats`), refs #153 (IFC census), PG1.

## What was built

`rvt.frontdoor.router._absorb_author_result` used to copy only the combination-verdict stamp,
the PROOF-ONLY status and the target-version line out of an absorbed `AuthorResult`; the
author manifest's `build.degradations` (the #153 IFC census line, `W-1 (wall): NOT built …`,
`validation SKIPPED (--no-validate) …`, feeder-circuit / planned-device shortfalls, …) never
reached `RouteResult.caveats`, so `tools/route.py run … --json` printed `ok` + `status` for a
hollow conversion and the *why* lived only in MANIFEST.md.

Now a small helper `_absorb_build_degradations(res, r)` (router.py, called from
`_absorb_author_result` right after the target-version line) appends every
`manifest.build.degradations` entry to `res.caveats`:

* prefixed `build: ` (`router.BUILD_CAVEAT_PREFIX`) so a consumer can tell build shortfalls
  from cell/route caveats;
* order preserved, duplicates dropped (also across the two absorbs of the prompt+ifc
  build-then-edit route);
* capped at 10 lines (`_BUILD_CAVEAT_CAP`) plus one tail
  `build: ... +N more degradation(s), see <out>/MANIFEST.md (build.degradations in manifest.json)`;
* `ok`, `status`, exit codes untouched — labels after delivery (hard rule 1); the caveats land
  in `route.json`, `ROUTE.md` and `RouteResult.as_json()` through the existing writer, so #313's
  ONE-JSON-on-stdout contract is unchanged (stderr stayed 0 bytes on every probe run).

No change to `build.py` / `manifest.py` wording, `matrix.py`, `tools/route.py` or any hot file.

## Evidence (this branch vs `main` @ ec62a06, same machine, plugin-bundled pinned base)

`tools/route.py run --output rvt <input> --out <tmp> --json`, exit code / stderr bytes / caveats:

| probe | exit main → branch | stderr | caveats main → branch | added `build:` lines |
|---|---|---|---|---|
| `--prompt "an electrical room with 2 panels"` | 0 → 0 | 0 → 0 B | 3 → 3, **byte-identical** | none (build.degradations empty) |
| same + `--no-validate` | 0 → 0 | 0 → 0 B | 3 → 4 | `build: validation SKIPPED (--no-validate): this is NOT a shippable run` |
| same + `--stages FL` | 0 → 0 | 0 → 0 B | 3 → 3, byte-identical | none |
| `--ifc tests/ifc_conformance/j_census_space_unreadable_body.ifc` | 0 → 0 | 0 → 0 B | 3 → 6 | `build: W-1 (wall): NOT built …`, `build: CT-1 (conduit_run): NOT built …`, `build: IFC census: 1 of 7 products dropped (IfcSpace×1); 1 of 5 body items unreadable (IfcSweptDiskSolid×1) -- … delivery unchanged …` |
| `--ifc inputs/ifc/electrical-room-2500a.ifc` | 0 | 0 B | 4 `build:` lines (TMGB / CONDUIT / SERVICE / HANGERS NOT built) | **none from the census** (nothing dropped/unreadable) |

`ok` and `status` identical before/after on every probe. `ROUTE.md` lists the `build:` lines
under "caveats (after delivery, per the deliverable rule)".

## Tests

`tests/test_router.py` section 4b (4 new cases):

* three build-free cases drive `R.route({"prompt": …}, "rvt")` with `rvt.frontdoor.author`
  monkeypatched to a fake `AuthorResult` — prefix + dedup + order (cell caveats first) +
  `route.json` / `ROUTE.md` / `as_json()` carry them; the cap + `+N more … MANIFEST.md` tail;
  no degradation → caveats == the cell's caveats exactly;
* one real build on the pinned base (`needs_pin` + `needs_catalog`, ~3 s): the #153 census
  fixture routed with `no_validate=True` → every `build.degradations` entry (incl.
  `validation SKIPPED` and exactly one `IFC census:` line naming `IfcSpace`) rides in
  `res.caveats`, and `route.json`'s caveats == `res.caveats`. (`/simplify` merged the two real
  builds first written into this one.)

Gate counts are in BRANCH STATE.

## Findings / open questions

* The edit route's manifest (`rvt.frontdoor.edit`) has no `build` block, so `--rvt --edit`
  routes gain nothing here — correct today; if edit ever grows its own degradations list it
  should use the same key or this helper needs a second source.
* `_absorb_convert_record` (the rvt.convert cells) already copied `degradations` into caveats,
  unprefixed. Left as is (out of territory; changing its wording would move existing
  `route.json` consumers) — a follow-up could align the prefix.

## BRANCH STATE

* Branch `cam/347-route-caveats` from `main` @ ec62a06. Files: `src/rvt/frontdoor/router.py`
  (`_absorb_build_degradations` + one call line + docstring), `tests/test_router.py` (+5 cases,
  section 4b), `docs/inbox/route-caveats.md` (this), `plugin/lib/src/rvt/frontdoor/router.py`
  (regenerated mirror).
* Gates (this session, this head): `tests/test_router.py -q -rs` → see PR body (main today:
  104 passed / 4 skipped with ifcopenshell; this VM has no ifcopenshell);
  `tests/test_frontdoor.py -q` → see PR body; `tools/sync_plugin.py` then `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py`
  ok (2839 paths).
* Nothing staged for the viewer; no ledger / matrix claim touched. Shipped = the router change
  (rides in the plugin mirror).
