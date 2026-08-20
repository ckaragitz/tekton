# 692-wiring — slice 2: the tables are what the prompt grammar and the plan resolver read

Issue #692 (P0, child of #685), DONE 3 (relay) + DONE 5, plus review nits 1–3 carried from #735.
Branch `cam/692-taxonomy-wiring`. Slice 1 (`692-tables.md`) built the two tables and their gates;
this slice makes them *load-bearing*: nothing in the prompt route keeps a product list of its own.

## What was built

**A phrase scanner over both tables** (`taxonomy.scan`, `vendors.scan`, one shared `_scan`):
whole words, plural/space/hyphen/case tolerant (`cable trays`, `down lights`, `J-boxes`, `VAVs`),
longest phrase first, non-overlapping, left to right. Words that are a kind as a whole *answer*
but plain English inside a sentence (`box`, `switch`, `drive`, `meter`, `panel`, `outlet`, `duct`,
`pipe`, …; `taxonomy.AMBIGUOUS_ALONE`) are skipped when they stand alone and read as always
inside a longer name (`pull box`, `transfer switch`, `meter socket`); a maker's name that is also
a common word (`Carrier`, `Watts`, `York`, `Price`; `vendors.AMBIGUOUS_ALONE`) counts alone only
when Capitalised as written, and the `generic` pseudo-vendor is never a maker a prompt can name.
`resolve()` gained the same plural tolerance. Both word sets are gated (`--check` fails if a word
is not a name the table carries).

**Generic words** (`Kind.refine`): `light fixtures` names a category, not a type. The new
`luminaire` row refines to the nine lighting rows and is never "buildable": `builder_available`
says *"a generic word — name the type: Recessed LED troffer, Recessed LED downlight (buildable
here); High-bay luminaire, … (known, not buildable here yet)"* — computed from those rows, so it
is also the interview's first question for that word (#684) with no interview code. `check_row`
rejects a refine row that declares mechanisms, refines to an unknown/generic kind, or crosses
category; a pending row may not refine.

**`Kind.intent`** (row-side): the intent schema's equipment kinds (`rvt.ifc.intent`
`Equipment.kind`, shared by the IFC and prompt routes) each row stands for — `panelboard` carries
the four panel flavours, `receptacle` and `receptacle_20a` both ride `receptacle_device` (first
row wins for `for_intent_kind`), `luminaire` is the IFC route's `light_fixture`, and the
`switchgear` row now says in data what the grammar always did: a switchgear lineup is carried as
the `switchboard` kind and built as the same house lineup model (`via=[house switchboard]`, note:
no draw-out / metal-clad construction modelled). The prompt grammar *derives* `_SCENE_KIND` from
it (no literal says "switchgear → switchboard"), the plan resolver reads the directory through
`for_intent_kind(eq.kind)`, and `check()` gates every named intent kind against the schema's own
vocabulary (`GENERATED_KINDS ∪ KIND_BY_CLASS`).

**The prompt grammar reads the taxonomy** (`prompt_intent.parse_prompt`): `_UNBUILT_PATTERNS`
(a hand list of nine regexes) is gone. Every kind the scanner finds that the room build does not
model is (a) *shielded* from the clause grammar before it runs — `a fire alarm control panel` /
`a lighting relay panel` were read as panelboards by their last word and **built as PP-1**; they
are now recorded, not built — and (b) recorded `not_built` with the table's line: label, Revit
category, lane, category-id status, whether a family is buildable here, and what this route does
with it (`_kind_record`). A modelled kind in words the clauses do not parse (`a load center`)
says which clause builds it. `switchgear` stays the service board (the switchboard clause reads
it). Two architectural context words (`door`, `housekeeping pad`) remain a two-entry list — they
are not equipment, so not rows. When nothing is buildable the `PromptError` carries each
recognised kind's line, so `route run --prompt "create a VAV box family" --output rfa` answers
*"VAV terminal unit: Mechanical Equipment; NOT buildable here -- … no lane builds it yet: no
catalog record is held and no archetype generates it"* instead of "nothing to author" (DONE 3,
with no router change — #674 rewrites that route function and must not conflict).

