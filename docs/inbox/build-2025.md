# BUILD 2025 — `author --target-version 2025` EMITS A REAL 2025 FILE

Stream: **build-2025** (2026-08-05, launched on VERDICTS ~01:20: G_ABPD_2025
PASSED, the G25-5 flip APPLIED).  Charter: wire the three named gaps
(compose-2025 §6 A/B/C) into a release-aware build context so the front
door's full build path constructs NATIVELY on the certified 2025 base;
finish line = `tests/test_target2025.py::test_END_STATE_author_2025_
produces_a_2025_file` green; plus the staged viewer batch and the
bare-plugin proof.

**DONE state: the finish-line test GREEN (13 passed / 1 by-design skip in
the file); the panel, walls-only-room and full-room 2025 outputs each pass
the FIVE-GATE emission check; batch 35 staged (certified control + both
room variants, nothing uploaded); the bare-plugin proof PASSES (unzipped
tekton-plugin.zip alone resolves the bundled 2025 base and authors a native
2025 file); mixed-release process order proven (2025→2026→2025 in one
process, all VALID).**

---

## 1. The mechanism — `src/rvt/frontdoor/release_ctx.py` (NEW)

`release_build_context(base_path)`: a process-local, fully-restored swap
set entered by `build_intent` whenever the resolved base's release differs
from the REGISTRY DEFAULT (`genesis_base.json default.revit_release` — the
year literal appears nowhere in logic).  Native base ⇒ hard no-op.  A
non-default release must be `KNOWN_RELEASES[y].creation_certified` AND have
a port layer module `rvt.genesis.port<y>` — anything else raises
`ReleaseContextError` naming the missing piece.

