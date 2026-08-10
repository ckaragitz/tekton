# inbox — perf-schema-memo (in-process schema memo, issue #183)

Stream: PERF-SCHEMA-MEMO (2026-08-09), issue #183 (folds in #216, closed as
its duplicate). Refs #108 / #124 (plugin latency epic, steer S-2026-08-09-g:
latency is only "done" with a measured before/after from a bare surface).
Territory: `src/rvt/schema.py`, `src/rvt/schema_cache.py`,
`tests/test_schema_memo.py` (new), `tests/ci_shard.txt`, this record.
No hot file touched.

## Verdict in one screen

* **One schema materialisation per process instead of one per decoder.**
  `rvt.schema.parse` is now memoized in-process by
  `hashlib.sha256(data).hexdigest()` (bounded dict, `MEMO_MAX = 8`, oldest
  evicted). `rvt.schema_cache` (`install` / `parse_cached` / `load_cached`)
  fills and consults the **same** memo through `rvt.schema.memoized`, so the
  plugin cold-start path (cache-file arm) and the repo/CI path (real-parser
  arm) both pay at most once per distinct `Formats/Latest` bytes.
* **Bare-unzip flagship job (`go author` 6 panels), this VM, median of 3:
  8.79 s → 3.83 s (−4.96 s, −56 %).** Cache-file loads per job 68 → 1; real
  parser runs 0 → 0 (the shipped `.tksc` serves the 2026 constant); distinct
  digests 1 (`6459a9a93ebd`). 2-panel job: 36 loads → 1, 5.08 s → 2.53 s.
* **Outputs unchanged in kind:** job `.rvt` validates 0 errors before and
  after (`tools/rvt_validate.py`, 1 pre-existing DataStorage warning both
  times, same size 643,072 B); the three pinned bases validate 0 errors; the
  shipped schema-cache assets rebuild byte-identical (`sync_plugin.py`
  synced only the two mirrored `.py` files).
* **Sharing is safe (audited):** no consumer anywhere mutates a `Schema` /
  `ClassDef` / `Field` after obtaining it (§4). Sharing one instance was
  already the norm in four places (`global_framing._SCHEMAS`,
  `standalone._SCHEMA_STATE`, `standalone.install_schema`,
  `release_ctx`).
* Validator green ≠ certified (rule 4): nothing here claims the outputs load
  in Revit; the change does not alter a single output byte path, only how
  often the same schema object is rebuilt.

## 1. What was built

`src/rvt/schema.py`
* `MEMO_MAX = 8`, `_MEMO: dict[str, Schema]` (sha256 hex → Schema, insertion
  ordered).
* `memoized(digest, build)` — the one chokepoint: return the memo hit, else
  `build()` (a Schema or `None`), remember non-`None`, evict oldest beyond
  `MEMO_MAX`. Exceptions propagate and are never stored.
* `parse_uncached(data, source="", digest=None)` — the old body of `parse`
  (real byte-level parse into a NEW object).
* `parse(data, source="")` — `memoized(sha256(data), parse_uncached)`. Same
  signature, same `ParseError` on junk. The shared object's `.source` names
  its first materialisation (nothing reads `.source` at runtime, §4a).
* `memo_clear()` for tests / long-lived hosts.

`src/rvt/schema_cache.py`
* `load_cached(sha)` → `memoized(sha, <disk lookup>)`: a digest already in
  the memo (from the parser or an earlier cache load) never touches the disk
  again; a disk hit is memoized; a miss is not.
* `install()`'s `parse_cached` is unchanged in shape (cache arm, then the
  original parser) — both arms are now memo-backed, so the wrapper the
  plugin bootstrap installs costs one `.tksc` load per process.
* `schema_to_payload` writes a constant `"source": ""` — the shipped cache
  payload is a function of the stream bytes alone by construction, so a
  memoized object whose `.source` names some caller's path can never leak
  into an asset (the shipped `.tksc` files were already built with
  `source=""`, so they stay byte-identical: `sync_plugin.py` reported no
  asset drift). `build_cache` parses with `parse_uncached` simply so the
  cache is always rebuilt from the byte-level parser, never re-serialised
  from an earlier cache load (tests:
  `test_cache_payload_never_carries_a_callers_source`,
  `test_build_cache_ignores_a_memoized_source` — byte-identical to the
  shipped asset).
* `src/rvt/versions/_release_schema.py` (hot file, untouched) calls
  `load_cached` directly and therefore benefits too.

`tests/test_schema_memo.py` (11 tests, 1.9 s, fresh-clone — only the pinned
plugin base's own schema bytes; listed in `tests/ci_shard.txt`):
identity (`parse(b) is parse(b)`, first `source` wins); different bytes →
distinct Schema and both stay addressable; `parse_uncached` is private and
does not displace the memo; junk raises `ParseError` twice and memoizes
nothing; **N=5 parses → `_Parser.run` exactly once**; **N=5 cache-served
parses after `install()` → `load_cache_file` exactly once**, and
`load_cached` / the wrapped and original `parse` all return that one object;
a `load_cached` miss is not memoized; bounded + oldest-first eviction
(`MEMO_MAX` monkeypatched to 3); two `Document.from_file(G_ABPD.rvt)` share
one Schema (one real parse), decode every seq-102 record identically, and
leave the shared object's shape (class / top-level / index / field / guid /
histogram / consumed / size / sha) unchanged; `build_cache` independence.

## 2. Measurements (steer S-2026-08-09-g: bare surface, before/after, same VM)

