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

## Second round — the annotation, mass and titleblock templates

The owner then supplied the annotation set (tags, heads, marks), `Mass.rft` and the
titleblocks: **108 templates total, 59 mined rows**, all still clean.

**The device/tag pairing law [VERIFIED on three matched pairs].** A low-voltage device
category is immediately followed by its own tag category, `tag == device − 1`:

| device | | tag | |
|---|---|---|---|
| Telephone Devices | −2008075 | Telephone Device Tags | −2008076 |
| Data Devices | −2008083 | Data Device Tags | −2008084 |
| Fire Alarm Devices | −2008085 | Fire Alarm Device Tags | −2008086 |

So the band **alternates**, and devices sit on the odd slots −2008075/77/79/81/83/85.
That is why inventory's assumed list looked contiguous when it is actually every
other slot.

**This resolved the open conflict, and exposed an eighth wrong id.**
`nurse_call_device` mapped to **−2008084 — which `Data_Device_Tag.rft` proves is Data
Device *Tags***: asking for a nurse-call device produced a family filed under a tag
category. Corrected to −2008081, the only device slot left once Data and Fire Alarm
are template-pinned. It stays `[INFERRED]` — no nurse-call template exists, so this is
the band law plus elimination, not a direct reading. The pairing law also independently
**confirms** the `security_device` −2008079 and `communication_device` −2008077 choices
made in the first round: both land on device slots.

inventory's assumed block had **Fire Alarm and Nurse Call swapped**. Its own −2008085
row still reads `OST_NurseCallDevices`; correcting that table is a different territory
and was left alone.

**19 annotation kinds are now resolvable** and marked as a distinct species
(`category_facts.ANNOTATION_KINDS`, part type −1, view-owned instances): titleblock
−2000280 (all six sheet sizes share it), generic annotation −2000150, generic tag
−2005013, multicategory tag −2005022, room/door/window tags −2000480/−2000460/−2000450,
electrical equipment/device tags −2005003/−2005004, level/grid/section/callout heads
−2006020/−2006040/−2000400/−2000538, elevation mark −2006045, spot elevation symbol
−2005100, view title −2000515. Plus **conceptual mass −2003400** (the one mined row
with `work_plane_based=True` — caught by the mining gate after I typed False).

Two gates earned their keep this round: `check_facts()` caught ten kinds present in the
mined table but missing from the resolver, and `rft_facts.py check` caught the Mass
work-plane flag.

## Open questions

- `nurse_call_device`, `security_device`, `communication_device` sit on the band law
  plus elimination, not a direct reading. A nurse-call or security template would
  settle them outright.
- Annotation categories are verified as **ids**; we have not built a tag family in each
  and watched Revit accept it. #691 is where that gets tested.

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
- `tests/test_category_facts.py` — new, 64 tests; `tests/ci_shard.d/516-category-facts.txt`.
- `plugin/skills/tekton-author/references/FAMSPEC-CAVEATS.md` — the four evidence
  tiers, and the note that families built in the seven wrong categories should be
  regenerated.
- this record + `docs/inbox/rft-mining.md` (new stream index).

**Gates**
- `tests/test_category_facts.py` — **64 passed** (37 after round 1, 64 after the annotation round).
- `tests/test_famgen_standards.py tests/test_famgen_factory.py` — **137 passed, 5 skipped**.
- full CI shard — **2464 passed, 160 skipped, 2 xfailed, 1 failed** (the failure was
  `test_plugin_sync` drift from the `src/` edit, cleared by running `sync_plugin.py`).
- `tools/sync_plugin.py` — synced 2 files, **deny-audit clean**, assets verified, zip
  rebuilt; `plugin/scripts/validate_plugin.py` — **PASS, 25 assertions**.
- `tools/rft_facts.py check` — **clean, 59 rows match the 108 templates on disk**.
- Anti-vacuity check: reverting two corrections in `skeleton.py` was confirmed to fail
  3 tests, and the file was restored (the round-5 lesson from #674 — a pinning test
  that cannot fail is worse than none).

**Staged vs shipped:** all shipped. No viewer batch — this changes an integer in a
header, and the certified-base lineage is untouched.