Composition (proven pieces + this stream's additions):

| layer | what | provenance |
|---|---|---|
| framing | `versions.reading(base)` → rvt.partitions ordinals + TERMINATOR + resync | version-model stream |
| local tags | reduce/manipulate/commit/writer BLOCK+TRAILER copies; famgen.factory CD_SEPARATOR/CD_END_RECORD | `tools/genesis_2025.py::context_2025` list |
| local tags (NEW) | famgen.skeleton `_PART_TAG/BLOCK_TAG/TRAILER_TAG/FOOTER_TAG`; famdoc_adoc `FAMILY_END_RECORD`; genesis.skeleton `EMPTY_CONTENT_DOCUMENTS`; `factory.build_family_save_unit`'s inline 12-byte unit separator (byte-rewrite wrapper) | this stream |
| codecs | `encode._DEFAULT_ENCODER`, `adocument._DECODER`, regadd/regdiff decoder factories, `genesis.types._STATE`, `genesis.skeleton._SCHEMA_CACHE`, schema-chokepoint `load_schema`/`DEFAULT_PATH` — ALL bound to the BASE's own schema, pin-verified against `KNOWN_RELEASES[y].schema_sha256` | run_ladder2025 swaps, scoped+restored |
| port seed | `port2025._STATE["s25"]` seeded (dec/enc/schema) FROM THE BASE — `samples/` is NEVER read (standalone rule; `schema_2025.load()`'s default source is the quarantined corpus) | this stream |
| class ids | mutate `CLASS_ELEMENT_HEADER/SERIALIZED_DUMMY/GELEMENT/SWALL/FAMILY_INSTANCE/ELECTRICAL_SYSTEM` resolved BY NAME from the base schema | this stream |
| fresh models | genesis.skeleton `minimal_history/elemtable/increment_table/partition_table/contents/basic_file_info` wrapped: class tags by-name (DocumentHistory 1309, ElemTable 1451 + IdentifierSource tail, DIT 1313, PartitionTable 3136, DocumentStorageIndexImpl 1315, EditingPermissionsImpl/EditingRequestsImpl trailing pair), format/build strings read from the BASE's own BasicFileInfo ("2025" / "Development Build"); History terminator 2662 needs NO swap (verified equal in the 2025 corpus) | this stream |
| schema pin | factory/famdoc `FORMATS_LATEST_SHA256_PREFIX` → the target release's pin prefix (c964f9aa) | this stream |
| standalone | `bundled_base_path()` → the ACTIVE base (family container donor = the 2025 base, tripwire allow-list follows); `SA._SCHEMA_STATE` force-seeded (idempotency cannot pin a stale release); specimen templates (`swall_template`/`family_instance_template`) port-adapted (mined GeomTable −1/−1) | this stream |
| port boundary | `genesis.skeleton.SkelElement.records` + `mutate.NewElement.records` wrapped: every (seq, class, obj) triple through `port2025.adapt` before encoding — 2026-shaped constructor literals gain 2025-only fields with the port's MINED corpus defaults instead of `EncodeError: missing field 'm_maxSafeTag'` | this stream (the ladder's adapt_record posture at the famgen boundary) |
| scan sanity | famdoc's donor-id byte scan corroborated against the schema-decoded tree (see §3) | this stream |

Everything restores LIFO on exit; `tests/test_target2025.py::test_release_
ctx_swaps_and_restores_everything` pins swap+restore, `..._native_base_is_
a_noop` pins the no-op path.

## 2. Surgical edits OUTSIDE the new module (every line documented)

* **`src/rvt/frontdoor/build.py`** (the release hook only):
  - import `release_ctx as RC`;
  - `build_intent` enters `RC.release_build_context(opts.base.path)` around
    the whole build (errors surface as `res.errors`, never a crash); the
    original body moved verbatim into `_build_intent_inner` (the
    `install_schema`→tripwire→degrade→`_run` sequence is UNCHANGED);
  - a `release-context` stage record when active;
  - the HONESTY STAMP: when the context is active and equipment instances
    were placed, `degradations` gains the known-limit line ("placed
    equipment instances carry the OPEN instance-audit residual of the
    famgen path … walls+base are the certified-clean subset").
* **`src/rvt/frontdoor/standalone.py`** (two seams):
  - `author_standalone`: a NON-default `target_version` with no explicit
    base resolves its REGISTRY SLOT first (`resolve_base(target_release=y)`
    probes the plugin bundle by basename), so the plugin entry authors on
    the bundled 2025 base instead of pinning the default 2026 base and
    being refused; `BaseNotCertified` (a pending slot) keeps the old
    default-base fallback flow (the honest line + IFC addition); any other
    resolution failure propagates RED.
  - `install_schema`: records `installed_from` and RE-SEEDS when called
    with a DIFFERENT base than the one that seeded the singletons — the
    idempotent early-return could otherwise pin a stale release's codecs in
    a mixed-release process.  Proven by the 2025→2026→2025 one-process run
    (§5) and the 10/10 standalone acceptance tests.
* **`tests/test_target2025.py`** (this stream's finish-line file): the
  finish-line test additionally proves the FRAMING (partitions walk clean
  under 2025 ordinals AND are refused under the native ordinals — only
  0x0ed9-family framing on disk); + the two release_ctx tests.  No xfail
  existed to remove (coordinated by file state).
* **`tests/test_plugin_sync.py`** — CROSS-TERRITORY TOUCH, flagged: the
  asset allow-list was the stale literal `{assets/genesis/G_ABPD.rvt}` and
  failed RED against the G25-5 flip's bundled `G_ABPD_2025.rvt` (the flip
  updated sync_plugin's mappings but not this test).  Made registry-driven:
  the default base + every `releases` slot that is certified AND
  sha256-pinned.  Mechanical truth-alignment with the applied flip, not a
  policy change; the packager stream owns the file and may re-shape.

`tools/sync_plugin.py` was run after each src edit (the standard mirror
mechanism; drift each time = exactly this stream's files); final `--check`
clean, zip rebuilt (4088 KB), deny-audit clean, assets verified.

## 3. The famdoc donor-id byte-scan false positive (diagnosed, mitigated in-context, permanent fix PROPOSED)

Stage F on the 2025 base initially failed:
`RuntimeError: donor element ids survive in the payload: {'examples': [18432]}`.

Diagnosis (full evidence in this record's session): the authored family
ADocument payload carries a monotone index table serialized as
`… 00 45 00 00 00 00 00 00 | 00 46 … | 00 47 … | 00 48 … | 00 49 …` (the
0x34..0x56 run near the payload tail).  Read at the +1 byte offset the
sliding-window i64 scan sees `k<<8` values; the 2025 base REALLY HAS
element 18432 (= 72<<8, a host-side `Family` row), so ONE window collides.
The donor TREE carries no 18432 anywhere (walked); the authored tree
neither — a textbook instance of the scan's own documented false-positive
class ("id-shaped windows inside … adjacent fields"), which never fired on
2026 only because G_ABPD's id set happens to miss the k<<8 values.

Mitigation (in `release_ctx`, context-scoped): `byte_scan_ids` wrapped so a
byte hit COUNTS ONLY when the schema-DECODED tree also carries the id as a
value — exactly the authority hierarchy famdoc_adoc's own report already
documents ("the schema-typed … census above is the authority").  A real
carried reference (id present in the tree) stays fatal; the cross-field
window is recorded as a named false positive.  With it: DP-1 .rfa emits,
family-mode validator VALID 0 errors, provenance scan ok, 0 suspects.

**PROPOSED to the famgen owner (famdoc_adoc.py, not applied here):** move
that corroboration INTO `author_family_adocument`'s raise site (raise only
on tree-corroborated ids; report the rest as
`byte_scan_donor_ids.false_positive_windows`), so the 2026 path gets the
same robustness — any base whose id set intersects the k<<8 range will
reproduce this on 2026 the moment ids drift.

## 4. Proofs (all re-runnable)

* **Finish line**: `tests/test_target2025.py` → **13 passed, 1 skipped**
  (the skip is `test_frontdoor_explicit_pinned_base_still_falls_back`,
  by-design once 2025 certified).
* **Five-gate emission check** (`experiments/frontdoor2025/emission_check.py`
  — G1 BasicFileInfo Format+build, G2 pinned schema aboard, G3 framing
  clean-under-2025 + REFUSED-under-2026, G4 validator 0 errors in-context,
  G5 four-registry coherence + ADocument clean): **ALL FIVE PASS** on
  - the panel output (610,304 B; save_units 2 / CD 1 / CT 1),
  - `experiments/frontdoor2025/room_walls/ROOM2025_walls.rvt`,
  - `experiments/frontdoor2025/room_full/ROOM2025_full.rvt`
    (7 .rfa built ok + 7/7 loaded + 4 walls + 7 instances; the one
    degradation is the pre-existing named circuit blocker, same as 2026).
* **Bare-plugin proof** (`experiments/frontdoor2025/bare_plugin_proof.py`,
  report `bare_plugin_proof.json`): bare dir + unzipped `tekton-plugin.zip`
  only, PYTHONPATH=lib/src — `resolve_base(target_release=2025)` returns
  `<bare>/assets/genesis/G_ABPD_2025.rvt` (pinned-bundled, certified,
  detect 2025) and `author_standalone(..., target_version=2025)` builds a
  native 2025 file, status match, self-checks green, pinned schema. **PASS.**
* **Mixed-release order**: 2025 → 2026 → 2025 builds in ONE process, each
  output detects its own release, 2026-after-2025 validates VALID.
* **CLI**: `tools/frontdoor.py author --prompt … --target-version 2025
  --no-handoff` → "version: target 2025 -> output release 2025 (match)".
* **Regressions (stream-local files only, per SUITE-COORDINATION)**:
  `test_frontdoor.py + test_versions.py + test_compose_2025.py` 77 passed;
  `test_plugin_sync.py + test_bootstrap.py` 15 passed;
  `test_frontdoor_standalone.py` 10 passed;
  `test_famgen_adoc.py + test_famgen_skeleton.py` 33 passed.

## 5. THE STAGED BATCH — batch 35 (NOTHING uploaded; the orchestrator uploads)

Staged via `tools/probe_batch.py stage_batch` into `experiments/acceptance/`
(`batch_35.json`; gate clean — both probes declare the CERTIFIED 2025 base
via `experiments/frontdoor2025/probes.json`):

| order | file | kind | md5 | note |
|--:|---|---|---|---|
| 0 | `CTRL_G_ABPD_2025_b35.rvt` | control | 47008773… | byte-identical copy of the certified `G_ABPD_2025.rvt` (md5-verified) |
| 1 | `ROOM2025_walls.rvt` | probe | a2b20738… | walls-only 2025 room — the certified-clean subset isolated |
| 2 | `ROOM2025_full.rvt` | probe | 729bcebe… | FULL 2025 room — **carries the OPEN instance-audit residual by construction** |

Reading order control-first; control FAIL ⇒ round VOID.  The batch note +
`probes.json` state the KNOWN LIMIT verbatim: a full-room FAIL with walls
PASS re-reads as the release-independent instance residual (the SX_f6i6
precedent — the discriminator is the famgen code path, not the base), NOT a
2025 regression; walls FAIL too ⇒ 2025 build-path problem, bisect from the
control.  Staged copies verified byte-identical to their sources.

## 6. Known limits (stated in output stamps)

* Placed equipment instances carry the open instance-audit residual
  (release-independent; the famgen fix stream's §7 symbol-geometry line of
  inquiry, next rung `symbol_solid=False`).  The 2025 author output states
  it: the manifest `degradations` line (release hook, §2) + the batch/probe
  notes.  Walls+base are the certified-clean subset — hence the two-variant
  batch design.
* Feeder circuits: the pre-existing named blocker (no RbsElectricalSystem
  constructor), identical on 2026; the resolved plan rides in the manifest.
* The `.rfa` deliverable's identity strings follow the 2025 base's own
  BasicFileInfo ("Development Build") — recorded here; if counsel C1 lands
  a distinct 2025 authoring string, `release_ctx` reads whatever the base
  carries, so re-certifying the base updates the outputs automatically.

## 7. Files (this stream)

* `src/rvt/frontdoor/release_ctx.py` — NEW (the whole mechanism, §1)
* `src/rvt/frontdoor/build.py` — the release hook (§2, every line listed)
* `src/rvt/frontdoor/standalone.py` — author_standalone target resolution +
  install_schema `installed_from` (§2)
* `tests/test_target2025.py` — finish-line framing proof + 2 release_ctx
  tests
* `tests/test_plugin_sync.py` — registry-driven asset allow-list
  (cross-territory, flagged §2)
* `experiments/frontdoor2025/` — `emission_check.py`,
  `bare_plugin_proof.py` (+ `.json` report), `probes.json`,
  `room_walls/ROOM2025_walls.rvt` (+ build manifests),
  `room_full/ROOM2025_full.rvt` (+ families/ + manifests)
* `experiments/acceptance/` — `batch_35.json`, `CTRL_G_ABPD_2025_b35.rvt`,
  `ROOM2025_walls.rvt`, `ROOM2025_full.rvt` (staged copies)
* plugin mirror: via `tools/sync_plugin.py` (release_ctx.py, build.py,
  standalone.py copies; zip rebuilt)
* `docs/inbox/build-2025.md` (this record)

## SUITE RESULT

Per `docs/inbox/SUITE-COORDINATION.md` (BINDING): NO new full-suite run —
the orchestrator's canonical run is the suite of record; this stream ran
its stream-local + adjacent files only (§4: 13+77+15+10+33 = 148 passed,
1 by-design skip, 0 failed).  Expected full-suite delta vs the canonical
baseline: +2 tests (the two new release_ctx tests), the finish-line test
flipped from self-armed-failing to PASSING, and `test_plugin_sync.py::
test_no_denylisted_data_in_plugin` flipped from RED (stale allow-list vs
the applied flip) to green.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — not a git repo; all work on disk as
  listed in §7; integration is the orchestrator's.
* DONE check against the charter:
  * finish-line test GREEN ✓ (arms itself, plus the framing counter-proof);
  * the three gaps wired ✓ (A: allow-list was already landed, verified
    covering the resolved base; B: the release context IS the
    versions-creating equivalent, entered by build_intent; C: port2025
    wired at the records() boundary + the famgen framing/model constants);
  * output invariants ✓ (detect_release 2025, ONLY 2025 framing on disk —
    proven by the walk-must-fail counter-check, validator 0 errors
    in-context, five-gate check, four-registry coherent);
  * staged batch ✓ (batch 35: certified control + walls-only + full;
    NOTHING uploaded);
  * bare-plugin proof ✓ (the bundled base resolves; native 2025 output);
  * honesty stamps ✓ (§6).
* STOP at READY: no viewer upload, no certification claim for the two
  probes; the control's certification carries over by bytes only.