VM: claude.ai/code cloud session, 4 vCPU Intel Xeon @ 2.80 GHz, Linux
6.18, system `python3` = 3.11.15, `env -i PATH=/usr/bin:/bin` (cleared
environment), plugin = `tekton-plugin.zip` built by `tools/sync_plugin.py`
at the named commit and unzipped into an empty scratch dir; nothing on
`PYTHONPATH`; numpy absent in the bare runs (validator falls back to its
stdlib decoder, as shipped). Baseline commit `a5dd53b` (main); "after" =
this branch on top of it. This VM is ~3× faster than the reference bare env
of #183's evidence (28.3 s job there, 8.8 s here), so absolute seconds are
smaller; the lever is the same 68 loads of one digest.

### 2a. Flagship job by hand — `python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/jN --json`, 3 runs each

| | run 1 | run 2 | run 3 | **median `go.job_seconds`** | stages (run 2: P · F · L · W · E · V) |
|---|---|---|---|---|---|
| before (`a5dd53b`) | 9.446 | 8.791 | 7.995 | **8.79 s** | 0.27 · 4.39 · 1.57 · 0.27 · 0.25 · 1.60 |
| after (this branch) | 4.177 | 3.831 | 3.821 | **3.83 s** | 0.15 · 1.23 · 1.16 · 0.18 · 0.13 · 0.81 |
| delta | | | | **−4.96 s (−56 %)** | F −3.2 s, V −0.8 s, L −0.4 s |

Every run: exit 0, `result.ok` true, `build.validation.combined.verdict`
VALID, 0 errors / 1 warning (the known DataStorage ES-blob decoder gap),
output 643,072 B. `tools/rvt_validate.py out/j1/prompt_room.rvt`: `ok=True,
{'error': 0, 'warning': 1, 'info': 2}` before and after.

The saving exceeds 67 × ~40 ms (one `load_cached` on this VM: 34–55 ms;
one real parse 77–97 ms; one sha256 of the 496,597 B stream 1.2 ms) because
each redundant load also allocated ~0.8 M dataclass/dict objects that then
sat alive inside 60-odd decoders — allocator and cyclic-GC pressure the F
stage (six family builds, each constructing several decoders/encoders) paid
on every pass.

### 2b. Real materialisations per job (instrument in §5)

| job (bare unzip, system python) | `parse` calls seen | distinct digests | real parser runs | cache-file loads | `go` wall |
|---|---|---|---|---|---|
| 6 panels, before | 68 | 1 (`6459a9a93ebd`) | 0 | **68** | 8.91 / 8.60 s |
| 6 panels, after | 68 | 1 | 0 | **1** | 3.91 / 3.81 s |
| 2 panels, before | 36 | 1 | 0 | **36** | 5.09 s |
| 2 panels, after | 36 | 1 | 0 | **1** | 2.54 s |

DONE check: schema materialisations per job == number of distinct digests
(1 for the prompt route on 2026; ≤ 2 by construction when a second release's
schema enters the process, e.g. a 2025 target — one memo entry per digest).

### 2c. `tools/surface_bench.py --zip tekton-plugin.zip` (all three simulated surfaces, same VM, back-to-back)

(before = `out/bench-before.json`, after = `out/bench-after.json`; wall
seconds per job as the bench reports them)

| job | cowork before → after | codeexec before → after | local before → after |
|---|---|---|---|
| preflight | 0.1 → 0.1 s | 0.1 → 0.1 s | 0.1 → 0.1 s |
| author-prompt | **4.8 → 2.7 s** (−2.2) | **4.5 → 2.7 s** (−1.8) | **4.3 → 2.3 s** (−2.0) |
| go-author-prompt | **4.0 → 2.2 s** (−1.8) | **4.1 → 2.7 s** (−1.4) | **3.8 → 2.3 s** (−1.5) |
| go-author-6panels | **8.1 → 4.0 s** (−4.1) | **8.9 → 4.5 s** (−4.4) | **7.9 → 3.9 s** (−4.0) |
| author-ifc | 0.4 → 0.4 s FAIL¹ | 0.5 → 0.5 s FAIL¹ | 11.0 → 5.7 s (−5.3) |
| edit-roundtrip (3 calls) | 1.6 → 1.5 s | 2.4 → 2.1 s | 1.6 → 1.4 s |
| go-edit | 1.3 → 0.9 s | 1.8 → 1.3 s | 1.2 → 0.9 s |
| validate | 0.8 → 0.7 s | 1.0 → 0.9 s | 0.9 → 0.7 s |
| **session total (10 calls)** | **21.2 → 12.4 s** (−8.7) | **23.2 → 14.8 s** (−8.4) | **30.8 → 17.4 s** (−13.4) |

go-author-6panels stage breakdown (cowork): before `P 0.3 · F 3.9 · L 1.5 ·
W 0.3 · E 0.2 · V 1.5`, after `P 0.2 · F 1.3 · L 1.1 · W 0.2 · E 0.1 · V 0.8`.
go-edit (cowork): job 1.117 → 0.77 s (validator 0.6 → 0.4 s); structural
PASS + validation PASS (0 errors, 0 warnings) both times.

¹ `author-ifc` FAILs on cowork/codeexec identically before and after: the
IFC route needs numpy and the simulated bare VM has none (`ImportError:
numpy is required here (IFC placement / geometry resolution)`, exit 3) —
pre-existing at `a5dd53b`, tracked as #127, unrelated to the schema path.
The bench prints its reason as `author --ifc failed: }` because `_tail()`
takes the last line of the pretty-printed JSON stdout instead of the job's
own `status` / `errors[0]`; filed as a follow-up task issue (see §6).

