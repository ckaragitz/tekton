# plugin-identity-scan — issue #193 (Refs #19, #108; PG5)

## What was built

The plugin's deny-audit (`tools/sync_plugin.py` `DENY_PATH_PARTS`) is path-based;
until now nothing looked at the **bytes** we ship. This stream adds a content
audit that freezes today's inherited identity residue and forces it to shrink.

**1. `tools/sync_plugin.py` — `audit_identity_strings()` / `check_identity_strings()`.**
Scans `plugin/**/*.{rvt,rfa,json,md,txt,ifc,tksc}` (the issue's five extensions
plus our `.ifc` examples and `.tksc` schema-cache assets — both named leak
vectors in the Why, both clean today) and, when it exists, every such member of
the built `tekton-plugin.zip`. Tokens = `rvt.provenance.AUTODESK_EMPLOYEE_USERNAMES`
(imported, no copy; the constant was already public and in `__all__`) +
`C:\Users\`. Every token is matched ASCII **and** UTF-16LE (the interleaved-NUL
spelling, no decode pass), case-insensitively, plus the JSON/markdown-escaped
`C:\\Users\\` spelling, in **one** regex pass over each blob's lowered bytes.
`.rvt`/`.rfa` are opened with our own `rvt.container` and scanned **per CFB
stream**: the de-paged bytes plus every gzip member inflated — a raw skim of the
container sees only `BasicFileInfo`/`ProjectInformation`/`TransmissionData` and is
blind to `Global/DocumentIncrementTable` and `Partitions/*`, where most of the
usernames live. Byte-identical blobs are scanned once (sha256 cache), so the zip —
which repeats the tree verbatim — costs a hash, not a second walk. A container
that will not open falls back to a raw scan under member `<raw>` (still caught);
a missing `olefile` fails loudly instead of silently degrading to that skim.

**2. `tools/plugin_identity_allowlist.json` (new).** Exactly the 41
`(file, member, token, count)` rows measured on `main` @ `c66333e`, all three
genesis bases, every row `tracked_by: "#19"`, one row per line so #19's scrub PR
is a readable deletion. `member` (the CFB stream) is a refinement of the issue's
`(file, token, count)`: it is what the issue's own Evidence was measured in, and
it lets #19 retire `BasicFileInfo` rows before `DocumentIncrementTable` ones.

**3. `--check` prints the table and exits 1** on any hit not in the allowlist
(or whose count differs) **and** on any allowlisted row no longer in the bytes
(`VANISHED … delete it from tools/plugin_identity_allowlist.json`). The full
build (`sync_plugin.py` without `--check`) runs the same audit *after*
`rebuild_zip()` so the fresh zip is covered, and returns 5 on a mismatch. Zip
rows are compared against the same allowlist (member path == plugin relpath);
a stale zip therefore fails `--check` with the rebuild being the fix — the zip
is git-ignored and absent in CI, where only the tree is scanned.

**4. `plugin/scripts/validate_plugin.py` — `check_identity_strings()`.** Borrows
the very same audit from `../tools/sync_plugin.py` when the plugin sits in the
repo (CI's "Plugin structure" step, `[plugin-root]` argument honoured), so the
two gates cannot disagree; a bare install has no repo beside it and records
`identity scan skipped` as a note (the build that produced it ran the scan).

**5. `tests/test_plugin_sync.py`** — `test_identity_scan_matches_allowlist`
(shipped tree == allowlist; allowlist hygiene: only the three bases, every row
`#19`, no duplicate keys, tokens ⊆ the engine's set) and
`test_identity_scan_catches_injected_strings` (tmp plugin + zip: mixed-case ASCII
`HansonJe` in a reference `.md`, UTF-16LE `C:\Users\…` in a `.txt`, `okapaw` in a
non-CFB `.rfa` → `<raw>`, a zip member, a JSON-escaped `c:\\users\\` path; a `.py`
carrying the deny constants is *not* scanned; the real allowlist yields 5
UNEXPECTED + all base rows VANISHED; a matching allowlist passes; a stale count
fails; and `validate_plugin.py <tmp-root>` goes red naming the leak). The existing
`test_plugin_is_in_sync_with_source` additionally asserts the table is printed.

## Evidence (numbers, current `main` c66333e, this cloud VM)

Measured hits — identical whether walked with `rvt.provenance.content_units`
(release-aware, per save-unit) or the lighter `rvt.container` per-stream walk
that ships (chosen: same numbers, no framing/schema dependency, ~4× faster warm):

| base | BasicFileInfo | Global/DocumentIncrementTable | ProjectInformation | TransmissionData | Partitions/N |
|---|---|---|---|---|---|
| G_ABPD.rvt (2026) | C:\Users\ 2, hansonje 2 | campbes 2, gbs_subsuser6 2, hansonje 2, loboarch 18, okapaw 8, xuew 6, youyi 4, zhangg 2 | C:\Users\ 2, hansonje 2 | C:\Users\ 2, hansonje 2 | — |
| G_ABPD_2025.rvt | same | same but loboarch 16 | same | **none** | Partitions/20: C:\Users\ 1, hansonje 1 |
| G_ABPD_2024.rvt | same | same but loboarch 20 and **no hansonje** (7 names) | same | **none** | Partitions/21: C:\Users\ 1, hansonje 1 |

Differences from the numbers quoted in the issue body (measured again, as asked):
the issue's `DIT{hansonje:2, zhangg:2}` undercounts — the increment table carries
all 8 names (7 on 2024, as the issue's identity_report list already said) with
2–20 occurrences each; the issue's "2025 = same + Partitions/20" implies a
`TransmissionData` hit on 2025 — there is none on 2025 or 2024 (only 2026 ships
that stream with a path in it), and 2024 has its own `Partitions/21` hit the issue
did not list; the issue's `BFI{Autodesk:2}` is real but `Autodesk` is not in this
gate's token set (DONE = usernames + `C:\Users\`; the author-string question is
counsel C1 / #19's identity block, and `rvt.provenance.RESOURCE_PATTERNS` already
ledgers it). All other text/example/asset files in the plugin: **0 hits** (also
0 for `.py/.js/.toml` apart from the engine's own deny constants, which is why
source files are deliberately outside the scan set).

Wall time (steer S-2026-08-09-g — this runs on every `--check`):

| command | before | after |
|---|---|---|
| `tools/sync_plugin.py --check`, no zip (CI / fresh clone) | 0.34 s | 0.58–0.67 s (scan itself 0.23–0.25 s: 97 files, 3 containers ≈ 12 MB inflated) |
| `tools/sync_plugin.py --check`, zip present | 0.35 s | 0.61–0.70 s (97 files + 97 zip members, 0.28 s — zip members dedupe to a hash) |
| `plugin/scripts/validate_plugin.py` | 0.05 s | 0.33 s (engine import + the same 0.25 s scan) |
| `tools/sync_plugin.py` full build (sync + claude validate + zip + scan) | — | 2.8 s total, scan 0.28 s |
| `tests/test_plugin_sync.py tests/test_plugin_validate.py` | 13 tests | 15 passed in 1.5 s |

Scan-strategy bench on G_ABPD.rvt (3.8 MB inflated): 18× `bytes.count` 64 ms;
one case-sensitive alternation regex 27 ms; `re.IGNORECASE` on bytes 509 ms (!);
`lower()` + case-sensitive regex ≈ 30 ms ← shipped. Container open + inflate ≈ 20 ms
warm per base; the first container pays ~45 ms of engine import.

Negative case driven for real (not only in pytest): a temp copy of `plugin/` with
`hansonje` appended to a reference `.md` → `validate_plugin.py <copy>` exit 1 with
`identity scan: UNEXPECTED …NOTES… carries 'hansonje' x1 (not allowlisted)`; and
`sync_plugin.py --check` with one allowlist count bumped → exit 1, `UNEXPECTED …
(allowlist says 3)`. Both recorded under `/verify` below.

## Findings

* The leak set is bigger than the path audit ever suggested: **82 tracked hits**
  across tree + zip, 8 distinct Autodesk usernames, and a `C:\Users\hansonje\…`
  path in four different streams of the 2026 base including an element record
  inside `Partitions/20|21` on 2025/2024 — #19's scrub has to reach into the
  partition, not only the metadata streams.
* `re.IGNORECASE` on a bytes alternation is ~19× slower than lowering the
  haystack once; worth remembering for any future byte-level guard.
* `validate_plugin.py` used to pass under a bare `python3` with no deps; it now
  needs `olefile` (the engine's one runtime dep) when run inside the repo, and
  says so (`identity scan could not run: No module named 'olefile' -- run with the
  repo's .venv/bin/python`). CI installs the package first, `cloud-setup.sh` uses
  `.venv`, and a bare *install* (no repo beside it) skips the scan, so no
  supported path regressed — but it is a behaviour change and is stated here.

## Open questions / follow-ups

* When #19 lands its scrubbed bases, its PR must delete the matching rows here —
  the gate enforces that mechanically (VANISHED → exit 1), so no follow-up issue
  is needed; noted on #19 instead.
* `Autodesk` / `Autodesk Revit` author strings in `BasicFileInfo` are outside this
  gate on purpose (counsel C1, #23/#19). If the owner wants them frozen the same
  way, it is one more token here — file it then, not now.

## BRANCH STATE

* Branch `cam/193-plugin-identity-scan` from `main` @ c66333e.
* Files written: `tools/sync_plugin.py` (+identity audit, wired into `--check` and
  the full build), `tools/plugin_identity_allowlist.json` (new, 41 rows),
  `plugin/scripts/validate_plugin.py` (+`check_identity_strings`),
  `tests/test_plugin_sync.py` (+2 tests, shared `_sync_plugin()` loader),
  `docs/inbox/plugin-identity-scan.md` (this record). No hot file, no `src/`
  change (the username constant was already public), no asset change.
* Gates: `tests/test_plugin_sync.py` + `tests/test_plugin_validate.py` 15 passed;
  `tools/sync_plugin.py` build OK then `--check` exit 0 (identity scan ==
  allowlist, 0 drift — `sync_plugin.py` is not mirrored into `plugin/lib/tools/`);
  `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok.
* Shipped in the PR; nothing staged for the viewer (no bytes changed).
