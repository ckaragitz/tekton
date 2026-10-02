# 876 (part B) — a profile map proposed from the user's own families

Stream **family-shared-params** (tech-lead session, 2026-10-02). Closes #876: DONE 2. Part A (`876-profile-map.md`) applies the map.

## What changed

New tool **`tools/profile_map_from_rfa.py LIBRARY --category ID -o MAP.json`**. It reads the user's own `.rfa` files, each in its own release. For each shared parameter that labels a dimension it records the axis of every labelled `LinearDimString` segment, from `m_pDimLine.m_dirVec` in the family's coordinates, and proposes the map `make_family --profile-map` takes.

- **Roles:** our generated equipment is Width along x, Depth along y and Height along z. `geometry.box` builds it that way, and the generated transformer labels its shared sizes on those axes (checked in the test). `--targets x=…,y=…,z=…` names other roles.
- **A parameter is proposed only when all of these hold:**
  - it is a **length**;
  - it labels an **axis-aligned** dimension in at least `--min-families` families (default 2);
  - at least `--min-share` of them (default 0.8) agree on the axis;
  - it is that axis's **primary** parameter: the one labelling the axis in the most families.

  A tie is not guessed. A parameter sizing a *part* along the same axis is not proposed, with its reason. The report lists every labelling parameter and why it was or was not proposed.
- **The map and report go only where the user says.** This module holds no library content; the owner's proposal lives in the quarantined `samples/reference-families/analysis/`, never in the repo (rule 6).

## Evidence

- `tests/test_profile_map_from_rfa_876.py`: **15 passed**. It covers:
  - axis detection (aligned in either sense, oblique, unreadable);
  - primary per axis, where a part's width loses to the family's width;
  - each refusal reason: non-length, oblique, too few families, disagreement, tie;
  - the category filter and custom targets;
  - **end to end:** a "library" of our own generated transformer and panelboard with shared Width/Depth/Height. The CLI reads the written files and proposes exactly x→Width, y→Depth, z→Height.
- **Owner's library (private, counts only):**
  - 421 of 421 read, 0 errors.
  - Electrical equipment (`-2001040`): 11 shared length parameters label dimensions.
    - **3 are proposed:** the library's overall depth (16 families, all y), height (16, all z) and width (15, all x).
    - The other 8 each label a part's width in a single family, so they are not proposed.
    - The first version of the rule proposed all 11 as Width. Reviewing that output is what added the primary-per-axis rule and the default of 2 families.
  - All categories at once: 34 labelling parameters.
    - Before the primary-per-axis rule, 24 were proposed across categories; 6 are not lengths and 4 have families that disagree on the axis.
    - This is why the docs say to run per `--category`.
- **Applying the owner's profile with the proposed map** (`ProfileRequest(links=…)`) to a 45 kVA transformer and a panelboard: 3 links each, VALID with 0 errors, provenance ok, no refusals.

## Not claimed

The proposal is a starting point the user reviews. That the linked parameters report our sizes in Revit needs a desktop verdict (hard rule 4).

## BRANCH STATE

- Files:
  - `tools/profile_map_from_rfa.py`. Like `shared_params_from_rfa.py`, it is a repo tool and not mirrored into the plugin; `sync_plugin --check` is clean;
  - `tests/test_profile_map_from_rfa_876.py`, added to the drop-in `tests/ci_shard.d/876-profile-map.txt`;
  - this record.
- Shipped on merge; nothing is staged.