**Makers are read, carried and judged — never substituted silently** (steer #685):
- grammar: a maker named inside an equipment clause rides that item (`six Eaton panels`, `two
  Square D lighting panels`); one maker named outside every clause (`all gear by Eaton`) rides
  every item that named none; two such makers ride nothing and a warning says so. The name goes
  into the tagging contract as `Pset_ManufacturerTypeInformation.Manufacturer` — exactly the cell
  the IFC route reads — so both routes meet in one place:
- `rvt.ifc.intent.declared_maker(con, eq.kind)` → `vendors.declared(text, kind)`: the maker's own
  **held** record for that kind (`vendors.record_for`) replaces the plan's default record
  (`Square D` panelboards → `square-d/nq-nf-iline-panelboards`, `Hammond` transformers →
  `hps/sentinel-g-transformers`; before this slice every panelboard/transformer plan said
  `vendor="eaton"` whatever the input declared). The default itself now lives in ONE place —
  `vendors.default_record(kind)`, the directory's first held record — instead of literals in the
  resolver, and placeholder cells (`unspecified`, `by others`, …; `vendors.UNNAMED_MAKERS`) declare
  nothing on either route. A maker known by name only (`Siemens`), not a maker of that kind
  (`Trane` panels), or unknown, keeps the default record and the plan carries the directory's one
  sentence (ending *"never presented as that maker's product"*) as a **`FamilyPlan.degradations`**
  entry — a new structured field, emitted by `as_json` / `summarize`, listed by
  `manifest.plan_note_degradations` among the build's top-level degradations (identical sentences
  share one line) and rendered per plan as **said**; no phrase-grepping. If the maker's record
  **refuses** the member (HPS holds no 45 kVA unit; NF has no sizing table at 480Y/277)
  `_fall_back` rebuilds from the default record, keeps the refusal verbatim, and says so the same
  way. When the maker's own record *is* read the sentence is a plain note. The prompt coverage
  carries the same sentence as a warning plus an `understood: manufacturer` entry per (maker,
  kind) with the record it selected; `vendors.declared` is memoised (one record parse per (maker,
  kind), not per item — review measurement: 26–40 % of parse time on maker-heavy prompts).

**Nits from #735**: (1) `vendors.describe(vendor, kind=)` and `make_family.py vendors --kind K`
count the tier on the *member* the kind selects (`variant box-4in-square: sourced facts: 4
fact-tier fields` vs `variant duplex-receptacle-5-15R: … NO fact-tier field`); (2) a record that
fails to load is a finding (`… does not load (CatalogError: …)`) in `taxonomy --check`,
`describe()` and `builder_available()`, never a traceback; (3) a `house:` mechanism must be a
*callable in an `rvt.` module* (`house:json:dumps` and a non-callable attribute now fail), a
pending label may be neither a category the resolver carries nor one of `INTENDED_LABEL`'s
values, and `_record_problems` also requires the member's variant to exist and the record's OST
label to agree with the row. Nit 4 waits for #698 as agreed.

**Review passes before the PR left draft**: `/simplify` (four angles) folded in — bookkeeping in
`parse_prompt` collapsed (one maker field on `PromptItem`, mentions marked once, `_SCENE_KIND`
derived), `declared()` reduced to `describe()`'s line + one substitution tail, `member_model()`
made public and key-tolerant, the scanner's inner search extracted (`_match_at`), the not-built
records sorted once by offset; the altitude review moved intent kinds row-side, the default
record into the directory, and the substitution sentence into a structured plan field (above),
and added the refine-completeness gate (a non-generic row of a category that has a generic row
must appear in a `refine` list); the reuse review made ONE record/row gate
(`vendors.record_row_problems`, called by both `--check`s, now also carrying the member-variant
check), moved every spliced error through `rvt._clause` (`cause_clause` / `clip`), put the
recognised kind FIRST in the `PromptError` so the manifest's 160-character status cut keeps it,
made the directory's default record an explicit `default=True` per line (exactly one per kind
with records, cross-checked against the factory constructors' own signature defaults in
`taxonomy --check`), and dropped two tests that only repeated slice 1. Left as a follow-up, filed as **#737**: unbuilt kinds are *shielded spans*,
not clauses, so a rating/tag written next to one (`a 400 A automatic transfer switch beside two
panels`) can still bleed into the neighbouring clause exactly as before this slice — parsing them
as full `PromptItem(buildable=False)` clauses is the deeper fix and what O12 needs.

