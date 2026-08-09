# rfa-load-product — product-wire the certified any-.rfa load lane (issue #99)

Stream: `rfa-load-product` (engineer session `eng99`, branch `cam/99-route-rfa-load`).
Refs #5 (permutation router), builds on #109 (convert cells registered) and #243
(`→rfa` target-version block). Certified ancestry: **T2a**
(`experiments/rftprobe/T2a.rvt`, ledger) — a Revit-born 1,992-element standalone
`.rfa` famloaded onto composed G_ABPD with a placed instance PASSES.

## What was built

* **`src/rvt/convert/rfa_load.py`** (new, mirrored into the plugin) — the research
  lane's mechanism as product code, zero donor bytes:
  * `RemapDecoder(schema, idmap)` — port of `tools/rft_probe.py:_remap_decoder`: an
    `ObjectDecoder` over the *file's own* schema that substitutes exactly the
    `ElementId`-typed values through `idmap` at decode time (the small-id aliasing
    fix, `docs/inbox/rft-probes.md` finding 3). `Identifier`-typed values are not
    touched.
  * `RfaSource(rfa_path)` — port of `load_rft_elements` split in two phases:
    phase 1 reads the file ONCE under **its own release**
    (`release_ctx.host_release_context(rfa)`; a native file enters no context):
    owner ids from the `Global/ElemTable` stream (standalone ownership law, finding
    2), unit-0 records + class names, `self_family_of_unit` facts (category,
    part type, type names), PartAtom title; phase 2 `build(start_id)` decodes every
    101/102/103 record through the typed remap into the contiguous block
    `start_id..` and wraps the elements in `BornRfaDoc` (port of
    `tools/famdoc_bisect.py:HybridFamilyDoc`: famload's FamilyDoc protocol, segments
    re-encoded by `rvt.famgen.skeleton.build_unit_segments`). `build` IS the
    `builder(start_id)` the four-registry loader calls with `watermark + 1` — T2a's
    allocation law exactly (`template_doc(rfa, wm)` allocated `wm+1..`).
    Types = the REAL-named types (blank `' '` pair skipped, finding 4); current
    type = the first real-named pair; content GUID minted per load.
  * `is_standalone_born(rfa, host)` — the id law that picks the lane: family id floor
    (its ElemTable) vs host watermark (footer `last_id` ∨ max row id, the
    `survey_host` law). Two ElemTable reads, no partition walk (0.0 s).
  * `load_rfa_into_project(rfa, host, out)` — `rvt.famload.load_family_documents`
    with `FamilyLoad(builder=src.build, core_categories=[family category])`, then the
    record: plan ids, rebase census, four-registry census, validator summary.
  * Refused **by name** (`RfaLoadError`, one clear line at the router): GraveyardRec
    ElemTable footer (`graveyard_count != 0`, codec gap #13 — per the issue's
    constraint), nested family documents (>1 save unit), seq-103 classes beyond
    `GElement`/`SerializedDummy`, records that do not decode against the file's own
    schema, a release with no certified creation support (from `release_ctx`).
