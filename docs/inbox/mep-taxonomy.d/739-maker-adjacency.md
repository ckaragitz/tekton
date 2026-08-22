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
   (`Eaton only:` yes, `Eaton only for panels` names a clause) after it. A bare `X equipment` /
   `X gear` mid-sentence is no cue (`existing Siemens equipment`); it names the whole job when the
   equipment word closes the phrase (`Eaton equipment: …`, `…, Eaton gear.`) or is led by a job verb
   (`using Eaton equipment`) — see round 5 below (wording corrected under #742).
3. **Soft whole-job cue**: `manufacturer|mfr|mfg|brand|vendor|oem [:|is|of choice] X`, `make: X`,
   `use|using|specify|standardize on|basis of design X` **when X closes the phrase** (`use Eaton.`,
   `use Eaton for …`, `use Eaton gear` — `use Eaton breakers` names a part), or a **leading** `X:`
   (not after `for|at|in|per …`: `electrical room for Eaton: …`, `Per Eaton: …` name a client / source). Inside a clause that
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
   that maker makes the kind) is now a property of the mention, classified once in the shared
   scanner (`taxonomy.Mention.weak`, set in `_match_at`: one token, in the ambiguous list, read only
   because Capitalised, not an acronym, not hyphenated): `Square D` / `Square-D` and `GE` / `EST`
   are real names / acronyms — `a GE 75 kVA transformer` is declared (ABB) and said exactly like
   `a Trane panel`, `all gear by GE` / `manufacturer: GE` take the cue; an acronym with neither
   noun nor cue (`designed by GE Consulting`, `delivery EST 6 weeks`) is an ignored word (see
   round 2 below). `squared` stays in `vendors.AMBIGUOUS_ALONE`; the IFC-cell reader
   (`vendors._declared`) ignores the grading — a Manufacturer cell is an explicit claim.
7. **Adjacency is measured with the clause's own extractors** (`_RE_AMP`, `_RE_KVA`, `_RE_KA`,
   `_RE_VOLT_*`, `_RE_SPACES`, `_RE_SECTIONS`, `_RE_MCB`, `_RE_MLO`, `_RE_FLUSH`, `_RE_SURFACE`):
   what stands between a maker and its noun (or inside the parenthetical it fills) must be nothing
   but what the equipment clause reads as ratings — one vocabulary, so `two Kohler main circuit
   breaker 225 amperes 480Y/277 V 42-circuit panels` is adjacent exactly when the clause can read
   it. `vendors.makes(vendor, kind)` is the one "does the directory list this maker for the kind"
   predicate (`_declared`, the attachment loop and the soft-cue application all call it).

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
`tests/test_maker_adjacency_739.py` 215 passed; `tests/test_taxonomy_wiring_692.py` +
`tests/test_prompt_intent.py` 111 passed; `tests/test_frontdoor.py tests/test_plugin_sync.py
tests/test_ifc_intent.py tests/test_taxonomy_692.py` 167 passed / 5 skipped;
`tools/sync_plugin.py` clean (validation passed, zip rebuilt).

### Independent review, round 1 (head `feea259`, verdict 🛑 — quoted verbatim on PR #741)

Six findings, all reproduced and fixed on the branch:

| prompt | `main` | `feea259` | fixed head |
|---|---|---|---|
| `an Eaton house panel and six tenant panels` / `two Eaton site lighting panels 100 A` / `two Eaton lab panels …` / `six Eaton suite panels 100 A MLO` | Eaton on the noun | all `None` (a place word *qualifying* the noun was read as a place) | Eaton on the noun again — a place noun followed straight by an equipment noun is a qualifier, and the noun list ends in `(?![\w-])` |
| `use Eaton site-wide: …` / `standardize on Eaton plant-wide: …` | one clause | all `None` (`site-`) | whole job (`X-wide` is a hard quantifier) |
| `a 2000 A Eaton factory-assembled switchboard`, `Eaton base bid: 4 panels` | Eaton | `None` | Eaton (`factory-` no place; `base` off the place list) |
| `two panels, both by Eaton, and a 45 kVA transformer` / `panels LP-1 thru LP-4, all by Eaton, plus a 45 kVA transformer` | nothing + warning | T1 Eaton too (job-wide) | the list before it only (PP / LP), T1 `None`, no warning; leading or trailing `all by X` stays the whole job |
| `Eaton or Siemens: 4 panels …` / `Eaton / Siemens: …` / `4 panels; manufacturer: Eaton, Siemens` | applied neither + warning | PP Eaton (a guess) | names joined by `or` `/` `&` `,` are ONE cued set → "makers Eaton, Siemens are all named for the whole job -- applied to nothing" |
| `six Eaton panels; manufacturer: Siemens` | — | "lists none of its equipment () by it" | "every item already names its own maker -- applied to nothing" |
| `two panels next to an Eaton 75 kVA transformer` / `4 panels near the Eaton switchboard` | T1 / MSB Eaton | `None`, silently | T1 / MSB Eaton (context names the maker of the noun it qualifies); `two panels; existing Siemens gear to remain` → warning "names existing or neighbouring equipment, not the new work -- applied to nothing"; `4 new panels to match the existing Eaton gear` → PP Eaton (`to match the existing X` is a soft whole-job cue) |
| `ROOM 20 FT SQUARED WITH 4 PANELS` / `PROVIDE 4 PANELS. PRICE SEPARATELY.` / `… YORK TO REVIEW.` | ignored word | spurious "outside any clause" maker warning | ignored word again (in an all-caps text capitals say nothing: `Mention.weak` stays true); `6 square-d receptacles` reads Square D like `square d` |
| `a GE 480-208Y/120V 75 kVA transformer`, `a GE step-down …`, `a Trane type NQ 225 A panel`, `two Kohler NEMA 3R panels`, `two Kohler 400A 65kAIC MLO 480/277V panels` | (GE ignored) / Trane said | maker → ignored word | declared and said (primary-secondary voltage, `step-down`, `type|model <token>`, `NEMA <x>` count as ratings between maker and noun) |

