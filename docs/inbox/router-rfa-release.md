# router-rfa-release — the standalone family routes honour `--target-version` (issue #171)

Stream: engineer session `eng171` (cloud, fresh clone: no `samples/`, no
ifcopenshell), 2026-08-09. Territory: `src/rvt/frontdoor/router.py`,
`tests/test_router_release.py` (new), `tests/ci_shard.txt`, the three `→ rfa`
rows of `docs/product/PERMUTATION-MATRIX.md`, this record.

## Problem (measured before the change, main @ 730fe5a)

`tools/route.py run --output rfa --prompt "an electrical room with 2 panels" --target-version N`
ignored `N` on all three family cells (`prompt_to_rfa`, `ifc_to_rfa`,
`spec_to_rfa`): `_families_from_model` / `_r_*_to_rfa` never read
`opts['target_version']`, so the emit always ran at the native release.

```
== before-none (tv=none rc=0 wall=2.6s)  releases= {'rfa:PP-1': 2026, 'rfa:PP-2': 2026}  line=''  target_version=null
== before-2024 (tv=2024 rc=0 wall=2.5s)  releases= {'rfa:PP-1': 2026, 'rfa:PP-2': 2026}  line=''  target_version=null   <- silent 2026 for a 2024 recipient
== before-2025 (tv=2025 rc=0 wall=2.7s)  releases= {'rfa:PP-1': 2026, 'rfa:PP-2': 2026}  line=''  target_version=null   <- silent 2026 for a 2025 recipient
   every families/*.rfa: detect_release == 2026, Formats/Latest sha256 6459a9a9… (the 2026 pin); ROUTE.md never mentions a release
```

## What was built

One runner in `router.py`, **`_emit_at_target(res, opts, out_dir, emit, *, model, source_ifc)`**,
that every standalone family emit goes through (`_families_from_model` for the
three cells, and the product-IFC downlight branch of `ifc_to_rfa`). It adds no
release logic of its own — it composes the existing machinery:

