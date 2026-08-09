# schema-gate — ONE schema-availability gate for the test suite (#298)

Stream: `schema-gate` · issue #298 (Refs #161, #102, review notes carried from PR #297) ·
PG3 / PG7 · territory: `src/rvt/schema.py` (one small function), `tests/conftest.py`, the seven
gated test files (gates only), `tests/test_schema_gate.py` (new), `tests/ci_shard.txt`, this
record, regenerated `plugin/lib/src/rvt/schema.py`.

## What was built

* **`rvt.schema.schema_available() -> bool`** (next to `load_schema`). The engine owns the
  rule: *True* when the research corpus blob (`DEFAULT_PATH`) exists, else when the sha-pinned
  bundled genesis base `load_schema` falls back to exists in one of its bundled locations
  (`rvt.frontdoor.standalone.bundled_base_path(verify=False)`; `StandaloneError` = absent).
  A pure existence check: it opens, hashes and parses nothing (no side effects — `_MEMO`
  untouched, asserted by a test), so collection stays cheap (measured 0.02 s for the call itself; the
  conftest import + gate adds ~30–35 ms per pytest run on this cloud VM and ~80 ms/session as
  measured independently by the #316 reviewer's sandbox on a corpus-less machine — either way
  it replaces seven collection-time full parses) and the first real `load_schema()` is the one memoized parse per process (#183).
  `load_schema()` keys its own fallback on `schema_available()` — one rule, one phrasing.
* **`load_schema()`'s fallback no longer swallows.** Before: `try: bundled_schema() except
  Exception: pass` fell through to `open(DEFAULT_PATH)` — so a pin mismatch or a corrupt
  bundled stream surfaced as `FileNotFoundError(extracted/…/000.bin)`, which
  `tests/conftest.py`'s research-input hook then turns into a **skip**. That was the same
  silent all-skips failure mode the #297 review flagged in the per-file `_have_schema()`
  probes, one layer down. Now the fallback is taken iff the corpus blob is absent *and* the
  bundled base is present, and whatever it raises propagates as itself; only "neither source
  exists" reaches the `FileNotFoundError` naming the corpus path (the hook's contract,
  unchanged for genuinely sample-less machines).
* **`tests/conftest.py`** exposes the single `HAVE_SCHEMA = schema_available()` and
  `needs_schema = skipif(not HAVE_SCHEMA, …)`; test files `from conftest import …`.
* The **seven files** import it instead of defining their own: the four famgen suites drop
  their byte-identical 8-line `_have_schema()`; `test_residue_b.py` takes `HAVE_SCHEMA` and
  `pytestmark = needs_schema` from the shared gate and **drops** its `_ensure_schema()` /
  `rvt.genesis.types._STATE` seeding (deviation from DONE (b)'s "keeps" — see Findings);
  `test_genesis_skeleton.py` and `test_ifc_family.py` lose their stale
  `os.path.exists(extracted/…)` probes.
* **`tests/test_schema_gate.py`** (new, in the shard): the ungated **sentinel** the review
  asked for — whenever `plugin/assets/genesis/G_ABPD.rvt` is in the tree, `schema_available()`
  and `HAVE_SCHEMA` are True *and* `load_schema()` parses to the corpus-constant sha — plus the
  no-side-effect check, the closed-gate path (no corpus, no bundle → False and
  `FileNotFoundError.filename == DEFAULT_PATH`), and the loud path (bundle present but
  `bundled_schema` raising `ParseError` → `ParseError`, not a skip).

## (c) Re-gating, the #161 way

Gates forced open on this sample-less cloud clone (no `samples/ extracted/ vendor/`; bundled
bases present; `.venv` from `scripts/cloud-setup.sh`, which installs ifcopenshell 0.8.5);
kept only what passes with **unchanged expectations**:

* `test_genesis_skeleton.py`: the three `@needs_schema` tests
  (`test_minimal_skeleton_roundtrip`, `test_view_constellation_cross_references`,
  `test_plan_view_is_bound_to_its_level`) pass on the bundled schema; the eleven
  `@needs_corpus` byte-exact specimen tests read `extracted/rstbasicsampleproject` and keep
  their corpus gate.
* `test_ifc_family.py`: the old `HAVE_SCHEMA` was `extracted blob exists OR vendor archetype
  .rfa exists` — two facts in one name. With the schema fact taken from the shared gate, seven
  `@needs_build` composition tests pass unchanged. The two delivery tests
  (`test_rfa_emits_clean_validates_and_is_provenance_clean`,
  `test_rfa_reads_back_the_authored_family`) ERROR at fixture setup with the gate forced open:
  `product.write_rfa(path)` uses the vendor archetype
  `vendor/phi-ag-rvt/…/racbasicsamplefamily-2026.rfa` as its default container source
  (`famdoc_adoc.py:1644`, "family container source not found"). That is a **sample
  dependency the old disjunction hid**, not a schema dependency and not a product finding —
  so those two get `needs_emit` (= build deps + `HAVE_RFA_DONOR`), exactly as true on the
  owner machine as before, and no expectation was edited. `needs_load` (slow, rst sample)
  unchanged.

## Evidence — per-file before/after (same machine, same venv, `-q -rs -p no:cacheprovider`)

| file | BEFORE passed/skipped | AFTER passed/skipped | wall (after) | note |
|---|---|---|---|---|
| `test_famgen_factory.py` | 41 / 5 | 41 / 5 | 2.4 s | skips = rme/rst samples |
| `test_famgen_skeleton.py` | 5 / 9 | 5 / 9 | 0.4 s | skips = .rfa/rme samples |
| `test_famgen_geometry.py` | 12 / 7 | 12 / 7 | 0.4 s | skips = .rfa/rme samples |
| `test_famgen_adoc.py` | 8 / 11 | 8 / 11 | 0.4 s | skips = archetype .rfa / assembler stack |
| `test_residue_b.py` | 39 / 14 | 39 / 14 | 0.4 s | skips = Y9/Yn/ZB ladders |
| `test_genesis_skeleton.py` | 6 / 14 | **9 / 11** | 0.3 s | 3 schema-only tests now run; 11 corpus |
| `test_ifc_family.py` | 9 / 10 | **16 / 3** | 0.9 s | 7 build tests now run; 2 emit (archetype) + 1 load (rst) skip |
| `test_schema_memo.py` | 11 / 0 | 11 / 0 | 1.6 s | untouched neighbour |
| `test_coldstart.py` | 11 / 0 | 11 / 0 | 3.7 s | untouched neighbour |
| `test_schema_gate.py` | — | 4 / 0 | 0.3 s | new |

Zero failures before and after. CI has no ifcopenshell: simulated with a poisoned
`ifcopenshell` on `PYTHONPATH`, `test_ifc_family.py` gives 2 passed / 17 skipped (green),
`test_genesis_skeleton.py` 9 / 11, `test_schema_gate.py` 4 / 0.

## (d) Shard

Added to `tests/ci_shard.txt`: `test_schema_gate.py` (listed **first** in the whole shard, so
its ungated sentinel exercises the real bundled-base fallback before any later file's
`install_schema()` swaps `load_schema` / materialises a schema cache — #316 review nit),
`test_famgen_skeleton.py`,
`test_famgen_geometry.py`, `test_famgen_adoc.py` (the #297 review's three, < 1.2 s together),
`test_residue_b.py`, `test_genesis_skeleton.py`, `test_ifc_family.py` — all fresh-clone green
above, ≤ 1 s each. Whole shard run locally the way `ci.yml` runs it
(`RVT_SKIP_LARGE=1 python -m pytest <shard> -q --durations=15`): see BRANCH STATE for the
count and wall time. GitHub Actions is unavailable on this repo (steer #302), so "CI wall
time" is the sandbox shard run the tech-lead session performs on the PR head; the local
number is the estimate.

## (e) Plugin

`schema.py` ships in the plugin: `tools/sync_plugin.py` regenerated
`plugin/lib/src/rvt/schema.py` (1 file synced), `--check` clean, `validate_plugin.py` PASS
(25 assertions), portable paths ok (2768). `/verify` drive from a **bare unzip of the rebuilt
`tekton-plugin.zip` with system Python 3.11** (bootstrap path insertion only):
`schema_available() → True`, `load_schema()` → source `assets/genesis/G_ABPD.rvt#Formats/Latest`,
4690 classes, sha == corpus constant; and from a **temp copy of that unzip with
`assets/genesis/G_ABPD.rvt` renamed** (plugin/assets never touched in place):
`schema_available() → False`, `load_schema()` → `FileNotFoundError` whose `.filename` is
`DEFAULT_PATH`.

## Findings / observations

* The engine-level swallow in `load_schema` (above) was the real root of the "regression
  becomes skips" risk; fixing the test probes alone would not have closed it because the
  conftest hook converts the disguised `FileNotFoundError` into a skip. Recorded here rather
  than as a `learned-` note: it is now enforced by `test_schema_gate.py`.
* **DONE (b) deviation, evidenced.** The issue says `test_residue_b.py` "keeps its `_STATE`
  seeding". That seeding was written when a no-arg `load_schema()` failed on a fresh clone; since
  #44 (and now as the single owner of the rule) `rvt.genesis.types._S()` builds
  `ObjectDecoder()` → `load_schema()` → the *same* bundled schema object lazily, and on the owner
  machine the seeding returned early anyway. Two independent `/simplify` reviewers (altitude,
  simplification) flagged it as a test-file re-implementation of engine behaviour; measured:
  with the seeding deleted the file is 39 passed / 14 skipped both alone and after a file that
  runs `install_schema()` first (`test_famload_batch.py` → `test_residue_b.py`: 58 passed / 14
  skipped together). So it is dropped; the module keeps a 4-line comment saying why the shared
  gate is the whole precondition. Trivial to restore if the reviewer prefers the letter of (b).
* **Follow-up filed** (outside territory, `src/rvt/frontdoor/standalone.py`): `install_schema()`
  step (b) is now a redundant second owner of the fallback rule, and its `_load_schema_bundled`
  wrapper still returns the bundled schema for ANY non-existent explicit path
  (`or not os.path.isfile(path)`) instead of raising — the same swallow class this PR removes
  from `load_schema`. It is also why `test_schema_gate.py` must bind the real `load_schema` at
  collection time and pass the live `DEFAULT_PATH` (the swap is process-wide once any earlier
  test installs). Issue: #315.
* No product-path behaviour change except the error *type* a caller sees when a bundled base
  exists but is broken (now the pin/parse error instead of a misleading missing-corpus path).

## Open questions

None blocking. `test_ifc_family.py`'s two emit tests could run fresh-clone if the `rfa` fixture
passed `donor=bundled_base_path()` (the error message itself suggests it) — that is a test
*behaviour* change (different container source), deliberately out of this gates-only scope.

## BRANCH STATE

* Branch `cam/298-schema-gate` from `origin/main@109345e`, rebased onto `origin/main@311dee9`
  after #310/#313/#314 merged (one conflict, `tests/ci_shard.txt`: kept #310's
  `tests/test_codec_bases.py` AND this stream's seven, no duplicates — 48 shard files); PR #316
  closes #298; independent review ✅ on the pre-rebase head `5f77f26` (sandboxed shard 939 / 99 /
  2 xfailed), the `test_residue_b` deviation accepted.
