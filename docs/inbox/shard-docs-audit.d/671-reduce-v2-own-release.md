# 671-reduce-v2-own-release -- `reduce_v2`'s public entries enter the file's OWN release themselves; a BARE `remove_units_v2` on the 2025 / 2024 pins writes #655's in-context bytes (shard-docs-audit stream, eng #671)

**Issue:** #671 (filed by eng #655 from its /simplify altitude pass; Refs #655 / PR #673 the end-record fix this completes,
#14 / O5 the 2025 lane, #93 the Global-stream tokens' home, #252 readers remembering their release -- the deeper cure).
**Date:** 2026-08-11. **Session:** eng #671 (cloud, `cse_012tcs5w`), started by the tech-lead session. **Base:** `main` @
`ea6b875` (#673 merged). Index `docs/inbox/shard-docs-audit.md` left untouched (README: optional; #636's hot spot).
Written in this engineer's voice; no other record edited.

## Why

#655 made `reduce_v2`'s partition end record follow the ContentMarker ordinal in force, so `remove_units_v2` wrote on
the 2025 / 2024 pins **inside the caller's `host_release_context`** -- and only there. `reduce_v2` was the one public,
path-taking engine surface that never entered the file's release itself: called bare on a foreign project every entry
died on the walker's first header check (`ValueError: unexpected Partitions header: v=9 cls=0x391` / `0x37b`), and the
read-only census `verify_content_coherence` / `python -m rvt.reduce_v2 --coherence FILE` had no caller to hold a context
for it at all (no production caller exists in `src/` / `tools/` / skills -- grep: tests + its own `--probes`). Every
sibling entry already does this: `famload.load_family_documents` → `host_release_context` (`famload.py:1125`),
`famload.four_registry_census` / `census.census` / `inventory` / `provenance` / `convert.rvt_to_ifc` →
`enter_own_release` on an `ExitStack`, `validate.validate_file`, `manipulate` (:1666).

## What landed -- entry wrappers only (`src/rvt/reduce_v2.py` + its `plugin/lib` mirror)

The path-taking public entries, listed, and the idiom each takes. The splice / rebuild / reconcile / census bodies are
byte-for-byte the old ones, moved under a private `_name` exactly as `famload.load_family_documents` /
`_load_family_documents` are split; inside `_remove_units_v2` the writer's own post-condition census is now spelled
`_verify_content_coherence(out_path)` -- i.e. exactly the un-laddered function it called before this PR, under the
source's release already in force (the output carries the source's `Formats/Latest` verbatim), so the writer's body
executes what it executed on `main` line for line.

