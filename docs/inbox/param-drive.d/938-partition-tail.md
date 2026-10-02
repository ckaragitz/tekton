# #938: does a project load carry stale ECC parity after the partition end record?

Branch `parity-938`, based on `origin/main` 1aa57d8 (#939 merged). Territory: the
two project loaders (`src/rvt/famgen/loader.py`, `src/rvt/famload.py`), one new
module (`src/rvt/partition_tail.py`), one new test module.

## The answer: yes, two generations per load, now fixed

Every project load added stale CRCIO parity as content after the partition end
record, twice:

- **Pass 1** (`commit.commit_new_elements`) splices into the host's de-paged
  stream and keeps the walker's `end_record`, which is everything from the end
  offset on. That includes the host's final-block pad-count and parity, which
  pass 1 then re-frames as content.
- **Pass 2** (`_commit_and_write`, and `famload` pass 2) re-read the pass-1
  file **de-paged** (`f.logical`). That added the pass-1 file's own final-block
  parity as a second generation.

How each check was made:

- **Exact tail.** The exact logical stream comes from `ecc.unframe_stream`:
  the final block's data length is decoded from its pad-count field and must
  re-encode byte for byte. The walker's `end_offset` is taken on that exact
  content, and the tail is everything from there on.
- **End record.** It is the release's own token (`FAMILY_END_RECORD` as bound
  by `global_framing`: `a303…`, `9103…`, `7b03…`). Every file was read under
  its own release (`enter_own_release`).
- **Walker and framing.** On every file below, the walker reports 0 errors
  and the expected unit count (base 1, one load 2, six panels 7), and
  `ecc.framing_mismatches` is 0.
- **Decomposition.** The before-fix load tail is the host's exact tail, then
  the host's de-paged parity, then the rest. I checked this with
  `startswith` on all three bases.

### Evidence table

Partition tails, in bytes after the 10-byte end record (`stray`). "Before" is
1aa57d8; "after" is this branch.

| Base / release / partition | Pristine base | Load (component loader, `place=False`): before | Added: host parity + pass-1 parity | After | Four-registry `famload` head: before → after | `add_to_project` (100 A panel, placed): before → after |
|---|---:|---:|---|---:|---:|---:|
| `G_ABPD.rvt` / 2026 / `Partitions/21` | 1,272 | 1,932 | 580 + 80 = 660 | **1,272** | 2,563 → **1,272** | 2,502 → 1,990 |
| `G_ABPD_2025.rvt` / 2025 / `Partitions/20` | 2,116 | 3,167 | 597 + 454 = 1,051 | **2,116** | 2,910 → **2,116** | 3,270 → 2,214 |
| `G_ABPD_2024.rvt` / 2024 / `Partitions/21` | 1,252 | 1,897 | 182 + 463 = 645 | **1,252** | 1,627 → **1,252** | 1,994 → 1,344 |

The `add_to_project` "after" still sits above the base: by 718, 98 and 92 B.
That remainder comes from the **placement** rewrite that follows the load (a
`mutate` pass, which is another writer and one generation). The loader's own
share is gone.

**The 6-panel `go author` project** (`frontdoor.py author --prompt "an
electrical room with 6 panels"`, 2026). Each stage's tail is shown, and each
stage's growth was decomposed the same way:

| Stage | Writer | Before | After | Generation(s) added (after) |
|---|---|---:|---:|---|
| base `G_ABPD.rvt` | n/a | 1,272 | 1,272 | n/a |
| `stage_P_identity` | project-info / identity rewrite | 1,852 | 1,852 | +580: the base's parity, one generation |
| `stage_L_loaded` (6 families, batch loader) | `load_families_into_project` | 2,540 | **1,852** | **0** (before the fix: +590 + 98) |
| `stage_W_walls` | `wallgeom` → `commit_new_elements` | 2,942 | 2,430 | +578, one generation |
| `prompt_room.rvt` (placement) | placement rewrite | 3,468 | 2,956 | +526, one generation |

All outputs pass `rvt_validate` with 0 errors, both before and after. The
2026 files carry the base's one DataStorage warning; the 2025 and 2024 files
carry 0 warnings. The `go author` status is `PROOF-ONLY (self-checks PASS)`.

### The tail is not a born law, but the certified lineage carries one

