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

`spec → rfa` shares `_families_from_model` (same call, same `opts`); its
generated IFC is the fallback addition. Authoring that IFC needs the real
ifcopenshell (optional `ifc` extra), so its per-release cases in
`tests/test_router_release.py::test_spec_to_rfa_honours_the_target_too`
self-skip on the CI shard and ran here (this venv has ifcopenshell 0.8.5):
`usecases/chicago-plenum-electrical-room/room-spec.json` at 2024 → 9/9
families release 2024, schema `0bfb947b…` pin_match True (11.1 s); at 2023 →
`fallback`, 9/9 native + `room-spec.ifc` beside + the line (11.5 s).

Correction after the first CI run (py3.11/py3.12 red on head 1ce5475): this
venv turned out to carry the real ifcopenshell, so the "steplite-readable"
room-IFC cases had never actually run through steplite; on CI (no
ifcopenshell) they failed with `IntentError: ifcopenshell is required to read
IFC` because only the plugin bootstrap (`tekton_env.ensure_engine`) appends the
`rvt/ifc/_ifcos_shim` fallback to `sys.path`. The test module now applies the
bootstrap's exact rule (real lib absent → append the shim); re-proven in a
scratch venv **without** ifcopenshell: 11 passed (58.8 s), IFC cases through
steplite. (The repo CLIs `tools/route.py` / `tools/frontdoor.py` themselves
still need ifcopenshell or a manual shim path for `--ifc` on a bare repo clone
— the plugin surface does not; that is #133's fresh-clone territory, not new.)

## Gates run

* `tests/test_router_release.py` (new, fresh-clone: prompt + steplite room IFC
  + refused-base; the two spec cases self-skip without the real ifcopenshell;
  the module self-skips without the bundled bases / catalog): CI-shaped venv
  without ifcopenshell → **12 passed, 2 skipped** (57 s); dev venv with
  ifcopenshell → **14 passed** — listed in `tests/ci_shard.txt`.
* `tests/test_router.py`: **65 passed, 11 skipped** (skips = ifcopenshell /
  owner-machine inputs), incl. the PERMUTATION-MATRIX doc-agreement test.
* `tests/test_frontdoor.py tests/test_target_version_first.py
  tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py`:
  **69 passed, 4 skipped**.
* `tools/sync_plugin.py` run (1 file mirrored: `plugin/lib/src/rvt/frontdoor/router.py`),
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS (23 assertions);
  `tools/dev/check_portable_paths.py` ok.

## Findings / follow-ups (out of territory — tracked as task issues, `Refs #171`)

Issue map: 1 → already #172; 2 → filed **#241**; 3 → filed **#242**; 4 → noted
in #242's territory (resolver mode) rather than a separate issue; 5 → already #94.

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

---

## eng #242 — 2026-08-10: the family LOAD routes honour `--target-version` too (issue #242)

Stream: engineer session `eng242` (cloud, fresh clone: no `samples/`, no viewer;
this venv has ifcopenshell 0.8.5 + numpy), started by the tech-lead session.
Territory: `src/rvt/frontdoor/router.py` (`_resolve_host`, `_r_rfa_load`,
`_r_ifc_family_load`, `_emit_at_target`), `src/rvt/frontdoor/matrix.py` (the two
rfa→rvt cells' caveat + evidence, the `ifc->rfa->loaded-rvt` chain note),
`tests/test_router_load_release.py` (new, CI shard drop-in
`tests/ci_shard.d/242-router-load-release.txt`), one assertion in
`tests/test_rfa_load.py` that pinned the behaviour this issue replaces,
`docs/product/PERMUTATION-MATRIX.md` (rfa → rvt, rfa + rvt → rvt, the chain row),
this section. Nothing under `src/rvt/versions/`, `famload.py`, `tools/frontdoor.py`.

### What was already true on main @ 2b87024 (measured, not assumed)

Follow-up 3 above was written against 730fe5a. Since then #351 (famspec
contract) routed `_resolve_host` through `_target_base` — the memoised call to
the front door's ONE resolver (`rvt.frontdoor._resolve_base_and_version`) that
`_emit_at_target` uses. So on today's main, with **no `--rvt`**:

| command (fresh clone, `--json`, exit 0 each) | `.rfa` | loaded `.rvt` | `target_version.status` | project validator |
|---|---|---|---|---|
| `route.py run --output rvt --rfa spec/examples/famspec-panelboard.json` | 2026 | 2026 | `unspecified` (+ ask-the-year note) | VALID 0 errors |
| `… --target-version 2025` | **2025** | **2025** | `match` | VALID 0 errors (2.6 s) |
| `… --target-version 2024` | **2024** | **2024** | `match` | VALID 0 errors (2.5 s) |
| `… --target-version 2023` / `2027` | 2026 | 2026 | `fallback` + THE line in caveats | VALID 0 errors |
| luminaire / device / transformer famspec `--target-version 2024` | 2024 | 2024 | `match` | VALID 0 errors |
| standalone-born `.rfa` PATH (2026-born, and 2025-born) `--target-version 2025` | — | **2025** (id-remap lane) | `match` | VALID 0 errors |

(`rvt.versions.detect_release` on every file; four registries coherent per the
load report.) That half of the DONE needed pinning, not building.

### What was NOT true, and is now

1. **`--rvt` given: the block described the wrong file.** `_resolve_host` only
   appended "`--target-version N ignored for the LOAD`"; `route.json.target_version`
   stayed whatever the `.rfa` emit had set. Measured on a Revit-2025 host
   (a famspec loaded onto G_ABPD_2025): `--target-version 2024` → block
   `match / output_release 2024` while the delivered `loaded_rvt` is **2025**; no
   flag → block `unspecified / output_release 2026` over a 2025 deliverable. PG1
   violation (the honest table claimed a release the primary deliverable is not).
   **Now** `_host_version_block` states the LOAD's story with the edit route's own
   block builder (`rvt.frontdoor._rvt_route_version_block`, reused — the host's
   release auto-detected via `rvt.versions.detect_release`, worded for a load):
   `detected` (no flag) / `match` / `match-older` / `fallback` + THE line
   ("target 2024 requested: the --rvt route preserves the input file's release
   (Revit 2025) -- your Revit 2024 cannot open the loaded output either; supply a
   Revit 2024 input file to get a Revit-openable load"), `input_release` +
   `output_release` = the host's year, the line/note in caveats, and the `.rfa`
   emitted beside it keeps its own resolver block under `target_version.rfa`
   (ROUTE.md prints both lines). Measured after: host 2025 × flag {none, 2024,
   2025, 2026} → `detected / fallback / match / match-older`, `releases ==
   {rfa: flag-or-2026, loaded_rvt: 2025}`, validator 0 errors each, `release`
   view relays `input_release` + the line verbatim.
2. **The ifc → rfa → loaded-rvt chain (`--via family`) emitted natively and said
   nothing.** `_r_ifc_family_load` called `_product_rfa` bare; with
   `--target-version 2025` the route JSON carried `target_version: null`.
   **Now** `_product_rfa` itself runs its compose + emit through `_emit_at_target`
   (`source_ifc=` for the fallback IFC copy) for both of its callers — the
   ifc → rfa product branch and this chain — with the release-independent
   `ifc->facts` measurement hoisted out of the retried thunk (measured once, was
   twice on a degrade; the load's builder reuses those facts instead of
   re-parsing the IFC per call), and the load host comes from `_resolve_host` →
   the memoised `_target_base` (one resolver call, one block, stated once).
   Fresh clone, `--target-version 2025`: `ifc->facts` once, the 2025 base
   resolved, the Revit-2025 release context entered (`release-context` step,
   release 2025), `facts->rfa` runs in it, and `rfa-emit` then stops on the
   **pre-existing, flag-independent** container
   gap (`family container source not found … racbasicsamplefamily-2026.rfa`,
   #94 — identical without the flag, exit 3 both before and after); the block is
   stated (`requested 2025`, degrade reason named verbatim), no traceback. The
   end-to-end proof at 2025 (rfa + loaded rvt both 2025, VALID) needs the family
   container archetype on disk → owner machine; the test's full branch runs there
   and self-selects the fresh-clone branch here. Not claimed beyond that.
3. **A degraded emit left the load host on the wrong release.** When
   `_emit_at_target` degrades a certified year to native (a class the older
   schema lacks — the ArcElemCell-at-2024 case above), it rewrote the block to
   `fallback / 2026` but the memo still held the *target's* base, so a following
   load would host on the 2024 base under a block saying 2026 (and rebuild the
   family under the very release it had just failed at). **Now** the degrade
   branch re-points the memo at the default base through the same resolver
   (`_resolve(res, opts, label, None)` — the router's single call site of
   `_resolve_base_and_version`, factored out of `_target_base`), so block, `.rfa`
   and host name ONE release. Proven with a synthetic single-variable failure
   (`famspec.write` raising only inside the 2024 context): delivered, both files
   2026, `fallback` + the reason in the line, host caveat names the 2026 base.
4. The two carry-along review nits from #243 on `_emit_at_target` (docstring: the
   IFC addition rides only on `fallback`; the dead `base is not None` condition)
   are folded in as posted on the issue.

### Evidence a reviewer reproduces as nobody (fresh clone, bundled bases)

```
tools/route.py run --output rvt --rfa spec/examples/famspec-panelboard.json --target-version 2025 --out X --json
tools/route.py run --output rvt --rfa spec/examples/famspec-panelboard.json --target-version 2024 --out Y --json
```
→ exit 0, ONE JSON document on stdout, `releases == {"rfa": N, "loaded_rvt": N}`,
`target_version.status == "match"`, status `OK (family loaded four-registry;
project validates 0 errors)`, load report `registries.coherent` +
`ours_in_all_four` true. `--target-version 2023` → exit 0, both files 2026,
`status == "fallback"`, the line in `caveats` and ROUTE.md. Add
`--rvt <a Revit-2025 .rvt>` → `status == "fallback"` for 2024 with the line,
`detected` with no flag. `--ifc inputs/ifc/chicago-plenum-downlight.ifc --output rvt --via family --target-version 2025`
→ `steps[0] == release-context (2025)`, block requested 2025, then the #94
container stop (exit 3, as on main). No flag → the same result as main
(compared field by field: status, releases `{rfa: 2026, loaded_rvt: 2026}`,
block, steps, stamps identical; the one addition is the matrix cell's new
PER RELEASE caveat line), and with `--rvt` the new host-release caveat replaces
"ignored for the LOAD".

### Gates run (this session, py3.11)

* `tests/test_router_load_release.py` (new): **21 passed** (54 s) — 8 famspec
  kind×year loads, 2 `.rfa`-path loads, 2 uncertified years, 5 explicit-host
  cases, the degrade consistency case, the no-flag case, the chain case
  (fresh-clone branch), the CLI case.
* `tests/test_router.py tests/test_router_release.py tests/test_rfa_load.py`
  (`RVT_SKIP_LARGE=1`): **132 passed, 12 skipped** (122 + 10) (skips = `@slow` large cases +
  one root-chmod case), after updating the one `test_rfa_load.py` assertion that
  pinned "ignored for the LOAD" to the new stated-not-ignored contract.
* `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py`: **28 passed**.
* `tools/sync_plugin.py` (2 files mirrored: `plugin/lib/src/rvt/frontdoor/{router,matrix}.py`),
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok; `tools/route.py matrix` evidence
  self-audit clean (21 cells, 23 stages, 5 chains).

### Follow-ups (out of territory; searched, then filed/noted)

* `rvt.frontdoor._rvt_route_version_block(target, in_rel)` words its note/line for
  an *edit* ("edited output", "Revit-openable edit", "the edit preserves"); the
  router rewrites those phrases for a load. A `verb=` keyword on the builder
  would retire the string surgery — filed as **#419** (`Refs #242`), a 4-line
  change in `src/rvt/frontdoor/__init__.py`:
  ```diff
  -def _rvt_route_version_block(target: Optional[int], in_rel: Optional[int]) -> Dict[str, Any]:
  +def _rvt_route_version_block(target: Optional[int], in_rel: Optional[int], *,
  +                             verb: str = "edit") -> Dict[str, Any]:
  ...  f"the {verb}ed output stays Revit {in_rel}" / f"a Revit-openable {verb}"
  ```
* `_emit_at_target`'s degrade line attributes ANY in-context emit failure to the
  release ("this family emit cannot run at Revit 2025 yet (<reason>)"); on a
  fresh clone the product-IFC chain's reason is the #94 container gap, which is
  not release-related. The reason is quoted verbatim so nothing is hidden, and
  #94 removes the case; noted rather than filed.
* `/simplify` pass (4 reviewers) applied: `_resolve` factored so the resolver has
  one call site; `_product_rfa` owns its `_emit_at_target` wrap (no duplicated
  wrapper at two call sites) with facts hoisted; the `"input_release" not in`
  sniff and a redundant `int()` dropped from `_host_version_block`; an unused
  test marker removed, two forked tests made straight-line. Skipped with reason:
  a first-class `RouteResult` field for the `.rfa` sub-block (nesting keeps ONE
  serialised block; the manifest/`release` view need no new key), dropping the
  `"edit" not in line` assertions (they guard exactly the user-visible wording
  this change promises), and folding the `match-older` case into a pure-function
  check (it is the end-to-end proof that the flag reaches the host block; ~3 s).

### BRANCH STATE

* branch `cam/242-router-load-release` from main @ 2b87024; files:
  `src/rvt/frontdoor/router.py`, `src/rvt/frontdoor/matrix.py`, their
  `plugin/lib/` mirrors, `tests/test_router_load_release.py` (new),
  `tests/ci_shard.d/242-router-load-release.txt` (new), `tests/test_rfa_load.py`
  (one test renamed/re-asserted), `docs/product/PERMUTATION-MATRIX.md` (three
  rows), `docs/inbox/router-rfa-release.md` (this section).
* gates: as above, all green locally; the new file is in the CI shard.
* shipped vs staged: code + tests + docs in the PR; nothing STAGED for the
  viewer — per-release loads stay validator-gated, the matrix says so.