| entry | reads / writes | idiom | why this one |
|---|---|---|---|
| `remove_units_v2(doc, guids, out, …)` | writes `Partitions/<N>`, rebuilds `Global/ContentDocuments` (famgen.factory tokens), re-encodes `Global/Latest` | `host_release_context(src)` around `_remove_units_v2` (lazy import, as famload) | the issue's DONE names it: the WRITE-side context every load / place / edit lane holds, keyed on the source; joins an active same-release context (`release_ctx._release_context`: "re-entrant: join, don't stack"); a native source enters nothing; a nested *different* foreign release is refused with the context's own sentence; an unreadable / uncertified source is the typed `UnreadableHost` / `ReleaseContextError` before anything is read, not a walker dump. `doc → src` resolution moved above the `with` (the context is keyed on the path) -- same two lines, same `ValueError`. **See "the one design call" below.** |
| `verify_content_coherence(path)` (also `--coherence FILE`) | read-only census of the four registries | `enter_own_release(stack, path)` on an `ExitStack`; `rep["release_note"]` = the rung (None = own schema) | the READ-side lenient ladder every instrument climbs (own schema → pinned table of the declared release → native constants), nest-safe inside any caller's context (LIFO restore), never raises for the rung. Key always present (`null` in the CLI JSON) so a reader sees the framing WAS settled, per the issue's DONE ("`release_note`: None when the own schema resolved it"). |
| `family_units(project)` | read-only (`families.FamilyIndex` walks the partition) | `enter_own_release(stack, project)` around `_family_units` | same ladder; returns rows, so no note slot -- docstring says so |
| `diff_old_vs_solved(old_out, base, source)` (`--diff`) | read-only, three files of ONE lineage (`source → base → old_out`, sample-derived, dev-only) | `versions.detect_release` on the three paths -- not one release → `ValueError` naming each file's year; then `enter_own_release(stack, base)`; `ev["release_note"]` | one context per call is the idiom and the body interleaves the three files' reads; the "one lineage, one release" premise is CHECKED (an attributed sentence) instead of a silent misread of the non-`base` files (/simplify altitude #4) |
| `build_probes` (`--probes`) | B1 / B3 / B4 through `remove_units_v2` (enter themselves), every probe's coherence via `verify_content_coherence` (enters itself), `_validate` via `validate_file` (enters itself); B2 (the OLD tool -- the control whose mechanics ARE the variable) and B5 (raw Latest reconcile of `R9B`) read the module's fixed native sample lineage `R9` / `R9b` and are left exactly as they were | a `host_release_context(R9B)` around B5 was in the first draft and dropped by /simplify (two angles): inert on its only, native input, and half a law (B2 writes too) -- the module docstring says the driver's lineage is native instead |
| `exact_partition_logical(path, stream)` | `open_rvt` + `ecc.unframe_stream` (CRCIO page trailers + final-block pad count) | **none** -- release-agnostic by construction (verified: `iter_blocks` is `PAGE_STRIDE` arithmetic, `final_block_data_len` a pad-count decode; no `rvt.partitions` ordinal, no schema) | wrapping it would be ceremony |
| `unit_ranges` / `splice_units` / `rebuild_content_documents` / `content_registry` / `reconcile_content_registry` | take BYTES / dicts, not paths | caller's context (unchanged) | nothing to key a context on; their path-taking callers above now hold it |

`from .global_framing import enter_own_release` is the module's one package import at load time: `global_framing` is
the leaf built for exactly this (imports `os/struct/contextlib` + `rvt._clause`; binds the famgen modules lazily at
entry; `-X importtime`: 0.65 ms cumulative, `import rvt.reduce_v2` 27 ms with the diff vs 34 ms at `main` = noise; no
frontdoor / skill / `go` path imports `reduce_v2`). `host_release_context` stays a lazy import inside the write entry,
as famload keeps it (nothing under `rvt.frontdoor` loads for a read). Error messages for genuinely unknown / unreadable
releases are `release_ctx`'s attributed sentences (`UnreadableHost.what` = "not a Revit container tekton can open";
"Revit N is not a certified creation release …"; "a Revit 2025 release context is active; cannot enter a Revit 2024
context for host2024.rvt inside it …") -- asserted in the new module.

**Nested / foreign contexts, said plainly (the idiom's behaviour, unchanged by this PR):** same-release active context →
joined (the outer context is left standing when the inner call returns: `active_release()` and
`partitions.CONTAINER_CLASS` still the year's, and a further same-release entry still yields the outer's very info
object); a different foreign release active → `ReleaseContextError`, outer context intact, nothing written; a *native*
(2026) source inside a foreign context → `host_release_context` is a no-op for a native file by design, so the caller's
foreign framing stays in force and the walker refuses the 2026 header -- the same caller error every lane has always
surfaced; the read ladder (`enter_own_release`) re-points framing to the file's own for its duration whatever is active
and restores LIFO.

### The one design call for the reviewer (raised by /simplify's altitude angle, measured, NOT taken)

`remove_units_v2` constructs nothing: every byte it emits comes from `rvt.partitions` ordinals read at call time, the
`famgen.factory` CD tokens `global_framing.bound` binds, and `encode_latest`, whose encoder is derived from the ADocument
decoder `bound(schema=)` installs -- none of the build context's encoder / constructor-singleton / port-layer /
standalone swaps is read on this path. **Measured: `_remove_units_v2` under the read-side strict context
`global_framing.reading(src)` alone writes the identical six digests** (`f4569244…` / `32341bb2…` / `4d841ea2…` /
`1d48e584…` / `199e0f07…` / `87720c3b…`). So `with global_framing.reading(src):` would be the lighter, equally correct
weight (nests under any release, would serve a 2023 file the day its ADocument codec round-trips, skips `resolve_base` +
the port import), at the price of the two things `host_release_context` gives and the issue's DONE asks for by name: the
typed `UnreadableHost` / `ReleaseContextError` sentence on garbage or uncertified input, and the policy that we do not
emit Global streams into a release we have not certified creation for. I built the DONE as written; switching is a
two-line change (`host_release_context(src)` → `GF.reading(src)`, and the typed-error test row goes) if the tech lead
prefers the lighter context -- the digests above say the bytes will not move either way.

## Evidence

**The bare-vs-wrapped sha table** (driver `drive671.py <outdir>` in the session scratchpad; input = #655's deterministic
fixture: each certified pin + ONE constructor-built `section_head_open` famload'ed with `uuid4` pinned to a counter and a
fixed basename, so the host digests ARE #655's `HOST_DIGEST`; "before" = `origin/main` @ `ea6b875`, "after" = this
branch's final diff (re-driven after /simplify: every cell identical to the pre-/simplify run); sha256[:16]; every "after"
digest is reproduced independently by the new test module and by #655's untouched one):

| pin (host sha16) | case | before: wrapped | before: BARE | after: wrapped | after: BARE |
|---|---|---|---|---|---|
| G_ABPD 2026 (`a6d27bfaf4b31a58`) | S4 `remove_units_v2(host,[guid])` | `199e0f07b2b33e5c` | `199e0f07b2b33e5c` | `199e0f07b2b33e5c` | `199e0f07b2b33e5c` **==** |
| | S4b `reconcile_adocument=False` | `87720c3b48997d76` | `87720c3b48997d76` | `87720c3b48997d76` | `87720c3b48997d76` **==** |
| G_ABPD_2025 (`d6b06ae72df4fc02`) | S4 | `4d841ea2a63fe1c9` | `ValueError: unexpected Partitions header: v=9 cls=0x391` | `4d841ea2a63fe1c9` | `4d841ea2a63fe1c9` **==** |
| | S4b | `1d48e58432f3c1bd` | same ValueError | `1d48e58432f3c1bd` | `1d48e58432f3c1bd` **==** |
| G_ABPD_2024 (`3ffab85827c48462`) | S4 | `f456924467c26cfc` | `ValueError: unexpected Partitions header: v=9 cls=0x37b` | `f456924467c26cfc` | `f456924467c26cfc` **==** |
| | S4b | `32341bb256b08e72` | same ValueError | `32341bb256b08e72` | `32341bb256b08e72` **==** |

Every written cell, before and after alike: `validate_file` **VALID, 0 errors** under its own release with **no
`release` fallback finding** (2026: 1 warning = the known DataStorage decoder gap, 2 info; 2025 / 2024: 0 warnings, 2
info); `reduce_law.check_files(host, out)` **EDIT-FREE removed 83 / added 0 / survivors edited 0** (rule 5: the
document's 83 records go with it, every survivor byte-identical; `git grep -n assert_edit_free src/rvt/reduce_v2.py` →
nothing, before and after -- the gate lives with the genesis callers, untouched: `git diff origin/main -- src/rvt/genesis
src/rvt/reduce.py src/rvt/reduce_law.py src/rvt/versions tools/` empty).

**The coherence census, bare** (`verify_content_coherence` / the module door with no context; the false-incoherence
case the issue names):

| file | before (main) | after |
|---|---|---|
| host2025 / host2024 (pin + 1 loaded document) | `ValueError: unexpected Partitions header: v=9 cls=0x391` / `0x37b` | `coherent True`, units 2, CD entries 1, ContentTable 1, FamilyMgr 1, `release_note None` |
| S4_2025 / S4_2024 bare outputs | same ValueError | `coherent True`, units 1, CD entries 0, tail junk 0, `release_note None` |
| host2026, S4_2026 | coherent (2/1 and 1/0) | identical, plus `release_note None` |
| `family_units(host2025)` bare | same ValueError | 1 row: unit 1, our GUID, `RW Section Head - Open`, category -2000400 |

**Tests -- `tests/test_reduce_v2_671.py` (new, 13 rows) + drop-in `tests/ci_shard.d/671-reduce-v2-own-release.txt`;
`no_release_leak` + `ladder_constants` module-wide; the `hosts` fixture and `HOST_DIGEST` / `OUT_DIGEST` are IMPORTED
from `test_reduce_v2_655` (one copy of the famload fixture -- #670's scaffolding law in spirit; that module stays
untouched and green):** bare == wrapped byte for byte per pin × {reconciled, registries-left}, 2026 included since its
documented use must not move (6): a real removal (units 2 → 1), the writer's own census coherent ⇔ reconciled,
`active_release() is None` right after the bare call, and == #655's `OUT_DIGEST` when the host is its pinned input;
the census bare on each FOREIGN host (2/1/1/1, coherent, `release_note None`), on the freshly reduced output re-read
outside the writer's context (1/0, tail junk 0), and `family_units` bare (2); the module door in a **child process**
(`python -m rvt.reduce_v2 --coherence host2024.rvt`, nothing but `src` on `PYTHONPATH`, the `test_estorage_cli_release`
shape) exits 0, empty stderr, prints `coherent true … release_note null` (1); an already-entered same-release context is
JOINED, by public observables only -- inside `host_release_context(host) as outer`: after `remove_units_v2` +
`verify_content_coherence` return, `active_release() == year`, `partitions.CONTAINER_CLASS` is still the year's, and a
further `host_release_context(host)` yields `outer` itself; None after exit; the joined write is the pinned digest (2); a
2024 removal inside a 2025 context is `ReleaseContextError("… is active; cannot enter …")` with the outer context intact
and nothing written (1); a text file named `.rvt` is `UnreadableHost` (a `ReleaseContextError`, `.what == "not a Revit
container tekton can open"`), not a walker dump (1).

- Gate suites (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider tests/test_reduce_v2_671.py tests/test_reduce_v2_655.py
  tests/test_reduce_v2.py tests/test_reduce.py tests/test_reduce_law.py tests/test_records_layout.py`): `origin/main`
  (new module absent) **49 passed, 25 skipped** → branch **62 passed, 25 skipped** (= main + the 13 new rows; identical
  skip list: absent `samples/` / genesis corpus). Plus `tests/test_conftest_scaffolding.py tests/test_plugin_sync.py`:
  27 passed.
- Whole merged shard, sequential, same VM: see BRANCH STATE.
- `tools/route.py matrix`: byte-identical to `origin/main` (39 lines, md5 `e9e2cc8d7f15`). `tools/sync_plugin.py`
  synced 1 file (`plugin/lib/src/rvt/reduce_v2.py`), deny-audit clean, `--check` in sync; `validate_plugin.py` PASS (25
  assertions); `check_portable_paths.py` ok; `shard_list.py --print` lists the new module (118 files).

## Findings / limits, stated

- Digests, VALID and EDIT-FREE are instruments on pins, not Autodesk's reader (rule 4): nothing here certifies that a
  2025 / 2024 project with a document removed *loads*; no viewer batch staged, no matrix cell changes.
- Behavioural differences outside "a bare call now works": the public census dicts (`verify_content_coherence`,
  `diff_old_vs_solved`) gain a `release_note` key (None on every pin); `remove_units_v2` on a non-container /
  uncertified-release source now fails FAST with the typed `ReleaseContextError` before any partition is touched (was:
  the container / walker layer's own error later); `diff_old_vs_solved` refuses a mixed-release triple with a sentence.
  `--coherence` on a non-container still ends in the container layer's traceback, as on `main` (the ladder never raises
  for the rung; an unopenable file was and is the container's error -- typing that for read instruments is #252 / #535
  territory, not an entry wrapper's).
- Seen in passing, not this issue's: a famload'ed host's exact partition stream carries 1.6–3.0 KB after its end record
  (`partition_tail_junk_bytes` 2609 / 2954 / 1672 on host{2026,2025,2024}; `partition_end_record_ok True`, and
  `remove_units_v2`'s `exact_tail` output has 0). Whether famload's writer should end the logical stream at the end
  record like Autodesk's own (+0) is a famload question with a viewer answer -- noted for whoever picks up the
  partition-tail thread; no issue filed from a passing observation without a failing reader.

## /simplify (four independent angles) -- taken / not taken

Taken: **simplification** -- the four function docstrings cut to one clause each (the module paragraph is the one home
of the idiom); the first test draft's derivable rows dropped (`detect_release(out)`, the join test's second bare write,
FOREIGN_FIRST → FOREIGN on the census row); the CLI row is ONE child process on `min(FOREIGN)` with `C.SRC`, not one per
year. **Altitude + simplification** -- the inert `host_release_context(R9B)` around B5 dropped (above).
**Altitude + reuse** -- the join test proves the join by public observables (`active_release`, `CONTAINER_CLASS`, the
re-yielded info) instead of counting the private `_codec_triple_from_base` / peeking `_ACTIVE`. **Altitude** --
`diff_old_vs_solved`'s one-lineage premise is checked. **Efficiency + altitude** -- the writer's post-condition census
calls `_verify_content_coherence` under the context it already holds (no second ladder climb / schema re-open on its own
fresh output, ~11 ms of ~300 ms; and byte-for-byte the pre-PR call).

Not taken, with the reason: **altitude #1** `GF.reading(src)` instead of `host_release_context(src)` for the writer --
measured equivalent, contradicts the issue's DONE by name; surfaced above as the reviewer's call. **Efficiency** -- the
`hosts` fixture is module-scoped in #655's module and imported here, so the 3-host famload (~2.5 s) runs once per module:
hoisting it session-scoped into `conftest.py` means editing #655's module (must stay untouched this round) and the
shared conftest for one more consumer; the day a third module wants it, hoist it as #670 did. **Efficiency** -- running
the wrapped call as the oracle in row 1 (6 × ~0.2 s) instead of comparing to `OUT_DIGEST` only: bare == wrapped in
bytes is the DONE's literal claim and survives an input re-pin; kept.

BRANCH STATE (cam/671-reduce-v2-own-release): `src/rvt/reduce_v2.py` (public `remove_units_v2` /
`verify_content_coherence` / `family_units` / `diff_old_vs_solved` become entry wrappers over private `_…` bodies; module
paragraph; one leaf import; the writer's post census under the held context; the lineage check), its mirror
`plugin/lib/src/rvt/reduce_v2.py` via `tools/sync_plugin.py`, `tests/test_reduce_v2_671.py` (new, 13),
`tests/ci_shard.d/671-reduce-v2-own-release.txt` (new), this fragment (new). Not touched: `src/rvt/versions/**`,
`global_framing.py`, `release_ctx.py`, `reduce.py`, `reduce_law.py`, `genesis/**`, `famgen/**`, `frontdoor/**`, any hot
file, #655's test module, the stream index. Gates: sha table above (2026 4/4 equal before/after; 2025 / 2024 bare:
exception → digest == wrapped digest, VALID 0, EDIT-FREE 83/0/0); gate suites 49/25 → 62/25; whole merged shard on the
final diff **2419 passed, 166 skipped, 2 xfailed, 3 warnings in 488 s** (118 files incl. the new module; skips = absent
`samples/` / corpora / ifcopenshell rows, as on `main`); `/simplify` RAN (above); `/verify` RAN -- `python -m
rvt.reduce_v2 --coherence` BARE on the six pin-derived files of the final drive: host{2026,2025,2024} → `coherent True`,
units 2, CD 1, ContentTable 1, FamilyMgr 1, end record ok, `release_note None`; S4_{2026,2025,2024}_bare → `coherent
True`, units 1, CD 0, tail junk 0, `release_note None`; `tools/rvt_validate.py S4_{year}_bare.rvt --json …` → `VALID (no
errors)` ×3 (2026 warnings=1 the known DataStorage decoder gap, 2025 / 2024 warnings=0, info=2, no `release` finding);
garbage `.rvt` → `remove_units_v2`: `UnreadableHost: … not a Revit container tekton can open (NotOleFileError …)`.
`tools/route.py matrix` byte-identical; `tools/sync_plugin.py` rebuilt + `--check` clean, `validate_plugin.py` PASS,
`check_portable_paths.py` ok. Nothing staged for the viewer; no certification claim; `tekton-plugin.zip` regenerated
locally, not committed.
