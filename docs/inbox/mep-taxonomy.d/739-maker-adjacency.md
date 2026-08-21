# #739 — maker adjacency, locatives and whole-job cues (follow-up of #736 / #692 slice 2)

Stream: MEP taxonomy + vendor directory (`docs/inbox/mep-taxonomy.md` is the index). Issue #739,
filed from the third independent review of PR #736 (verdict 🟡). Refs #692, #685.

## What was built

`src/rvt/frontdoor/prompt_intent.py::_attach_makers` (and its cue / adjacency regexes) now reads a
maker mention in a room prompt in this order:

1. **A place, a client, existing gear → no maker.** A directory name followed — directly, or across
   a Capitalised proper-noun phrase of up to two more words — by a place noun (`building, plant,
   office, campus, hall, wing, residence, school, street, vault, …`) with no equipment noun in
   between is a *locative*: `4 panels for the Edwards building`, `two panels in Cooper Hall`,
   `Sloan wing: 4 panels`, `the Kohler campus needs 4 panels`, `4 panels for Armstrong High
   School`, `… for the Schneider residence`, `a 75 kVA transformer for the Hammond plant / in the
   Hammond Street vault`. So is gear the new work merely sits beside (`beside the existing Siemens
   equipment`, `next to the Eaton gear`). The word goes to `ignored_words`; nothing is declared, no
   warning. `six Eaton panels in building B`, `an Eaton transformer in vault 2`, `a transformer by
   Hammond for the plant` still declare their maker (the equipment noun sits in between / the place
   phrase does not follow the name).
2. **Hard whole-job cue** (literal, every item that names no maker of its own): `all|both [the]
   gear|equipment|products|hardware [by|from|is|:] X`, `all|both|everything [else] by|from X`,
   `everything: X` before the name; `X [gear|equipment] throughout|everywhere|exclusively|across the
   board|for everything|for the whole job`, and `X only` / `X for all` **when they close the phrase**
   (`Eaton only:` yes, `Eaton only for panels` names a clause) after it. The bare `X equipment` /
   `X gear` after-cue is gone: it needs its quantifier (`existing Siemens equipment` is no cue).