## 3. Gates run

* `tests/test_schema_memo.py tests/test_coldstart.py tests/test_frontdoor_standalone.py
  tests/test_plugin_sync.py tests/test_bootstrap.py -q` → **46 passed, 1
  skipped** (18.4 s) on the final tree (first pass before the `/simplify`
  cleanups: 30 + 15 passed, 1 skipped).
* `/simplify` (four review angles) ran on the diff: taken — drop the
  `digest=` pass-through on `parse_uncached`, one counting fixture instead
  of two idioms, a plain `memo_clear()` autouse fixture (the one installing
  test restores `S.parse` via `monkeypatch`), inflate the blob directly,
  state that FIFO eviction is deliberate, and (altitude) make the cache
  payload's `source` a constant so `build_cache` determinism is structural;
  skipped as out of scope — replacing `install()`'s monkeypatch with a
  miss-loader hook in `schema.py`, and restating/retiring
  `global_framing._SCHEMAS` (off-limits file) — both filed as one follow-up
  (§6).
* `tools/sync_plugin.py` → synced 2 files (`plugin/lib/src/rvt/schema.py`,
  `schema_cache.py`), deny-audit clean, assets verified, validation passed,
  zip rebuilt; then `--check` → in sync, exit 0.
* `plugin/scripts/validate_plugin.py` → PASS (24 assertions).
* `tools/dev/check_portable_paths.py` → ok.
* `tools/rvt_validate.py` on the job output before/after and on
  `plugin/assets/genesis/G_ABPD{,_2025,_2024}.rvt` → 0 errors each.
* Full suite NOT run (SUITE-COORDINATION: stream-local files only).

## 4. Mutation audit (why handing every caller the same object is safe)

Question: does any caller under `src/`, `tools/`, `tests/`, `skills/`,
`plugin/skills/` (mirrors under `plugin/lib/` excluded) mutate a `Schema`,
`ClassDef` or `Field` after obtaining it from `parse` / `load_schema` /
`bundled_schema` / `schema_of` / `_load_schema` / a decoder's `.schema`?

**Mutators found: none.** Every write to those objects happens during
construction: `_Parser` (`schema.py`), the tail of `parse_uncached`
(sort / size / sha / source, before the object is published), and
`schema_cache.payload_to_schema` (fresh object from a `.tksc`). Consumers —
`ObjectDecoder`, `ADocumentDecoder`, `_RefDecoder`, `ObjectEncoder`,
`FamilyIndex`, `Validator`, `Document.from_file`, `estorage`, `release_ctx`,
`global_framing`, `versions/*`, `records32`, `parity`, `tools/genesis_20xx`,
`rvt_inspect`, the tests — only read; decoders keep derived state on
themselves (`ObjectDecoder._chain_cache` etc.), never on the schema; no
aliasing of `.classes` / `.by_name` / `.fields` into a later-mutated local.

(a) `Schema.source` / `._from_cache` readers: only
`schema_cache.schema_to_payload` (build time; `build_cache` now uses a
private `parse_uncached(source="")`, so the memo cannot leak a path into the
asset). `_from_cache` is read by no code. Nothing branches on `.source` at
runtime → "first materialisation wins" is harmless.
(b) `parse` call sites: `schema.load_schema`; `schema_cache.install` /
`build_cache`; `frontdoor/standalone.bundled_schema` and
`schema_identity_report`; `versions.schema_of`; `mutate.Document.from_file`;
`validate.Validator._load_schema`; `families.FamilyIndex`;
`estorage._decoder_for`; `tools/genesis_2023/2024/2025.py`;
`plugin/skills/tekton-native/scripts/rvt_inspect.py`; `tests/test_coldstart.py`
— all read-only users of the result.
(c) identity reliance: `tests/test_frontdoor_standalone.py` asserts the
three `load_schema` importers return the *same* object (strengthened, not
weakened); nothing requires two parses of equal bytes to be distinct.
(d) no `pickle` / `copy` / `deepcopy` of a Schema anywhere; the only
serialisation is `schema_cache`'s marshal payload.

Greps behind the audit (ripgrep from the repo root, all with
`--glob '!plugin/lib/**'`, `--type py` unless noted):

