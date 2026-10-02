# #941: every project-rewriting writer keeps the host's partition tail

Branch `tail-941`, based on `origin/main` 60823f0. It follows #938/#942
(`938-partition-tail.md`). Those changes made the two project **loaders** keep
the host's exact partition tail. The other writers that rewrite a project's
partition still added one generation of stale CRCIO parity each.

## What was wrong

Each of these writers read its source partition **de-paged**
(`doc.logical(pname)`) and kept the walker's `end_record` whole:

- the identity stage;
- `commit_new_elements` (walls, equipment);
- the mep writers;
- placement.

A de-paged stream's `end_record` is the host's exact tail followed by the
source's final-block pad-count and parity. So every rewrite re-framed that
parity as content, adding one generation per stage. On the 6-panel project
(2026) that was +580 B at stage P, +578 B at W and +526 B at placement.

## The fix

One rule, in one place: `rvt.partition_tail.writer_logical(doc, pname)`.

- It returns the **exact** logical stream (`ecc.unframe_stream`). The
  walker's `end_record` is then the host's exact tail, and
  `out[:end_offset + len(end_record)]` keeps it byte for byte.
- When the final block does not decode exactly (an Autodesk-born block with
  heap bytes in its pad region), it falls back to the de-paged read, which is
  what every writer did before. The report says `exact: False`.

As in #938, the host's tail is **kept**, not cut to the end record. The
certified bases' own lineage tail (1,272 / 2,116 / 1,252 B) is therefore
untouched.

