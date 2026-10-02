# #984 — every certified file of OUR content the matrix cites is either an earlier FORM (fingerprinted) or MECHANISM-ONLY, and its rows say which

Stream: perm-matrix (index `docs/inbox/perm-matrix.md`). Issue #984 (follow-up of #981 / PR #985,
PG1). No status changed, no citation added or removed. No viewer batch staged.

## What was wrong

#981 registered one certified file (`L_downlight_loaded.rvt`) whose content a generator in this
repo still emits. The matrix cites thirteen more `certified:` files. Several of them hold content
we generated (families, walls, placed elements), and some rows implied that what a route emits
today is what the ledger certifies:

- `_FAMSPEC_GATES` said "what the ledger certifies is **the same constructors' families** LOADED into
  projects (stage_L8_lp4 …, L1a …)". In fact L1a's family is a level-head annotation skeleton from
  `rvt.famgen.heads`, not a famspec constructor. `stage_L8_lp4`'s families predate the repo's
  history, and the constructors have changed a lot since then.
- **`stage_L8_lp4.rvt` certifies less than its citations claim.** The ledger line says "family LOAD +
  instance PLACEMENT … PASS". Verdict #25 (`docs/inbox/genesis-audit.md`) **retracted** that PASS
  as an empty-design translation: 8 families, 0 walls, 0 instances. All eight tracked stage load
  records say `instance_id: -1`, "family loads unplaced". Despite that, `plugin/docs/HONEST-STATUS.md`
  cited it for "family load + instance placement", and the `prompt->rfa->loaded-rvt` chain cites
  it as the only evidence for "families generated, loaded, then placed".
- `V25_room_from_ifc.rvt` is cited for the `ifc->intent` stage (`rvt.ifc.intent`). It was built by
  the earlier `tools/ifc_to_spec.py` (ifcopenshell) → `tools/spec_to_rvt.py` pipeline on an Autodesk
  MEP template (KNOWLEDGE "THE GOAL — ACHIEVED"), so it is a different mechanism.

## Inventory (DONE 1)

Every `certified:` path in `src/rvt/frontdoor/matrix.py`, plus the two files of our content that
only `plugin/docs/HONEST-STATUS.md` cites. Dates come from the ledger and from
`docs/inbox/genesis-audit.md`. The repo's own history begins on 2026-08-11 (`6f33fb7`), so every
build below predates it.

