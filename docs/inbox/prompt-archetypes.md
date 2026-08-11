# prompt-archetypes — named products generated at standard nominal sizes

Stream record. Issue #591 (owner steer, verbatim):

> "but we have a python engine and reverse engineered the binary format you should be able
> to generate the rfa with a prompt if so make it so you can!"

clarified moments later, when the session started building only a dimension parser:

> "pause , for example if i say crate a cable tray family you should be able to create it
> in lod 400, you should be able to create anything"

Territory: `src/rvt/famgen/archetypes.py` (new), `src/rvt/famgen/factory.py`
(`make_archetype`, the `nominal` tier in `FactSheet.unverified`, `FamilyProduct.archetype`),
`src/rvt/frontdoor/famspec.py` (the `archetype` kind + one validator gap closed),
`spec/famspec.schema.json`, `src/rvt/frontdoor/router.py` (`_archetype_rfa`),
`src/rvt/frontdoor/matrix.py`, `tools/make_family.py`,
`plugin/skills/tekton-author/SKILL.md`, `tests/test_famgen_archetypes.py`.

---

## The state this started from

Verified on today's `main` (`3ec84d7`) **before** writing any code:

```
route run --prompt "create a cable tray family" --output rfa
→ FAILED (prompt->intent: PromptError: the prompt names neither buildable equipment
  ... Recognised-but-unbuilt kinds: cable_tray. Ignored words: family)
```

Three honest lanes existed and the request fell between all of them: the catalog holds no
cable tray, the `generic_model` lane needs the caller to supply geometry, and the IFC lane
needs an IFC. So the engine refused a thing it was perfectly capable of building.

## What the contract actually forbids

The rule is **never present an invented dimension as a manufacturer fact**. It has never
been *never generate geometry* — the session that first read it that way was wrong twice
over, and #591 records both errors. So this adds a fourth provenance tier beside the three
`factory.Fact` already had:

| provenance | where the number came from | example |
|---|---|---|
| `fact` | a published catalog record we hold | Eaton PRL2X, 20.00 in wide |
| `given` | the caller said so (prompt, IFC mesh, famspec) | "a 24 inch cable tray" |
| `assumed` | a catalog-flagged assumption / a rule off a fact | the PRL1X height row |
| **`nominal`** | **standard practice for the product class** | a 12 in ladder tray |

`nominal` joins `assumed` and `given` in `FactSheet.unverified()`, so every generated
dimension surfaces in every report exactly as an assumption does — it is never quietly
equal to a sourced fact.

**What a `nominal` is and is not.** It is standard industry practice for the product
class, and each parameter names the practice it follows in its `basis`. It is **not** read
from a standards document held in this repo, and the module says so in its own docstring
rather than implying a citation it cannot produce. No archetype family carries a
manufacturer, model or part number — pinned by
`test_no_archetype_family_claims_a_manufacturer` across every archetype. Ask for "an Eaton
B-Line 24 in tray, part number X" and the guard fires — **see round 2 below: as first
written this sentence claimed a refusal that was not implemented, and the fix is not a
refusal but a delivery that says plainly the named item is not what you got.**

## The registry (DONE 5: one entry + one function)

`ARCHETYPES` maps a product key to an `Archetype`: its category, the practice its nominals
follow, its `Param` list, the regexes that recognise it in a prompt, a builder, its LOD
note and — required — what it does **not** model.

| product | category | parts at its nominals | LOD 400 means |
|---|---|---|---|
| `cable_tray` (ladder) | Cable Tray Fittings | **16** | two side rails, each a channel with flanges turned inward, plus a rung at every standard spacing |
| `strut_channel` | Generic Models | 5 (solid back) / 65 (slotted at 2 in) | back, two webs, two inturned lips; with a slot spacing the back is the material **between** the slots |
| `wireway` (lay-in) | Electrical Equipment | 4 | bottom, two sides, removable cover — an open-ended trough |
| `junction_box` | Electrical Fixtures | 6 | back, four walls, screw cover |
| `conduit` | Conduit Fittings | 1 | one cylinder about the run axis |