```
rg -n "_from_cache"
rg -n "(schema\.parse\(|\bS\.parse\(|parse\(blob|rvt\.schema\.parse|from \.schema import .*\bparse\b|from rvt\.schema import .*\bparse\b|from \.\.schema import .*\bparse\b|_schema\.parse\(|schema_mod\.parse\()"
rg -n "parse_schema\("
rg -n "\b(load_schema|bundled_schema|schema_of|_load_schema|load_release_schema)\(" --glob '*.py'
rg -n "\.classes\.(append|sort|extend|insert|pop|remove|clear|reverse)|\.classes\[[^\]]*\]\s*=|\.classes\s*(\+|\-)?="
rg -n "\.fields\.(append|extend|insert|pop|remove|sort|clear|reverse)|\.fields\[[^\]]*\]\s*=[^=]|\.fields\s*(\+)?=[^=]"
rg -n "\.guids\.(append|extend|insert|pop|remove|sort|clear)|\.guids\s*(\+)?=[^=]"
rg -n "by_name\[[^\]]*\]\s*=[^=]|by_name\.(update|pop|clear|setdefault|popitem)|del [^\n]*by_name\["
rg -n "by_id\[[^\]]*\]\s*=[^=]|by_id\.(update|pop|clear|setdefault|popitem)|del [^\n]*by_id\["
rg -n "(top_level|desc_hist|type_refs|unresolved)\s*(\+|\-)?=[^=]|(top_level|desc_hist|type_refs|unresolved)\.(append|extend|insert|pop|remove|sort|clear|update|subtract|setdefault)"
rg -n "\b(schema|sch|sch2[3-6]|s2[3-6]|_schema|SCHEMA)\.\w+\s*(\+|\-)?=[^=]"
rg -n "setattr\([^)]*(schema|sch)\b|delattr\([^)]*(schema|sch)\b"
rg -n "\.source\b"
rg -n "\b(c|cd|cls|klass|cdef|tgt|got|p|root|parent)\.(name|fields|guids|parent|version|type_id|offset|end|depth)\s*=[^=]"
rg -n "\b(f|fld|field|fd|elem|sub|e|ff)\.(name|kind|flags|count|type_id|element|extra|offset)\s*=[^=]"
rg -n "\.schema\.\w+\s*(\+|\-)?=[^=]|\.schema\.\w+\.(append|extend|insert|pop|remove|sort|clear|update|setdefault)\("
rg -n "\bis\s+(not\s+)?(s|sch|schema|sb|sc|hit|cached|fresh|parsed)\b|id\((schema|sch|s)\)"
rg -n "(pickle\.dumps?|copy\.copy|deepcopy)\([^)]*(schema|sch|\.classes|by_name|by_id|ClassDef|Field\b)"
rg -n "=\s*\w+(\.\w+)*\.(classes|by_name|by_id|top_level|fields|guids|desc_hist|type_refs|unresolved)\s*(#.*)?$"   # aliasing
```

## 5. The parse-count instrument (session scratchpad; re-create from here)

Run with the system python from an unzipped `tekton-plugin.zip` root; it
loads the skill bootstrap by path, arms the engine exactly as `go` does
(`ensure_engine` → lazy-schema + schema-cache wrappers), wraps
`rvt.schema._Parser.run`, `rvt.schema_cache.load_cache_file` and the
module-attribute `rvt.schema.parse` with counters, then calls
`tekton_env.go(argv)` in-process (the job runs via `runpy`, so one process
== one job) and prints `COUNTS: {...}` on stderr.

```python
#!/usr/bin/env python3
# count_parses.py BOOTSTRAP author --prompt "..." --out out/cnt --json
import hashlib, importlib.util, json, os, sys, time
boot = os.path.abspath(sys.argv[1]); argv = sys.argv[2:]
sys.path.insert(0, os.path.dirname(boot))
spec = importlib.util.spec_from_file_location("_bootstrap", boot)
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
env = bs._load_tekton_env(); env.ensure_engine()
import rvt.schema as S, rvt.schema_cache as SC
counts = {"parser_runs": 0, "cache_loads": 0, "parse_calls": 0}; digests = set()
_run = S._Parser.run
def run(self, *a, **k): counts["parser_runs"] += 1; return _run(self, *a, **k)
S._Parser.run = run
_lcf = SC.load_cache_file
def lcf(*a, **k): counts["cache_loads"] += 1; return _lcf(*a, **k)
SC.load_cache_file = lcf
_parse = S.parse
def parse(data, source=""):
    counts["parse_calls"] += 1; digests.add(hashlib.sha256(data).hexdigest()[:12])
    return _parse(data, source=source)
S.parse = parse
t0 = time.time()
try: rc = env.go(argv, base_dir=os.path.dirname(boot))
except SystemExit as e: rc = e.code
sys.stderr.write("COUNTS: " + json.dumps({**counts, "digests": sorted(digests),
                 "go_wall_s": round(time.time() - t0, 2), "rc": rc}) + "\n")
sys.exit(rc or 0)
```

## 6. Findings / open questions

* The remaining 68 `parse` *calls* per 6-panel job are now ~1.2 ms each
  (one sha256 of 496 KB) ≈ 80 ms/job. Passing the schema object down
  instead of re-inflating `Formats/Latest` per decoder would remove that and
  the ~68 gzip inflates too — that is #124's "reuse across stages" lever
  proper (out of scope here; this issue was the bounded carve-out).
* F is still the largest stage after the change (1.2 s of 3.8 s): six family
  builds; L (batched host pass) 1.1 s; V 0.8 s.
* Memory trade-off, stated once: while a job runs the memo adds nothing (the
  1–2 live schemas are already held by every decoder's `.schema`); it only
  keeps them alive until process exit. A long-lived multi-release host could
  pin up to `MEMO_MAX = 8` schema graphs (tens of MB each) — `memo_clear()`
  exists for that host, and 4 (one per known release) would be an equally
  hit-free cap if it ever matters. One job == one process today.
* Not re-measured here: the `rfa → rvt` cell from #183's first comment
  (11 parses of one digest, 0.8 s of 2.3 s) — same lever, expected to drop
  to one; `tools/surface_bench.py` has no job for that cell yet.
* Follow-up filed: #287 — `surface_bench` FAIL reasons print `}` (last line
  of pretty JSON stdout) instead of the job's own `status`/`errors[0]`
  (P2, `area:perf`, `ready`). The numpy-less IFC failure itself is #127.