## Evidence

- Gates: `make_family.py taxonomy --check` → `83 kinds, 0 problems` (13 `#516` conflict rows
  warned, unchanged); `vendors --check` → `50 vendors, 118 lines, 7 with a catalog record, 0
  problems`; `standards --check` unchanged.
- Tests: new `tests/test_taxonomy_wiring_692.py` — 54 tests, 0.3 s (scanner, generic rows,
  nits, `declared` / `default_record` / placeholders, intent-kind + refine gates, grammar
  shield/records/error relay, maker attach/global/ambiguous, plan resolver
  held/refused-fallback/named-only with structured degradations, `declared_maker` never raises,
  `route()` relay);
  drop-in `tests/ci_shard.d/692-taxonomy-wiring.txt`. Two existing assertions that pinned the
  generic word `luminaire` for `LED troffers` now expect the taxonomy's `troffer`
  (`tests/test_prompt_intent.py`, `tests/test_frontdoor.py`). Stream-local: `test_taxonomy_692`,
  `test_prompt_intent`, `test_frontdoor`, `test_ifc_intent`, `test_intent_*`, `test_router`,
  `test_frontdoor_manifest_pin` green (counts in the PR).
- `/verify` (front door, this sandbox): `frontdoor.py author --prompt "an electrical room with 3
  Siemens panels, two Square D lighting panels 225 A 42 spaces 208Y/120 V, a Hammond 75 kVA
  transformer, a fire alarm control panel, twelve LED troffers and 6 Leviton receptacles"` →
  READY/PROOF-ONLY as before; `prompt_room.rvt` validates `VALID (no errors)`; families
  `lp1_square_d_nq_225a_42sp_208y_120.rfa` (family-mode `VALID`, provenance ok) and
  `t1_…hps…` built from the declared makers' records for the first time; PP-1..3 (Siemens) and
  R-1..6 (Leviton) built from the default records with the sentence in `build.degradations`;
  `fire alarm control panel` recorded under Fire Alarm Devices instead of becoming a panelboard.
  Validator green is a fact about the files, not a Revit verdict (rule 4).

## Findings

- The Square D record resolves fewer members than Eaton's (NQ at 208Y/120 with the sizing rows it
  holds; NF at 480Y/277 has no circuits→height table): a declared Square D 480Y/277 panel falls
  back to PRL2X *and says so*. That is the catalog's depth showing through honestly, not a bug;
  #688 (spec sheets) is how it deepens.
- The room grammar's default service is 480Y/277, so `two Square D lighting panels` with no
  voltage stated fall back too; stating `208Y/120 V` in the clause selects NQ.

## Open questions / follow-ups

- #737 — unbuilt kinds parsed as full clauses (their own count / rating / tags / maker) instead
  of shielded spans; also what O12's `prompt → rfa` parse needs.
- The router could echo `not_built` kinds and maker sentences as `res.caveats` on the prompt
  routes; left out here because #674 rewrites `_r_prompt_to_rfa` — a three-line follow-up once
  #674 lands. Today they ride in the manifest (degradations, coverage) and, when nothing is
  buildable, in the status line.
- #684 (interview): `Kind.refine`, `vendors.lines_for_kind()` and `INTENT_KINDS` are the data it
  asks from; no interview code exists yet.
- Nit 4 (category evidence from #698's `category_facts`) when #698 merges.

## BRANCH STATE

- Files: `src/rvt/famgen/taxonomy.py`, `src/rvt/famgen/vendors.py`,
  `src/rvt/frontdoor/prompt_intent.py`, `src/rvt/ifc/intent.py`, `src/rvt/frontdoor/manifest.py`,
  `tools/make_family.py`, `tests/test_taxonomy_wiring_692.py` (new),
  `tests/ci_shard.d/692-taxonomy-wiring.txt` (new), `tests/test_prompt_intent.py`,
  `tests/test_frontdoor.py` (one assertion each), this fragment + the index line; plugin mirrors
  regenerated by `tools/sync_plugin.py` (`--check` clean).
- Gates: listed above; sandboxed CI + independent review recorded on the PR.
- Nothing staged for the viewer; no ledger change; no donor bytes (tables are words).