Each declares its limits and the route prints them: the tray says it is a **loadable**
family in Cable Tray Fittings and that Revit's drawable Cable Trays element is a system
family which generates its own straight-run geometry (#608); the conduit says **the bore is
not modelled** — the writer has no void or boolean, so the run is a solid rod at the
outside diameter, not a tube. Stating that is the point; silence would read as complete.

`check_registry()` is the gate: every archetype must build from its own nominals, emit only
shapes the famspec accepts, have a primary parameter, use lower-case aliases, and be
recognised by its own title. 5 archetypes, 0 problems.

## Reading a prompt (DONE 3 and 4)

Parameters carry `aliases`, and the resolver builds its patterns from them — a new
parameter needs no regex. It reads `24 inch`, `1-5/8 in`, `3/4 in`, `600 mm`, `20 ft long`,
`6 in rung spacing`, `12x12`, and a bare measurement in front of the product noun ("a 24
inch cable tray" → the primary parameter). A square section `follows` its width and says
so — `"follows the given Width (12 in)"` — rather than presenting a derived number as a
nominal.

```
$ make_family.py archetypes --prompt "a 24 inch cable tray 20 ft long with 6 in rung spacing"
Cable Tray - Ladder  (cable_tray, category cable_tray_fitting)
  Width                     24 in   GIVEN   <- '24 inch cable tray'
  Loading Depth              4 in   nominal <- standard loading depths 3 / 4 / 5 / 6 in
  Length                    20 ft   GIVEN   <- '20 ft long'
  Rung Spacing               6 in   GIVEN   <- '6 in rung spacing'
  ...
  -> 46 parts; 5 nominal, 3 given. No manufacturer identity is claimed.
```

## Lane order (DONE 6)

`_r_prompt_to_rfa` now tries the **catalog lane first** and only falls through to the
archetype lane when nothing catalog-backed came out. "a 225 A Eaton panelboard" still
routes to real catalog facts and never to a generated approximation — pinned by
`test_catalog_facts_still_win_when_the_prompt_names_a_catalog_product`. When it does fall
through, the catalog lane's refusal is demoted from an error to a caveat, so the manifest
still shows why the first lane did not apply. A prompt naming nothing we build ("make me a
spaceship") is refused exactly as before.

## A validator gap closed on the way

The stdlib famspec validator handled `additionalProperties: false` but ignored
`additionalProperties: <schema>` — so a free-key map's **values** went unchecked, and
`{"dimensions": {"width_in": "wide"}}` validated clean and only failed at the constructor.
It now checks them, which also closes the same hole for `standard_values` (#601).

## Evidence

| gate | result |
|---|---|
| `python -m rvt.famgen.archetypes --check` | 5 archetypes, **0 problems** |
| `tests/test_famgen_archetypes.py` | **46 passed** (round 1; 71 after round 2) |
| `tests/test_router.py` | **138 passed, 8 skipped** |
| `test_frontdoor + test_famgen_factory + test_famgen_standards + test_standards_apply_safe` | **461 passed, 18 skipped** (with the archetype suite) |
| `tools/route.py matrix` self-audit | clean (the new `prompt->archetype` stage is declared with its evidence) |
| `tools/sync_plugin.py` + `--check` | clean, deny-audit clean; `validate_plugin.py` **PASS (25)** |
| `tools/dev/check_portable_paths.py` | ok, **3039** paths |
| every archetype's `.rfa` | family-mode **VALID 0 errors**, provenance **ok, zero suspects** |
| bare plugin unzip, system python | `go route.py run --prompt "create a cable tray family" --output rfa` → READY, exit 0, delivered |

The headline, on `main` before and after:

```
before: FAILED (prompt->intent: PromptError ... Recognised-but-unbuilt kinds: cable_tray)
after:  OK (Cable Tray - Ladder: 16-part .rfa generated at standard nominal sizes;
            0 dimension(s) from the prompt, 8 nominal)
```

Two pinned expectations updated, both because the contract grew a kind:
`test_famspec_schema_is_draft07_and_covers_every_kind`'s kind tuple, and nothing else.

## What is NOT claimed

- **No desktop round.** Every archetype `.rfa` is family-mode VALID and provenance-clean;
  nothing here says desktop Revit has opened one. The parts are boxes and one X-axis
  cylinder — both shapes the owner's Revit 2026 verified in #583 (boxes load; the rotated
  cylinder draws round) — which is a reason to expect it to hold, not evidence that it
  does (hard rule 4). **The cable tray is the file to put in front of Revit first.**
- **The nominals are industry practice, not a cited standard.** Every `basis` string says
  which practice; none claims to quote a document this repo holds.
- **A tray section is placed, not routed.** #608 is the native `RbsCableTrayType` work; the
  two are complementary and the caveat says so on every delivery.
- **The conduit bore is not modelled** (no void/boolean in the writer), stated on delivery.

## Open questions

1. Desktop: do the 17-part tray, the slotted strut and the X-axis conduit open **and load**?
2. Should a room prompt that mentions cable tray also emit the tray family? Today it stays
   an honest `recognised-but-unbuilt` line in the room build; only a family-shaped prompt
   reaches the archetype lane.
3. The next archetypes worth having are probably ladder-tray **fittings** (elbow, tee,
   reducer) — which is also what #608 needs LOD-400 geometry for, so the two meet there.

---

## BRANCH STATE

Branch `claude/591-prompt-archetypes` from `main` @ `3ec84d7`.

Files written:
- `src/rvt/famgen/archetypes.py` (new: `Param`, `Archetype`, `Resolved`, the five products
  and their builders, `resolve_prompt` / `resolve`, `build_parts`, `describe`, `table`,
  `check_registry`, a `__main__`)
- `src/rvt/famgen/factory.py` — `make_archetype`, `nominal` in `FactSheet.unverified()`,
  `FamilyProduct.archetype` + its `summary()` block, the bounding-box facts moved aside so
  an archetype's own width is not overwritten by the assembly bbox
- `src/rvt/frontdoor/famspec.py` — the `archetype` kind; the stdlib validator now checks
  schema-valued `additionalProperties`
- `spec/famspec.schema.json` — the `archetype` definition (`product`, `dimensions`,
  `prompt`, plus the common fields)
- `src/rvt/frontdoor/router.py` — `_archetype_rfa`, and `_r_prompt_to_rfa` restructured to
  catalog-first / archetype-second / honest-refusal-last
- `src/rvt/frontdoor/matrix.py` — the `prompt->archetype` stage and the `prompt -> rfa`
  cell's caveat + hint
- `tools/make_family.py` — the `archetypes [product] [--prompt] [--json] [--check]` verb
- `plugin/skills/tekton-author/SKILL.md` — the named-product route and how to report its
  provenance
- `tests/test_famgen_archetypes.py` (new, 46 tests),
  `tests/ci_shard.d/591-prompt-archetypes.txt`
- `tests/test_router.py` — the kind-tuple pin
- this record

Gates: all green (table above). Plugin re-synced and re-zipped.

Staged vs shipped: everything is **shipped** on the branch; nothing staged for a viewer
batch. The desktop question (do these open and load) is the open work and needs the
owner's machine.

---

## Round 2 — the independent review found six real defects

PR #674's first head (`b05b238`) went through the session-hosted gate: sandboxed CI **pass**
(2362 passed / 162 skipped), then a fresh reviewer context that had not seen the code.
Verdict: **🛑 changes requested**, six blocking findings. All six were real; every one now has
a regression test that fails on the code as first written.

| # | defect | how it showed |
|---|---|---|
| 1 | **A regression I introduced.** Teaching the famspec validator schema-valued `additionalProperties` made `standard_values: {"Voltage": null}` a hard refusal — but `standards.py` documents `None` as *"no value: the slot stays blank"*, and a list value used to be reported as `values_unusable`. A delivered family became a refusal. | `main` normalised it fine; the head raised `FamspecError` |
| 2 | **A short alias swallowed a longer one.** `length` sits inside `slot length`; parameters were scanned in declaration order and the winner locked the region. `"a strut channel with slot spacing 2 in and slot length 1.125 in"` built a **1.1-inch-long** channel reporting a slot spacing it did not have. | word-order dependent: the same prompt with `10 ft long` first resolved correctly |
| 3 | **The manufacturer guard did not exist.** Five places — the matrix caveat, the schema, the SKILL, the module docstring, this record — asserted that a named manufacturer's part is *refused*. `route({"prompt": "an Eaton B-Line 24 in cable tray part number 24A-09-120"})` returned `ok=True` and a delivered `.rfa`; the tokens only appeared in an `Ignored words:` line. | a user-facing claim about a guard that was not implemented — exactly the overclaim PG1 forbids |
| 4 | **A foot measurement bound an inch dimension.** `"a 10 ft cable tray"` → `width_in = 120` — a ten-foot-**wide** tray. | reported `given` with the user's words, so it looked deliberate |
| 5 | **Two guard sets incomplete.** `depth_in: 0.15` gave overlapping tray flanges (no `D > 2t` guard, which both siblings have); `lip_in: 0.8` passed `2·lip < Wd` but the lips overlapped **0.185 in** through the centreline, because each starts behind its own web. | self-intersecting solids, no raise |
| 6 | **The reported rung spacing was not the built one.** Rungs were spread `L/(n-1)`, so 9 in asked for became **9.23 in** built, and even the default had 11.5 in end bays. | a parameter lying about its own geometry |

Plus hygiene the reviewer flagged and this round took: the `Fact` docstring now lists `nominal`;
the route's caveat label says *generated / assumed / user-given* rather than *assumed / user-given*;
and the "we hold no standards document" disclaimer moved out of the module docstring into the
**printed** caveat, since the caveat is what names "NEMA VE 1" to a user.

### What #3 became

Not a refusal. Hard rule 1 says output is never withheld, and steer #591's own wording is that a
named part *"must not **silently** become a generic nominal tray wearing that part number"* — the
objection is to the silence, not to the building. So `manufacturer_claim()` detects three things —
part/catalog/model-number phrasing, a token *shaped* like a part number, and the brand names our
catalog actually resolves (Eaton, Schneider Electric, Lithonia … sourced from the corpus, not a
guessed list) — and when it fires:

- the family is still built and delivered;
- the status line gains **"-- NOT the product you named"**;
- the **first** caveat is `YOU NAMED A SPECIFIC PRODUCT (…) AND THIS FILE IS NOT IT`, with the two
  honest routes (give the real dimensions, or send the manufacturer's IFC);
- the identity block still carries no manufacturer, model or part number — pinned by a test that
  greps the whole type row and the family name for the token.

The detector is deliberately narrow on the token pattern (letters **and** digits **and** two
separators) so `1-5/8`, `12x12`, `480Y/277` and `2x4` do not trip it; six ordinary prompts are
pinned as *not* flagged, because a false positive would put a scary line on every honest delivery.

### Round-2 evidence

| gate | result |
|---|---|
| `tests/test_famgen_archetypes.py` | **71 passed** (46 → 71: one regression test per finding, plus the guard's true/false-positive sets) |
| `test_router + test_frontdoor + test_famgen_factory + test_famgen_standards + test_standards_apply_safe + test_famgen_archetypes` | **490 passed, 18 skipped** |
| `python -m rvt.famgen.archetypes --check` | 5 archetypes, **0 problems** |
| `sync_plugin.py` + `--check`, `validate_plugin.py`, `check_portable_paths.py` | clean / PASS (25) / ok, **3044** paths |

The reviewer also verified, with no finding: mirrors byte-identical for all seven mirrored files;
the `res.errors[mark:]` demotion correct in all four paths; the slotted-back material removal exact
(60 slots × 1.125 in over 10 ft); `viewer-certified.json` untouched; no other open PR closes #591.

---

## Round 3 — a second fresh reviewer, six more defects

The round-2 head passed sandboxed CI (2433 passed) and then failed a SECOND independent
reviewer, which was told explicitly not to take round 2's list on trust. It was right to be
told that: three of its six findings are in the code round 2 wrote.

| # | defect | how it showed |
|---|---|---|
| 1 | **The manufacturer guard fired on ordinary English.** `_PART_PHRASE` had no word boundary after the keyword: *"a junction box on the **part**ition wall"* → token `'ition'`, *"above the **cat**walk"* → `'walk'`, *"a generic **model** family"* → `'family'`. End-to-end that put `YOU NAMED A SPECIFIC PRODUCT (ition) AND THIS FILE IS NOT IT` as the first caveat of an honest delivery — the line the SKILL tells a session to relay verbatim, first. Round 2's own claim that six ordinary prompts were pinned as not-flagged was true and useless: all six happened to avoid `part`/`cat`/`model`. |
| 2 | **Rungs wider than their spacing interpenetrated.** `rung_width_in: 24` at 12 in centres → 8 overlapping pairs, no raise — the exact class round 2 said it had closed. Reachable by prompt (`"rung width 2 in"` resolves). |
| 3 | **`max(2, …)` put rungs outside the section.** A spacing wider than the length gave two rungs a foot past both ends of the rails, attached to nothing, status still `OK`. |
| 4 | **Two more stale "still refused" texts** — the `prompt->archetype` **stage description** (which `route matrix --json` prints verbatim) and `make_archetype`'s docstring. Round 2 fixed five places and missed two. |
| 5 | **A bare metric measurement was silently dropped.** `"a 600 mm cable tray"` → nothing given, width left at the nominal, no word to the user — while this record advertised `600 mm` as read. |
| 6 | **A zero dimension passed every guard**, authoring zero-volume solids (`thickness_in: 0`). |

Plus two nits taken: the budget compared the RUNG count to `MAX_PARTS` so 401- and 405-part
families slipped past a stated 400 limit (it now counts parts); and the guard's docstring
claimed the patterns "catch the rest" while `"a Hoffman F66L120 wireway"` was not caught — a
bare-designator rule now catches it, and the docstring states the remaining gap by name
(a one-letter designator like Unistrut's `P1000` is below the bar).

**The part counts in round 1 were stale** and are corrected above: the tray builds **16**
parts at its nominals, not 17; the worked example **46**, not 47; the slotted strut **65**.
Those moved when round 2 changed the rung pitch, and nobody re-measured them.

### The lesson worth keeping

Three of six round-3 findings were introduced by round-2 fixes, and one was a claim that
survived a whole round of "fix the overclaim" work in two of seven places. A fix is not a
fix until an adversarial reader has run it: **`test_no_shipped_text_claims_a_refusal_that_does_not_happen`**
now greps the shipped surfaces for that class of sentence, because prose is where this kept
going wrong and prose had no test.

### Round-3 evidence

| gate | result |
|---|---|
| `tests/test_famgen_archetypes.py` | **104 passed** (46 → 71 → 104) |
| false-positive set for the guard | 12 ordinary prompts pinned as NOT flagged |
| true-positive set | 5 real designators pinned as caught |
| `python -m rvt.famgen.archetypes --check` | 5 archetypes, **0 problems** |