Each writer's report now carries `partition_tail`, which records `exact`,
`host_tail_bytes` and `kept_host_tail` (an in-memory check that the
re-walked `end_record` equals the source's).

Each writer's own verifier now runs `partition_tail.tail_verdict(path,
host_rvt, partition)`:

- It is `check_tail` under the written file's own release.
- The tail must start on the release's end record.
- Given the host, the tail must equal the host's exact tail.
- A mismatch is reported as `partition_tail_defect`, worded "partition tail:
  N B != the host's M B (stale parity carried as content)".

### Per writer

| Writer | Status | How it is verified |
|---|---|---|
| `commit.commit_new_elements` (walls via `ifc_intent.stage_walls` and `wallgeom.build_walls_file`; equipment/placement via `ifc_intent.stage_equipment`; `mep.views_spaces.commit_elements`; `genesis.types`; loader / `famload` pass 1) | **fixed** | `verify_written(..., host_rvt=)`. `ifc_intent._commit_summary` and `wallgeom`'s `structurally_valid` now fail on a judged tail mismatch. `ifc_intent`, `wallgeom` and `genesis.types` pass their host. |
| `manipulate.commit_plans` (stage P identity, stage D levels, edits, `convert.edit_family` / `modify_family`, `famload` pass 3 `repoint_usage`, `mep` modify/delete plans) | **fixed** | `verify_manipulated(..., host_rvt=)`. Stage P and stage D require `kept_host_tail` in their `ok` (in memory, no extra read). `famload.repoint_usage` verifies against its source. |
| `mep.conduit.commit_created` | **fixed** | `verify=True` runs `verify_written(..., host_rvt=src)`. |
| `mep.electrical_data.commit_electrical` | **fixed** | `verify_electrical(..., host_rvt=)`. `structurally_valid` fails on a judged tail mismatch. |
| `famload` final verification | **tightened** | Pass 3 now keeps its source's tail, so `verify_loaded_project` always compares against the host. Before, it skipped the comparison when pass 3 had rewritten the file. |
| `famgen.loader._commit_and_write` pass 2, `famload` pass 2 | unchanged (#942) | `keep_host_tail` now drops 0 B, because pass 1 no longer adds any. `loader.py` was not edited. |
| `regadd` (2026-era creation) | n/a, already exact | It has read `unframe_exact` since K1. |
| `reduce.delete_elements` | **not changed**, by decision | It is the genesis **composition** instrument (`tools/genesis_*.py`) that built the certified bases with their lineage tails. Changing its output would break byte-reproduction of those certified compositions. It is not a product path. `reduce_v2` already offers an `exact_tail` opt-in. |
| family writers (`famgen.geometry.emit_form_rfa`, `families.emit_rfa`, `famgen.skeleton`, `convert.rfa_assemble`, nest) | n/a | They write `.rfa` families, not project rewrites. A generated family's tail is the bare end record (#939). |
| `adocument.write_with_latest`, `identity` streams, ElemTable / Latest / ContentDocuments framing | n/a | They frame non-partition streams from decoded payloads, with no carried tail. |
| `tools/genesis_*`, `k1_autopsy`, probes | n/a | Campaign and dev instruments. They inherit the fix wherever they call `commit` or `manipulate`. |

## Evidence

All counts are bytes after the 10-byte end record in the exact partition.
"Before" is 60823f0, "after" is this branch. Outputs were run under each
base's own release with `SOURCE_DATE_EPOCH` pinned.

### Each writer, once on each bundled base

| Writer | 2026 `G_ABPD` (base 1,272) | 2025 `G_ABPD_2025` (base 2,116) | 2024 `G_ABPD_2024` (base 1,252) |
|---|---:|---:|---:|
| stage P `commit_plans` | 1,852 → **1,272** | 2,713 → **2,116** | 1,434 → **1,252** |
| `commit_new_elements` (1 element) | 1,852 → **1,272** | 2,713 → **2,116** | 1,434 → **1,252** |
| `commit_electrical` (1 element) | 1,852 → **1,272** | 2,713 → **2,116** | 1,434 → **1,252** |
| `conduit.commit_created` (1 element) | 1,852 → **1,272** | 2,713 → **2,116** | 1,434 → **1,252** |
| loader load (`place=False`, #942) | 1,272 → 1,272 | 2,116 → 2,116 | 1,252 → 1,252 |

The same holds for all 15 pairs:

- Every stream other than the partition is **byte-identical** before vs
  after, including BasicFileInfo, ElemTable and Latest.
- The partition's exact content up to and including the end record is
  **byte-identical**. The only change is the dropped stale suffix.
- `ecc.framing_mismatches` is 0 on the new partition, so the last block's
  parity was recomputed by `frame_stream`.
- `rvt_validate` reports 0 errors both before and after. Warnings are
  unchanged: one DataStorage warning on 2026 (the base's own), 0 on 2025 and
  2024.
- The loader-load output is byte-identical as a whole file. The loaders
  changed nothing.

### The 6-panel `go author` project, per stage

`frontdoor.py author --prompt "an electrical room with 6 panels"`:

| Stage | 2026 before | 2026 after | 2025 before | 2025 after |
|---|---:|---:|---:|---:|
| base | 1,272 | 1,272 | 2,116 | 2,116 |
| `stage_P_identity` | 1,852 | **1,272** | 2,713 | **2,116** |
| `stage_L_loaded` | 1,852 | **1,272** | 2,713 | **2,116** |
| `stage_W_walls` | 2,430 | **1,272** | 2,929 | **2,116** |
| `prompt_room.rvt` (placement) | 2,956 | **1,272** | 3,417 | **2,116** |

The same holds per stage, before vs after:

- Other streams are byte-identical.
- The partition head (up to the end record) is identical.
- `framing_mismatches` is 0.
- Validation is 0 errors, with the same warnings (2026: 1 DataStorage; 2025:
  0).
- Status is `PROOF-ONLY (self-checks PASS)` with 0 errors and 0
  degradations.

The job took 6.4 s after vs 7.1 s before on 2026, and 11.5 s vs 11.8 s on
2025. These are single runs, within noise, and make no speed claim.

### Bare unzip

- Setup: `tekton-plugin.zip` unzipped, system `python3` 3.11.15, run as
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "an
  electrical room with 6 panels"`.