- **Revit-born streams.** `docs/writer/content-splice.md` (row 11, measured on
  all six project samples with `unframe_exact`) says a Revit-born
  project's exact partition **ends on** the end record, with 0 B after it.
  KNOWLEDGE §Storage says the same: "the writer must construct logical from
  decoded structures, never from `depage()`'s tail".
- **Our certified bases.** The three bundled bases are viewer-certified (see
  the ledger), and each carries 1,272, 2,116 or 1,252 B after the end record.
  That is accumulated junk from their composition, and the reader tolerated
  it.
- **Prior reader evidence.**
  - Tails both with and without such junk have passed the viewer before. The
    junk tail passed in K3, K4 and R0_identity (`add-path.md` §1.5) and in the
    viewer-certified load of a Revit-born `.rfa` onto `G_ABPD` (ledger:
    "THE BIRTH LAW CONFIRMED", through the old default path).
  - The exact tail passed in E_ALL (batch 42, verdict #36) and KD1.
  - Nothing has isolated the tail as a reader axis in either direction: E6
    failed only because it lacked the footer blob.

## The decision and why

The fix makes a load **keep the host's own tail byte for byte**, and drop the
stale parity both passes added. It does **not** cut to the end record.

- **Why not cut to the end record.** Cutting would also delete the certified
  bases' own 1.2–2.1 KB lineage tail. That changes certified-base bytes no
  load has any business touching, and no viewer evidence covers it on 2025 or
  2024. The nest path's exact cut (#939) is right for family hosts, whose
  generated tail *is* the bare end record.
- **Why this rule.** "Keep the host's tail" holds on both kinds of host:
  - A Revit-born project, whose exact tail is the bare end record, stays
    exact.
  - A certified base stays byte-identical to what was certified.
- **The invariants kept, measured on all three bases** (before vs after
  output):
  - Every stream other than the partition is **byte-identical**, including
    BasicFileInfo, ElemTable, ContentDocuments and Latest.
  - The partition's exact content up to and including the end offset is
    **byte-identical**.
  - The after-tail is a strict prefix of the before-tail, and equals the
    host's tail.
  - In other words, the only change in the file is that the stale suffix is
    gone.
- **Unknown host tail.** When the host's final block does not decode exactly
  (an Autodesk-born block with heap bytes in its pad region), the host tail is
  unknown. The pass-1 exact content is then kept whole and reported
  (`partition_tail.kept_host_tail = False`). Even then the pass-2 generation
  is gone, because the pass-1 file is read exactly.
- **Certification (hard rule 4).** The fixed outputs are **not certified**.
  They differ from viewer-passed outputs only by the dropped bytes, but a
  viewer round is required before any claim that they load. None was staged
  (per the task).
- **Byte pins.** No test pinned a project-load SHA. `test_famload_batch`'s
  `len(batch tail) <= len(chained tail)` still holds, since both now equal the
  base's tail. The #917 record's `d2ddb644…` SHA for the `G_ABPD.rvt` load is
  superseded **on purpose**: that file is now 512 bytes shorter in raw size
  (238,479 → 237,967).

## The check that keeps it from going unseen

`rvt.partition_tail.check_tail(path, expected)` checks two things:

- the tail must start on the release's end record;
- given `expected`, the tail must equal it.

`famgen.loader.verify_loaded_projects(..., host_rvt=)` and
`verify_loaded_project(..., host_rvt=)` now call it. Both loaders pass their
host. A mismatch is a named `file_errors` entry:
"partition tail: N B != the host's M B (stale parity carried as content)".

`famload.verify_loaded_project(..., host_rvt=)` makes the same check. It skips
the host comparison when pass 3 (usage repointing, a `manipulate` rewrite) has
rewritten the file. A tail that cannot be judged is reported, not failed.

## Tests: `tests/test_partition_tail_938.py` (10)

Every test runs under the `no_release_leak` guard, with the extended
`release_leak_extra` from `test_famload_2025`.

- Each bundled base starts its tail on its release's end record and carries
  its measured lineage tail (×3).
- A component-loader load into each base keeps the host tail, reports the
  stale bytes it dropped, and passes the verifier's tail check (×3).
- A chained second load and a two-family batch load both keep the **base's**
  tail, so no generation accumulates.
- The four-registry `famload` lane keeps the host tail.
- The verifier names a stale suffix. The file is built with conftest's
  `rewrite_stream`, frames 97 junk bytes after the host tail, and is caught as
  `partition tail: …`. Without `host_rvt`, only the end-record check runs.
- An unjudgeable host tail or a foreign tail is never trimmed, and an
  unframed stream has no exact tail.

## Gaps and follow-ups

1. **No viewer verdict on the fixed outputs** (hard rule 4). The change is a
   strict byte removal of junk the reader never needed (the exact-tail E_ALL
   and KD1 passed). Even so, the claim "they load" waits for a round.
2. **Other writers still add one generation each.** These are the
   identity/project-info rewrite (stage P), `commit_new_elements` callers
   (walls via `wallgeom`, `mep/*`), `manipulate` / `mutate` placement, and
   `famload` pass 3. On the 6-panel project they still add 580 + 578 + 526 B.
   `commit_new_elements` reads `doc.logical()` and keeps the walker's
   `end_record` whole. The same keep-the-host-tail rule
   (`rvt.partition_tail.keep_host_tail`) applies to each of them, but they are
   shared writers outside this territory. **Follow-up issue to file:** "every
   project rewrite keeps the host partition tail (commit / manipulate /
   mutate / identity)".
3. **The certified bases' own lineage tail** (1.2–2.1 KB) is not a born law.
   Removing it from the bases would be a base change and needs its own
   certified round. It is not proposed here.
4. **Autodesk-born hosts.** A user's Revit-born project whose final block
   does not decode exactly has no samples here (`samples/` is absent). The
   fallback (`kept_host_tail = False`, the tail reported unjudged) is
   unit-tested, not exercised on a real foreign file.

## Review of #942 (🟡)

- **Fallback fixed.** A pass stream that does not decode exactly now returns de-paged
  and whole, as the writers read it before this change. Previously
  `ecc.unframe_stream` raised there. The branch is unreachable today, since
  `commit.py` always frames, but it is now pinned by a test.
- **Why the tail is kept, not cut.** #938's DONE (2) said "write exactly what the nest
  path writes", which would cut at the end record. Keeping the host's lineage tail is a
  deliberate deviation, accepted at merge. The reason is that cutting would also remove
  the certified bases' own tail, which no 2025/2024 viewer evidence covers.
  `docs/writer/content-splice.md` row 11 also flags mixed zero+parity tails as an
  unproven reader axis (D2). Keeping the host's tail stays on the certified side of
  that axis.
- **Test totals.** This record's 168 and the PR's 208 come from different file sets.
  Both are 0 failed.

## BRANCH STATE (`parity-938`)

**Files written**

- `src/rvt/partition_tail.py` (new): `exact_tail`, `host_tail`,
  `keep_host_tail`, `check_tail`.
- `src/rvt/famgen/loader.py`:
  - `_commit_and_write`: the project path keeps the host tail; the docstring
    says so;
  - `proofs["partition_tail"]`;
  - `verify_loaded_projects` / `verify_loaded_project(host_rvt=)` with the
    tail check.
- `src/rvt/famload.py`: pass 2 keeps the host tail;
  `verify_loaded_project(host_rvt=)` has the tail check.
- `plugin/lib/src/rvt/{partition_tail.py,famgen/loader.py,famload.py}`: sync
  mirrors.
- `tests/test_partition_tail_938.py` and
  `tests/ci_shard.d/938-partition-tail.txt` (new).
- This record.

**Gates** (counts are in the commit report)

- `tools/sync_plugin.py`, then `--check`: in sync (deny-audit clean, identity
  scan == allowlist).
- `plugin/scripts/validate_plugin.py`: PASS (25).
- `pytest`:
  - **168 passed, 30 skipped, 0 failed** over `test_partition_tail_938`,
    `test_famgen_loader`, `test_famgen_loader_release_700`, `test_famload`,
    `test_famload_2025`, `test_famload_batch`,
    `test_famload_determinism_794`, `test_famload_fix`, `test_nest_917`,
    `test_nest_locks_917`, `test_trapeze_nested_917`,
    `test_build_latency_932` and `test_conftest_scaffolding`. The skips are
    sample/ladder-gated: `samples/` is absent.
  - **17 passed** over `test_surface_perf` and `test_plugin_sync`.
- Bare unzip of `tekton-plugin.zip` with system `python3`, running
  `go author --prompt "an electrical room with 6 panels"`: READY, job 6.8 s.
  The stage-L tail equals the stage-P tail (1,852), matching the repo run.

**Staged / shipped**

Nothing is staged for the viewer. Nothing is certified.
