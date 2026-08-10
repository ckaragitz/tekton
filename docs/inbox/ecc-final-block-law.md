# ecc-final-block-law — one page-walk law for every reader/checker of a CRCIO stream (issues #294, #236)

Stream: `eng294` (engineer session under the tech-lead session; branch
`cam/294-final-block-law`). Closes #294 (P1, verify gates) and #236 (P2, the
codec's own inverse) — one root cause. Refs #147 / PR #293 (where #294 surfaced),
#182 (whose sample-free round-trip test carried the `xfail` for #236), #75 / PR #128
(`unframe_stream`'s strict `ValueError` contract, kept).

## 1. The bug, computed rather than assumed

CRCIO's own geometry (`ecc.geometry` / `select_params`) makes every FINAL block of
**64,388..64,895 data bytes** (508 of the 64,896 possible tail lengths ≈ 0.78 % of
stream lengths) select the full-page class `(11, 0x500, 2047, 2)` and encode to
exactly `PAGE_STRIDE` = 65,249 bytes with a pad-count field of 1..508
(`encoded_size(64387) = 64,737`; `encoded_size(64388..64896) = 65,249`;
`tests/test_ecc_final_block.py::test_band_is_what_the_geometry_says` pins it).
By length alone that block is indistinguishable from a genuine full page.

Four places walked `len(raw) // PAGE_STRIDE` "full pages" and so took such a final
block for a page:

| where | effect on a stream whose last block is a padded stride |
|---|---|
| `ecc.unframe_stream` (the codec's inverse; `rvt.validate`-adjacent tools, `terminal_diff`, `layout_diff`, famgen's exactness probes) | returned data **+ 1..508 pad bytes**; `frame_stream(unframe_stream(raw)) != raw` |
| `commit.verify_written` | `page_trailer(first 64,896 bytes)` vs the block's parity (pad field ≠ 0 lives in trailer bytes 0/1) → **1 false `ecc_mismatches`** |
| `manipulate.verify_manipulated` | same → `structural FAIL` → `tools/rvt_job` / the front door label a healthy edit **`FAILED (structural)`, exit 3** |
| `reduce.verify_reduced` | already right — `reduce.unframe_exact` had found the law (R1s, a 64,875-byte final block) but kept it private |

The writer was never involved: the CRCIO-faithful validator (`tools/rvt_validate.py`,
syndrome-based) says 0 errors on the very files the gates failed, and they reopen with
every element.

## 2. What was built (reader/checker side only — no written byte changes)

`src/rvt/ecc.py`
* **`iter_blocks(raw)`** — the ONE law, the exact inverse of `frame_stream`'s emission
  order: yields `(block, is_final)`; a stride-sized block *followed by more bytes* is a
  full page; the LAST block (1..`PAGE_STRIDE` bytes) is always the final block, decoded
  by its pad-count field — which covers a genuine full page uniformly (pad 0 → 64,896).
* **`final_block_data_len(block)`** — the size class whose pad field decodes the block
  AND reproduces it byte-for-byte (`final_block_candidates` + exact re-encode, the check
  `unframe_stream` already did inline and `reduce._final_block_data_len` duplicated).
* `unframe_stream` rebuilt on the two (same strict `ValueError` on unframed input).
* **`framing_mismatches(raw)`** — the post-write self-check for streams WE framed: a
  full page whose trailer ≠ `page_trailer(payload)`, or a final block no class
  reproduces. `0 ⇔ frame_stream(unframe_stream(raw)) == raw`.

`src/rvt/commit.py::verify_written`, `src/rvt/manipulate.py::verify_manipulated`,
`src/rvt/reduce.py::verify_reduced` — their three hand-rolled page loops are now
`rep["ecc_mismatches"] += ecc.framing_mismatches(d.raw(name))` over
`(pname, "Global/ElemTable")` (both streams are re-framed by `frame_stream` on every
commit / commit_plans / reduce, so the exact writer's-inverse law is the right judge;
Autodesk-born partial blocks — heap bytes in the pad region, KNOWLEDGE "ECC SOLVED" —
are never in these two streams after our write and stay the syndrome validator's
business). `reduce.unframe_exact = ecc.unframe_stream` (one deframer in the engine;
`regadd`, `reduce_v2`, `versions/records32` keep importing the name).

Semantics that moved, on purpose: the verify_* gates now also judge the **final block**
(< stride) — before, a damaged final block of the partition/ElemTable was invisible to
them; `verify_reduced` counts per block instead of ≤ 1 per stream (only zero-ness feeds
`ok`). `container.depage` / `elemtable.deframe` are the documented junk-tolerant
depagers (true logical is a prefix; KNOWLEDGE "Logical-length convention") and were left
alone: on a padded stride they already return data + junk, exactly their contract.

## 3. Evidence (numbers)

**Synthetic (fresh clone):** `unframe_stream(frame_stream(s)) == s` for
`len(s) ∈ {0,1,7,300,5081,5082,64387,64388,64500,64895,64896,64897,129396,129792,194687,194688}`
(before: False for 64388, 64500, 64895, 129396, 194687 — data + pad returned);
`framing_mismatches == 0` on all of them, `== 1` for one flipped bit in a page trailer,
a page payload, the final block's parity or its data, `== 2` for two damaged blocks,
`== 1` for unframed junk; `ValueError` kept for junk / damaged final block.

**End to end on the tracked pinned bases (fresh clone, `tmp_path`):** a variant of each
base whose `Global/ElemTable` logical is zero-padded to 64,500 bytes (raw = exactly one
stride, pad field ≠ 0): `verify_manipulated` → `ecc_mismatches 0` on 2026/2025/2024
(before: 1), every other key equal to the untouched base; `verify_written` (2026) → 0
(before: 1); one flipped bit in the partition's page-0 trailer → exactly 1 in both
gates; one flipped bit in the partition's final block → 1 (before: 0, invisible).
`tests/test_ecc_final_block.py`: 39 passed on this head; **38 failed / 1 passed on
`origin/main`** (the e2e cases fail on the assertion, the rest on the missing law).

**The three pinned bases + real outputs, before → after (probe
`scratchpad/baseline.py`: verify_written under the file's own release, verify_manipulated,
frame∘unframe on every framed stream):**

| file | verify_written ecc/crc/walker | verify_manipulated ecc/crc/walker/isize | ElemTable = header | streams round-trip |
|---|---|---|---|---|
| G_ABPD.rvt (2026) | 0/0/0 → 0/0/0 | 0/0/0/0 → same | 3102 = 3102 | 9/9 → 9/9 |
| G_ABPD_2025.rvt | 0/0/0 → 0/0/0 | 0/0/0/0 → same | 3316 = 3316 | 9/9 → 9/9 |
| G_ABPD_2024.rvt | 0/0/0 → 0/0/0 | 0/0/0/0 → same | 3278 = 3278 | 9/9 → 9/9 |
| front door `--prompt "an electrical room 30 by 20 ft"` (`RVT_WALL_REP=dummy`), `Partitions/21` raw 195,235 (final block 64,387 data bytes — one byte under the band) | 0/0/0 → 0/0/0 | 0 → 0 | 3106 | 9/9 → 9/9; output **byte-identical** before/after; validation 0 err / 1 warn both |
| that file + `rvt_edit.py set-mark --id 1472525 --mark M` → raw **195,747 = 3 × 65,249** (the band, reached through the real product surface) | **1 → 0** | **1 → 0** | 3106 = 3106 | **8/9 → 9/9**; `rvt_validate`: 0 errors / 1 warning (known DataStorage decoder gap) both times |

**The product surface (rule 1 held throughout — the file was always delivered; only the
label was wrong):** `tools/frontdoor.py author --rvt prompt_room.rvt --edit "set mark of
element 1472525 to M"` — before: exit 3, `"ok": false`, `"status": "FAILED (structural)"`;
after: exit 0, `"ok": true`, `"status": "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"`,
edited `.rvt` **byte-identical** to the one main wrote, validation counts identical
(0/1/2). Bare unzip of the rebuilt `tekton-plugin.zip`, system `python3`, no repo on the
path: `go author --prompt "an electrical room with 6 panels"` → `ready: true`, `ok: true`;
`go author --rvt <band file> --edit "set mark …"` → `ready: true`, `ok: true`, output
byte-identical to main's.

## 4. Gates run (this head)

* `tests/test_ecc_final_block.py` (new, shard drop-in `tests/ci_shard.d/294-final-block-law.txt`)
  + `tests/test_ecc_encode.py` (xfail for #236 removed; round trip gains 64388, 64895,
  64896+64500, 3×64896−1, 3×64896): **283 passed**.
* Stream-local neighbours — `test_codec_bases test_commit test_ecc test_ecc_intel
  test_edit_own_release test_go_edit test_manipulate test_reduce test_reduce_law
  test_reduce_v2 test_regadd test_terminal_diff test_verify_manipulated_release
  test_bare_family_validate test_validate_footer_blob`: **186 passed, 73 skipped
  (all sample/ladder absence), 1 xfailed (#138, unrelated)**.
* `tools/sync_plugin.py` → 4 files mirrored, deny-audit clean, `--check` in sync;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths` ok
  (2861); `test_plugin_sync test_bootstrap test_coldstart test_surface_perf
  test_shard_list`: **51 passed, 5 skipped** (bare-numpy perf host gate).

## 5. Follow-ups (outside this territory — filed, not done here)

The same naive `len(raw) // PAGE_STRIDE` loop survives in three checkers this stream may
not touch (territory / hot file / another campaign's tree):

* `src/rvt/versions/records32.py::verify_manipulated32` (~l.397, the 2023-era edit gate;
  hot file) — same two re-framed streams, so it IS the two-line change
  `rep["ecc_mismatches"] += ecc.framing_mismatches(raw)`; its `verify_reduced32`
  (~l.310) is already right through `unframe_exact` and can become the same one line.
* `src/rvt/families.py::verify_rfa` (~l.734) and its copy
  `src/rvt/famgen/skeleton.py::verify_family_rfa` (~l.2499) loop over **every** framed
  stream of the file, including Autodesk-born streams copied verbatim whose final
  partial blocks leak heap bytes into the pad and never re-encode (KNOWLEDGE "ECC
  SOLVED") — so NOT `framing_mismatches` there: walk `ecc.iter_blocks(raw)` and
  trailer-check the `not is_final` blocks only (their `ecc_full_pages` counter = those).

And `rvt.validate.ecc_verify_stream` reaches the right *verdict* on a padded stride (a
valid codeword of the same geometry → zero syndromes) but hands downstream a logical with
the 1..508 pad bytes appended and counts the block as a page; adopting `iter_blocks`
there is a purity fix, not a verdict fix. Junk-tolerant depagers whose contract is
"logical is a prefix" (`container.depage`, `elemtable.deframe`, `partitions` l.136,
`writer.repage_like` / its informational counts) are correct as they are. → filed as **#394** (Refs #294).

## BRANCH STATE

* Branch `cam/294-final-block-law` from `origin/main` @ e5b7864.
* Files: `src/rvt/ecc.py`, `src/rvt/commit.py`, `src/rvt/manipulate.py`,
  `src/rvt/reduce.py`; mirrors `plugin/lib/src/rvt/{ecc,commit,manipulate,reduce}.py`
  (sync_plugin); `tests/test_ecc_final_block.py` (new), `tests/test_ecc_encode.py`,
  `tests/ci_shard.d/294-final-block-law.txt` (new); this record.
* Shipped: reader/checker law only; zero change to any written byte (pinned bases and a
  front-door output verified byte-identical). Nothing staged for the viewer (nothing to
  certify: no output changed).
* Gates: §4. /simplify and /verify run before the final commit (see PR body).