- Result: **READY**, with a job time of 7.1 s.
- All four stage files end on the base's 1,272 B tail with
  `framing_mismatches` 0.

## Tests: `tests/test_partition_tail_941.py` (11)

Every test runs under the `no_release_leak` guard, with the extended
`release_leak_extra` from #938.

- **`commit_plans` (stage P)**, on each base (×3): the host tail is kept, and
  `verify_manipulated(host_rvt=)` reports `equals_host_tail`.
- **`commit_new_elements`**, with one real element on each base (×3): the
  host tail is kept, and `verify_written(host_rvt=)` reports
  `equals_host_tail`.
- **A P → commit → P chain** keeps the **base's** tail, so no generation
  accumulates.
- **`commit_electrical` and `conduit.commit_created`** keep the host tail and
  their verifiers judge it.
- **Stale parity is named by the verifiers.** 97 framed junk bytes are added
  after the host tail (conftest `rewrite_stream`):
  - `verify_manipulated` names `partition_tail_defect`;
  - `verify_written` flags it;
  - `verify_electrical` is not `structurally_valid`;
  - without the host, only the end-record check runs.
- **The `writer_logical` fallback**: a stream that does not decode exactly
  comes back de-paged with `exact: False`.
- **End to end** (`@slow`): the 6-panel `go author` (2026) runs, and the P,
  L and W stages and the output all end on the base's exact tail.

One #938 assertion was re-pinned. `test_project_load_keeps_the_host_tail` had
asserted `stale_bytes_dropped > 0`. That count is now `== 0`: pass 1 no longer
adds a generation, so pass 2 has nothing left to drop.

## Certification (hard rule 4)

**No viewer verdict exists for the fixed outputs.**

- Nothing was staged and nothing is certified.
- The outputs differ from the earlier, uncertified outputs of the same
  writers only by the dropped stale suffix.
- Their tail is now byte-identical to the certified base it descends from.
- Even so, "they open" waits for a viewer round.

## Gaps

1. **No viewer round** was run on the fixed outputs (see above).
2. **`reduce.delete_elements` still re-frames a de-paged tail.** This is
   deliberate: it is the genesis composition instrument, and changing it
   breaks byte-reproduction of the certified bases (see the per-writer
   table). A future re-composition that wants exact tails should use
   `reduce_v2`'s `exact_tail`.
3. **The Autodesk-born fallback is not exercised on a real file.** A host
   whose final block does not decode exactly takes the de-paged read, with
   `exact: False` and the tail unjudged. The fallback is unit-tested only,
   because `samples/` is absent here.