* Follow-up filed: #291 — one interception mechanism (miss-loader hook in
  `rvt.schema` instead of `install()` monkeypatching `parse`) and
  re-measure/retire-or-restate `global_framing._SCHEMAS`, whose "a parse is
  ~0.1 s" justification the memo now serves (P2, `area:engine`, `ready`).

## BRANCH STATE

* Branch `cam/183-schema-memo` from `main@a5dd53b`. Files:
  `src/rvt/schema.py`, `src/rvt/schema_cache.py` (+ their regenerated
  mirrors `plugin/lib/src/rvt/schema.py`, `plugin/lib/src/rvt/schema_cache.py`
  via `tools/sync_plugin.py`), `tests/test_schema_memo.py` (new, in
  `tests/ci_shard.txt`), `docs/inbox/perf-schema-memo.md` (this record).
* Gates: §3 — all green. Shipped: nothing beyond the PR; no viewer batch
  (no output bytes change → nothing to STAGE). `tekton-plugin.zip` rebuilt
  locally for the measurements, not committed (git-ignored artifact).
* Bench artifacts (`out/bench-before.json|md`, `out/bench-after.json|md`,
  validation JSONs) are session-local under `out/` (git-ignored); their
  numbers are transcribed in §2.

---

## eng #291 — 2026-08-10 — one interception mechanism (miss-loader hook), `_SCHEMAS` re-measured and restated

Stream: PERF-SCHEMA-MEMO follow-up · issue #291 (filed by §6 above) · Refs #183 #110 · PG6 ·
steer S-2026-08-09-g (measured before/after from a bare surface) · size S · territory:
`src/rvt/schema.py`, `src/rvt/schema_cache.py`, `src/rvt/global_framing.py` (+ their
regenerated `plugin/lib/src/rvt/` mirrors), `tests/test_schema_memo.py`, `tests/test_coldstart.py`
(one subprocess assertion reworded), this section. Not touched: `src/rvt/frontdoor/standalone.py`,
`plugin/skills/_shared/tekton_schema.py` / `tekton_env.py` (#377/#389/#267 — read
`docs/inbox/install-schema.md`; nothing here needed them), `src/rvt/versions/**` (hot), any
SKILL.md.

### What was built

* **`rvt.schema.register_miss_loader(loader) -> bool`** — the one documented hook below the
  memo. `parse(data, source)` = `memoized(sha256(data), _materialise)`, and `_materialise` asks
  each registered `loader(digest, source)` (registration order) for a ready-made `Schema` before
  it runs `parse_uncached`. Contract in the docstring: `digest` is the only key (`source` is a
  label for `Schema.source`), a loader answers `None` for "not mine" and never raises, a returned
  Schema whose `.sha256` is not `digest` is refused (one comparison in `_materialise`, so the
  memo's key provably stays the content hash whoever registers), and an accepted one is memoized
  exactly like a parse (asked at most once per digest per process). Idempotent by identity
  (`False` if already registered). `parse_uncached` bypasses memo *and* loaders (so
  `schema_cache.build_cache` still rebuilds from the byte-level parser). `_MISS_LOADERS` sits next
  to `_MEMO`; nothing else in `schema.py` moved — `memoized` / `memo_clear` / `load_schema` /
  `load_schema_file` / `schema_available` are byte-for-byte what #183/#377 left (an existing
  explicit copy IS parsed verbatim and memoized per content; a missing explicit path raises
  `FileNotFoundError`; the no-arg call falls back to the bundled base).
* **`rvt.schema_cache.install()`** no longer rebinds `rvt.schema.parse`: it is
  `register_miss_loader(disk_loader)` + the same small report (`"(already)"` on a repeat, `dirs` =
  `cache_dirs()`). **`disk_loader(digest, source="")`** (new public name, 3 lines) =
  `_load_cached_from_disk(digest, None, source)` — the sha-verified `.tksc` lookup over
  `cache_dirs()` that already never raises. Gone: `parse_cached`, `parse._schema_cache_orig`,
  `rvt.schema._schema_cache_installed`, the never-used `install(dirs=…)` parameter (no caller in
  `src/ tools/ tests/ plugin/skills/` ever passed it; `$RVT_SCHEMA_CACHE_DIR` is the extra-dir
  knob and stays) — and with it any install state outside `rvt.schema`'s one list — and the
  import-order sensitivity the issue names (`families.py`'s `from .schema import parse` bound at
  import time used to bypass the wrapper on a cold process when imported before `install()`; the
  hook is inside `parse`, so every binder gets the disk arm). `load_cached(sha, dirs)` (used
  directly by `versions/_release_schema.py`) is unchanged: `memoized(digest, <disk lookup>)`.
  `plugin/skills/_shared/tekton_env.py::_install_schema_cache` is **unchanged** (still
  `schema_cache.install()` inside a `try`); its docstring's verb "wraps `rvt.schema.parse`" is
  now loosely worded — suggested 1-word patch for whoever next holds that file (outside this
  territory): `wraps` → `hooks` (`_install_schema_cache.__doc__`, line 238).
* **`global_framing._SCHEMAS` kept, comment restated** (DONE option 2, decided by the numbers in
  the next section): it is *not* a parse cache — the parse is served by `rvt.schema`'s memo
  whichever way the bytes arrive — what a hit skips is `versions.schema_of`'s container re-open
  + `Formats/Latest` re-inflate + sha256 (~7 ms) on a repeat `reading()` entry of the same file.
  The old comment ("a parse is ~0.1 s") invited a third fix of parse cost there; the new one says
  what it saves, how much, and cites the measurement.
