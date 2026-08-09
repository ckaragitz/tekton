# RECORDS32-CI — the 32-bit record layer gets sample-free, per-PR coverage (issue #175)

Stream: **records32-ci** (2026-08-09, issue #175, branch `cam/175-records32-tests`,
engineer session `eng175` started by the tech-lead session's fan-out).

Charter (issue #175, Refs #108 / #17 / #132, PG4): `rvt.versions.records32` — the
reversible ~40-point patch set that puts the whole read/write stack into the
Revit ≤ 2023 32-bit-id era, and the `reading32` ladder the validator (#50) and the
readers (#121) go through — had no coverage a fresh clone or CI could run. The two
2023 test files run 16 tests and skip 41 off the owner's machine, only two of which
touch records32, and neither file is in `tests/ci_shard.txt`. A refactor of
`objects` / `encode` / `elemtable` / `manipulate` could break certified-2023 reading
with CI green.

**DONE (the issue's five bullets + shard + record):** new `tests/test_records32.py`,
33 tests, **32 passed / 0 skipped / 1 xfailed (strict) in 0.37 s** on a fresh cloud
clone (no `samples/`, no `extracted/`), listed in `tests/ci_shard.txt`. No file under
`src/` changed (test-only PR). Every fixture is synthetic — packed in the test with
`struct` from the wire law in `docs/writer/format-2023.md` §1; zero Autodesk bytes
(rule 3). The one real file opened is our own certified composed base
`plugin/assets/genesis/G_ABPD_2024.rvt`.

---

## 1. What the file covers (issue DONE → tests)

| DONE bullet | Tests | What is pinned |
|---|---|---|
| (1) synthetic 32-bit segments → framing + sentinels | `test_wire_constants`, `test_iter_records32_walks_records_then_sentinel[101/102/103]`, `test_iter_records32_flags_bad_trailer_and_stops_on_garbage`, `test_iter_records32_is_not_the_64bit_walker`, `test_validator_walker32_agrees_with_iter_records32[101/102]`, `test_parse_record_header32_and_spans[101/102/103]`, `test_assert_sentinel_tail32[101/102/103]`, `test_le_id_patterns32_and_scan_stream_ids32`, `test_emit32_roundtrips_through_iter_records32` | 8/12-byte headers, adler32 stamp, psize repeat → `trailer_ok`, sentinel = id −1 / psize 0 (stamp 1 on 102/103), walker stops on id < −1 / overrun / short header, `_iter_seg_records32` ≡ `iter_records32` (payload_off = seg_offset + hlen), `parse_record_header32.hdr_len` = raw + 4, `record_bytes32` / `_record_spans32` tile the segment exactly, the same bytes under the 64-bit walker do **not** yield the ids (fixture discriminates eras); under `ids32()` `Writer.element_id` / `Reader.element_id` are i32 and both `encode_record` entry points emit byte-identical 32-bit sentinels, 64-bit again outside |
| (2) ElemTable32 byte-exact round trip + INVALID_ID | `test_elemtable32_round_trip_is_byte_exact_and_normalizes_owner`, `test_elemtable32_is_not_the_64bit_codec`, `test_elemtable32_refuses_malformed`, `test_elemtable32_renumbered_row_round_trips_byte_exact`, **xfail** `test_elemtable32_row_order_follows_schema_m_id_first` | 6 + 28·n + 19 layout, owner `0xffffffff` ↔ `INVALID_ID` (never leaks the 32-bit value into the model), footer fields incl. pad byte, `encode(decode(p)) == p` for populated / empty / renumbered tables, 2023 payload refused by the 2024+ codec and vice versa while the *model* is shared, malformed inputs raise, ids ≥ 2³² refused on encode |
| (3) `is_ids32` on stub schemas | `test_is_ids32_on_stub_schemas`, `test_is_ids32_false_on_our_2024_base_schema` | stubs are real `rvt.schema.Schema`/`ClassDef`/`Field` objects; `m_id`/0x04 → True; `m_id64`/0x0b, wrong name, wrong kind, no class, empty fields → False; first field decides; G_ABPD_2024's real schema declares `m_id64`/0x0b |
| (4) `ids32()` swap / LIFO restore / exception / nesting | `test_patch_table_shape`, `test_ids32_swaps_every_patch_point_and_restores_lifo`, `test_ids32_restores_on_exception`, `test_ids32_nests_and_unwinds_in_order`, `test_activate_restore_pair_is_the_context_manager_contract`, `test_port2023_id32_is_the_same_context` | every (holder, attr) point unique and pre-existing (swap, never add), inactive at rest; inside: **every** point `is` its replacement, from-import rebinds (`mutate` / `families` `iter_records`, `stream_encoders.decode_elemtable`) move with the defining module, `partitions.RECORD_HDR_*` = 12/16, `elemtable.REC_SIZE/REC_FMT` = 28/`<7I`, footer len 19; after (normal exit, `RuntimeError`, three-deep nesting with an inner raise): every point `is` the original object again; `port2023.id32` is the same context |
| (5) `reading32(G_ABPD_2024)` | `test_reading32_on_2024_base_is_framing_only_and_restores`, `test_reading32_restores_partitions_on_exception`, `test_reading32_activates_ids32_iff_schema_declares_identifier_v1[2023/2024]` | yields exactly `KNOWN_RELEASES[2024].framing`, binds all six framing ordinals + the recomputed `TERMINATOR` into `rvt.partitions` while open, does **not** activate any ids32 point, and every watched `rvt.partitions` name (`rvt.versions._PATCHED_NAMES` + the three ids32 adds, so the leak check stays exhaustive by construction) is the identical object after exit, also after an exception inside; the branch is decided by the schema alone — with only `schema_of` monkeypatched to return a tiny *real* `rvt.schema.Schema` (six framing `ClassDef`s + `Identifier` v1/v2), the real `reading → ordinals_from_schema → activate` chain binds 2023 ordinals **and** enters ids32 for `m_id`/0x04, binds 2024 ordinals framing-only for `m_id64`/0x0b, restoring both times |

## 2. The one finding: ElemTable32 row order (strict xfail → #174)

`records32.parse_elemtable32` / `encode_elemtable32` read the 28-byte row as
`(original_id, id, ce, me, ue, partition, owner)`. The file's own schema (`ElemRec`
in the 2023 `Formats/Latest`: `m_id, m_history{orig, ce, me, ue}, m_partitionId,
m_OwningElementId`, `docs/writer/format-2023.md` §1 last row) and the reference
parser kept in `rvt.genesis.port2023.parse_elemtable_2023` put **`m_id` first**. The
two are byte-indistinguishable while `id == original_id`, which holds on every corpus
row (49,845/49,845 per port2023's note), so reading certified 2023 files is unaffected
and the round trip stays byte-exact either way
(`test_elemtable32_renumbered_row_round_trips_byte_exact` passes). It matters the day
we *write* a renumbered row for a 2023 target. Search-before-file found the fix
already chartered: **#174** ("…settles the one documented records32/port2023
disagreement (ElemTable32 row order: schema declares m_id first)…", territory
`src/rvt/versions/records32.py`, hot file). So no new issue was filed;
`test_elemtable32_row_order_follows_schema_m_id_first` is `xfail(strict=True)` citing
#174 and asserts the schema order — it flips to XPASS (and, being strict, fails the
shard) the moment #174 lands, forcing whoever lands it to delete the marker. Verified
with `--runxfail`: `assert (4096, 4099) == (4099, 4096)` — it fails for the stated
reason, not incidentally.

## 3. Gates (fresh cloud clone, Python 3.11, no samples)

```
.venv/bin/python -m pytest tests/test_records32.py -q -rs --durations=5
  32 passed, 1 xfailed in 0.37s   (slowest: 0.11s first ids32() = cold import of the patched stack, 0.07s schema_of(G_ABPD_2024))
.venv/bin/python -m pytest tests/test_versions.py tests/test_port2023.py tests/test_genesis_2023.py -q
  31 passed, 60 skipped in 0.16s   (unchanged from the issue's evidence run)
  + tests/test_records32.py in the same run (both orders): 63 passed, 60 skipped, 1 xfailed in 0.43s
  + tests/test_validate_release.py tests/test_versions.py after it: 54 passed, 19 skipped, 1 xfailed (no leaked state)
python3 tools/dev/check_portable_paths.py     ok
.venv/bin/python tools/sync_plugin.py --check  in sync (src/ untouched)
```
Shard cost: +0.4 s standalone (~0.2 s incremental, the import cost is shared with earlier shard files). `/simplify` ran on the diff (4 angles): findings applied — one `_bound`/`_assert_inactive` helper, partitions snapshot derived from `_PATCHED_NAMES`, real-`Schema` stubs so only `schema_of` is faked, incidental pins (`>= 40`, post-restore 64-bit literals, hex ordinals) replaced by comparisons against the captured state / `KNOWN_RELEASES`. `/verify`: skipped — tests-only diff (`tests/test_records32.py`,
`tests/ci_shard.txt`, this record), no runtime surface to drive.

## 4. Open questions / follow-ups

- #174 owns the row-order correction (and the creation-side 32-bit chokepoints); when
  it lands, drop the `xfail` marker here — the strict xfail will say so by failing.
- `verify_reduced32` / `verify_manipulated32` need a whole container (CFB + pages +
  gzip + partition stream); a synthetic one is buildable from `rvt.ecc` /
  `rvt.partitions` but is a bigger fixture than this S-sized issue — worth its own
  task once #17's compose gives a certified 2023 base to pin against.

## BRANCH STATE

- Branch `cam/175-records32-tests` from `main` @ c66333e; files written:
  `tests/test_records32.py` (new), `tests/ci_shard.txt` (+1 line),
  `docs/inbox/records32-ci.md` (this file). Nothing under `src/`, `tools/`,
  `plugin/`, `skills/`.
- Gates: above. Nothing staged for the viewer; no certification claim made or changed.
- Shipped vs staged: shipped = the test file in the CI shard; staged = nothing.
