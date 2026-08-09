# revit-kit-v2 — the regenerable desktop-Revit check kit (issue #118; serves #16)

Stream: **revit-kit-v2** (2026-08-09, cloud engineer session `eng118`).
Charter (#118, P0): make the P0 desktop-Revit round (#16, O1) regenerable from a
fresh clone and post-#48-correct.  The v1 kit shipped two stale probe copies —
H12 (whose ONLY defect was the empty 0x0f3f blob: E1/E1b PASSED, VERDICTS #36) and
BXhf_f1i1 (batch-38 era, predates the blob fix) — so opening them would have spent
the one desktop round re-discovering a solved law.

**Territory touched ONLY:** `tools/revit_kit.py` (new), `tools/terminal_diff.py`
(`kit` verb only: delegation; the `KIT_MD`/`BXHF` constants it alone used are
gone), `experiments/terminal/REVIT-CHECK-KIT.md` (regenerated v2),
`experiments/terminal/kit2/{manifest.json,REVIT-CHECK-KIT.md}` (json/md tracked;
`.rvt`/`.rfa` git-ignored), `tests/test_revit_kit.py` (new), `tests/ci_shard.txt`
(one line), `docs/inbox/terminal-diff.md` (dated addendum header only), this
record — plus one necessary adjacent deletion, recorded here in this stream's
voice: `tests/test_terminal_diff.py::test_revit_check_kit_in_place` asserted the v1
text + the H12/BXhf copies (red on the owner's machine once the kit is v2, and not
in the CI shard); the kit is no longer terminal_diff's artifact, so the test is
removed and `tests/test_revit_kit.py` owns those facts.  No
ledger / KNOWLEDGE.md / TRACKER.md edits; read-only use of `rvt.frontdoor`,
`rvt.families.FamilyIndex`, `rvt.elemtable`, `rvt.partitions.StreamWalker`,
`rvt.validate`.

## What was built

`tools/revit_kit.py` — three verbs:

* `build [--out experiments/terminal/kit2] [--no-publish] [--keep-build]`:
  copies the pinned `plugin/assets/genesis/G_ABPD.rvt` to `K0_CTRL_G_ABPD.rvt`
  (sha256 asserted against the pin `84173b89…6df50`), then builds ON K0 through
  `rvt.frontdoor.author(prompt="an electrical room with 1 panel", base=K0)` —
  `strict=True` gives the twins `K1_shell_walls.rvt` (shell) +
  `K2_equipment_1fam_1inst.rvt` (equipment), `strict=False` gives
  `K3_room_combined.rvt` (the stamped product shape) — and copies the generated
  `families/*.rfa` beside them.  Every file is validated (`rvt.validate.
  validate_file`, family mode for `.rfa`) and inspected read-only; the run writes
  `manifest.json` + `REVIT-CHECK-KIT.md` into the kit dir and (unless
  `--no-publish`) regenerates `experiments/terminal/REVIT-CHECK-KIT.md`.  Exit 0
  only if every shape law in `check_kit()` holds; the kit is written either way
  (deliverable rule — labels, not refusals).  The shape laws are data: one
  `KIT_SPEC` row per file (front-door job/role, exact added structural classes,
  added save units, SWall total) drives the copy loop, the manifest entries and
  `check_kit` alike; the pin sha is a literal (kit v2 is *defined* on
  `84173b89…`) asserted equal to `rvt.frontdoor.base.PIN` at build start, the base
  is located by `resolve_base()`, the blob law is `rvt.validate.UNIT_FOOTER_BLOB_LEN`,
  host families come from `rvt.families.family_documents`.
* `verify [--kit DIR]`: re-checks an existing kit dir against its manifest (sha256
  per file + the shape laws) — for the human after copying the folder to Windows.
* `lookup ID… [--kit DIR]`: resolves an element id a Revit dialog / journal names
  through the manifest's `id_index`.

`manifest.json` (schema `tekton.revit-check-kit/2`) records: base path/sha/pin/
watermark; the prompt and build route; per file `sha256`, `bytes`, `role`,
`expected` reading, `validation` {ok, errors, warnings, messages}, `stamps`,
`census` {classes of interest, added_classes, save_units with blob length,
added_save_units, watermark, elemtable rows}; for K1–K3 `added_elements` = every
host element id above the base watermark 1472524 → class, unit 0, owning family
(by reference closure over the added set: ParamElemFamily/FamilySurrogate → Family,
FamilySymbol.m_familyId → Family, FamSymSurrogate → symbol → Family, FamilyInstance
→ symbol → Family), famdoc unit, build tag (W-S…/PP-1); `family_documents` = every
GUID unit → host Family name, blob length, and its OWN element id → class map; and a
kit-wide `id_index` (id → [{file, unit, unit_guid, class, family, tag}]).

`REVIT-CHECK-KIT.md` v2 (rendered from the manifest, so the tracked copy can be
tested for equality with `render_kit_md(tracked manifest)`): retirement note for
H12/BXhf_f1i1 with the VERDICTS #36 reason; open order K0 → K1 → K2 → K3 → Insert >
Load Family of the `.rfa`; instructions add *tick Audit on File > Open*, *Select by
ID for any id a dialog names* (+ `revit_kit.py lookup`), *Review Warnings → export*,
*always copy the newest journal out by hand — never point a tool at the Autodesk
directory*, crash handling per `rfa-revit-api-compat.md` Iteration 3; outcome
table rewritten around K0/K1 clean vs K2/K3 dialog (+ same/different dialog, clean
with Audit, warnings-only, `.rfa` load, crash).

## Evidence (this VM, fresh clone: no samples/, vendor/, extracted/)

`build` wall time **16.2–17.1 s** over four runs (front door: split 6.4–7.0 s +
combined 5.4 s; the rest is census + the kit's own validator pass, ~3 s).  Manifest
summary of the tracked run:

| file | bytes | sha256 | validator | added classes | added units (blob) |
|---|---|---|---|---|---|
| K0_CTRL_G_ABPD.rvt | 581,632 | `84173b8960b8…` (== pin) | 0 err / 1 warn | {} | 0 |
| K1_shell_walls.rvt | 581,632 | `7d013d43a219…` | 0 err / 1 warn | SWall 4 | 0 |
| K2_equipment_1fam_1inst.rvt | 593,920 | `19d316822770…` | 0 err / 1 warn | Family 1, FamilySymbol 1, FamSymSurrogate 1, FamilySurrogate 1, FamilyInstance 1, ParamElemFamily 14; SWall total 0 | 1 (64 B) |
| K3_room_combined.rvt | 593,920 | `9cac854210a1…` | 0 err / 1 warn | the K2 set + SWall 4 | 1 (64 B) |
| families/pp1_eaton_prl2x_225a_42sp_480y_277.rfa | 217,088 | `de82cde9eb6f…` | 0 err / 0 warn (family mode) | – | – |

The one standing warning on every project file is the inherited DataStorage
Extensible-Storage decode gap (1/3106 records), present on the certified base too.
`tools/rvt_validate.py experiments/terminal/kit2/*.rvt …/families/*.rfa --quiet` →
five `OK … errors=0` lines.  `revit_kit.py verify` → VERIFIED.  `lookup 1472584
1472525 42` → K2 host FamilyInstance 'Panelboard PP-1 …' tag PP-1 / K3 host SWall
W-S; K1 host SWall W-S / K2 unit 1 Family / K3 unit 1 Family; 42 → not kit-added.
`id_index`: 64 ids.  Famdoc unit: 41 elements (Family 1, ParamElemFamily 14,
CurveElem 4, ExtrusionElem 1, ConnectorElem 1, ElectricalLoadClassification 1, views/
datums), blob 64 B, 3 blocks.  `tools/provenance.py K2 --baseline all --streams`
runs (unbaselined on a fresh clone — no samples — as expected; kit files are
PROOF-ONLY probes, not deliverables).

Gates: `tests/test_revit_kit.py` **13 passed in 16.0 s** (module builds the kit
once into tmp_path; includes a negative `check_kit` case and the terminal_diff
delegation via a cheap `lookup`); `tests/test_terminal_diff.py` 9 passed / 5
skipped (samples-gated) on this clone;
`tools/sync_plugin.py --check` clean (in sync, deny-audit clean);
`plugin/scripts/validate_plugin.py` PASS (23 assertions); `check_portable_paths`
ok (2698 paths); `tools/terminal_diff.py kit` end-to-end → delegates, exit 0.

## Findings

1. **Id spaces collide across host and famdoc — the manifest must (and does) say
   which unit.**  A generated family document allocates its own ids starting right
   above the same watermark (1472525…), so K1's wall `1472525` (host) and K2/K3's
   famdoc self-Family `1472525` (unit 1) share a number; K2's instance `1472584`
   is K3's wall W-S.  A dialog id is only meaningful with the file name; `lookup`
   prints every candidate with file + unit + GUID.
2. **K1 is byte-deterministic across builds; K2/K3/.rfa are not.**  Four builds
   over an hour gave the identical K1 sha (`7d013d43a219`) but different K2/K3/
   .rfa shas and famdoc GUIDs each time — the famgen/famload lane mints fresh GUIDs per run
   (cf. #9 determinism).  Consequence for the round: the human must send back (or
   we must keep) the exact `manifest.json` of the kit they opened; the manifest
   carries a `volatility` note, the md says so, and `verify` catches a mismatched
   folder.
3. The equipment twin carries **19 added host elements** for one panel (Family,
   14 ParamElemFamily, FamilySurrogate, FamilySymbol, FamSymSurrogate,
   FamilyInstance) — all attributed to the one family by reference closure, no
   orphans; walls attribute to no family.  This is the complete list a K2 dialog
   can name on the host side.

## Open questions / follow-ups

* The desktop round itself stays #16 (needs-revit-desktop): open kit2 in order,
  return screenshots + journal; the receiving session writes VERDICTS #49.
* If #9 (determinism) lands, finding 2 disappears and the tracked manifest's
  shas become reproducible; until then the manifest is per-build evidence.
* `/simplify` review skips, on purpose: the kit re-validates K1–K3 itself (~2.3 s)
  although the front door validated the same bytes — kept as the kit's independent
  gate on what it ships; the two front-door jobs repeat stage F/L (~2.5 s) — an
  engine-side nicety for a dev tool, not filed.

## BRANCH STATE

* Branch `cam/118-revit-kit-v2` from `main` @ 730fe5a; PR `Closes #118`.
* Files written: `tools/revit_kit.py`, `tools/terminal_diff.py` (kit verb),
  `tests/test_revit_kit.py`, `tests/test_terminal_diff.py` (v1 kit assertion removed),
  `tests/ci_shard.txt` (+1 line), `experiments/terminal/REVIT-CHECK-KIT.md`
  (regenerated), `experiments/terminal/kit2/{manifest.json,REVIT-CHECK-KIT.md}`,
  `docs/inbox/terminal-diff.md` (addendum), `docs/inbox/revit-kit-v2.md`.
* Gates at close: listed above, all green.  No `src/`, `skills/` or `plugin/`
  change; sync `--check` clean anyway.
* Staged vs shipped: nothing staged for the viewer, no certification claim; kit
  binaries are git-ignored PROOF-ONLY probes regenerable by anyone
  (`tools/revit_kit.py build`).  Comment left on #16 pointing at kit2.

## Addendum by engineer session eng171 (issue #248, 2026-08-09): K1 is its own walls-only job

#244 (front door stamps the real open cell) redefined the strict split's
`shell` role as walls + the LOADED family (the WF_fix-certified shape) and
merged to main minutes before this kit (#245); each was green alone, together
`K1_shell_walls.rvt` (= the split's `shell`) carried `Family/FamilySymbol/
FamSymSurrogate/FamilySurrogate` + `ParamElemFamily ×14` + 1 save unit and the
three K1 assertions in `tests/test_revit_kit.py` went red on main and on every
PR (`added structural classes {… 'Family': 1, … 'SWall': 4} != {'SWall': 4}`,
`added save units 1 != 0`).  The kit side moved, not the tests: K1 is now built
by an explicit walls-only front-door job — `rvt.frontdoor.author(prompt,
base=K0, stages="WV")` (no F/L/E: no family generated, loaded or placed; the
narrowest walls-only selection the front door offers, no hot file touched) —
while K2 stays the strict split's `equipment` half and K3 the combined job, so
the ladder is again K0 base / K1 4 walls, 0 units / K2 1 family + 1 instance,
1 unit / K3 both.  Evidence (fresh clone, venv without ifcopenshell):
`tools/revit_kit.py build --out out/verify/kit248 --no-publish` → `checks: ALL
HOLD`, K1 `added {'SWall': 4} units+0`, K2 `{FamSymSurrogate 1, Family 1,
FamilyInstance 1, FamilySurrogate 1, FamilySymbol 1, ParamElemFamily 14}
units+1`, K3 = K1 + K2, every file 0 errors, 16.9 s;
`tests/test_revit_kit.py` 13 passed (17.7 s); `tests/test_revit_kit.py
tests/test_frontdoor.py tests/test_router.py` 110 passed / 15 skipped;
`sync_plugin.py --check` clean; portable paths ok.  The tracked
`experiments/terminal/kit2/manifest.json` was NOT regenerated here (its
`built_through` line and per-build shas move with the next `build`; #9).