* the year is resolved by the front door's ONE resolver,
  `rvt.frontdoor._resolve_base_and_version` (the issue text calls it
  `_resolve_for_target`; that name does not exist — this is the function the
  rvt routes and PR #173 use), so the `target_version` block in `route.json`
  is byte-for-byte the shape the author manifest carries
  (`requested / status / output_release / line / target_support /
  nearest_supported / supported_targets / …`);
* a certified non-native target (`status == 'match'`, 2025 / 2024) runs the
  emit inside `rvt.frontdoor.release_ctx.release_build_context(base.path)` —
  the same context `build.build_intent` enters (framing ordinals, codec
  singletons, `FORMATS_LATEST_SHA256_PREFIX`, the port layer, the standalone
  donor = that year's bundled certified base); a `release-context` step is
  recorded in `steps` exactly like the build path's stage record;
* an uncertified (2023) / unknown (2027) year is the resolver's own
  `fallback`: the families are DELIVERED by the native emit (rule 1), THE one
  clear line rides as a caveat after delivery, and `_emit_ifc_addition` (reused)
  puts the version-agnostic IFC beside them (prompt: the intent re-emitted;
  ifc/spec: the input/generated IFC copied);
* if the emit itself cannot run at a certified target (a class the older
  schema lacks, no port layer) the context attempt's error becomes the
  `pending` reason, the block degrades to `fallback` with the line, and the
  native emit delivers — never a failure where a file used to be delivered.
  Measured instance: the product-IFC **downlight archetype at 2024** raises
  `KeyError: class 'ArcElemCell' not in the archive class map` (the class is
  absent from the 2024 schema: `'ArcElemCell' in schema.by_name` → 2026 True,
  2025 True, 2024 False) → degraded honestly; room-IFC / prompt / spec
  catalog families (panelboards, switchboard, transformer) build natively at
  2024 and 2025;
* a wrong-release explicit `--base` is `refused` *as a base* by the resolver;
  a family emit needs no base, so the families are delivered native and the
  line says so (interim shim, flagged in the code; see follow-ups);
* no `--target-version` → the native emit untouched (no base is even hashed);
  the block only reports `status: unspecified` + the ask-the-year note;
* `RouteResult` gains `target_version` (the block) and `release_view()` (the
  compact `release` view via `target_status.release_view`, the shape #173's
  `--json` carries); both land in `route.json`; ROUTE.md prints one
  `* target version: requested … -> output Revit … (**status**): <line>` bullet;
  the rvt routes' `_absorb_author_result` now also copies the author
  manifest's block into `res.target_version`, so every route reports one shape.

## Evidence (after, branch head; Python 3.11.15, fresh clone, warm disk)

`prompt → rfa`, "an electrical room with 2 panels" (2 × Eaton PRL2X 225 A):

```
== final-none (tv=none rc=0 wall=3.2s)  status=unspecified  families: release 2026, schema 6459a9a9… pin_match True ×2
== final-2026 (tv=2026 rc=0 wall=2.6s)  status=match        families: release 2026, schema 6459a9a9… pin_match True ×2
== final-2025 (tv=2025 rc=0 wall=2.6s)  status=match        families: release 2025, schema c964f9aa… pin_match True ×2
== final-2024 (tv=2024 rc=0 wall=2.3s)  status=match        families: release 2024, schema 0bfb947b… pin_match True ×2
== final-2023 (tv=2023 rc=0 wall=2.4s)  status=fallback     families: release 2026 (delivered) + prompt_intent.ifc beside
   line: "target 2023 requested: tekton has no certified Revit 2023 creation base (supported: 2024, 2025, 2026); the nearest
          supported target is Revit 2024, which Revit 2023 cannot open either; this file targets 2026 -- your Revit 2023
          cannot open it; the IFC alongside is version-agnostic (links into Revit 2019+)"   (in caveats, route.json, ROUTE.md)
== final-2027 (tv=2027 rc=0 wall=2.6s)  status=fallback     families: release 2026 (delivered) + prompt_intent.ifc beside
   line: "target 2027 requested: tekton has no certified Revit 2027 creation base (supported: 2024, 2025, 2026); this file
          targets 2026 -- your Revit 2027 cannot open it; …"
```

`pin_match` = `schema_of(rfa).stats()['sha256'] == KNOWN_RELEASES[release].schema_sha256`.
Wall time per target is flat (2.3–3.2 s, noise-level; the release context adds
no measurable cost to a 2-family emit) — steer #108.

`ifc → rfa`, `inputs/ifc/electrical-room-2500a.ifc` (steplite reader; 8 catalog families T1/MSB/DP-1,2/LP-1..4):

```
== ifc-2024 (tv=2024 wall=11.0s)  status=match     8/8 release 2024, schema 0bfb947b… pin_match True
== ifc-2025 (tv=2025 wall=10.1s)  status=match     8/8 release 2025, schema c964f9aa… pin_match True
== ifc-2023 (tv=2023 wall= 9.8s)  status=fallback  8/8 release 2026 + electrical-room-2500a.ifc copied beside + the line
```

`ifc → rfa`, PRODUCT IFC (`chicago-plenum-downlight.ifc`) at 2024: the 2024
context is tried, `facts->rfa` raises the `ArcElemCell` KeyError, the block
degrades to `fallback` with that reason in the line, and the native emit runs —
which on this fresh clone then stops on the **pre-existing, flag-independent**
donor gap (`family container source not found … racbasicsamplefamily-2026.rfa`;
identical without `--target-version`; PERMUTATION-MATRIX "next steps" already
names it). Not introduced here.

Validation (`tools/rvt_validate.py --family`): all 36 `.rfa` produced above
(none/2026/2025/2024/2023/2027 prompt ×2, ifc 2024/2025/2023 ×8) → `ok: true`,
0 errors, 0 warnings. Necessary, not sufficient (rule 4): per-release `.rfa`
are validator-gated, not viewer-certified — the matrix rows say so.
Provenance (the per-family emit report `families/*.json`, computed inside the
release context): `provenance ok=True, suspects=0, validate=VALID` for every
2024 / 2025 / 2026 family. `tools/rvt_analyze.py` on a 2024 family: `release
2024 (format 2024, build 20230308_1635(x64)); schema 470502 bytes, release
2024, sha 0bfb947b…`.

`/verify` (router surface): `tools/route.py matrix` → evidence self-audit clean
(21 cells, 20 stages, 5 chains; 38 certified probe binaries absent on a fresh
clone, ledger entries check out); `route run --output rvt --prompt … --target-version 2019`
→ delivered PROOF-ONLY 2026 `.rvt`, and the route JSON now carries the same
`target_version` block on the rvt path too (`status=fallback, requested=2019,
output=2026`, `release.nearest_supported=2024`, the line in caveats).

`spec → rfa` shares `_families_from_model` (same code path; its generated IFC
is the fallback addition) but needs ifcopenshell to author the IFC, so it is
exercised by `tests/test_router.py::test_e2e_spec_to_rfa_chain` on machines
that have it, not on this clone.

## Gates run

* `tests/test_router_release.py` (new, fresh-clone: prompt + steplite room IFC;
  self-skips without the bundled bases / catalog / numpy): **11 passed** in 52 s
  — listed in `tests/ci_shard.txt`.
* `tests/test_router.py`: **65 passed, 11 skipped** (skips = ifcopenshell /
  owner-machine inputs), incl. the PERMUTATION-MATRIX doc-agreement test.
* `tests/test_frontdoor.py tests/test_target_version_first.py
  tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py`:
  **69 passed, 4 skipped**.
* `tools/sync_plugin.py` run (1 file mirrored: `plugin/lib/src/rvt/frontdoor/router.py`),
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS (23 assertions);
  `tools/dev/check_portable_paths.py` ok.

## Findings / follow-ups (out of territory — filed as task issues, `Refs #171`)

1. **The fallback line for a NEWER target is worded for an older one.**
   `_resolve_base_and_version` says "your Revit 2027 cannot open it" for a
   2027 request that receives a 2026 file — a newer Revit *does* open (and
   upgrades) an older file. The rfa routes relay the resolver's line verbatim
   by design, so the fix belongs in `rvt.frontdoor.__init__` /
   `rvt.versions.creation_fallback_line` (a `reason=` / direction-aware
   wording), which would also retire the router's one locally-phrased line
   (the emit-cannot-run degrade).
2. **Port layer 2024: `ArcElemCell`.** The downlight archetype (arc geometry,
   `famgen/geometry.py:1875`) cannot be emitted at 2024 because the class is
   absent from the 2024 schema; `rvt.genesis.port2024` needs the 2024 name /
   shape for arc cells before luminaire families can target 2024.
3. `_r_ifc_family_load` (ifc → rfa → loaded rvt) still resolves its default
   host and emits the family at the native release regardless of
   `--target-version`; threading the year there means resolving the target's
   base as the host + `host_release_context` — an rvt-output cell, separate task.
4. The `refused`-base shim: a `needs_base=False` mode on the resolver would let
   family routes ignore `--base` cleanly instead of re-labelling a refusal.
5. **`tools/make_family.py provenance` is release-unaware.** On ANY Revit-2024
   family — including those the existing `frontdoor author --target-version 2024
   --stages FL` build path emits — it dies with `ValueError: unexpected
   Partitions header: v=9 cls=0x37b` (native framing ordinals on a 2024 file).
   Pre-existing, reproduced on `out/verify/fd24/families/lp1_*.rfa`; the tool
   should enter `release_ctx.host_release_context(path)` like the validator does.
   The in-context emit report proves provenance meanwhile (above).

## BRANCH STATE

* branch `cam/171-rfa-target-version` from main @ 730fe5a; files:
  `src/rvt/frontdoor/router.py`, `plugin/lib/src/rvt/frontdoor/router.py`
  (mirror), `tests/test_router_release.py` (new), `tests/ci_shard.txt`,
  `docs/product/PERMUTATION-MATRIX.md` (the three `→ rfa` rows only),
  `docs/inbox/router-rfa-release.md`.
* gates: as above, all green locally (py3.11); CI shard carries the new file.
* shipped vs staged: code + tests + docs shipped in the PR; nothing STAGED for
  the viewer (per-release `.rfa` remain validator-gated; a viewer round for
  2025/2024 standalone families would be a separate `needs-viewer` task).