* **`src/rvt/frontdoor/router.py`** — `_reload_rfa` now runs `rfa-classify` first:
  ids above the watermark → the existing verbatim `rfa-reload` lane
  (`extract_family.reload_family`, **unchanged bytes** — nothing in that path was
  edited); ids at/below → `rfa-born-load` (`rfa_load.load_rfa_into_project`). The
  `_STANDALONE_BORN_LINE` refusal is gone; failures of either lane still end in ONE
  clear line (`_RFA_LANES_LINE`). After delivery the caveat states: standalone-born,
  N ElementId values remapped into block [a, b], the MECHANISM is certified (T2a),
  THIS artifact is not. `_resolve_host(..., opts)` now honours `--target-version`
  when no `--rvt` is given: the default host becomes the certified base *of that
  release* through the front door's one resolver (`_resolve_base_and_version`), the
  load runs under that host's release (famload's `host_release_context`), and
  `res.target_version` carries the block; with an explicit `--rvt` the target is
  reported as ignored (the host's own release rules).
* **`src/rvt/frontdoor/matrix.py`** — stages `rfa-classify`, `rfa-born-load`
  registered; both rfa cells list them; `_RFA_INPUT` form (c) rewritten from
  *clear line* to *loads … mechanism certified (T2a), this lane's artifacts
  needs-viewer*; evidence adds `test:tests/test_rfa_load.py` + this record.
  `verify_evidence()` clean (only the fresh-clone soft marks for absent certified
  binaries).
* **`docs/product/PERMUTATION-MATRIX.md`** — the `rfa → rvt` and `rfa + rvt → rvt`
  rows and the named gap only (gap now = certify this lane's own artifacts).
* **Tests** — `tests/test_rfa_load.py` (new, 9 tests, 11 s, fresh-clone runnable: our
  panelboard `.rfa` from `rvt.famgen.factory.make_panelboard` at `start_id=1000` +
  the plugin-bundled bases; added to `tests/ci_shard.txt`);
  `tests/test_router.py`: `test_standalone_born_rfa_gets_the_clear_line_not_a_traceback`
  → `test_standalone_born_rfa_loads_onto_the_pinned_base` (positive: validator 0
  errors, census coherent, caveat honest), and the full-cycle test's "reload back
  into the source project" now asserts the remap lane loads it (was: refused by name).

## Evidence (numbers)

Reproduction BEFORE (main @ 5a40b22, this VM, the issue's own command):

```
$ .venv/bin/python tools/make_family.py panelboard --out DP-1.rfa      # 1.5 s, VALID 0 errors, provenance ok=True
$ .venv/bin/python tools/route.py run --output rvt --rfa DP-1.rfa --json
  ok=false  route=rfa_load  1.5 s
  steps: rfa-reload ok=false "LoaderError: product ids start at 1000 <= host watermark 1472524: rebuild with start_id=1472525"
  status: UNSUPPORTED-INPUT-FORM (standalone-born .rfa: ids below the host watermark)
```

AFTER (this branch):

```
$ .venv/bin/python tools/route.py run --output rvt --rfa DP-1.rfa --json           # wall 2.5 s (route 2.3 s)
  ok=true  route=rfa_load
  steps: rfa-classify ok 0.0 s "rfa id floor 1000 vs host watermark 1472524: standalone-born -> id-remap lane"
         rfa-born-load ok 2.3 s  (rvt.convert.rfa_load:load_rfa_into_project)
  status: OK (family loaded four-registry via the id-remap lane, standalone-born: host family 1472566,
          symbol 1472583, +18 host elements; project validator VALID 0 errors)
  rebase: 41 elements, 480 ElementId values remapped -> block [1472525, 1472565]; 14 param twins
$ .venv/bin/python tools/rvt_validate.py DP-1_loaded.rvt        -> VALID (no errors); warnings=1 (the base's own DataStorage ES blob)
  detect_release=2026; four_registry_census: coherent=True save_units=2 familymgr=10 ours_in_all_four=True

$ ... --target-version 2025 --json                                                 # wall 2.5 s
  ok=true; target_version.status=match; host = certified Revit 2025 base (sha256 6242c3aaccf8...)
  releases.loaded_rvt=2025; rvt_validate -> VALID (no errors), warnings=0; detect_release=2025; census coherent
$ ... --target-version 2024 --json                                                 # wall 2.8 s
  ok=true; releases.loaded_rvt=2024; validator VALID 0 errors
```

Bare surface (steer #108): `tekton-plugin.zip` unzipped to a temp dir, system
`python3` 3.11, repo NOT on `sys.path`, engine + vendored olefile via
`skills/tekton-author/scripts/_bootstrap.py go <script>`: preflight READY 0.02 s;
the same cell ok=true in **1.9 s** (2026) / **1.8 s** (2025), VALID 0 errors both.

Provenance of the output (`tools/provenance.py --baseline all --streams`): identity
`author='rvt-writer'`, username `''`, no violations; element ledger unbaselined (no
`samples/` in a cloud VM — expected).

Gates: `tests/test_rfa_load.py` 9 passed (10.9 s); `tests/test_router.py
tests/test_frontdoor.py` 112 passed / 8 skipped (48.9 s, includes the built-room
full cycle); `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py`
26 passed; `tools/sync_plugin.py` run + `--check` clean (deny-audit clean);
`plugin/scripts/validate_plugin.py` PASS (24 assertions); `check_portable_paths` ok.

## Findings

1. **The port needed no new format law.** Our `start_id=1000` `.rfa` is exactly the
   species T2a's selftest measured (owners in `Global/ElemTable`, empty inline elem
   table). 480 typed substitutions on 41 elements; owners remapped alongside; zero
   references left into the old block (test asserts it).
2. **Cross-release works through the existing port layer, unplanned but free.** A
   2026-born `.rfa` decoded by its own schema re-encodes under the 2025 and 2024
   host contexts (`build_unit_segments` uses the context-seeded encoder; the port
   layer adapts at the record boundary) and validates 0 errors under each release.
   Reading the `.rfa` happens OUTSIDE the host context on purpose (phase 1), so a
   host of another release never mis-frames the family's partitions.
3. **Reloading an extracted `.rfa` into the project it came from** used to be the
   one by-name refusal of lane (b); it is now simply lane (c) (a second content
   document with a fresh GUID). Revit's own reaction to two same-named families is
   a viewer question, recorded here, not asserted.

## Open questions / follow-ups (filed as issues, `Refs #99`)

* `needs-viewer`: STAGE a batch of this lane's outputs (DP-1 on G_ABPD + byte-identical
  control; then 2025/2024) so form (c) can cite its own ledger entry instead of T2a's.
* A Revit-born multi-type `.rfa` authors one host symbol per real-named type (famload's
  N-type path, as for our own families); T2a certified a single type. Worth one probe in
  the same batch.

## BRANCH STATE

* Branch `cam/99-route-rfa-load` from `main` @ 5a40b22; PR: Closes #99.
* Files written: `src/rvt/convert/rfa_load.py` (new), `src/rvt/frontdoor/router.py`,
  `src/rvt/frontdoor/matrix.py`, `tests/test_rfa_load.py` (new), `tests/test_router.py`,
  `tests/ci_shard.txt`, `docs/product/PERMUTATION-MATRIX.md` (two rows + gap),
  `docs/inbox/rfa-load-product.md`; plugin mirrors regenerated by `tools/sync_plugin.py`
  (`plugin/lib/src/rvt/convert/rfa_load.py`, `.../frontdoor/{router,matrix}.py`).
* Hot files: none touched (`base.py`, `versions/`, `tools/frontdoor.py`, `SKILL.md` untouched).
* Shipped: the product lane + tests + docs. Staged for viewer: nothing (a session
  STAGES only on request; the follow-up issue carries it). Certification claims: none.