* **Tests.** `tests/test_schema_memo.py::test_five_cached_parses_load_the_cache_file_once` now
  asserts the new observable: after `install()` `S._MISS_LOADERS == [SC.disk_loader]`, **`S.parse`
  is the same function object as before** (nothing rebound), a second `install()` reports
  `(already)` without a second registration, 5 parses → `load_cache_file` once and `_Parser.run`
  never, `load_cached` and a pre-install reference to `parse` return that one object, **a digest
  no cache file answers reaches the real parser exactly once** (not `_from_cache`), and junk still
  raises `ParseError` with the loader registered; the list is monkeypatch-restored so ordering
  with the other memo tests never matters. New `test_a_loader_answering_the_wrong_digest_is_refused`
  (a registered loader returning a Schema of another sha → the real parser runs, and the memo then
  answers without asking the loader again). `tests/test_coldstart.py::test_cached_parse_hit_and_fallback_miss`
  (bare subprocess through the real bootstrap): `installed` = the parsed schema's `_from_cache`
  (only a registered disk loader can produce one) instead of the retired module flag; hit +
  `ParseError` miss as before.

### Measurements

VM: claude.ai/code cloud session, 4 vCPU, Linux 6.18, Python 3.11.15 (repo `.venv` for the
in-process rows, system `python3` for the bare rows). BEFORE = `origin/main@2b87024`; AFTER =
this branch. Scratch instruments live in the session scratchpad (`bench/micro.py`,
`bench/count_parses.py` = §5's counter plus `global_framing.schema_of` / `versions.schema_of`
call, hit and time counters, `bench/summarize.py`).

**(a) Chokepoint micro-timings, ×200 per fresh process, 3 interleaved processes per side
(medians of the per-process medians).** Corpus absent, so the first `load_schema()` is the
bundled fallback; "cache" rows call `schema_cache.install()` first (the plugin order), "parser"
rows do not.

| call | BEFORE | AFTER |
|---|---|---|
| `import rvt.schema` self time (`-X importtime`, 3 runs) | 2.38–2.45 ms | 2.45–2.69 ms |
| first `load_schema()` (cache arm: one `.tksc` load) | 75–217 ms (first process cold disk) | 76–86 ms |
| first `load_schema()` (parser arm: one real parse) | 119–122 ms | 117–122 ms |
| `load_schema()` ×200 (fallback: base sha256 + inflate + memo hit) | 1571 µs | 1563 µs |
| `ObjectDecoder()` ×200 (same path) | 1621 µs | 1612 µs |
| `parse(blob)` ×200 (sha256 of 496,597 B + memo hit) | 1181 µs | 1187 µs |
| after `install_schema(base)`: `load_schema()` ×200 | 0.17 µs | 0.17 µs |
| after `install_schema(base)`: `ObjectDecoder()` ×200 | 0.76 µs | 0.76 µs |

Same order everywhere (run-to-run spread on this VM is ±10 %; the hook adds one empty-list
iteration on a *miss* only and nothing on a hit).

**(b) What `_SCHEMAS` still saves — counted inside real bare jobs (BEFORE zip, `env -i`, system
python3, `count_parses.py`).**

| job | `parse` calls / distinct digests / real parses / `.tksc` loads | `global_framing.schema_of` calls → LRU hits | `versions.schema_of` calls, total time | `go` wall |
|---|---|---|---|---|
| `go author` "an electrical room with 6 panels" (2 runs) | 70 / 1 / 0 / 1 | 18 → **9 hits** (6 family `.rfa` ×2, `prompt_room.rvt` ×4, `stage_L_loaded.rvt`, `G_ABPD.rvt`) | 27 calls, 0.207 s (7.7 ms each) | 4.96 / 5.24 s |
| `go edit G_ABPD.rvt set-level …` | 6 / 1 / 0 / 1 | 2 → **1 hit** | 4 calls, 0.032 s | 0.71 s |

So the LRU saves 9 × ~7.5 ms ≈ **70 ms per flagship job (1.4 %)** and ~8 ms per edit — CPU that
is deterministic but smaller than this VM's run-to-run spread of a whole job (±0.15 s). Deleting
20 lines to buy a known +70 ms on the flagship path is the wrong trade under S-2026-08-09-g, so
the LRU stays and its comment now tells the truth. The 27 − 9 = **18 remaining
`versions.schema_of` calls are `records32.reading32`'s own unconditional inflate per `reading()`
entry** (~135 ms per flagship job): that is exactly open issue **#251** ("`global_framing.reading`
parses once per entry, not twice" — needs the `reading32(source, schema=…)` passthrough in the hot
`versions/` dir); re-measured numbers posted there rather than a duplicate filed.

**(c) `tools/surface_bench.py --zip … --jobs preflight,go-author-prompt,go-author-6panels,go-edit`,
three zips built by `tools/sync_plugin.py` — BEFORE (`main`), AFTER (this head), and a bench-only
NO-LRU variant of this head (`global_framing.schema_of` = plain `versions.schema_of`) — 3 full
runs each, interleaved (before, after, no-lru, before, …), machine otherwise idle; medians of job
wall time, individual runs in parentheses.**