| path | what it evidences (cited for) | generator of our content | recipe known? | today's output still that form? | decision |
|---|---|---|---|---|---|
| `experiments/families/ifc/L_downlight_loaded.rvt` | IFC downlight loads (verdict #21, 2026-08-04): facts->rfa, rfa-load, ifc->rfa, rfa[+rvt]->rvt, chain ifc->rfa->loaded-rvt | `rvt.ifc.famfrom_ifc:make_downlight` | our convention (#981); the certified build used the owner-machine family container | **no** (#981) | form, registered by #981 (unchanged) |
| `experiments/ifc_room/stage_L8_lp4.rvt` | the build step (intent->rvt), the component loader (rfa-reload), prompt->rvt, rfa[+rvt]->rvt, chain prompt->rfa->loaded-rvt; `_FAMSPEC_GATES` / `_RFA_HOST` implied the constructors' families are certified | `rvt.famgen.factory` make_panelboard ×6 / make_transformer + `rvt.ifc.intent.make_house_switchboard`, loaded by `rvt.famgen.loader` on ZA_deep (owner machine), verdict #22, 2026-08-04 | kwargs: yes (tracked `experiments/ifc_room/build_record.json` stage F, consistent with the 8 stage load records' family names); the certified bytes: no | **no**. Very likely moved: the panelboard was rebuilt from real parts (#892) with drives (#931), the transformer from real parts with clearance zones (#887/#935), and the loader's nulled slots were fixed (genesis-12). PASS retracted to empty-design (verdict #25) | **form, registered** (`recipe='family_set'`) + retraction stated |
| `experiments/frontdoor2025/room_walls/ROOM2025_walls.rvt` (HONEST-STATUS only) | native 2025 authoring from a prompt (verdict #32, 2026-08-05) | `rvt.frontdoor:author`, prompt "an electrical room 30x20 ft", `--target-version 2025` (`experiments/frontdoor2025/probes.json`) | **yes**, and the ledger records the certified sha256 `666f66a5…` | **no**: the rebuild (stem = the certified name) is `497ddc82…` with today's clock and `83d7bb46…` pinned; with `RVT_WALL_REP=dummy` (pre-#144 walls) it is `9b3150d5…`, still not the certified bytes | **form, registered** (`recipe='author'`; `certified` = the ledger's own sha) |
| `experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt` | four-registry loader (verdict #7, 2026-08-03) | `rvt.famgen.heads` level-head annotation skeleton, loaded by `rvt.famload` into the git-ignored rst sample | partly (`heads.build_head_family('level_head')`); the host is a sample | n/a, because no route emits a level head. `probes.json` itself says "L1a = the mechanism on a passing base" | **mechanism only** |
| `experiments/ifc_room/electrical_room_2500a_walls_only.rvt` | wall creation on the genesis lineage (verdict #22) | `tools/ifc_intent.py` build_room, stage W, on ZA_deep (owner machine), dummy wall reps | needs ZA_deep, so not on a fresh clone | **no**: the base is now G_ABPD and the walls carry solids since #144 | **mechanism only** |
| `experiments/render/RSOLID_walls_A_solid.rvt` | created walls render (verdict #26) | render-emit probe builder (batch 25) on the walls-only base | owner-machine base | a probe, not a route output | **mechanism only** |
| `experiments/render/g12/W1_gabpd_wall_solid.rvt` (HONEST-STATUS only) | wall solid renders on G_ABPD | `experiments/render/g12/build_g12_probes.py` | yes (probe script), but it is cited for the mechanism | a probe, not a route output | **mechanism only** |
| `experiments/acceptance/V23_electrical_room.rvt` | spec->rvt legacy (2026-08-03) | `tools/spec_to_rvt.py` on an Autodesk MEP template: our walls plus instances of the **template's** family types | template is a git-ignored sample | unknown/very likely moved (writer changes); no family of ours inside | **mechanism only** |
| `experiments/acceptance/V25_room_from_ifc.rvt` | IFC->rvt (2026-08-03); also cited for the ifc->intent stage | `tools/ifc_to_spec.py` → `tools/spec_to_rvt.py` on the template | template sample | different pipeline from today's ifc->rvt | **mechanism only** |
| `experiments/acceptance/V26_room_from_ifc_with_walls.rvt` | as V25 + synthesized walls | same | same | same | **mechanism only** |
| `experiments/manipulate/M2_delete_cascade{,_rac}.rvt`, `M3_modify.rvt`, `M4_move_retype.rvt` | edit pipeline | none (they edit or delete existing elements) | — | — | none (no change) |
| `experiments/rftprobe/T2a.rvt` | any-.rfa load mechanism | none (Revit-born family; our loader and placement) | — | — | none, wording already says "the MECHANISM is viewer-CERTIFIED (T2a) … this lane's own artifacts pending" |
| `experiments/species/TB0g.rvt` | extract->place at base level | none (embedded-born famdoc) | — | — | none, wording already says "base level … the product lane's own artifact is validator/census-gated" |

Not touched: `WF_fix` / `WF_nofix` / `V29` / `V18` / `V19` / `V15` in HONEST-STATUS. They are cited as
open-cell controls or for template-era / edit evidence, and their rows already say so.

## Decisions (DONE 2)

- **Registered (form):** `stage_L8_lp4.rvt` and `ROOM2025_walls.rvt`. In both cases the citing
  rows read as "what this route / these constructors emit is certified". Both rebuild
  deterministically on a fresh clone. `EVIDENCE_FORMS` entries now carry a `recipe`
  (`downlight` | `family_set` | `author`), and `generator_fingerprint` dispatches on it.
  `family_set_fingerprints` gives the per-family `(tag, sha, family-mode verdict)`. The recipes pin
  their own env: `SOURCE_DATE_EPOCH` is unset for families, and for the author recipe it is `0`
  with `RVT_WALL_REP` unset (otherwise the project's issue date is the wall clock).
- **Mechanism only:** `EVIDENCE_MECHANISMS`, with one caveat per file (`L1A_MECHANISM_ONLY`,
  `ROOM_2500A_WALLS_MECHANISM_ONLY`, `RSOLID_MECHANISM_ONLY`, `W1_MECHANISM_ONLY`,
  `V23/V25/V26_MECHANISM_ONLY`). Each caveat says what the file certifies, when it was certified
  (before the repo's history), and what it does not certify. These files are not fingerprinted,
  because no row claims their form and most need owner-machine bases or samples.
- **One hook:** `required_caveat(path)` returns the earlier-form caveat or the mechanism caveat.
  `verify_evidence()` fails any matrix row that cites such a file without it, and also fails a
  registry entry that is not in the ledger.
- **Wording.** Every changed caveat says "not complete" and never claims to be a complete list of
  changes.
  - `_FAMSPEC_GATES` now says the ledger holds *earlier forms* of these constructors' families,
    loaded unplaced (stage_L8, an empty-design translation), plus the load mechanism (L1a, a
    level-head annotation family, not a famspec kind).
  - `_RFA_HOST` says the same in short form.
  - The `prompt->rfa->loaded-rvt` chain note now says the certified file has NO placed instance.
- **Status:** none changed. Every affected cell's `works` rests on runnable tests and worked
  manifests, and its caveats now say what the viewer has and has not seen. Honesty does not
  require a downgrade. Note one judgement call: the `prompt->rfa->loaded-rvt` chain's only
  evidence is now an explicitly caveated, unplaced file, so it says nothing certified about
  "placed". The chain's `works` is still the F/L stages that run, as before. Whether that chain
  should cite `test:` evidence too is left as an open question (below).

## Rows changed

- **`matrix.py`:**
  - stages ifc->intent (V25), intent->rvt (2500a walls-only + stage_L8 + RSOLID), rfa-load (L1a),
    spec->rvt-legacy (V23), rfa-reload (stage_L8);
  - cells prompt->rvt (walls-only + stage_L8), ifc->rvt (V25 + V26), rfa->rvt (L1a + stage_L8),
    spec->rvt (V23), rfa+rvt->rvt (L1a + stage_L8), rvt+spec->rvt (V23);
  - chain prompt->rfa->loaded-rvt (stage_L8);
  - shared texts `_RFA_HOST` and `_FAMSPEC_GATES`.
- **`docs/product/PERMUTATION-MATRIX.md`:** rows prompt → rvt, ifc → rvt, rfa → rvt (L1a, stage_L8),
  rfa → rfa (the "same constructors" sentence), spec → rvt, rfa + rvt → rvt (L1a, stage_L8),
  spec + rvt → rvt, chain prompt → rfa → loaded-rvt. Each gained a short "(**an earlier form**,
  #984: …)" or "(**mechanism only**, #984: …)" parenthesis.
- **`plugin/docs/HONEST-STATUS.md`:** the prompt → `.rvt` row (ROOM2025 earlier form, W1/RSOLID
  mechanism only, stage_L8 re-worded from "family load + instance placement" to "family **load**"
  plus its caveat), IFC → `.rvt` (V25/V26), spec → `.rvt` (V23), family generation (L1a), LOAD vs
  RENDER (W1).

## Evidence (numbers)

Reviewed fingerprints at `276a5a8`, computed in two separate processes in different orders and
identical both times:

| entry | 2026 | 2025 |
|---|---|---|
| stage_L8 family set | `ea239c27…45f4` | `5fe7308d…b1ba` |
| ROOM2025_walls (author) | — | `83d7bb46…e26f` (ledger's certified: `666f66a5…2d55`) |
| downlight (#981, re-checked) | `ea274092…7910` ✓ | `4a67e333…79bb` ✓ |

- All eight stage_L8 families today are family-mode **VALID** (per-family 2026:
  MSB `6d724d5f`, DP-1 `cbcfec18`, DP-2 `d6149f86`, LP-1 `088e1d7f`, LP-2 `c3d7279c`,
  LP-3 `43b70a01`, T1 `769c11e2`, LP-4 `333b6ade`).
- Build times: ~7 s at 2026, ~14 s at 2025; the author recipe takes ~1 s.
- A subprocess test with a hostile env (`SOURCE_DATE_EPOCH=1234567890`, `RVT_WALL_REP=dummy`)
  reproduces the reviewed values. The author out dir is not in the bytes, but the stem is
  (`prompt_room` gives `dcdfb683…`).

## What the guard can and cannot prove

- **Can:**
  - No machine-matrix row can cite one of these files without its caveat.
  - A new `certified:` citation fails `test_every_certified_citation_has_an_inventory_decision`
    until someone classifies it.
  - The next byte change to the panelboard / transformer / house-switchboard constructors at these
    kwargs, or to the 2025 prompt walls-only build, turns `test_matrix_evidence_984` red in that PR.
  - Doc rows naming a registered file must carry `#984` plus "earlier form" / "mechanism only".
- **Cannot:**
  - Say anything about Revit (hard rule 4).
  - Tell what the certified stage_L8 families' bytes were (`certified: None`).
  - Cover HONEST-STATUS / PERMUTATION-MATRIX statically beyond the regex row check: the docs are
    hand-kept, and a row that names a file by a new spelling escapes `doc_names`.
  - Fingerprint the stage_L8 *load*. The recipe is the standalone `.rfa` of each family, not the
    component-loaded project.
  - Promise that the family-set recipe equals what `prompt->rvt` builds for the 2500 A room today
    (different intent → kwargs path). It pins the constructors at the recorded kwargs.

## Coordination note

The stage_L8 fingerprint pins `rvt.famgen.factory` / `rvt.ifc.intent.make_house_switchboard`
output. Any in-flight PR that changes those constructors' bytes, such as the famgen PR in flight
now, will turn this test red, or this branch's reviewed values will be stale after that PR merges.
That is intended. Whoever merges second re-words the caveat if needed, then re-records `reviewed`
with `M.generator_fingerprint(path, release)`.

## Open questions (not changed here)

- **Ledger:** the `stage_L8_lp4.rvt` ledger line still reads "family LOAD + instance PLACEMENT …
  PASS". Verdict #25 retracted the placement reading. Correcting `viewer-certified.json` (a
  hot file, human verdict domain) needs its own `hot-file` PR.
- **Chain evidence:** `prompt->rfa->loaded-rvt` cites only stage_L8. It could also cite
  `test:tests/test_frontdoor.py` so that its `works` visibly rests on runnable evidence.
- **Templates:** V23/V25/V26 are template-era files. `ifc->rvt` today has no certified *ifc->rvt
  output* on the genesis base except the 2500a walls-only shell (an earlier base). A viewer batch
  of today's ifc->rvt walls-only output would replace that.

## BRANCH STATE

Branch `fix-984` from `276a5a8`, one local commit, **not pushed**.
- **Files written:**
  - `src/rvt/frontdoor/matrix.py`, plus its mirror `plugin/lib/src/rvt/frontdoor/matrix.py` via sync
  - `docs/product/PERMUTATION-MATRIX.md`
  - `plugin/docs/HONEST-STATUS.md`
  - `tests/test_matrix_evidence_984.py` (new)
  - `tests/ci_shard.d/984-matrix-evidence.txt` (new)
  - `tests/test_matrix_evidence_981.py`: one assertion relaxed. A registered file is fingerprinted
    at the releases its recipe builds; the downlight is still pinned at both.
  - this record
- **Gates** (`RVT_SKIP_LARGE=1`):
  - test_matrix_evidence_981 + test_matrix_evidence_984 + test_router + test_router_load_release +
    test_router_release + test_frontdoor_manifest_pin + test_ci_fresh + test_conftest_scaffolding +
    test_records_layout + test_plugin_sync, run together: **316 passed / 15 skipped** (182 s).
  - The two evidence modules alone: 39 passed / 1 skipped (25 s; the skip is the downlight doc
    check, which belongs to #981's module).
  - `tools/route.py matrix` self-audit clean (25 cells / 27 stages / 5 chains).
  - `tools/sync_plugin.py`, then `--check`: in sync. `validate_plugin.py` PASS.
    `check_portable_paths.py` ok.
- **Staged:** nothing.
