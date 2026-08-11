# 516 — family category ids and part types, mined from Revit's own templates

Closes #516 DONE (1). Stream: `rft-mining`.

## What removed the `needs-revit-desktop` gate

#516 asked a human to build one family per category, open it in Revit 2026, and read
the Family Category and Parameters dialog to confirm each id. Revit's default family
templates answer the same question from the format itself, and answer it *better*: a
template named for a category **is** a family document of that category, so its
self-`Family.m_categoryId` is the id Revit itself assigns — the value Revit wrote,
rather than a label it rendered. The label was dropped and the issue set `ready`.

What this does **not** settle, and the record says so in code
(`category_facts.BROWSER_PLACEMENT_UNVERIFIED`): that a family *we* author with that
id lands in the expected branch of the Project Browser. That is still a Revit-side
observation (hard rule 4). DONE (2) — inferring a category from the object being
described — is not in this PR.

## Evidence

82 templates in `samples/rft/`, all decoding clean through `load_rft_elements`
(1686–2194 elements each). Two independent in-repo sources cross-checked:

| tier | source | strength |
|---|---|---|
| `rft` | the category's own default family template | Autodesk's own declaration |
| `inv` | `rvt.inventory.BUILTIN_CATEGORIES_VERIFIED` | a real sample ELEMENT carries the id |
| `inv?` | `rvt.inventory.BUILTIN_CATEGORIES_ASSUMED` | a public constant nothing exercises |

Every template-verified id matches inventory's VERIFIED row wherever inventory has
one — 39 rows agree, 0 disagree (`tools/rft_facts.py check`).

## Seven shipped ids were wrong

Each silently produced the **wrong kind of family** — not an error, a plausible file
in the wrong category.

| key | was | now | tier | what `was` actually is |
|---|---|---|---|---|
| `casework` | −2000079 | **−2001000** | rft | Room Separation (`residue_a.PARENT_LABELS`) |
| `fire_alarm_device` | −2008013 | **−2008085** | rft | **`OST_DuctTerminal` / Air Terminals** — asking for a fire-alarm device built an *air terminal* |
| `telephone_device` | −2008086 | **−2008075** | rft | nothing in any in-repo table |
| `security_device` | −2008085 | **−2008079** | inv? | Fire Alarm Devices, by that category's own template |
| `lighting_device` | −2008080 | **−2008087** | inv | nothing; −2008087 is `OST_LightingDevices` (real 'Single Pole' switch) |
| `cable_tray_fitting` | −2008131 | **−2008126** | inv | nothing; −2008126 is `OST_CableTrayFitting` (real 'Channel Horizontal Bend') |
| `conduit_fitting` | −2008133 | **−2008128** | inv | nothing; −2008128 is `OST_ConduitFitting` (real 'Conduit Body - Type L') |
| `communication_device` | −2008012 | **−2008077** | inv? | nothing in any in-repo table |

`security_device` was **not** retired. Raising would turn a working route into no file
(hard rule 1); it now resolves to the public `OST_SecurityDevices` constant and stays
labelled `[INFERRED]`, which is a strict improvement on a known-wrong value rather
than a verification.

## Also mined

- **20 categories we had no key for** are now resolvable: `structural_foundation`
  −2001300, `structural_stiffener` −2001354, `furniture_system` −2001100, `entourage`
  −2001370, `planting` −2001360, `parking` −2001180, `site` −2001260, `detail_item`
  −2002000, `profile` −2003000, `curtain_wall_panel` −2000170, `baluster` −2000127,
  `railing_support` −2000948, `railing_termination` −2000949, `duct_fitting` −2008010.
- **Part types.** −1 or 0 everywhere except Electrical Equipment **14**, Data Panel
  **17**, and the duct fittings, which enumerate by kind: elbow **5**, tee **6**,
  transition **7**, cross **8** (new constant `SK.DUCT_FITTING_PART_TYPE`).
- **`PART_TYPE` 15/16 are still guesses.** Our table calls 14 "panelboard" and guesses
  15 = transformer, 16 = switchboard `[H]`. The Electrical Equipment category's *own*
  template carries 14, so 14 is the category-generic value and 15/16 rest on nothing —
  and we emit them today. Settling that needs a real panelboard/transformer `.rfa`,
  not a template. Follow-up filed; behaviour deliberately unchanged in this PR.

## Open questions

- **The low-voltage band is offset somewhere.** inventory's ASSUMED block reads it as
  Communication −2008077 / Security −2008079 / Fire Alarm −2008081 / Data −2008083 /
  Nurse Call −2008085. The templates agree on Data but put **Fire Alarm at −2008085**
  and **Telephone at −2008075**. So `nurse_call_device` (−2008084) and
  `security_device` rest on a band known to be wrong somewhere. Recorded as
  `category_facts.INVENTORY_ASSUMED_BAND_CONFLICT` and pinned by a test rather than
  quietly picked. Needs a nurse-call/security template or a sample element.
- inventory's own −2008085 row still reads `OST_NurseCallDevices`; correcting that
  table is a different territory and was left alone.

## Provenance / rule 3

Zero donor bytes. What crosses into the repo is three integers and a boolean per
family kind plus the source file's **name** as citation. Templates stay in the
git-ignored quarantine; `tools/sync_plugin.py`'s deny-audit ran clean and the identity
scan reports 0 mismatches. `tools/rft_facts.py` emits values only — never content.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/category_facts.py` — new: the mined table (39 rows), `CORRECTIONS`
  with evidence tiers, `HOST_VARIANTS`, `STILL_INFERRED`, the band conflict, and
  `check_facts()` as the provenance gate.
- `src/rvt/famgen/skeleton.py` — `_resolve_category` corrected + 20 kinds added, each
  row tagged with its evidence tier; `PART_TYPE` docstring records the template
  reading and that 15/16 remain guesses; new `DUCT_FITTING_PART_TYPE`.
- `tools/rft_facts.py` — new: `mine` / `check` / `params`. Exits 0 with a plain
  message when no templates are present (a fresh clone has none).
- `tests/test_category_facts.py` — new, 37 tests; `tests/ci_shard.d/516-category-facts.txt`.
- `plugin/skills/tekton-author/references/FAMSPEC-CAVEATS.md` — the four evidence
  tiers, and the note that families built in the seven wrong categories should be
  regenerated.
- this record + `docs/inbox/rft-mining.md` (new stream index).

**Gates**
- `tests/test_category_facts.py` — **37 passed**.
- `tests/test_famgen_standards.py tests/test_famgen_factory.py` — **137 passed, 5 skipped**.
- full CI shard — **2464 passed, 160 skipped, 2 xfailed, 1 failed** (the failure was
  `test_plugin_sync` drift from the `src/` edit, cleared by running `sync_plugin.py`).
- `tools/sync_plugin.py` — synced 2 files, **deny-audit clean**, assets verified, zip
  rebuilt; `plugin/scripts/validate_plugin.py` — **PASS, 25 assertions**.
- `tools/rft_facts.py check` — **clean, 39 rows match the templates on disk**.
- Anti-vacuity check: reverting two corrections in `skeleton.py` was confirmed to fail
  3 tests, and the file was restored (the round-5 lesson from #674 — a pinning test
  that cannot fail is worse than none).

**Staged vs shipped:** all shipped. No viewer batch — this changes an integer in a
header, and the certified-base lineage is untouched.