| surface | job | BEFORE `main` | AFTER (this head) | NO-LRU variant | Δ after − before | Δ no-LRU − before |
|---|---|---|---|---|---|---|
| cowork | preflight | 0.105 s (0.096 / 0.105 / 0.106) | 0.106 s (0.098 / 0.108 / 0.106) | 0.115 s (0.118 / 0.103 / 0.115) | +0.00 | +0.01 |
| cowork | go-author-prompt | 3.109 s (3.023 / 3.112 / 3.109) | 3.029 s (3.029 / 3.002 / 3.266) | 3.023 s (3.023 / 3.023 / 3.257) | −0.08 | −0.09 |
| cowork | go-author-6panels | 4.919 s (4.932 / 4.919 / 4.812) | 5.086 s (5.214 / 5.086 / 5.053) | 4.968 s (4.968 / 4.829 / 5.147) | +0.17 | +0.05 |
| cowork | go-edit | 0.909 s (0.909 / 0.903 / 0.926) | 0.983 s (0.983 / 0.907 / 1.013) | 0.939 s (0.939 / 0.921 / 1.005) | +0.07 | +0.03 |
| codeexec | preflight | 0.098 s (0.095 / 0.102 / 0.098) | 0.101 s (0.101 / 0.098 / 0.108) | 0.113 s (0.111 / 0.114 / 0.113) | +0.00 | +0.01 |
| codeexec | go-author-prompt | 3.029 s (3.029 / 2.891 / 3.213) | 3.223 s (3.223 / 2.948 / 3.272) | 3.002 s (2.951 / 3.002 / 3.242) | +0.19 | −0.03 |
| codeexec | go-author-6panels | 5.696 s (5.696 / 5.304 / 5.705) | 5.590 s (5.997 / 5.372 / 5.590) | 5.933 s (5.400 / 5.933 / 6.100) | −0.11 | +0.24 |
| codeexec | go-edit | 1.316 s (1.345 / 1.212 / 1.316) | 1.284 s (1.284 / 1.316 / 1.226) | 1.314 s (1.182 / 1.401 / 1.314) | −0.03 | −0.00 |
| local | preflight | 0.075 s (0.089 / 0.068 / 0.075) | 0.071 s (0.071 / 0.077 / 0.067) | 0.077 s (0.067 / 0.103 / 0.077) | −0.00 | +0.00 |
| local | go-author-prompt | 2.495 s (2.962 / 2.364 / 2.495) | 2.658 s (2.736 / 2.361 / 2.658) | 2.436 s (2.611 / 2.436 / 2.412) | +0.16 | −0.06 |
| local | go-author-6panels | 4.982 s (4.674 / 5.021 / 4.982) | 5.122 s (4.915 / 5.122 / 5.740) | 4.739 s (5.034 / 4.698 / 4.739) | +0.14 | −0.24 |
| local | go-edit | 0.898 s (0.876 / 0.898 / 0.942) | 0.921 s (0.896 / 0.921 / 1.146) | 0.869 s (0.934 / 0.863 / 0.869) | +0.02 | −0.03 |

