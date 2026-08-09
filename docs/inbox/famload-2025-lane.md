# FAMLOAD-2025-LANE — load / place / edit on an EXISTING Revit-2025 file (issue #14, gap B)

Stream: **famload-2025-lane** (2026-08-09, cloud engineer session fanned out
by the tech-lead session under steers #58/#61; program objective O5).
Charter = issue #14: port family loading + placement to native 2025 framing;
DONE = load + place on `G_ABPD_2025` validates 0 errors under its own
release, `tests/test_target2025.py` gains the family/instance finish line, a
viewer batch STAGED (control = byte-identical `G_ABPD_2025`), no upload.
(The issue names the record `docs/inbox/famload-2025.md`; the lead's brief
named it `famload-2025-lane.md` — this file is that record.)

**DONE state: gap B closed for every lane that operates on an existing 2025
file; the four lanes run BARE on the certified 2025 base and chain
(load → add → move); every output validates VALID / 0 errors with the
standalone release-aware validator (which no longer false-fires E1 on 2025
loaded content); 8 new fresh-clone tests + the family/instance finish line
green and in the CI shard; batch 56 STAGED through the gate (control md5 ==
batch 35's certified control); nothing uploaded.**

---

## 0. What "gap B" precisely was (stated before any code changed)

`docs/inbox/compose-2025.md` §6 named three build-path gaps; build-2025
(`docs/inbox/build-2025.md`) closed all three **for the front door's own
build** by writing `rvt.frontdoor.release_ctx.release_build_context(base)`
and entering it from `build_intent`. That context is keyed on the BASE the
front door resolved. Measured in this fresh clone on `origin/main` af59d26:

| lane on a 2025 file | entry | before this stream |
|---|---|---|
| `author --prompt … --target-version 2025` (build on the 2025 base) | `build_intent` → famgen.loader inside the build context | **works** (batch 35: walls PASS / full-room FAIL = residual) |
| prompt + the user's 2025 project → 2025 (`rvt.convert.add_to_project`, the field workflow) | `resolve_target` → `Document.from_file` | **dies**: `ValueError: unexpected Partitions header: v=9 cls=0x391` |
| `--rvt <2025 file> --edit "move DP-1 …"` (the CRUD entrypoint every 2025 manifest prints) | `_route_rvt` → `Document.from_file` | **dies**, same error (`FAILED (edit did not complete: rc None)`) |
| `rvt.famload.load_family_document(<2025 host>, …)` (four-registry loader; rfa→rvt, rfa+rvt→rvt, ifc→rvt via family, `selfcontained.py build_u16g_on`) | `survey_host` → `Document.from_file` | **dies**, same error (selfcontained §4's measured blocker) |
| `rvt.famgen.loader.load_family_into_project(<2025 host>, …)` called bare | `survey_host` | **dies**, same error |
| `tools/rvt_validate.py <any 2025 file with loaded content>` (release-aware since #51) | `_check_loaded_content` | **false ERROR** `FOUR-REGISTRY INCOHERENCE: save units 1 / ContentDocuments 0 / ContentTable 0 / FamilyMgr 0` — including on the shipped `author --target-version 2025` panel output |
| `tools/provenance.py <any 2025 file>` (the P0 gate instrument) | `Document.from_file` | **dies**, same framing error |

So gap B = **release activation keyed on the HOST**: the mechanism existed,
nothing that starts from an existing file entered it, and two instruments
that judge files read a 2025 file's Global streams with 2026 tokens.

## 1. What was built

* **`src/rvt/global_framing.py` (NEW, engine leaf).** The three Global-stream
  byte tokens that are class ordinals but live as pre-packed constants
  `versions.reading` cannot reach — `factory.CD_SEPARATOR` /
  `CD_END_RECORD` (ContentMarker/ContentKey), `famdoc_adoc.FAMILY_END_RECORD`,
  `genesis.skeleton.EMPTY_CONTENT_DOCUMENTS` — derived from the ordinals in
  force (`tokens()`), bound + restored LIFO (`bound(ords, schema=)`, which
  also binds `adocument._DECODER` to the file's schema),
  `reading(path)` = `records32.reading32` (own framing + the 32-bit id
  layer for ≤ 2023) + `bound` against the file's own schema (strict), and
  `enter_own_release(stack, path)` — the lenient instrument ladder (own
  schema → the pinned table of the release BFI declares → native, returns
  the rung, never raises) that used to live privately in `rvt.validate`
  and now serves the validator, the census and provenance alike; plus a
  4-entry `schema_of` LRU keyed (path, size, mtime) because a census /
  provenance run enters `reading` several times per file (~0.1 s a parse).
  This is the read-side context every instrument that looks at a file's
  Global streams enters; the write-side context composes it.
* **`rvt.frontdoor.release_ctx` (territory) — the host-keyed entry.**
  `release_build_context(base)` and the new `host_release_context(host)`
  are two doors onto one `_release_context(path, host=)`:
  - keyed on ANY existing file's detected release; native → no-op;
    uncertified → `ReleaseContextError` naming the piece;
  - **re-entrant**: a same-release context already active is *joined*
    (yields the outer info), so the loaders — now entering it themselves —
    cost nothing inside `build_intent`; a *different* release inside an
    active one is refused (one release per process scope);
  - **the donor rule**: for a host lane the family CONTAINER donor and the
    standalone "active base" are OUR bundled pinned+certified base of the
    host's release (`resolve_base(target_release=year)`), never the user's
    file (rule 3), and the fresh-document identity strings are read from
    that donor, never from a user's host (rule 6). For a build the donor is
    the build base, as before (same file for `--target-version 2025`);
  - the Global-stream tokens + ADocument decoder now come from
    `global_framing.bound` instead of hand-rolled swaps (one source), and
    the base's schema parse is the shared cached one;
  - `enter_host_release(stack, path) -> Optional[note]` — the one "enter,
    or record why not and let the lane's own guard refuse" helper the
    survey/edit entries share; `_ACTIVE` holds the single info dict
    (`active_release()` derives from it); info gains `keyed_on / path /
    base_note` (`base` = our donor base, `path` = the keyed file).
* **Entry hooks (each = "public function enters the host context, body moved
  verbatim to `_…inner`", the build-2025 pattern):**
  `rvt.famload.load_family_documents`, `rvt.famgen.loader.load_family_into_project`,
  `rvt.convert.add_to_project.resolve_target` + `build_into_target` (so
  `add_to_project()`, `merge_ifc` and the CLI inherit it; an unsupported
  release still gets the honest `ConvertError`, never a guessed framing),
  `rvt.frontdoor._route_rvt` (a context refusal is attached to the
  open/plan error, never fatal on its own — an undetectable-release file
  behaves exactly as before).
* **Instruments made release-true:** `rvt.famload.four_registry_census`
  reads under `enter_own_release` (every caller — the registry gate in
  ifc_intent, famload/famgen verify, tools — gets counts, not a mis-parse;
  a fallback rung surfaces as `release_note`); `rvt.validate.
  enter_own_release` delegates to the shared ladder (so `validate_file` /
  `tools/rvt_analyze.py` also bind the tokens + decoder) and
  `_check_loaded_content` additionally runs E1/E2 under
  `bound(schema=dec.schema)` so the rule is self-sufficient however the
  `Validator` is driven; `rvt.provenance.reading_own_release` (public) wraps
  `embedded_units` / `content_units` and `tools/provenance.py` opens
  candidate + baselines through it (the P0 instrument now RUNS on 2025
  files instead of crashing).
* **Tests:** `tests/test_famload_2025.py` (NEW, 8, fresh-clone runnable on
  the bundled bases) and `tests/test_target2025.py::
  test_END_STATE_2025_family_and_instance_lane` (the DONE's finish line,
  gated on the *bundled* base so it runs in CI — the pre-existing finish
  line keys on the git-ignored compose path and skips in every fresh
  clone). Both files added to `tests/ci_shard.txt`.
* **The lane driver:** `experiments/frontdoor2025/famload_lane.py`
  (`build` / `stage` / `all`) + three `probes.json` entries.

## 2. Evidence (numbers)

All on `plugin/assets/genesis/G_ABPD_2025.rvt` (sha256 `6242c3aa…`, the
registry `releases.2025` pin, ledger-certified), every lane called BARE:

| probe | lane | bytes | md5 (this VM) | five-gate | census after |
|---|---|--:|---|---|---|
| `FL25_head` | `rvt.famload.load_family_document` (RW Section Head – Open) | 602,112 | `8d87c53a…` | **G1–G5 PASS** | 2 / 1 / 1 / FM 10, coherent, host linkage ok |
| `L25_panel_noinst` | `rvt.famgen.loader.load_family_into_project(place=False)` (Eaton 400 A) | 610,304 | `4992993f…` | **G1–G5 PASS** | 2 / 1 / 1 / FM 10, coherent |
| `ATP25_lp1` | `rvt.convert.add_to_project("add a 100 A lighting panel")` — 1 family loaded + **1 instance placed** | 610,304 | `6b0f953f…` | **G1–G5 PASS** | 2 / 1 / 1 / FM 10, coherent |

(five-gate = `experiments/frontdoor2025/emission_check.py`: BFI Format 2025
+ build present; pinned 2025 schema aboard; partitions walk clean under 2025
ordinals AND refuse under 2026; release-aware validator 0 errors; four
registries coherent + ADocument clean. Report:
`experiments/frontdoor2025/famload_lane_report.json`, 15.5 s for all three.)

* **Standalone validator (no context around the judge)** on every output
  above + the edited files + the `author --target-version 2025` panel:
  `VALID (no errors); warnings=0` — before this stream the same command
  reported the false E1 on each. The three pinned bases stay `VALID`
  (2026: its 1 known DataStorage warning; 2025/2024: 0/0).
* **Chained, host-keyed:** head loaded onto the base → `add_to_project` onto
  THAT file → `--rvt --edit "move LP-1 to 3,1,0"` on THAT file: all ok, all
  2025, all VALID.
* **CLI, bare:** `python -m rvt.convert.add_to_project G_ABPD_2025.rvt
  --prompt "add a 100 A lighting panel and a 400 A distribution panel"` →
  delivered 622,592 B, 2 families + 2 instances, Revit 2025;
  `tools/frontdoor.py author --rvt <that> --edit "move DP-1 to 3,1,0"` →
  `ok True … (hard gates PASSED)`, Revit 2025.
* **Mixed-release, one process:** `add_to_project` on 2025 → 2026 → 2024 →
  2025 bases: each output detects its own release, VALID 0 errors, census
  coherent, `active_release() is None` after each; module singletons after
  a 2025 run == before (the only post-run difference is `install_schema`'s
  native encoder seed on the 2026 run — pre-existing native behaviour).
  **2024 rides the same lane** (nothing in it is a year literal).
* **Provenance:** `tools/provenance.py <probe> --baseline all --streams`
  now completes on all three (before: framing crash). In this clone
  `samples/` is absent, so `--baseline all` = 0 baselines and G1 reads
  "no baseline supplied (unattributable)" for the probes **and for the
  certified base itself** (which additionally shows its 4 disclosed identity
  residue items, #19); identity ok=True on all three outputs. The in-lane
  family scan (v2, run inside the context with the 2025 pin) reports the
  emitted `.rfa` `PROVENANCE-CLEAN` + family-mode `VALID 0 errors`
  (`famload_lane/ATP25_lp1/families/*.json`). Byte attribution against the
  samples is an owner-machine re-run of the same command.
* **Tests:** `tests/test_famload_2025.py` 8 passed (21 s);
  `tests/test_target2025.py` 7 passed / 8 skipped (the skips key on the
  git-ignored `experiments/` bases); CI shard as CI runs it
  (`RVT_SKIP_LARGE=1 … $(grep -vE '^\s*(#|$)' tests/ci_shard.txt)`):
  **145 passed / 30 skipped in 57 s** (was 129 / 23 in 26 s before the two
  files joined); stream-local + adjacent (`test_famload*.py`,
  `test_famgen_{loader,adoc,skeleton,factory}.py`, `test_convert*.py`,
  `test_frontdoor_standalone.py`, `test_target202{4,5}.py`,
  `test_census.py`, `test_surface_perf.py`, `test_validate_release.py`):
  71 passed / 107 skipped, 0 failed. `tools/sync_plugin.py` → 8 files
  synced, deny-audit clean, `--check` clean; `validate_plugin.py` PASS (23
  assertions); `check_portable_paths.py` ok (2654 paths).

## 3. THE STAGED BATCH — batch 56 (NOTHING uploaded)

`experiments/frontdoor2025/famload_lane.py stage` → `tools/probe_batch.py`
gate → `experiments/acceptance/batch_56.json`:

| order | file | kind | md5 |
|--:|---|---|---|
| 0 | `CTRL_G_ABPD_2025_b56.rvt` | control | `470087732a98168af313f8a253f65edd` (== batch 35's certified control, == the bundled base) |
| 1 | `FL25_head.rvt` | probe | `8d87c53a61b31e02e6f261084ab763c8` |
| 2 | `L25_panel_noinst.rvt` | probe | `4992993f1cd1bec3252f9b95effe82c0` |
| 3 | `ATP25_lp1.rvt` | probe | `6b0f953f68a450cd868e353828d724b1` |

Reading order control-first (control FAIL ⇒ VOID). **Design:** the two
no-instance loads are the shapes that PASS on 2026 (L1a / L_v2 / BX_f2 /
H10) and isolate the one question batch 35 never asked — *does the 2025
four-registry WRITE (CD tokens 0x391/0x390, unit separator, 0x0eee footer,
ContentTable/FamilyMgr rows under the 2025 schema) satisfy Autodesk's 2025
reader?* `ATP25_lp1` adds exactly the OPEN cell's variable (a placed
instance of our generated family on our composed base) and is expected to
share that cell's fate; its FAIL with both loads PASS is the
release-independent residual (ROOM2025_full precedent), not a lane defect.
A load FAIL would be real news (a 2025-specific registration write defect)
and would re-open ROOM2025_full's reading.

**Caveat the uploader must know:** the probe BYTES are VM-local (loader
GUIDs are uuid4 — issue #9 — so outputs are not byte-reproducible, and
`experiments/**/*.rvt` is git-ignored by policy). On the upload machine run
**`.venv/bin/python experiments/frontdoor2025/famload_lane.py all`** — it
rebuilds the three probes, re-runs the five gates, and stages a fresh batch
(next number) with the same declared entries and the same byte-identical
control; upload THAT batch. `batch_56.json` is committed as the record that
the gate accepts this design from a fresh clone.

## 4. Findings for other streams (filed as issues, not fixed here)

* **Altitude follow-up (the deeper fix, deliberately not done here):** the
  three Global-stream tokens should stop being stored constants and become
  call-time reads of `rvt.partitions.CONTAINER_CLASS / UNIT_INNER_CLASS`
  (`famgen/factory.py:1469-71`, `famdoc_adoc.py:203`,
  `genesis/skeleton.py:1982`, with a module `__getattr__` keeping external
  `F.CD_END_RECORD` byte-compares working) — then `versions.reading` alone
  suffices, `global_framing.bound`, `release_ctx`'s `bfsu` 12-byte rewrite
  and the three tool-side copies (`tools/genesis_2025.py:90-131`,
  `genesis_2024.py:105-155`, `genesis_2023.py:97-117`) all delete. It
  touches two "prefer-wrapper" shared famgen files + genesis.skeleton, so it
  is filed as its own issue. **Patch note for the `src/rvt/versions/`
  owner (hot file, not edited):** `_PATCHED_NAMES` / `activate()` is the
  natural single home for every ordinal-derived framing token once that
  lands; and `records32.reading32` could take a pre-parsed `schema=` so
  callers holding one (global_framing's cache) do not parse twice.
* **Known limit carried into the host lane:** `_codec_triple_from_base`
  pins the HOST's `Formats/Latest` sha to the release pin. All six 2025
  samples share one schema (docs/writer/format-2025.md), so this holds for
  every 2025 file seen; a point-release file with a drifted schema would be
  refused with a clear message rather than built on — relax to "decode
  against its own schema + warn" only with such a file in hand.
* **`famspec_load` (rfa→rvt, rfa+rvt→rvt) cannot run in a fresh clone on ANY
  release**: its rfa-emit step looks for the vendor donor
  `vendor/phi-ag-rvt/…/racbasicsamplefamily-2026.rfa` instead of the bundled
  base (`FileNotFoundError: family container source not found`), identical
  on the 2026 base — release-independent, router/famfrom_ifc territory. The
  load step behind it (famload) is now 2025-ready.
* **`tools/make_family.py provenance <2025 .rfa>`** dies on the framing and,
  once read under the file's framing, judges `Formats/Latest` against the
  2026 pin (`formats_latest_is_format_constant: false`) — the family
  provenance CLI needs the file's release pin the way `release_ctx` step (5)
  supplies it in-lane.
* `rvt.famgen.loader`'s own `place=True` clones a host instance of the
  family's category; a family-free genesis base has none on any release
  (`LoaderError: no template instance`). Product placement goes through the
  constructed-specimen path (`add_to_project` / `build_intent`), which is
  what the lane and the tests exercise — recorded so nobody mistakes it for
  a 2025 defect.
* For #5 / O3 (honest matrix): the 2025 column of `prompt+rvt→rvt`
  (edit-shaped), the `add_to_project` field route and the famload host lanes
  now have executable evidence (`tests/test_famload_2025.py`); certification
  depth is whatever batch 56's successor returns.

## 5. Files

* NEW: `src/rvt/global_framing.py`, `tests/test_famload_2025.py`,
  `experiments/frontdoor2025/famload_lane.py`,
  `experiments/frontdoor2025/famload_lane_report.json`,
  `experiments/frontdoor2025/famload_lane/{FL25_head,L25_panel_noinst}.load.json`,
  `experiments/frontdoor2025/famload_lane/ATP25_lp1/{manifest.json,families/*.json}`,
  `experiments/frontdoor2025/famload_lane/.gitignore`,
  `experiments/acceptance/batch_56.json`, this record.
* EDITED (territory): `src/rvt/frontdoor/release_ctx.py`.
* EDITED (entry hooks / instruments outside the listed territory — each a
  public-function wrapper or a `with` around an existing read, bodies
  unchanged): `src/rvt/famload.py` (2 hooks), `src/rvt/famgen/loader.py`
  (1), `src/rvt/convert/add_to_project.py` (2 + `contextlib` import),
  `src/rvt/frontdoor/__init__.py` (`_route_rvt`), `src/rvt/validate.py`
  (E1/E2 under `global_framing.bound`), `src/rvt/provenance.py` +
  `tools/provenance.py` (own-release walks), `tests/test_target2025.py`
  (+1 test), `tests/ci_shard.txt` (+2 files),
  `experiments/frontdoor2025/probes.json` (+3 entries).
* NOT touched: `src/rvt/versions/**` (hot — called, never edited),
  `tools/frontdoor.py`, `src/rvt/frontdoor/base.py`, any `SKILL.md`,
  `TRACKER.md`, `KNOWLEDGE.md`, `viewer-certified.json`, `.github/**`.
* Plugin mirrors regenerated by `tools/sync_plugin.py` (8 files incl. the
  new `plugin/lib/src/rvt/global_framing.py`).

## SUITE RESULT

Per `docs/inbox/SUITE-COORDINATION.md`: no full-suite run. Stream-local +
CI shard only (§2). Expected full-suite delta: +9 tests (8 new + the finish
line), `four_registry_census` / `validate_file` / `tools/provenance.py` now
succeed on 2025/2024 files with loaded content where they crashed or
false-fired before; no native-release behaviour change (native hosts enter
no context; verified by the unchanged 2026 shard results).

## BRANCH STATE

* Branch `cam/14-famload-2025-lane` from `origin/main` af59d26; PR opened
  with `Closes #14`; issue #14 labelled `needs-viewer` for the certification
  step with a comment naming the one command the uploader runs.
* DONE check against the charter:
  * famload + the famgen loader run inside the 2025 release context
    end-to-end ✓ (§0/§2 — and now enter it themselves on any 2025 host);
    `author --prompt … --target-version 2025` emits a 2025 file with a
    loaded family + placed instance, validator 0 errors **standalone under
    its own release** ✓ (was a false E1), `detect_release()==2025` ✓, only
    0x0ed9-family framing on disk ✓ (walk-must-fail counter-check in both
    new tests);
  * `tests/test_target2025.py` gains the family/instance finish line ✓
    (runs in CI, not only on the owner machine);
  * a viewer batch STAGED (control = byte-identical `G_ABPD_2025`) ✓ batch
    56, gate-clean — with the §3 caveat that the uploader re-stages the
    VM-local bytes with one command;
  * beyond the letter of the DONE: `add_to_project`, `--rvt --edit`,
    bare famload/famgen loads, the validator's E1 and the provenance
    instrument all work on existing 2025 (and 2024) files.
* STOP at READY: no upload, no certification claim; every output ships
  PROOF-ONLY-stamped as before.
