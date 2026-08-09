# identity-g2-prep — G2 identity rungs on the pinned composed bases (#134 → #19)

Stream: `identity-g2-prep` (engineer session `eng134`, 2026-08-09). Issue #134
(P1, fresh-clone child of #19). Territory: `tools/genesis_identity.py` (new),
`tests/test_genesis_identity.py` (new, in `tests/ci_shard.txt`),
`experiments/identity_g2/**` (json only; `.rvt` git-ignored),
`experiments/acceptance/batch_{60,61,62}.json` (STAGED manifests), this record.
Engine used read-only; `PRODUCT_AUTHOR_PLACEHOLDER` untouched (hard rule 6);
no pin / ledger / bundle / KNOWLEDGE change (those are #19's after PASS).

## What was built

`tools/genesis_identity.py` — one tool, four verbs:

| verb | does |
|---|---|
| `build --release {2026,2025,2024,all} [--with-guid]` | from the sha-verified pinned base of each release (`rvt.frontdoor.base.PIN` slots → `plugin/assets/genesis/G_ABPD*.rvt` on a fresh clone) writes `experiments/identity_g2/<year>/I_{all,bfi,dit,pi,td}[,_guid]_<year>.rvt`, asserts every rung (below), writes `<year>/rungs.json` and the stream-wide `experiments/identity_g2/probes.json` |
| `check` | re-runs the assertions on built rungs |
| `gate [--stage] [--batch N]` | `tools/probe_batch.py check` (default) / `stage`, one batch per release: `I_all` as `--candidate-base`, the singles as probes, `--manifest experiments/identity_g2/probes.json`; the control is cut from the pinned base of that release (sha256 alias rule, #131/#263) |
| `ready [--batch N]` | **#19's one command** = `build` + `gate --stage` for every release; `--batch 60` reproduces the committed `batch_60..62.json` md5-for-md5 on any machine |

Rungs (each = the pin's CFB entries with ONLY the named stream(s) replaced —
`read_entries` → `dataclasses.replace` → `write_cfb`, the `rvt.commit` write
pattern; `write_cfb(read_entries(pin))` reproduces all three pins byte-for-byte,
so any diff is the edit):

| rung | stream(s) rewritten | mechanism (all pre-existing engine functions) |
|---|---|---|
| `I_bfi` | `BasicFileInfo` | `rvt.identity.own_basic_file_info(raw, out_path=<pinned basename>, username='', document_guid=<CURRENT guid>)` — author/client = `PRODUCT_AUTHOR_PLACEHOLDER` (`rvt-writer`, the existing constant; counsel C1 decides the final string), `last_save_path` = `G_ABPD[_20xx].rvt`, nil central/model identity, version marker + increments + GUID kept (== `Global/History[0]`), mirror text regenerated. Exactly what `rvt.commit` does on every certified front-door output. |
| `I_dit` | `Global/DocumentIncrementTable` | `rvt.identity.own_increment_table_stream(raw, prefix, inflated, username='')` — every save-episode username in both copies → `''` (what `rvt.commit` writes); row count, counters, sequence untouched. |
| `I_pi` | `ProjectInformation` | our PartAtom ZIP: one member `Revit<document_guid>.project.xml` (no directory), our `rvt.genesis.house_standard.PROJECT_INFO` values, `<A:product-version>` = the release, fixed `updated`/DOS date (2026-08-09T12:00:00Z) for reproducible hashes. Same vocabulary as `tools/genesis_assemble.our_project_information_zip` (G0), parameterised by release and kept import-free (that module exec-loads the reduction driver). |
| `I_td` | `TransmissionData` | minimal: each `ExternalFileReference`'s `LastSavedAbsolutePath` := its own relative `LastSavedPath`; every reference, element id (86291 KeynoteTable, 1218726 AssemblyCodeTable, 1250029 RvtLinkSymbol), path type and load state kept exactly; u32 UTF-16 count re-framed. |
| `I_all` | the four above | = the **candidate base** for #19's re-pin |
| `I_guid` (opt-in `--with-guid`) | `BasicFileInfo` + `Global/History` | higher-risk: NEW document GUID (deterministic uuid5 of the base sha256) written to BFI unique/central episode GUID **and** History entry 0 together (the `streams_edit` cross-check invariant; `validate.py` L2 error otherwise); refuses to run unless both codecs are byte-exact on the base. Not staged in batches 60–62. |

Per-rung assertions (tool + tests): changed-stream set == intended and every
other directory entry identical (data, CLSID, state bits, FILETIMEs);
`rvt.validate.validate_file` (enters the file's own release) → 0 errors and
`detect_release` == the year; `rvt.provenance.identity_report` violations;
decode round-trips (BFI fields, DIT usernames/copies, PI member names, TD
paths, BFI GUID == History[0]); a byte scan of every stream's raw / de-paged /
inflated bytes for the eight inherited employee usernames
(`rvt.provenance.AUTODESK_EMPLOYEE_USERNAMES`) + absolute foreign path stems,
case-insensitive, UTF-8 and UTF-16LE.

## The facts this started from (fresh clone, 2026-08-09)

`tools/provenance.py plugin/assets/genesis/G_ABPD*.rvt --baseline all --streams`
→ `4 identity violation(s)` on each pin: `author`, `client_app_name`,
`last_save_path`, `DocumentIncrementTable.username`. Decoded (`rungs.json` →
`base.identity`; `<employee>` = an Autodesk sample maintainer's login, not
repeated here):

| surface | G_ABPD (2026) `84173b89…` | G_ABPD_2025 `6242c3aa…` | G_ABPD_2024 `e4a40671…` |
|---|---|---|---|
| BFI author / client | `Autodesk Revit` / `RevitApplication` | same | same |
| BFI build | `20250227_1515(x64)` | `Development Build` | `20230308_1635(x64)` |
| BFI username | `''` | `''` | `''` |
| BFI last_save_path | `C:\Users\<employee>\Desktop\Downloadable Files\rstbasicsampleproject.rvt` | same | `C:\Users\<employee>\Desktop\Revit - 190062 Update Sample Files\2024\rstbasicsampleproject.rvt` |
| BFI document GUID (== History[0]) | `34447475-…` | `527cedc9-…` | `badabcab-…` |
| DIT save episodes / distinct employee usernames | 22 / 8 | 21 / 8 | 22 / 7 |
| PI zip member name | `C:\Users\<employee>\AppData\Local\Temp\<guid>\Revit<guid>.project.xml` | same shape | same shape |
| PI title / Client / product-version | `rstbasicsampleproject` / `Autodesk` / 2026 | … / 2025 | … / 2024 |
| TD LastSavedAbsolutePath ×3 | `C:\Users\<employee>\Desktop\Downloadable Files\{RevitKeynotes_Metric,UniformatClassifications}.txt`, `C:\..\Desktop\rac_basic_sample_project.rvt` | `C:\ProgramData\Autodesk\RVT 2025\Libraries\…\*.txt` ×2, same link | `C:\ProgramData\Autodesk\RVT 2024\Libraries\…` ×2, `C:\Desktop\rac_…rvt` |
| byte-scan hits OUTSIDE the four streams | none | `Partitions/20` member 4: `<employee>`, `C:\Users\`, `ProgramData\Autodesk`, `OneDrive - Autodesk` (1 each) | `Partitions/21` member 4: same |

(`Formats/Latest` matches the bare token `AppData` once in every release — a
schema identifier, not a path; the scan's needles are path-shaped for that
reason.)

## Evidence — the candidates (`tools/genesis_identity.py ready --batch 60`, byte-reproducible: two builds → identical sha256)

| release | rung | kind | file | sha256 | md5 | bytes | changed streams | validate errors | identity violations left | byte scan |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | I_all | candidate-base | I_all_2026.rvt | b03904bcc97db33b654f279f5579b845d50eb480ff063d6ba3476cc51215f65a | baebd9dd49343ac15af4d6676adf97c6 | 577536 | TransmissionData,BasicFileInfo,ProjectInformation,Global/DocumentIncrementTable | 0 | none | clean |
| 2026 | I_bfi | probe | I_bfi_2026.rvt | 2a825f51fceaf40f063e17c8abdc77761970ad90b0ae96ee2ee87d0124699a00 | 1d38a846dc9cd06e547dc836a6f4c42e | 581632 | BasicFileInfo | 0 | DocumentIncrementTable.username | clean |
| 2026 | I_dit | probe | I_dit_2026.rvt | 41db16bdb01069b62bd73fd08a3eeaf85927dd246c1300744cd01ba84a73822e | 70026fadb03b8529e914b3efe55afd44 | 581632 | Global/DocumentIncrementTable | 0 | author;client_app_name;last_save_path | clean |
| 2026 | I_pi | probe | I_pi_2026.rvt | cd9c3e46deea432b9b595662191333dc1dd38eead4524bd17af63d2b1fc483b6 | 2daf30215d83d9a1749e6b257041445f | 581632 | ProjectInformation | 0 | DIT.username;author;client_app_name;last_save_path | clean |
| 2026 | I_td | probe | I_td_2026.rvt | 6ec3c97ac1e96508fc2b0a835c312e9ef7825e6951b80d5aedc52d6b7863c716 | 5ff8f834e52e2a4a5bf04be79900a471 | 581632 | TransmissionData | 0 | DIT.username;author;client_app_name;last_save_path | clean |
| 2025 | I_all | candidate-base | I_all_2025.rvt | 42efb84cc349c7df7388c31f3fc748e94eb511b6f87575e4a6cf6449a507a029 | d9602493ed801d9cd8ea39ec8ab80339 | 593920 | TransmissionData,BasicFileInfo,ProjectInformation,Global/DocumentIncrementTable | 0 | none | Partitions residue only (#273) |
| 2025 | I_bfi | probe | I_bfi_2025.rvt | a4d979a741cf4ab28e755130a1f4d23e9f14177f9820046daaa849eb5c4bd266 | 87eec63b3a6df4471fa615ce4d762fba | 598016 | BasicFileInfo | 0 | DocumentIncrementTable.username | Partitions residue only (#273) |
| 2025 | I_dit | probe | I_dit_2025.rvt | 8363961dd2807392c1e95b62574e8eb17d32f1129e40c32de4a2b4e2d120757f | 2a72049eaaa2a020da29fdf9f1d1edec | 598016 | Global/DocumentIncrementTable | 0 | author;client_app_name;last_save_path | Partitions residue only (#273) |
| 2025 | I_pi | probe | I_pi_2025.rvt | bffaeb31ceaf93e85b951c3360e86ee515fe034b3bfaf0087bb339b7b33120e6 | e167d9de089f90a9c9a555d428584b37 | 598016 | ProjectInformation | 0 | DIT.username;author;client_app_name;last_save_path | Partitions residue only (#273) |
| 2025 | I_td | probe | I_td_2025.rvt | 1357aadaac056e4ae57c8a0d3b097c280d0344e470db5ff1d6e48eaa24438098 | e71e2854b0d1fb38e143ed23ab7f7e57 | 598016 | TransmissionData | 0 | DIT.username;author;client_app_name;last_save_path | Partitions residue only (#273) |
| 2024 | I_all | candidate-base | I_all_2024.rvt | e2b10ff9b8b72486a8244590aadad3865072de96ca03f7698bb346175026a7fa | 53a87e848d6f8f0d48db29c5366154e0 | 573440 | TransmissionData,BasicFileInfo,ProjectInformation,Global/DocumentIncrementTable | 0 | none | Partitions residue only (#273) |
| 2024 | I_bfi | probe | I_bfi_2024.rvt | 19a6ac7037bbaee5646b53de64aa09ee7fa7a743b8bc5b237a056192c0a52a1e | a5b4cc796b504006568ec803a5568405 | 577536 | BasicFileInfo | 0 | DocumentIncrementTable.username | Partitions residue only (#273) |
| 2024 | I_dit | probe | I_dit_2024.rvt | ed437a1ff0f040850c1f3ed07a858a9602838ab0ab78cb6b7f87c21a23273b6a | 5d6d9c7c0eb7f42dc0a0c5452eb91f86 | 577536 | Global/DocumentIncrementTable | 0 | author;client_app_name;last_save_path | Partitions residue only (#273) |
| 2024 | I_pi | probe | I_pi_2024.rvt | c71cee78adaf95460be789f4c932edd1346c1aa4ad2fab0192082095072ebdbe | 91582d4e0c29bc79306f2828a45abebf | 577536 | ProjectInformation | 0 | DIT.username;author;client_app_name;last_save_path | Partitions residue only (#273) |
| 2024 | I_td | probe | I_td_2024.rvt | 14123c06c208f28d0b8bf11215e0c2e29ee76c5271d663dfa337d3eb9dcbd87b | 03825ab20e684a984500f805925bb7cc | 577536 | TransmissionData | 0 | DIT.username;author;client_app_name;last_save_path | Partitions residue only (#273) |

- `tools/provenance.py experiments/identity_g2/2025/I_all_2025.rvt --baseline all --streams --json …` → `identity ok: True`, `violations: []`, `gate_G1.identity_violations: 0` (base: 4). Same for 2026/2024 (in `rungs.json`). The G1 gate as a whole still reads FAIL on a fresh clone for the unrelated, pre-existing reasons (no `samples/` baseline → unattributable; Autodesk resource identifiers) — identity is the only layer this stream claims.
- I_all decodes, all releases: author/client `rvt-writer`, username `''`, `last_save_path` = `G_ABPD[_2025|_2024].rvt`, format/build/increments/GUID = the base's, GUID == History[0]; DIT usernames `{'': 22|21|22}`, copy 2 == copy 1; PI member `Revit<base guid>.project.xml`, design-file title = the pinned name, product-version = the release; TD `LastSavedAbsolutePath` = `RevitKeynotes_Metric.txt`, `UniformatClassifications.txt`, `..\..\..\..\..\Desktop\rac_basic_sample_project.rvt`.
- The candidate is 4,096 B smaller than its pin (one CFB sector: the PI zip and TD shrank); the singles keep the pin's size.

## STAGED (stop at READY — a human uploads; hard rule 4)

`probe_batch` verdict per release: **ADMISSIBLE → STAGED**, control cut from the
pinned base by the sha256 alias rule (`control_certified_as` = the ledger relpath):

| batch | release | control (md5 = the pin's) | then | then only if I_all FAILS |
|---|---|---|---|---|
| `experiments/acceptance/batch_60.json` | 2026 | `CTRL_G_ABPD_b60.rvt` (`1f1ff65b…`) | `I_all_2026.rvt` | `I_bfi_2026` → `I_dit_2026` → `I_pi_2026` → `I_td_2026` |
| `experiments/acceptance/batch_61.json` | 2025 | `CTRL_G_ABPD_2025_b61.rvt` (`47008773…`) | `I_all_2025.rvt` | `I_bfi_2025` → `I_dit_2025` → `I_pi_2025` → `I_td_2025` |
| `experiments/acceptance/batch_62.json` | 2024 | `CTRL_G_ABPD_2024_b62.rvt` (`37979615…`) | `I_all_2024.rvt` | `I_bfi_2024` → `I_dit_2024` → `I_pi_2024` → `I_td_2024` |

The `.rvt` files are git-ignored and this session's VM is ephemeral, so the
human round regenerates them: `.venv/bin/python tools/genesis_identity.py ready --batch 60`
rebuilds byte-identical rungs (the md5s above must reappear — the tool refuses
to overwrite a staged file with different bytes) and re-stages the same three
batches, then `tools/serve_acceptance.py` for the upload loop and
`tools/probe_batch.py verdicts experiments/acceptance/batch_60.json --verdict I_all_2026.rvt=PASS …`.
Expected reading (`probes.json.expected_reading`): V30/V31 — the reader does not
gate on author/client strings and accepts a scrubbed path on the rst lineage;
V32 — scrubbed DIT usernames PASS there; verdict #36 — the only single-surface
identity probes on a composed base (E4 = BFI, E5 = DIT) FAILED as
empty-footer-blob artefacts, so BFI/DIT are untested in isolation; #47 —
G_ABPD's identity surfaces are byte-inherited from rst. Expected: I_all PASS
per release ⇒ #19 re-pins it (base.py pin + `plugin/assets/genesis` + ledger,
hot-file PR); an I_all FAIL is localised by the four singles of that release.

## Findings

1. **A fifth identity surface exists on the 2025/2024 pins, outside the four
   metadata families** → filed **#273** (P2, `needs-viewer`, Refs #134 #19 #21).
   Element 1218726 = `AssemblyCodeTable` (the same element TransmissionData
   names) stores its external-resource reference inside the model partition
   (`Partitions/20` member 4 @ ~0x4fe5 / 0x5287 in 2025; `Partitions/21` in
   2024) with two absolute paths: the sample maintainer's
   `C:\Users\<employee>\OneDrive - Autodesk\FY-2021 Projects\…\UniformatClassifications.txt`
   and `C:\ProgramData\Autodesk\RVT 20xx\Libraries\English-Imperial\US\UniformatClassifications.txt`.
   The 2026 pin's AssemblyCodeTable carries none (its sample had the tables
   "Not Found"), so `I_all_2026` is fully clean; `I_all_2025/2024` clear the
   four metadata surfaces (provenance identity 4 → 0) and leave this element
   byte-identical to the certified base. No metadata rewrite can reach it; it
   needs an element-level rung decoded against the file's own schema (or a
   lawful reduction), hence a separate issue rather than scope creep here.
2. `rvt.provenance.identity_report` inspects only BFI + DIT; PI and TD leaks
   surface only through the strings/stream layers. The tool's byte scan covers
   them; promoting "PI member name is a path" / "TD absolute path" to identity
   *violations* is already chartered as **#192**, and scrubbing PI/TD on every
   delivered file as **#194** — a note on #194 asks that stream to lift this
   tool's `own_transmission_xml` / `encode_transmission` /
   `our_project_information_zip(…, product_version=…)` and the needle set into
   the engine (beside `rvt.meta`'s parsers) instead of adding a fourth encoder
   copy; they stay tool-local here only because `src/rvt/meta.py` /
   `provenance.py` are outside #134's territory.
3. Rung basenames must be globally unique (`I_bfi_2026.rvt`, not
   `2026/I_bfi.rvt`): `experiments/acceptance/` and the viewer key on basename
   and `probe_batch` refuses a different file at an occupied name. The issue's
   `<year>/{I_bfi,…}.rvt` layout is kept as directories; only the filenames
   gained the suffix.
4. The committed manifests (`experiments/identity_g2/**/rungs.json`, `probes.json`) are stamped
   `PROOF-ONLY` and write every inherited login as `<employee_N>` (hard rule 3 — the review on
   #283 asked for it); the in-memory reports the assertions run on keep the raw bytes' values.
5. Everything needed decodes release-independently: BFI / DIT / History / PI /
   TD codecs are byte-exact on all three pins with no release context, and
   `validate_file` enters the file's own release itself — the tool never swaps
   framing and the tests assert no release context leaks.

## Open questions (for #19 / the human round)

- If counsel C1 lands a different author string before upload, rebuild — the
  tool reads `rvt.identity.DEFAULT_AUTHOR`, so the hashes above change and this
  table must be regenerated (the batch manifests refuse stale bytes).
- `I_guid` (new document GUID) is built only with `--with-guid` and was not
  staged: the inherited GUID is the sample's, but changing it moves two streams
  and provenance only flags it against a `samples/` corpus. Stage it as a
  follow-on single once I_all is certified, if G2 is read to require it.

## BRANCH STATE

- Branch `cam/134-genesis-identity-rungs` (from `main` @ a5a853f); PR opened with `Closes #134`.
- Files: `tools/genesis_identity.py` (new; one family registry + rung specs, `probes.json` regenerated from
  the `rungs.json` files, `gate` reads `probes.json` and refuses missing / stale / failed rungs; reuses
  `probe_batch`'s `rel` / digests / pins / ledger after the /simplify pass), `tests/test_genesis_identity.py` (new; 18 tests, ~8 s),
  `tests/ci_shard.txt` (+1 line), `experiments/identity_g2/{probes.json,2026/rungs.json,2025/rungs.json,2024/rungs.json}`,
  `experiments/acceptance/batch_{60,61,62}.json` (STAGED manifests), `docs/inbox/identity-g2-prep.md`.
- Gates: `pytest tests/test_genesis_identity.py` 18 passed; `tests/test_provenance.py tests/test_probe_batch.py tests/test_plugin_sync.py` 46 passed / 29 skipped (samples-gated); `tools/sync_plugin.py --check` clean (the tool is dev-only, not mirrored); `plugin/scripts/validate_plugin.py` PASS (24 assertions); `tools/dev/check_portable_paths.py` ok. /simplify (4 review angles) applied; rung bytes identical before/after the refactor (sha256 table above unchanged).
- Staged, not shipped: batches 60/61/62 READY in `experiments/acceptance/` (binaries git-ignored; regenerate with `tools/genesis_identity.py ready --batch 60`). First staged as 57–59; renumbered to 60–62 because PR #277 (wall-solid stream, opened first) holds 57–59 — same rung bytes, controls `_b60.._b62`. No verdicts recorded, no ledger / pin / `plugin/assets` / KNOWLEDGE / TRACKER change (all #19's after PASS). Follow-up filed: #273 (fifth surface); engine promotion of the PI/TD encoders + checks noted on the existing #194 / #192.