**Every cell PASS on all three zips** (36/36 job runs per variant; `go-edit` = structural PASS +
validation PASS, 0 errors, everywhere). Read as: **no slowdown, and no measurable whole-job
signal from the LRU either way** — both Δ columns are mixed-sign and each sits inside its own
row's run-to-run spread (6panels moves +0.17 on cowork and −0.11 on codeexec for the same AFTER
zip; the NO-LRU zip is −0.24 on local and +0.24 on codeexec). That is what (a) and (b) predict:
the hook costs nothing on the 69 memo hits and one empty-list walk on the single miss, and the
LRU's 70 ms is a third of one row's spread. Because cowork/6panels was the one row whose AFTER
runs did not overlap BEFORE, it was re-run head-to-head with nothing else on the machine — bare
unzips of the two zips, `env -i PATH=/usr/bin:/bin python3 …/_bootstrap.py go author --prompt "an
electrical room with 6 panels"`, **5 alternating runs each: BEFORE `go.job_seconds` 4.939 / 5.104
/ 4.927 / 4.766 / 4.820 (median 4.93 s), AFTER 5.628¹ / 4.998 / 4.849 / 4.835 / 4.830 (median
4.85 s)** — same order (¹ first run straight after that tree's unzip). Both trees' `prompt_room.rvt`:
692,224 B, `tools/rvt_validate.py` → ok, **0 errors** / 1 warning (the known DataStorage
Extensible-Storage decoder gap) / 2 info, identical before and after.

### Gates (final head)

* `RVT_SKIP_LARGE=1 pytest tests/test_schema_memo.py tests/test_coldstart.py
  tests/test_frontdoor_standalone.py tests/test_lazy_schema_wrapper.py tests/test_schema_gate.py
  tests/test_bootstrap.py tests/test_plugin_sync.py tests/test_surface_perf.py tests/test_go_edit.py
  -q -rs` → **63 passed / 6 skipped / 0 failed** in 30 s (skips: `test_frontdoor_standalone.py:316`
  "research machine only" and five `test_surface_perf.py` "no bare python3 with numpy on this
  host" — pre-existing environment skips). The four order-sensitive schema files
  (`test_schema_gate`, `test_lazy_schema_wrapper`, `test_frontdoor_standalone`,
  `test_schema_memo`) also run green in both directions (27 passed / 1 skipped each way).
  Adjacent consumers of `load_cached` / `schema_of`: `tests/test_records32.py test_codec_bases.py
  test_validate_release.py test_readers_own_release.py` → 100 passed / 2 xfailed. Full suite NOT
  run (SUITE-COORDINATION). No new test *file* → no shard drop-in (`test_schema_memo.py` and
  `test_coldstart.py` are already in the shard).
* `tools/sync_plugin.py` → synced 3 files (`plugin/lib/src/rvt/{schema,schema_cache,global_framing}.py`),
  deny-audit clean, identity scan == allowlist, assets verified (**no schema-cache asset drift**:
  the `.tksc` payload is untouched), zip rebuilt (5201 KB); `--check` → in sync, exit 0;
  `plugin/scripts/validate_plugin.py` → PASS (25 assertions); `tools/dev/check_portable_paths.py`
  → ok (2879 paths).
* `/simplify` (4 angles): reuse — clean; efficiency — clean (hit path = one sha256 + one dict
  get, as before; the miss path now hashes twice instead of three times); simplification —
  applied: the never-used `install(dirs=…)` parameter and its `_INSTALL_DIRS` global dropped, the
  test's tautological "early binder" asserts and the coldstart probe's private-list peek dropped;
  altitude — applied: `_materialise` refuses a loader's Schema of the wrong digest (the memo owns
  its key invariant), the hook docstring says `source` is a label not a key, the `_SCHEMAS`
  comment names #251 as its retirement condition; skipped: threading `digest` into
  `parse_uncached` (cold path, ~1 ms once per process; #183's simplify removed exactly that
  pass-through), the stale verb in `tekton_env._install_schema_cache.__doc__` (outside territory,
  patch suggested above).
* `/verify` from a **bare unzip of the rebuilt zip, `env -i PATH=/usr/bin:/bin`, system `python3`
  3.11.15**, no repo on the path: `skills/tekton-author/scripts/_bootstrap.py go author --prompt
  "an electrical room with 6 panels" --out out/j1 --json` → exit 0, one JSON document, preflight
  `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | family-donor
  missing | out-dir OK | 0.061s`, `go.ready true`, job 5.5 s, `result.ok true`, `errors []`, six
  `.rfa` + `prompt_room.rvt` delivered (PROOF-ONLY stamped, as always); `tools/rvt_validate.py` on
  it → ok, **0 errors** / 1 warning (the known DataStorage Extensible-Storage decoder gap) / 2
  info. `skills/tekton-edit/scripts/_bootstrap.py go edit assets/genesis/G_ABPD.rvt set-level --id
  1351691 --elevation-ft 12.0 -o out/e1/edited.rvt` → exit 0, READY, job 0.63 s, `result.ok true`,
  `structural PASS (crc_failures=0, ecc_mismatches=0, walker_errors=0, stamps_ok=True) | validation
  PASS (0 errors, 1 warnings)`; `rvt_validate.py` on the edited file → 0 errors. The hook itself
  through the plugin's own bootstrap in that unzip (`tekton_env.ensure_engine()`):
  `rvt.schema._MISS_LOADERS == [rvt.schema_cache.disk_loader]`, `rvt.schema.parse` is still the
  module's own function, `install()` again → `(already)`; `load_schema()` → 4690 classes, sha
  `6459a9a93ebde32c…`, **`_from_cache True`**, 79 ms, second call `is` the same object;
  `load_schema('/nonexistent/2025.bin')` → `FileNotFoundError /nonexistent/2025.bin`; `parse(b"junk")`
  with the loader registered → `ParseError`; and the import-time binder the issue names,
  `rvt.families.parse_schema is rvt.schema.parse` → **True** (it now gets the disk arm too).

### Findings / observations

* No new issue filed: the one follow-up this work surfaces (one schema read per `reading()`
  entry) is already #251; commented there with the post-memo cost model (inflate + sha ≈ 7 ms per
  redundant call, 18 per flagship job) so whoever takes it measures against the right baseline.
* `docs/inbox/perf-coldstart.md` §Runtime still describes the retired `parse._schema_cache_orig`
  wrapper — left as that stream's historical record (no cross-voice edit); this section is the
  current description.

### BRANCH STATE

* Branch `cam/291-schema-miss-loader` from `origin/main@2b87024`; PR `Closes #291`; no new issue
  (the follow-up is #251, commented there).
* Files: `src/rvt/schema.py` (`_MISS_LOADERS`, `register_miss_loader`, `_materialise`; `parse`
  routes its miss through it), `src/rvt/schema_cache.py` (`disk_loader`; `install()` registers it,
  no rebinding, no `dirs` parameter; module docstring), `src/rvt/global_framing.py` (comment +
  docstring of `_SCHEMAS` / `schema_of` only — no code change), `tests/test_schema_memo.py` (one
  test rewritten to the new observable, one added), `tests/test_coldstart.py` (one subprocess
  assertion + one docstring word), this section, and the regenerated
  `plugin/lib/src/rvt/{schema,schema_cache,global_framing}.py` (by `tools/sync_plugin.py`, never
  hand-edited). No hot file, no `standalone.py`, no `plugin/skills/_shared/*`, no SKILL.md.
* Gates: as above — 63 / 6 skipped / 0 failed (+100 / 2 xfailed adjacent); sync `--check` clean,
  no asset drift; validate_plugin PASS; portable paths ok; bare-unzip `go author` READY + VALID 0
  errors and `go edit` READY + 0 errors; micro-timings same order; bench: all 36 cells PASS on
  all three zips, no slowdown, LRU kept on the counted 70 ms/job with a truthful comment.
* Shipped vs staged: everything ships with the merge; no `.rvt`/`.rfa` committed, no viewer
  claim, no probe batch; `tekton-plugin.zip` and the three bench zips regenerated locally only
  (git-ignored / session scratchpad).