`tests/test_maker_adjacency_739.py` grew to 114 cases (every prompt above, both orders where order
matters, plus a linear-time guard on hostile gaps).

### Independent review, round 2 (head `6e99d84`, verdict 🛑 — quoted verbatim on PR #741)

Three blocking findings and four nits, all reproduced and fixed:

| prompt | `main` | `6e99d84` | fixed head |
|---|---|---|---|
| `6 Hubbell hospital grade receptacles …`, `4 Eaton hospital grade panels`, `two Eaton lab area panels`, `an Eaton garage sub panel`, `two Eaton mall tenant panels`, `four Eaton dorm floor panels`, `two Siemens data center row panels`, `an Eaton campus loop switchboard 2000 A` | maker on the noun | `None`, silently (a place word among the noun's qualifiers) | maker on the noun: when an equipment noun follows in the clause, the place reading needs the place SAID as one — a locative word before the name (`for the Edwards building: …`, `the Kohler campus needs …`, `in the Sloan wing, …`) or a proper place name after it (`Cooper Hall`, `Hammond Street vault`); otherwise the maker rules decide (`Sloan wing: 4 panels` → an ignored word, Sloan makes no panelboard) |
| `two panels (Eaton only) and a 45 kVA transformer`, `4 panels (Eaton only) and a 45 kVA transformer (any make)`, `two panels - Eaton for all - and …`, `two panels, Eaton only, and …` | T1 `None` | T1 Eaton (job-wide) | the noun(s) before the aside: `X only` / `both by X` the noun, `X for all` / `all by X` the list; leading or trailing still the whole job |
| `two panels by Eaton, Hammond 75 kVA transformer`, `a 75 kVA transformer by Hammond, Eaton panels LP-1 and LP-2`, `panels LP-1 and LP-2 from Eaton, Siemens 2000 A switchboard`, `…, Cummins genset` | each noun its maker | one merged "Eaton, Hammond" mention → nothing + a false "both named" warning | each noun its maker: a bare comma joins two names only inside an `or` / `/` / `&` list or next to a cue (`manufacturer: Eaton, Siemens`, `Eaton, Siemens: …`) |
| `… the carrier's demarc`, `york's team to review` | ignored word | "maker Carrier (written carrier's) … outside any clause" | ignored word (a possessive is judged as the word before `'s`; the capital gate holds for every one-word plain-English name) |
| `4 panels …. NOTE: PRICE ALTERNATES SEPARATELY.`, `4 panels, delivery EST 6 weeks`, `designed by GE Consulting …` | ignored word | maker warning | ignored word: shouting is judged per sentence, and an ACRONYM (`Mention.acronym`: `GE`, `EST`) counts where it is adjacent (`a GE transformer`, `an EST panel`) or cued (`all gear by GE`, `manufacturer: GE`), nowhere else |
| `4 panels beside the York units …` | `York` an ignored word | `York` consumed, nothing said | `York` an ignored word again (the context branch marks only what it attaches or warns about) |
| `a 2000 A switchboard feeding two panels, both by Eaton, and a 45 kVA transformer` | — | MSB Eaton too | the panels only (`both` = the group before it) |
| a Manufacturer cell `Cooper Lighting Solutions by Eaton` / `Cooper Lighting (Eaton)` / `Halo, an Eaton brand` | Cooper Lighting | "names 2 makers" | Cooper Lighting (`X by Y`, `X (Y)`, `X, an Y brand`, `X - Y` name the brand, then its parent) |
| 200-clause prompt | 161 ms | 493 ms | 51 ms (cues are searched in a 72-character reach before/after the name, not the whole prefix) |

`tests/test_maker_adjacency_739.py`: 144 cases.

### Independent review, round 3 (head `4359aaa`, verdict 🛑 — quoted verbatim on PR #741)

One blocking finding, three nits, fixed:

| prompt | `main` | `4359aaa` | fixed head |
|---|---|---|---|
| `the Eaton house panel …`, `our Eaton house panel …`, `for two Eaton house panels …`, `feed the Eaton house panel …`, `replace one of the Eaton lab panels …`, `the Eaton branch panels …`, `6 Leviton Hospital Grade receptacles …`, `6 Hubbell Hospital Grade duplex receptacles …`, Title Case `Two Eaton Lab Panels`, `4 Eaton Hospital Grade Panels`, `An Eaton Campus Loop Switchboard` | maker on the noun | `None`, silently (an article before the name, or a Capitalised qualifier, satisfied "said as a place") | maker on the noun: qualifier-vs-place is now decided by what stands BETWEEN the place word and the equipment noun — nothing or up to three plain words (`grade`, `loop`, `tenant`) and it qualifies the noun (the maker rules decide; `Cooper Hall panels`, `the Kohler campus panels`, `the Sloan house panel` still end as ignored words because those makers make no panelboard); a count, digit, article, verb or punctuation (`the Kohler campus needs 4 panels`, `Sloan wing: 4 panels`, `in Cooper Hall, two panels`) and it is a place. `two panels next to the existing Siemens site lighting panel` → the lighting panel Siemens (context reaches the noun it qualifies across qualifier words) |
| `electrical room for Eaton: 4 panels and a 75 kVA transformer` | PP only | whole job (T1 too) | PP only (a client preposition before a leading `X:` is no cue) |
| cells `Eaton - Siemens`, `Eaton by Siemens`, `Eaton (Siemens)` | (one picked) | collapsed to Eaton | two makers, neither (`X by Y` collapses to X only when Y lists nothing for the kind — a parent, `Cooper Lighting by Eaton`) |
| `two Eaton or Siemens or ABB panels` | — | "are both named" | "makers ABB, Eaton, Siemens are all named for it -- applied none" |

`tests/test_maker_adjacency_739.py`: 164 cases.

### Independent review, round 4 (head `7b09fde`, verdict 🛑 — quoted verbatim on PR #741)

Three findings and nits, fixed:

| prompt | `main` | `7b09fde` | fixed head |
|---|---|---|---|
| `Provide 4 panels and a 75 kVA transformer. Panelboards shall be by Eaton only.` / `…; panels Eaton only` / `… Transformers: Hammond only.` / `…; receptacles Hubbell only` | the trailing noun's items | every item (a trailing `X only` became the whole job) | the noun(s) before the cue **in its own clause**; whole job only when the cue OPENS its clause (`…, Eaton only` / `Eaton only: …`); `…; breakers Eaton only`, `use Eaton breakers`, `using Eaton lugs`, `specify Siemens breakers` (a part, no equipment noun) → nothing + "named outside any equipment clause" as on `main` (a verb cue names the job only when the name closes the phrase) |
| `6 Hubbell hospital grade 20 A duplex receptacles`, `… 5-20R receptacles`, `two Siemens data center 400 A panels`, `four Eaton branch circuit 42-circuit panels`, `two Eaton lab 225 A panels`, `an Eaton station service 45 kVA transformer`, `an Eaton house 100 A panel`, `… hospital grade (green dot) receptacles` | maker on the noun | `None`, silently (a rating in the qualifier gap made a "place") | maker on the noun: ratings, NEMA configuration tokens and joiners (`,` `and` `/` `(…)`) are stripped/allowed in the qualifier gap; `two Eaton house and tenant panels 100 A` / `6 Hubbell hospital grade, tamper resistant receptacles` (the boundary hides the noun and a count leads) → nothing + the "outside any clause" warning as on `main`, while `For the Kohler campus, provide 4 panels` / `Kohler headquarters; 4 panels` stay places |
| `Eaton for everything except the transformer: …` | — | whole job, silently | whole job + warning "named 'for everything except ...' -- the exception is not modelled …" |
| `Per Eaton: 4 panels and a transformer` | PP only | whole job | PP only (`per` / `via` name a source, like `for`) |
| cells `Eaton (Siemens)` / `Eaton - Siemens` on a transformer | one picked | collapsed to Eaton | two makers, neither: only worded parents collapse (`X by Y`, `X, an Y brand`, `X, a division of Y`, Y listing nothing for the kind); `Cooper Lighting (Eaton)` therefore also names two makers now (said, never picked) |
| 200 × `…, Eaton only, …` prompt | 17 ms | 34 ms | 57 ms with everything above (anchor lookups and sentence stops are bisected once per prompt; 200 plain clauses 59 ms vs `main` 49 ms) |

`tests/test_maker_adjacency_739.py`: 192 cases.

### Independent review, round 5 (head `9fadac6`, verdict 🛑 — quoted verbatim on PR #741)

Two findings and nits, fixed:

| prompt | `main` | `9fadac6` | fixed head |
|---|---|---|---|
| `Eaton equipment: 4 panels, a 75 kVA transformer and 6 receptacles`, `All Eaton equipment: …`, `… using Eaton equipment`, `provide … using Eaton gear`, `furnish Eaton equipment: …`, `Eaton equipment - …`, `use Eaton equipment for …`, `…, Eaton equipment`, `… with Eaton equipment`, `Eaton gear. …` | whole job | one clause, or nothing + warning | whole job again: `X gear|equipment|products|hardware` is a whole-job cue when the equipment word CLOSES the phrase or is led by `all|use|using|provide|furnish|supply|install|with`; `beside the existing Siemens equipment` is intercepted first as context, so #739's motivating prompt stays fixed; a leading `Eaton equipment:` also counts as the leading-colon cue |
| `two Eaton lab 3-phase panels`, `an Eaton house 1ph panel`, `two Eaton site 3ph 480V lighting panels`, `an Eaton house 120/240V 1-phase 100 A panel`, `two Eaton lab 208Y/120V 3-phase 4-wire 225 A panels`, `an Eaton house 100A 3P panel`, `two Eaton lab 3PH 4W 225A panels`, `an Eaton house type PRL1a panel`, `an Eaton campus 15 kV switchgear lineup` | Eaton on the noun | `None`, silently | Eaton on the noun: ONE stripping vocabulary (`_strip_ratings`: the extractors + phase/pole/wire, `type|model <token>`, NEMA, `kV`, `step-down`, `series`) serves both the adjacency test and the qualifier gap, so the two can no longer disagree |
| `Eaton only, except the transformer by Hammond: …` | — | silent | the `except …` disclosure now follows every whole-job after-cue, not only `for everything` |

Pre-existing and left as is (documented, = `main`): a trailing listable cue with no punctuation before it
(`… transformer all by Eaton`) binds to the last noun only; leading or trailing `all by X` names the
whole job once it is set off by `,` `;` `.` `:` `-` or opens the prompt.

`tests/test_maker_adjacency_739.py`: 215 cases.

## Findings

- `/simplify` (four independent angles) on the first cut found one real hazard: the hand-written
  rating-filler regexes (`(?:\s+|…|\d[\d.,/y]*|…)*$`) backtracked catastrophically on a failed
  match — `two Trane 111111111111111111111111 custom panels` took 6.9 s in `parse_prompt`, a
  24-digit token on the product path. Replaced by the extractor-based `_only_ratings()` with a
  single-character residue pattern: the same prompt parses in 2 ms. Also from those reviews: the
  weak-name classification moved into the scanner, `vendors.makes()`, the substitution tail shared
  with `NOT_THAT_MAKER` (the two-maker sentence now carries the marker surfaces filter on), the
  room nouns shared between `_RE_ROOM` and the locative list, a dead branch and duplicated
  comprehensions removed. Skipped on purpose: lazy compilation of the maker regexes (+3 ms import,
  0.1 % of a job — not worth the indirection) and treating `existing <noun>` as a shielding pass
  over equipment clauses (changes what gets *built*: #740 / #737 territory, noted there).
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
  `src/rvt/famgen/vendors.py`, `src/rvt/famgen/taxonomy.py` (`Mention.weak`),
  `tests/test_maker_adjacency_739.py` (new),
  `tests/ci_shard.d/739-maker-adjacency.txt` (new), `tests/test_taxonomy_wiring_692.py` (2 assertions,
  see Findings), this fragment + one index line in `docs/inbox/mep-taxonomy.md`, regenerated plugin
  mirrors (`plugin/lib/src/rvt/frontdoor/prompt_intent.py`, `plugin/lib/src/rvt/famgen/vendors.py`,
  `plugin/lib/src/rvt/famgen/taxonomy.py`).
- gates above green locally; `/verify` ran (front door, two prompts); nothing staged for the viewer
  (no writer change); shipped = nothing until the PR merges through the session-hosted pipeline.