4. **Some verifiers cannot compare against the host when no host is passed.**
   They then check only that the tail starts on the end record. This applies
   to `verify_written` called without `host_rvt` from the loader file
   verifier (which compares on its own, #938) and from `tools/` probes.
5. **`verify_written` now opens the file once more.** It reads the partition
   raw and the schema for the release to run `tail_verdict`. The job times
   above show no measurable cost, but that is not a benchmark.

## Review of #946 (🟡; fixed in this PR)

- **`tools/rvt_edit_text.py` was missing.** It ships as the tekton-native skill script,
  read de-paged, and added one stale generation. It now reads through `writer_logical`.
  `test_edit_text_release.py::test_a_text_edit_keeps_the_hosts_partition_tail` checks
  this on 2026, 2025 and 2024. Without the fix that test fails: a 1,862 B tail against
  the host's 1,282 B on 2026.
- **The 2023 verifier's signature.** Inside `ids32()`, `verify_manipulated` is rebound to
  `verify_manipulated32`, which lacked `walked=` and `host_rvt=`. #941's callers
  (`verify_electrical`, `famload.repoint_usage`) would raise `TypeError` there. It now
  accepts both. The 2023 tail check is not ported, so the report says
  `"not checked (2023 era)"` rather than claiming one. A signature-parity test covers it.
- **`partition_tail` docstring.** It no longer names a non-existent
  `reduce.reduce_elements`, and it says `reduce.delete_elements` is deliberately
  unchanged.
- **Genesis composition.** No composition path touches the changed writers:
  `reduce.delete_elements` is unchanged, and `GenesisCatalog.commit_into` has no caller.
  The `samples/`-gated reproduction tests could not run in a fresh clone.
- **Measurement correction.** The reviewer measured W-before on 2026 as 2,432 B on base
  main, not 2,430. That is a before-number only.

## BRANCH STATE (`tail-941`)

**Files written**

- `src/rvt/partition_tail.py`: adds `writer_logical`, `tail_verdict` and
  `tail_defect`; the docstring extends the law to every writer.
- `src/rvt/commit.py`:
  - `commit_new_elements` reads the source exactly;
  - `CommitReport.partition_tail`;
  - `verify_written(host_rvt=)` with the tail verdict.
- `src/rvt/manipulate.py`:
  - `commit_plans` reads the source exactly;
  - `ManipCommitReport.partition_tail`;
  - `verify_manipulated(host_rvt=)` with the tail verdict.
- `src/rvt/mep/conduit.py`: `commit_created` reads the source exactly, and
  its `verify=True` path passes the host.
- `src/rvt/mep/electrical_data.py`:
  - `commit_electrical` reads the source exactly;
  - `ElectricalCommitReport.partition_tail`;
  - `verify_electrical(host_rvt=)`;
  - `structurally_valid` includes the tail.
- `src/rvt/famload.py`: the final verify always compares against the host;
  `repoint_usage` verifies against its source.
- `src/rvt/frontdoor/project_info.py` and `src/rvt/frontdoor/levels.py`: the
  stage `ok` requires `kept_host_tail`, and the record carries it.
- `src/rvt/render/wallgeom.py`, `src/rvt/genesis/types.py` and
  `tools/ifc_intent.py`: pass the host to `verify_written`;
  `_commit_summary` and wallgeom's `structurally_valid` include the tail.
- `plugin/lib/**` and `plugin/skills/tekton-author/scripts/ifc_intent.py`:
  sync mirrors.
- `tests/test_partition_tail_941.py` and
  `tests/ci_shard.d/941-partition-tail.txt` (new); one assertion re-pinned in
  `tests/test_partition_tail_938.py`.
- This record.

`src/rvt/famgen/loader.py` was **not** edited.

**Gates**

- `tools/sync_plugin.py`, then `--check`: in sync (deny-audit clean,
  identity scan == allowlist, assets verified).
- `plugin/scripts/validate_plugin.py`: PASS (25).
- pytest, group 1: **198 passed, 51 skipped, 0 failed**, in 105 s, over:
  - `test_partition_tail_941` and `test_partition_tail_938`;
  - `test_famgen_loader` and `test_famgen_loader_release_700`;
  - `test_famload`, `test_famload_2025`, `test_famload_batch`,
    `test_famload_determinism_794` and `test_famload_fix`;
  - `test_commit`, `test_manipulate`, `test_manipulate_import_context` and
    `test_mutate`;
  - `test_identity_helper_657` and `test_electrical`;
  - `test_render_wallgeom`, `test_build_latency_932` and
    `test_conftest_scaffolding`.

  The skips are gated on `samples/` or ladders, which are absent here.
- pytest, group 2: **254 passed, 20 skipped, 1 xfailed, 0 failed**, in
  155 s, over:
  - `test_frontdoor`, `test_frontdoor_209`, `test_frontdoor_json_strict`,
    `test_frontdoor_manifest_pin`, `test_frontdoor_standalone` and
    `test_frontdoor_wallsolid`;
  - `test_surface_perf`, `test_plugin_sync`, `test_bootstrap`,
    `test_coldstart` and `test_coldstart_locale_210`;
  - `test_reduce` and `test_reduce_law`.
- Bare unzip `go author` 6-panel: READY.

**Staged / shipped**

Nothing is staged for the viewer. Nothing is certified.