3. **Soft whole-job cue**: `manufacturer|mfr|mfg|brand|vendor|oem [:|is|of choice] X`, `make: X`,
   `use|using|specify|standardize on|basis of design X`, or a **leading** `X:`. Inside a clause that
   names equipment it ties X to that noun; set off mid-list (`two panels, manufacturer Eaton, and a
   transformer, manufacturer Hammond`) it binds to the noun before it in the same sentence (an
   abbreviation's period — `mfr.` — and a decimal point are not sentence stops); leading or trailing
   the job it names the whole job — but only for the job's equipment **the directory says X makes**
   (`two panels and a 30 kVA transformer, manufacturer Hammond` → T1 Hammond, the panels none, and
   one warning says what was skipped and how to force it); a soft cue by a maker of none of the
   job's kinds (`Kohler: 4 panels`) applies to nothing and says so.
4. **Nearest noun in the clause** for a maker that makes the noun's kind (unchanged from #736).
5. **Adjacency for a maker that does not make it**: `<Maker> [ratings] <noun>` (`a Trane panel`,
   `two new Kohler 225 A panels`, `six Square D receptacles`) or `<noun> [tags] [family] by|from|
   (…)|manufacturer: <Maker>` (`panels LP-1 and LP-2 by Kohler`, `two panels (Kohler)`, `a cable
   tray family by Eaton`) — declared **and said** (the directory's sentence ending "never presented
   as that maker's product"); a parenthetical counts only when the maker *is* the parenthetical
   (`(Generac backup)` is not). Not adjacent and not a maker of the kind → an ignored word (`Kohler
   wants 4 panels`, `4 panels for Edwards`).
6. **Plain-English names**: the one-word rule (`York`, `Price`, `Watts`, `Simplex` count only where
   that maker makes the kind) now applies to one-token mentions that are not written as an acronym:
   `Square D` (two tokens) and `GE` / `EST` (acronyms) are real names everywhere — `a GE 75 kVA
   transformer` is declared (ABB) and said exactly like `a Trane panel`; `designed by GE Consulting`
   warns "maker ABB (written GE) is named outside any equipment clause". `squared` stays in
   `vendors.AMBIGUOUS_ALONE` for the scanner.

`src/rvt/famgen/vendors.py`: Price Industries and Titus each get a named-only `grds` line
(`air_terminal`, a pending row → "known by name only … not buildable here yet"), so `Price grilles`
/ `Titus diffusers` put the maker on the not-built record instead of dropping the word; `_declared`
on a cell that names two makers (`Eaton or Siemens`, `Eaton / Siemens`) returns `known=False`,
`record=None` and the sentence "'…' names 2 makers (Eaton, Siemens) -- no single maker is read from
it; built here from what tekton holds for the kind instead …" instead of picking the longest
mention (`Square D by Schneider Electric`, `Eaton Corporation` still resolve to their one maker).

## Evidence (numbers, not adjectives)

Parsed prompts, `main` @ 5da6836 → this branch (items' makers · warnings · ignored words):

| prompt | before | after |
|---|---|---|
| `4 panels for the Edwards building` | PP-1..4 **Edwards** + "makes nothing…" warning | all `None`; ignored `Edwards`; no warning |
| `two panels in Cooper Hall` | PP-1..2 Cooper Lighting Solutions | `None`; ignored `Cooper, Hall` |
| `Sloan wing: 4 panels` / `the Kohler campus needs 4 panels` / `4 panels for Armstrong High School` | Sloan / Kohler / Armstrong Fluid Technology on every panel | `None`; the name is an ignored word |
| `two lighting panels … for the Schneider residence` | LP-1..2 Square D (NQ attempted) | `None`; ignored `Schneider` |
| `a 75 kVA transformer for the Hammond plant` / `… in the Hammond Street vault` | T1 built from `hps/sentinel-g-transformers` | T1 `None` (default record); ignored `Hammond` |
| `two panels beside existing Siemens equipment and a new transformer` | T1 + PP Siemens (the `X equipment` cue) | all `None`; ignored `Siemens` |
| `6 Square D receptacles at 18 in AFF and two panels` | R-1..6 `None`; ignored `Square, D` | R-1..6 **Square D** + one "makes nothing … never presented" warning; PP `None` |
| `a GE 75 kVA transformer` | T1 `None`; ignored `GE` | T1 **ABB** + the same sentence `a Trane panel` gets |
| `Eaton: two panels and a transformer` | PP Eaton, T1 `None` | all Eaton (whole job) |
| `use Eaton for everything: …` / `4 panels; manufacturer: Eaton` / `Manufacturer: Eaton. Two panels…` / `please use Eaton. …` / `basis of design Eaton, …` / `all the gear is Eaton: …` / `Eaton only: …` | one clause or nothing (+ "outside any clause" warning) | whole job, no warning, no ignored word |
| `two panels and a 30 kVA transformer, manufacturer Hammond` | nothing + warning | T1 Hammond; PP `None`; "applied to the Dry-type distribution transformer only (T1)" |
| `two panels, manufacturer Eaton, and a transformer, manufacturer Hammond` | — | PP Eaton, T1 Hammond, no warning |
| `Price grilles and two panels` | not-built `grilles` with no maker; ignored `Price` | not-built `grilles` carries Price Industries |
| `Kohler wants 4 panels` / `provide 4 panels (Generac backup) and a switchboard` | — / PP Generac | `None`; ignored `Kohler` / `Generac, backup` |
| unchanged: `six Eaton panels`, `two panels by Eaton and a 75 kVA Hammond transformer`, `a 500 kW Cummins generator and two panels`, `panels LP-1 and LP-2 by Eaton`, `a Trane panel`, `a GE panel`, `two panels by Square D and a 75 kVA transformer by Square D`, `all gear by Eaton: …`, `Eaton equipment throughout`, `4 Simplex receptacles`, `Supply 4 panels for our New York office`, `Price out 4 panels`, `a room twenty feet squared with two panels` | | |

`VD.declared("Eaton or Siemens", "panelboard")` → `known=False, vendor=None, record=None`,
line `'Eaton or Siemens' names 2 makers (Eaton, Siemens) -- no single maker is read from it; …`.

Front door (`/verify`): `tools/frontdoor.py author --prompt "an electrical room 20 ft by 15 ft
with 4 panels for the Edwards building"` → delivered `prompt_room.rvt` + 4 PRL2X panel families
(PROOF-ONLY stamped), `rvt_validate` **error 0** / warning 1 (the known DataStorage decoder gap);
`intent.json` carries **no** `Manufacturer` contract value or `Pset_ManufacturerTypeInformation`
(the only manufacturer-valued keys are the default record's own `facts.manufacturer = Eaton`);
`MANIFEST.md`: `ignored words: Edwards`. The `… 6 Square D receptacles … two panels, manufacturer
Hammond, and a 30 kVA transformer` job → delivered, error 0; contracts carry `Square D` on R-1..6
and `Hammond Power Solutions` on PP-1..2 (the mid-list aside follows the panels) with the "never
presented as that maker's product" lines in MANIFEST.

Gates: `make_family.py vendors --check` → 50 vendors, 120 lines, 7 with a catalog record, 0
problems; `taxonomy --check` → 83 kinds, 0 problems (13 #516 warnings unchanged);
`tests/test_maker_adjacency_739.py` 81 passed; `tests/test_taxonomy_wiring_692.py` +
`tests/test_prompt_intent.py` 111 passed; `tests/test_frontdoor.py tests/test_plugin_sync.py
tests/test_ifc_intent.py tests/test_taxonomy_692.py` 167 passed / 5 skipped;
`tools/sync_plugin.py` clean (validation passed, zip rebuilt).

## Findings

- `re.compile(r"^…").match(text, pos)` never matches for `pos > 0` — `^` means the start of the
  string, not `pos`; the parenthetical check used that form at first and silently never fired. The
  locative / parenthetical patterns are written without `^` and rely on `.match(text, pos)`.
- DONE 5 of #739 asked for `tests/test_taxonomy_wiring_692.py` to stay unchanged; DONE 1 and DONE 4
  each reverse one of its assertions (`for the Hammond plant` no longer warns — it is a locative;
  `a GE transformer` is now declared). The two edits are minimal: the "outside any clause" test uses
  `Hammond preferred; …` instead, and the GE parameter moved to the #739 module with its new
  expectation.
- Pre-existing, not from this change: `two panels fed from the switchboard` builds **two**
  switchboards (`MSB`, `MSB-2`) — the count word of the panel clause leaks into a later kind that
  shares the clause window. Filed as a follow-up task issue.

## Open questions

- A soft cue trailing the job (`…, manufacturer Hammond`) names the maker for the kinds it makes;
  a hard cue (`all gear by Hammond`) is literal. If the owner prefers the literal reading everywhere,
  it is one line (`hard or …` → `True`) — the disclosure sentences already exist for both.
- `an EST panel` declares Edwards on a panelboard (adjacent acronym); the phrase more likely means a
  fire-alarm panel — that is #737's territory (unbuilt kinds read as full clauses), not attachment.

## BRANCH STATE

- branch `cam/739-maker-adjacency` from `main` @ 5da6836; files: `src/rvt/frontdoor/prompt_intent.py`,
  `src/rvt/famgen/vendors.py`, `tests/test_maker_adjacency_739.py` (new),
  `tests/ci_shard.d/739-maker-adjacency.txt` (new), `tests/test_taxonomy_wiring_692.py` (2 assertions,
  see Findings), this fragment + one index line in `docs/inbox/mep-taxonomy.md`, regenerated plugin
  mirrors (`plugin/lib/src/rvt/frontdoor/prompt_intent.py`, `plugin/lib/src/rvt/famgen/vendors.py`).
- gates above green locally; `/verify` ran (front door, two prompts); nothing staged for the viewer
  (no writer change); shipped = nothing until the PR merges through the session-hosted pipeline.
