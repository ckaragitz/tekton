# mep-taxonomy — the MEP equipment taxonomy and the vendor directory (#692, steer #685)

Stream record. Engineer session on `eng/692-taxonomy`.

## What this closes

`standards` (#601) answers *"given a category, what parameters does a family carry"*.
`catalog` answers *"given a vendor and a line, what are the published figures"*. Nothing
answered the two questions in between, which are the ones a request actually arrives as:

- "make me a **motor control centre**" — what is that, and which Revit category is it?
- "make me an **Eaton panelboard**" — do we hold real facts for that line, or are we about
  to invent them?

`src/rvt/famgen/taxonomy.py` (new, 1403 lines) is those two tables plus the gate that keeps
them honest. Nothing imports it yet — this PR delivers the tables and the gate, not the
wiring into the family constructors. That is stated rather than implied (see *Open*).

## The line this stream was drawn around

The issue's central constraint, and the thing every design decision here serves:

| may come from model knowledge | may **not** |
|---|---|
| what MEP equipment exists; which Revit category it belongs in; which parameters an engineer schedules it by | **any member's dimensions or ratings presented as a `fact`** |
| that Eaton makes Pow-R-Line panelboards, Square D the NQ/NF/I-Line, Hoffman enclosures | anything written into `facts/**` or anywhere `catalog.py` resolves |

`catalog.py`'s basis line — *facts are not copyrightable; we store no manufacturer files* —
is about **published tables that were read**, with a source document and date accessed per
figure. It is not a licence to write down recalled numbers: those are indistinguishable
downstream from the genuinely sourced records, which is precisely what makes them harmful.
**No file under `src/rvt/famgen/facts/**` is touched by this branch** — the diff in
*BRANCH STATE* is five files, all additions, none of them a facts record.

A third tier exists and is deliberately **not** here: standard practice for a product
CLASS (a 12 in ladder tray, a 1-5/8 in strut) is the `nominal` tier of steer #591 and
belongs to the **archetype registry**, not to this table. `archetype_status()` reports the
boundary; see *Degrading without #674*.

## The two tables

**Taxonomy** — 62 taxa over 19 Revit categories, 185 trade aliases:

| discipline | taxa | discipline | taxa |
|---|---|---|---|
| electrical | 12 | fire_alarm | 6 |
| lighting | 9 | raceway | 2 |
| low_voltage | 10 | mechanical | 12 |
| plumbing | 11 | | |

Each row is `key / label / discipline / category / schedule_by / role / aliases / note`.
**There is no field for a size, a rating, a voltage or a weight** — by construction, so a
recalled figure has nowhere to go. `schedule_by` names *parameters*, never values.

**Vendor directory** — 46 vendors, 99 product lines, of which **7 carry `facts_held: true`**
— exactly the 7 records in the store, no more and no fewer:

| vendor / line | taxa | facts record |
|---|---|---|
| Eaton — Pow-R-Line panelboards | panelboard | `eaton/pow-r-line-panelboards` (6 variants) |
| Eaton — Dry-type distribution transformers | dry_type_transformer | `eaton/dry-type-transformers` (9) |
| Square D — NQ / NF / I-Line panelboards | panelboard | `square-d/nq-nf-iline-panelboards` (3) |
| HPS — Sentinel G dry-type transformers | dry_type_transformer | `hps/sentinel-g-transformers` (2) |
| Lithonia — BLT LED troffers | recessed_troffer | `lithonia/blt-led-troffer` (2) |
| Lithonia — LDN LED downlights | downlight | `lithonia/ldn6-led-downlight` (1) |
| Generic — Wiring devices and mounting boxes | receptacle, wall_switch, enclosure | `generic/devices-and-mounting` (4) |

The other **92 lines say `facts_held: false`** and carry no `facts_ref` at all. That is the
honest majority, and it is the answer that stops a named part number from silently becoming
a generic object wearing that number (steer #591).

## The gate — the deliverable, as much as the tables

`python -m rvt.famgen.taxonomy --check`, and `taxonomy.check()` in-process. Nine rules; the
headline is **T5**.

| rule | what it refuses |
|---|---|
| T1 | either dataclass gaining a field a dimension or rating could live in |
| T2 | a category `skeleton._resolve_category` does not know, or that `standards` has no table for |
| T3 | a `schedule_by` name that is not really a parameter of that category in `standards` — compared by `standards.meaning_key`, so #622's one-entry-per-meaning law reaches this table too |
| T4 | malformed keys, unknown disciplines, duplicate/ambiguous aliases, empty `schedule_by`, unknown taxon refs |
| **T5** | **a `facts_held: true` line `catalog` cannot resolve** — the record is *loaded*, and must have ≥1 variant |
| T6 | a `facts_held: false` line carrying a `facts_ref` |
| T7 | a number-followed-by-a-unit anywhere in either table's prose |
| T8 | *backwards*: a record in the store that no line claims (the directory understating what we hold), or two lines claiming one record |
| T9 | a facts-held line whose taxa disagree with the record's own `category` |

**T1 + T7 together are the "no fabricated figures" guarantee.** T1 is structural — the
schema has no slot for a figure, so the check is `fields(Taxon) == the allowed set`, and a
future edit that adds `dims` or `ratings` fails. T7 closes the prose loophole: a dimension
cannot be smuggled in as a `role` or a `note` either.

### Evidence that each rule actually fires

A gate nobody has watched fail is not evidence, and the shipped tables passed on the very
first run — so the test module is mostly **negative**: it breaks a copy of the table in
exactly one way per rule and asserts the gate fails.

```
tests/test_famgen_taxonomy_692.py ................................. 49 passed in 0.32s
```

| rule | test that watches it fail |
|---|---|
| T5 | `test_a_facts_held_line_catalog_cannot_resolve_fails_the_gate`, `..._naming_a_missing_vendor_dir...`, `..._with_a_malformed_ref...` |
| T5 (exit code) | `test_the_check_cli_exits_nonzero_when_a_claim_cannot_be_backed` — asserts `main(["--check"]) == 1`, not just that a message was printed |
| T6 | `test_a_facts_ref_without_the_claim_fails_the_gate` |
| T8 | `test_an_unclaimed_facts_record_fails_the_gate` (drops the HPS vendor), `test_two_lines_claiming_one_record_fails_the_gate` |
| T2 | `test_an_unknown_category_name_fails_the_gate`; second branch simulated in `test_a_category_with_no_standards_table_fails_the_gate` |
| T3 | `test_an_invented_schedule_parameter_fails_the_gate`, `test_a_second_spelling_of_a_standards_parameter_fails_the_gate` (`Lumens` vs `Luminous Flux`) |
| T4 | empty `schedule_by`, unknown discipline, unknown taxon ref |
| T7 | 5 parametrised figures (`12 in`, `480 V`, `75 kVA`, `4600 lm`, `300 lb`) + a vendor-note case |
| T1 | `test_a_field_that_could_hold_a_dimension_fails_the_gate` |
| T9 | `test_a_facts_record_category_disagreeing_with_the_taxon_fails` |

And the positive half — `test_every_facts_held_line_really_resolves_through_catalog` walks
all 7 claimed lines, loads each record, asserts `catalog.validate_line(doc) == []`, and for
every one of the 27 variants asserts `dims_feet` returns `{w,h,d}` and the model is
selectable by name. **If a table row says we hold facts for a line, that test proves we can
resolve them.**

### Two false-positive traps T7 had to survive

`_NUM_UNIT_RE` requires a unit token *after* the number, so product designations are not
mistaken for figures — pinned in `test_product_designations_are_not_mistaken_for_figures`:
`NEMA 5-15R`, `Cat 6`, `Model 6`, `I-Line`, `Pow-R-Line`, `9395 UPS`, `39 series`,
`P1 / P2`. Without that, half the directory would be unwritable.

## Degrading without #674

`src/rvt/famgen/archetypes.py` exists **only on the unmerged PR #674** and is absent from
`main`. It is imported **softly**, inside `archetype_status()`, and nothing here requires
it. On this branch:

```
archetypes ABSENT — ImportError: cannot import name 'archetypes' from 'rvt.famgen'
```

`--check` reports `archetypes ABSENT` and still exits 0.
`test_the_module_works_without_the_archetype_registry` asserts the gate is clean either
way, and `test_taxonomy_does_not_import_archetypes_at_module_scope` reads the source and
fails if the import is ever hoisted to the top. When #674 lands, `present` flips to `True`
with no change here.

## Findings

1. **The `--check` gate passed on the first run of the shipped tables.** That is not
   reassuring on its own — it is exactly the condition under which a gate that checks
   nothing looks identical to a gate that works. The negative tests above exist because of
   it, and one of them caught a wrong premise in my own first draft (below).
2. **`cable_tray` is not a category with no standards table.** My first T2 test assumed it
   was, because `CATEGORY_STANDARDS` has no `cable_tray` key. It failed: `standards`
   aliases `cable_tray → cable_tray_fitting`, which does have a table, and the gate
   correctly resolved it. **Every category `skeleton._resolve_category` knows currently has
   a standards table after aliasing** — pinned in
   `test_every_skeleton_category_this_table_uses_has_a_standards_table` — so T2's second
   branch is defensive and its test says so explicitly rather than pretending otherwise.
3. **The store's `generic/devices-and-mounting` record spans three taxa** (receptacle,
   wall switch, box), which is why `VendorLine.taxa` is a tuple and why T9 maps a facts
   record's `category` to a *set* of Revit categories rather than one.
4. **`schedule_by` is the taxonomy's only checkable claim, and it is worth more than the
   category.** "An engineer schedules a transformer by its kVA rating" is trade knowledge
   that would otherwise float free; binding every name to `standards` makes it a statement
   this repo can verify, and made T3 catch two spelling drifts while I was writing the
   table.

## Where this lands relative to S-2026-08-11-b (#684)

`main` gained the prompt-interview steer while this branch was open (rebased onto
`e55bd9b`). That steer asks for an interview whose questions are **derived** from what the
engine already holds — "adding a vendor, product line, archetype or category produces its
questions with no new interview code", with "vendor and line … first-class questions
wherever the catalog holds more than one, and a catalog answer routes to real facts".

These two tables are usable as part of that substrate, and the read API was built to be
queried rather than printed: `resolve()` takes the user's word ("xfmr", "horn strobe") to a
taxon, `describe()` returns its category, its `schedule_by` parameters and every vendor
line with `facts_held` on each, `lines_for_taxon()` sorts the sourced lines first, and
`sourced_lines()` is the set a catalog answer can route into. **No interview is implemented
here and none is claimed** — #684 is its own issue. This is only a note that the shape fits,
so whoever picks it up does not rebuild the directory.

## Open

- **Nothing consumes these tables yet.** The obvious next step is `prompt_intent` /
  `factory` resolving a request through `resolve()` to pick a category and a parameter set,
  and through `lines_for_taxon()` to say honestly whether a named vendor line has facts.
  That is a separate issue with its own DONE; this PR does not claim it.
- **The 62 taxa and 46 vendors are INFERRED trade knowledge.** No desktop-Revit round and
  no manufacturer confirmation stands behind the category assignments — the same
  `convention`-tier caveat `standards` carries. What *is* verified is internal consistency:
  the category vocabulary, the parameter names, and the facts claims.
- **Category assignments a Revit content author might argue with**, recorded rather than
  smoothed over: `water_heater → mechanical_equipment` (noted on the row);
  `vav_terminal → mechanical_equipment` rather than an air-terminal category the repo has
  no table for; `fire_alarm_control_panel` and `lighting_control_panel → electrical_equipment`.
- **T7's unit vocabulary is hand-authored** (`_UNIT_TOKENS`). It covers the units an MEP
  figure would plausibly be written in, but it is a denylist, not a proof.
- The 92 `facts_held: false` lines are where sourcing work would go next; each is a
  ready-made target with its taxon and category already decided.

## Gates run

| gate | result |
|---|---|
| `pytest tests/test_famgen_taxonomy_692.py -q` | **49 passed** in 0.32 s |
| `pytest tests/test_famgen_taxonomy_692.py tests/test_famgen_standards.py tests/test_plugin_sync.py -q` | **138 passed** in 2.43 s |
| `pytest tests/ -k "famgen or catalog or standards or taxonomy"` | **391 passed, 61 skipped** in 36.8 s (skips = no `samples/` in a fresh clone) |
| `python -m rvt.famgen.taxonomy --check` | `62 taxa across 19 categories, 46 vendors / 99 lines, 7 facts-held (store has 7), archetypes ABSENT, 0 problems` — **exit 0** |
| same, from a bare unzipped `tekton-plugin.zip` | 0 problems, **exit 0** |
| `tools/sync_plugin.py --check` | **exit 0** (drifted on `lib/src/rvt/famgen/taxonomy.py` until `sync_plugin.py` was run — mirror committed) |
| `plugin/scripts/validate_plugin.py` | **PASS**, 25 assertions |
| `tools/dev/check_portable_paths.py` | ok: 3066 tracked paths portable |
| `tools/dev/shard_list.py --print` | 118 entries, includes `tests/test_famgen_taxonomy_692.py` |

## BRANCH STATE

**Branch** `eng/692-taxonomy`, cut from `main` at `ea6b875`. One issue = one branch = one PR
(`Closes #692`).

**Files written**

| path | what |
|---|---|
| `src/rvt/famgen/taxonomy.py` | new, 1403 lines — both tables, the lookups, `check()` (T1–T9), the `--check` CLI |
| `tests/test_famgen_taxonomy_692.py` | new, 514 lines, 45 test functions / 49 cases — mostly negative: each gate rule watched failing |
| `tests/ci_shard.d/692-taxonomy.txt` | new drop-in (`tests/ci_shard.txt` **not** edited) |
| `docs/inbox/mep-taxonomy.md` | this record |
| `plugin/lib/src/rvt/famgen/taxonomy.py` | generated mirror, from `tools/sync_plugin.py` |

```
 docs/inbox/mep-taxonomy.md            |  236 ++++++
 plugin/lib/src/rvt/famgen/taxonomy.py | 1403 ++++++++++++++++++++++++++++++
 src/rvt/famgen/taxonomy.py            | 1403 ++++++++++++++++++++++++++++++
 tests/ci_shard.d/692-taxonomy.txt     |    4 +
 tests/test_famgen_taxonomy_692.py     |  514 ++++++++++
 5 files changed, 3560 insertions(+)          # all additions; 0 facts records
```

**Not touched:** `src/rvt/famgen/facts/**` (no record added, changed or removed),
`catalog.py`, `standards.py`, `skeleton.py`, `factory.py`, any writer path, any hot file,
`tests/ci_shard.txt`, `tekton-plugin.zip` (git-ignored build artifact, regenerated not
committed).

**Shipped vs staged:** the tables and the gate are shipped on this branch. Nothing is
staged for a viewer round — this stream produces no `.rvt`/`.rfa` and touches no geometry,
so no batch was reserved and none is needed.

**Regime #302:** this is an engineer session. It does **not** merge. The PR is pushed for a
tech-lead session to run sandboxed CI + an independent review on the exact head and merge.
Findings come back to this same branch.

**Blocked, and reported rather than worked around:** this session has **no GitHub API
access** — `api.github.com` returns *"GitHub access is not enabled for this session. An org
admin must connect the Claude GitHub App for this organization."*, and no GitHub MCP
`issue_write` / `add_issue_comment` tool is present on this surface. So the claim
(self-assign + 🔒 comment) and the PR could not be made from here, and issues #692 / #685
could not be read — the work was built from the dispatching session's brief. `git` over
HTTPS is unaffected; the branch is pushed. Per hard rule 8 the denial is surfaced verbatim,
not routed around.
