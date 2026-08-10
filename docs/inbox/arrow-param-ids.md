# arrow-param-ids — which LeaderStyle parameter id is the arrow ANGLE and which is the SIZE (issue #343)

Stream: `arrow-param-ids` (eng #343, cloud engineer session started by the tech-lead session,
2026-08-09). Charter = issue #343 (Refs #333, found by the independent review of #336; **PG1
honesty / PG2 open-cell hygiene**). Territory: `src/rvt/genesis/residue_a.py` (the two
`BIP_ARROW_*` constants, their comment block, `arrowhead_type()` — the single writer — and its
`ours` labels), NEW `tools/dev/arrow_param_ids.py` (the analysis + byte-identity instrument), NEW
`tests/test_arrow_param_ids.py` + drop-in `tests/ci_shard.d/343-arrow-param-ids.txt`, the
regenerated `plugin/lib/src/rvt/genesis/residue_a.py` mirror, this record. NOT touched:
`src/rvt/famgen/skeleton.py` (the collaborator's live desktop-Revit territory, #333), the pinned
bases under `plugin/assets/genesis/` (files, not rebuilt), any hot file, `docs/inbox/genesis-residue-A.md`
(another stream's record; its table row "params -1006414 angle / -1006426 size" is now known to be
the wrong way round — noted here, not edited there).

## Why

`residue_a.py:244-245` named `BIP_ARROW_ANGLE = -1006414` ("radians") and `BIP_ARROW_SIZE =
-1006426` ("feet"). The review of #336 noticed both Revit-born sources in the tree put the 30°
value under **-1006426**. If the labels are swapped, every constructor keyed by the names puts an
angle where a length belongs — invisible to our validator (both are doubles in range), visible to
Revit — and famgen's new dimension-style constellation (#333/#336, `skeleton.py:585-586`) copies
ids from the same neighbourhood.

## What the corpus says (DONE 1) — `python3 tools/dev/arrow_param_ids.py table --md`

The instrument reads only tracked files: the 1024-arrowhead invariant, `Z_annot.json`, the birth
template's decoded elements, and our own pinned 2026 base. Its output, verbatim:

### 1. `invariants/LeaderStyle.json`: 1024 Revit-born arrowheads, 6 projects

* every arrowhead carries a `ParamValueSetDouble` of exactly 2 entries; id multiset
  `{-1006426: 1024, -1006414: 1024}` (each id once per arrowhead); `-1006424` occurs **0** times.
* value RANGE `[0.0, 1.570796326794895]`; the top-12 histogram covers 1902/2048 values and splits
  into two magnitude clusters with nothing between 0.0105 and 0.26:
  * radians cluster: 999 values — 60° ×700, 30° ×248, 15° ×49, 20° ×2
  * feet cluster: 903 values — 1/8" ×473, 3.125 mm ×275, 3.000 mm ×114, 1/64" ×15, 1.000 mm ×12,
    1.500 mm ×9, 3/64" ×3, 3/32" ×2
* insertion order of the two histograms (= `paramSet[0]` of the first arrowhead scanned): first id
  **-1006426**, first value **0.5235987755982984 (30°, radians)**.

The invariant merges both ids' values into one histogram, so *alone* it proves that one id is
always an angle and the other always a length (2 ids × 1024, two disjoint clusters of ~1024 each)
and points at -1006426 = angle through insertion order; the paired sources settle it:

### 2. Paired (id, value) evidence from Revit-born records in the tracked tree

| source | arrowhead | -1006426 carries | -1006414 carries |
|---|---|---|---|
| Z_annot.json id 285 (certified PARENT) | SecretInternalLinAngArrowhead… | 0.5235987755982984 = 30 deg | 0.001302083333333333 = 1/64" |
| template_birth.json [17] tick 8 | Arrowhead 1 | 1.0471975511965967 = 60 deg | 0.010416666666666666 = 1/8" |
| template_birth.json [221] tick 0 | **Diagonal 1/8"** | 1.0471975511965967 = 60 deg | 0.010416666666666666 = **1/8"** |
| template_birth.json [233] tick 0 | SecretInternalLinAngArrowhead… | 0.5235987755982984 = 30 deg | 0.0013020833333333333 = 1/64" |
| template_birth.json [242] tick 8 | SecretInternalRadArrowhead… | 0.5235987755982984 = 30 deg | 0.001302083333333333 = 1/64" |
| template_birth.json [345] tick 11 | Filled Elevation Target | 0.0 = 0" | 0.02083333333333333 = 1/4" |
| template_birth.json [364] tick 0 | SecretInternalTypePreviewgArrowhead… | 0.5235987755982984 = 30 deg | 0.001302083333333333 = 1/64" |
| template_birth.json [1377] tick 8 | SecretInternalDiameterArrowhead… | 0.5235987755982984 = 30 deg | 0.0013020833333333333 = 1/64" |

The birth template's own type **named** `Diagonal 1/8"` carries its 1/8" under -1006414 — the
name labels the id.

### 3. Per-id distribution over those Revit-born pairs

| param id | n | radians-range values (0.1..π/2) | feet-range values (< 0.1 ft) | verdict |
|---|---|---|---|---|
| -1006414 | 8 | — | 1/64" ×5, 1/8" ×2, 1/4" ×1 | **SIZE (feet)** |
| -1006426 | 8 | 30° ×5, 60° ×2 | 0" ×1 | **ANGLE (radians)** — the one 0.0 is the `Filled Elevation Target` dot (tick 11), which has no angle |

### 4. What OUR certified 2026 base carries today (`plugin/assets/genesis/G_ABPD.rvt`)

| id | name | tick | paramSet as written |
|---|---|---|---|
| 285 | SecretInternalLinAngArrowhead148q039326 | 0 | (-1006414, 0.2617993877991494 = 15 deg) (-1006426, 0.008202099737532808 = 2.500 mm) |
| 296 | SecretInternalRadArrowhead640d780868 | 0 | (-1006414, 0.2617993877991494 = 15 deg) (-1006426, 0.008202099737532808 = 2.500 mm) |
| 23773 | SecretInternalTypePreviewgArrowhead461q950683 | 0 | (-1006414, 0.2617993877991494 = 15 deg) (-1006426, 0.008202099737532808 = 2.500 mm) |
| 1468024 | SecretInternalDiameterArrowhead129b808021 | 0 | (-1006414, 0.2617993877991494 = 15 deg) (-1006426, 0.008202099737532808 = 2.500 mm) |
| 1471069 | GEN Arrow Filled 20 Degree | 8 | (-1006414, 0.3490658503988659 = 20 deg) (-1006426, 0.00984251968503937 = 3.000 mm) |

**Verdict: confirmed swapped.** `-1006426` = arrow ANGLE (radians) and `-1006414` = arrow SIZE
(feet) in every Revit-born record; our certified bases carry our angle under -1006414 and our size
under -1006426, and in the opposite order (ours: -1006414 first; Revit: -1006426 first). Read as
Revit reads them, our arrowheads have a 0.35 ft (106 mm) / 0.26 ft (80 mm) *size* and a 0.56° /
0.47° *angle*. The viewer certified those bytes anyway (it loads; nobody has looked at a leader in
desktop Revit on these bases).

## What changed (DONE 2) — a rename that moves no byte

* `BIP_ARROW_SIZE = -1006414`, `BIP_ARROW_ANGLE = -1006426`, comment block cites the evidence.
* `arrowhead_type()` now spells out what it has always written:
  `double_params={BIP_ARROW_SIZE: radians(angle_deg), BIP_ARROW_ANGLE: mm(size_mm)}` — same ids,
  same values, same insertion order as before — with a `KNOWN-CROSSED, kept byte-identical`
  paragraph in its docstring: the certified bases carry this crossing, un-crossing it is a value
  change on certified records = its own viewer round, filed as **#362** (`needs-viewer`, P2).
* the `ours` report labels say `param -1006414 (size id, carries our angle #343)` /
  `param -1006426 (angle id, carries our size #343)` instead of the old mislabels (report strings,
  not file bytes; nothing parses them — `grep` over `src/ tools/ tests/`).
* No other user of the two names exists in `src/`, `tools/`, `tests/`, `skills/` (grep); the
  `tekton-eval-kit/` copy is an untracked artefact.

### Byte-identity proof (`/verify`)

`tools/dev/arrow_param_ids.py fingerprint` builds every arrowhead the engine can emit —
`arrowhead_type` defaults, the `demo()` call, a no-width-pen variant, and `inplace_arrowhead` over
synthetic slots for the house arrowhead + each of the four secret roles + an unlisted secret role,
each with and without the int set (15 cases) — encodes each record with the genesis encoder
(`_S().enc.encode_object`, the same call `check_object` gates on) and prints sha256 + the pairs.
BEFORE = `origin/main`'s `residue_a.py` (restored via `git stash` of the one file), AFTER = this
branch:

```
diff before.json after.json            -> 0 differing lines
sha256sum before.json after.json       -> 86b6c98c5ff0da82…786643956  (both files: the SAME digest)
15 cases, 75 leaves before / 75 after; differing leaves: 0
  e9739831dd273397==e9739831dd273397  255B  arrowhead_type/defaults          [[-1006414, 0.3490658503988659], [-1006426, 0.00984251968503937]]
  45e5d38be8d9374f==45e5d38be8d9374f  255B  arrowhead_type/demo              [[-1006414, 0.3490658503988659], [-1006426, 0.00984251968503937]]
  68698a735c7c72ca==68698a735c7c72ca  187B  arrowhead_type/no-width-pen      [[-1006414, 0.6108652381980153], [-1006426, 0.014763779527559055]]
  b059df06e1438e63==b059df06e1438e63  237B  inplace_arrowhead/Arrowhead 30 Degree/int=False   [[-1006414, 0.349…], [-1006426, 0.00984…]]
  9ed1e16f09679fe0==9ed1e16f09679fe0  255B  inplace_arrowhead/Arrowhead 30 Degree/int=True    [[-1006414, 0.349…], [-1006426, 0.00984…]]
  a9da20f9…/5b809a32…  267/285B  inplace_arrowhead/SecretInternalDiameterArrowhead…/int=False|True     [[-1006414, 0.2618…], [-1006426, 0.0082…]]
  c6e4b31f…/61b94936…  263/281B  inplace_arrowhead/SecretInternalLinAngArrowhead…/int=False|True       (same pairs)
  1443e5dc…/bf4b8b98…  257/275B  inplace_arrowhead/SecretInternalRadArrowhead…/int=False|True          (same pairs)
  487a083f…/9d4c262b…  275/293B  inplace_arrowhead/SecretInternalTypePreviewgArrowhead…/int=False|True (same pairs)
  e7b5b538…/5e57dd41…  257/275B  inplace_arrowhead/SecretInternalUnlisted…/int=False|True              (same pairs)
```

The pinned bases under `plugin/assets/genesis/` are files and were not rebuilt (untouched by
definition; `sync_plugin.py --check`: assets verified). `frontdoor author` / `make_family` outputs
build on those pinned bases and never call `arrowhead_type`, so they are identical trivially; the
fingerprint above is the path that actually exercises the renamed code.

### The pinning test (DONE 2b) — `tests/test_arrow_param_ids.py`, 7 tests, fresh-clone safe

Ties the names to the evidence so the swap cannot recur silently: constants == the corpus ids; the
invariant's id multiset, two disjoint magnitude clusters and insertion order; parent 285's pairs
(angle id ↔ 30°, size id ↔ 1/64", Revit's order); the birth template's 7 arrowheads (size id always
feet-range > 0, angle id radians-range or the tick-11 dot's 0.0; `Diagonal 1/8"` ↔ 1/8" under the
size id); the per-id verdict; and — deliberately — the certified crossing `arrowhead_type` still
writes (SIZE id first carrying radians, ANGLE id second carrying feet, `check_object` ok) plus the
`arrowhead_type/defaults` record sha, so #362's un-crossing is a visible, reviewed test inversion.
All three inputs are tracked (`git ls-files` confirms), so the drop-in puts it in the CI shard.

## Note for #333 (the desktop campaign)

`skeleton.py:585-586` writes the "Diagonal" LeaderStyle as `[(-1006426, 0.5236), (-1006424,
0.0104167)]`. The corpus reading supports the first pair exactly (angle id, 30°, first) and says
the second id should be **-1006414** (size, 1/8"): `-1006424` occurs on 0/1024 corpus arrowheads,
and the birth template's own `Diagonal 1/8"` is literally `(-1006426, 60°) (-1006414, 1/8")`. So
`-1006414` there is not just "safe", it is the Revit-born form; with `-1006424` the diagonal tick
has no size parameter and one stray id. Not edited here (their live territory); said on #333.

## Gates (this session, branch head before push)

* `tests/test_arrow_param_ids.py`: **7 passed**.
* stream-local: `tests/test_arrow_param_ids.py tests/test_residue_a.py tests/test_residue_a2.py
  tests/test_genesis_types.py tests/test_genesis_settings.py tests/test_genesis_substitute.py
  tests/test_genesis_substitute_v3.py tests/test_genesis_2024.py tests/test_genesis_2025.py
  tests/test_required_settings.py` → **149 passed, 121 skipped** (baseline on `main` before the
  change: 142 passed, 121 skipped — the +7 are the new file; skips = ladder artefacts / quarantined
  samples absent, expected in a cloud clone).
* `tools/sync_plugin.py` rebuilt the mirror + zip, deny-audit clean, identity scan == allowlist;
  `--check`: in sync. `plugin/scripts/validate_plugin.py`: PASS (25 assertions).
  `tests/test_plugin_sync.py tests/test_shard_list.py`: 32 passed. `tools/dev/check_portable_paths.py`:
  ok (2843 paths). `tools/dev/shard_list.py --print` lists `tests/test_arrow_param_ids.py`.
  `python3 -W error::ResourceWarning tools/dev/arrow_param_ids.py table` runs on system Python.
* `/simplify` pass applied (helpers for the repeated paramSet/name/table-row idioms, context-managed
  JSON loads, dead verdict arm, named ids; the whole-record sha literal dropped from the test as
  over-fitted — the proof lives above); fingerprint re-taken after it: still == `main`'s, 0 lines.
* `/verify`: `residue_a.demo()` → `LeaderStyle bytes 255 clean True exact True`, rc 0;
  `SOURCE_DATE_EPOCH=1700000000 tools/frontdoor.py author --prompt "an electrical room with 2 panels"
  --out out/verify/p --json` → self-checks PASS, `prompt_room.rvt` delivered (PROOF-ONLY stamp, rule 1);
  `tools/rvt_validate.py out/verify/p/prompt_room.rvt` → `verdict: VALID (no errors); warnings=1`
  (the known DataStorage extensible-storage decoder gap), exit 0.

## Open questions / follow-ups

* **#362** (filed): un-cross the values in `arrowhead_type` and re-certify the three bases — a
  value change, viewer-gated; best ridden on an already-planned re-compose (#17 / #19).
* `docs/inbox/genesis-residue-A.md`'s constructor table still says "-1006414 angle / -1006426
  size"; whoever next owns that record should flip the words (facts here).
* `BIP_ARROW_WIDTH_PEN = -1006447` was not in question and is unchanged (961/1024, always 1).

## BRANCH STATE

* Branch `cam/343-arrow-param-ids` from `main` @ ec62a06; PR opened (number in the report to the
  tech-lead session); issue #343 assigned + 🔒 comment; follow-up #362 filed; one comment on #333.
* Files: `src/rvt/genesis/residue_a.py` (rename + comments + docstring; no byte moves),
  `tools/dev/arrow_param_ids.py` (new), `tests/test_arrow_param_ids.py` (new),
  `tests/ci_shard.d/343-arrow-param-ids.txt` (new drop-in; `tests/ci_shard.txt` untouched),
  `plugin/lib/src/rvt/genesis/residue_a.py` (sync mirror), this record.
* Staged vs shipped: nothing staged for the viewer (no bytes changed); shipped = the rename, the
  instrument, the test.