* Files: `src/rvt/schema.py` (`_bundled_base_present`, `schema_available`, `load_schema`
  fallback narrowed), `tests/conftest.py` (shared `HAVE_SCHEMA`/`needs_schema`),
  `tests/test_famgen_{factory,skeleton,geometry,adoc}.py`, `tests/test_residue_b.py`,
  `tests/test_genesis_skeleton.py`, `tests/test_ifc_family.py` (gates only),
  `tests/test_schema_gate.py` (new), `tests/ci_shard.txt` (+7 files), this record,
  `plugin/lib/src/rvt/schema.py` (regenerated by `tools/sync_plugin.py`).
* Gates: the ten files in the table above — 156 passed / 71 skipped / 0 failed after
  (142 / 70 / 0 before, over the nine pre-existing files); **full CI shard locally, exactly as
  `ci.yml` runs it (`RVT_SKIP_LARGE=1 python -m pytest <47 files> -q --durations`): 939 passed /
  99 skipped / 2 xfailed / 0 failed in 137 s** (a first run caught my own new gate tests being
  order-sensitive behind `install_schema()`'s process-wide swap — fixed by binding the real
  `load_schema` at collection and passing the live `DEFAULT_PATH`; the sentinel turns a
  `FileNotFoundError` into `pytest.fail` so conftest's skip hook can never hide it);
  `sync_plugin.py` synced `plugin/lib/src/rvt/schema.py`, `--check` clean; `validate_plugin.py`
  PASS (25); portable paths ok (2768); `/verify` on the rebuilt zip: bare unzip + system Python
  3.11 → `schema_available() True`, `load_schema()` from `assets/genesis/G_ABPD.rvt#Formats/Latest`
  (4690 classes, corpus-constant sha); temp copy with the base renamed → `False` +
  `FileNotFoundError.filename == DEFAULT_PATH`; `go author --prompt "an electrical room with 6
  panels"` from the bare unzip → preflight `READY` 0.023 s, job 3.5 s, exit 0, `prompt_room.rvt`
  delivered (stamped PROOF-ONLY as always). `/simplify` 4-angle review applied: reuse — nothing
  duplicated; simplification — private helper folded (load_schema keys on `schema_available()`),
  docstrings/comments de-narrated, `ROOT` imported from conftest, no-side-effect test made
  side-effect-free, dead residue_b seeding dropped; efficiency — measured negligible (+~35 ms
  per pytest run, 22 µs per fallback call); altitude — engine-side fix judged the right layer,
  `install_schema` wrapper filed as follow-up, `needs_emit` judged the right layer.
* Shipped vs staged: everything ships with the merge; no `.rvt`/`.rfa` output produced, no
  viewer claim, no probe batch.
