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

1. Desktop: do the 16-part tray, the slotted strut and the X-axis conduit open **and load**?
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

---

## Round 4 — a third reviewer, and the worst bug of the four rounds

CI passed on the round-3 head (2474 tests). The third fresh reviewer returned **changes** with
five findings. One of them had been in the code since round 1 and three reviewers had to look
for it before it was found.

### `_NUM` had no left boundary

The dimension patterns matched digits **inside** an alphanumeric token:

| prompt | read as | delivered |
|---|---|---|
| `"an IP65 junction box"` | `width_in = 65`, `height_in` follows | a 65 × 65 × 4 in box |
| `"a Unistrut P1000 strut"` | `height_in = width_in = 1000` | an 83 ft section |
| `"a 480Y/277 wireway"` | `277 in` | — |
| `"a T8 wireway"` | `8 in` | — |
| `"a Hoffman F66L120 wireway"` | `120 in` | — |

Every one reported `provenance: given` and quoted back `from_prompt = "65 junction box"` — words
the caller never wrote as a measurement. That is the provenance contract lying about itself,
which is the one thing this whole module exists to get right, and it shipped through three
rounds of review that were all looking at the provenance logic. Fixed with a
`(?<![A-Za-z0-9./-])` lookbehind on every leading number; the cross-dimension path keeps the raw
form for its 2nd and 3rd numbers, which sit behind the `x` of `12x12`.

### The guard's third false-positive class

Round 3's bare-designator rule ("two letters and two digits, five characters") is **exactly the
shape of a wire gauge**: `12AWG`, `500MCM`, `200A3P`, `THHN12`, `NFPA70`, `480V3PH`, `4C10AWG`
all tripped it, so `"a cable tray for 12AWG conductors"` delivered with `YOU NAMED A SPECIFIC
PRODUCT (12AWG) AND THIS FILE IS NOT IT` as its first caveat. Third instance of this class in
three rounds.

The fix is a change of principle rather than another pattern tweak: **a bare designator alone no
longer accuses anyone.** It is a catalogue number only when the prompt *also* names a
manufacturer or uses part-number phrasing. `_KNOWN_BRANDS` became `_BRAND_HINTS`, widened with
the containment/enclosure manufacturers and relabelled as what it is — hand-written, certainly
incomplete, and only ever raising a designator from "ambiguous" to "specific".

### Two more surfaces claiming a blanket refusal

`matrix._CATALOG` and the schema's top description both said facts the catalog lacks are
"REFUSED by name, never invented" with `generic_model` as the *only* exception — and
`_CATALOG` prints **first** on the archetype lane's own deliveries, immediately before the
caveat that contradicts it. Both now name `archetype` as the second exception.

`test_no_shipped_text_claims_a_refusal_that_does_not_happen` was real but too narrow: it matched
three literal phrases and did not scan `router.py` or `famspec.py`. It now also asserts that any
surface claiming the blanket catalog refusal names the archetype lane as an exception — the
subtler form, and the one three reviewers had to find by hand.

Plus: a slot longer than its own pitch returned a **solid** back while reporting both slot values
as `given` (now refused, as its sibling condition already was), and a rung wider than its section
is refused.

### What the reviewer verified clean

24,768 override combinations fuzzed across all five archetypes for pairwise AABB intersection and
non-positive dimensions: **0 self-intersections, 0 zero-volume parts** — the geometry class that
rounds 2 and 3 both found is now closed. `nominal` reaches every surface (`unverified()`,
`summary()`, the written `.report.json`, the route caveats, the CLI). Lane order and the error
demotion correct live. All mirrors byte-identical.

### Round-4 evidence

| gate | result |
|---|---|
| `tests/test_famgen_archetypes.py` | **131 passed** (46 → 71 → 104 → 131) |
| `test_famgen_archetypes + test_router + test_frontdoor` | **354 passed, 13 skipped** |
| `python -m rvt.famgen.archetypes --check` | 5 archetypes, **0 problems** |
| `sync_plugin --check` / `validate_plugin` / portable paths | clean / PASS / **3044** |

### The count that matters

Four rounds, **seventeen** defects, every one found by a reader who had not written the code and
every one after CI was green. The tests in this file are the record of what CI cannot see.

---

## Round 5 — hyphens, and a test that was lying about doing its job

CI green again on the round-4 head (2511 passed). The fourth fresh reviewer returned **changes**
with five findings. Two of them are one defect seen from both ends.

### The commonest phrasing in this domain was broken both ways

English hyphenates measurement adjectives, and electrical drawings do it constantly:
*"a 24-inch-wide cable tray"*, *"a 6-in-deep tray"*, *"a 10-ft-long run"*. Every one of those:

1. **had its dimension silently dropped** — the patterns put `\s*` between the number, its unit
   and the word it qualifies, so a hyphen killed the match. `"a 24-inch-wide cable tray 20 feet
   long"` delivered a **12 in** tray and reported the width `nominal` — i.e. *"we generated
   it"* — for a number the caller had explicitly stated; **and**
2. **tripped the manufacturer guard**, because `6-in-deep` fits the separator-bearing
   part-number shape exactly. So the delivery led with `YOU NAMED A SPECIFIC PRODUCT
   (6-in-deep) AND THIS FILE IS NOT IT`.

The same request, wrong size *and* accused. Fourth instance of the guard class, and the second
instance of a stated dimension being reported as generated.

Fixed with `[\s-]*` around units and aliases everywhere a number is parsed, and by rejecting any
hyphen group that is a unit or measurement adjective (`in`, `inch`, `ft`, `wide`, `deep`,
`long`, `gang`, `pole`, `awg`, …) from the part-number shape.

Also: `"a 1,200 mm cable tray"` matched the `200` and delivered a **7.9 in** tray, quoted back
as `'200 mm cable tray'` — a truncated fragment that reads deliberate. Grouped numbers now parse,
and `,` joined the lookbehind class.

### The guard test was vacuous, and was proved so

Round 4 added `test_no_shipped_text_claims_a_refusal_that_does_not_happen`. The reviewer copied
the head, **reverted `matrix._CATALOG` to the exact round-4 regression**, ran the test — and it
**passed**. The assertion was `"archetype" in text` over the whole file, and every file in its
list mentions the word somewhere else.

It is now sentence-local (the exception must appear within the same passage as the claim),
scoped to the *blanket* claim so honest refusals stay sayable, and it covers
`docs/product/PERMUTATION-MATRIX.md`. **Re-proved by the same method**: reintroducing the
regression in a scratch copy now fails the test.

### The product's own capability table still had the claim — and was never in the diff

`docs/product/PERMUTATION-MATRIX.md` lines 57 and 66 still said *"anything without facts is
refused by name"*, and the `rfa → rfa` row's kind enumeration omitted `archetype` although the
schema had accepted it since round 1. `git diff --stat -- docs/product` was **empty** for four
rounds. That is the surface PG1 names, and no reviewer had been pointed at it until now.

### Round-5 evidence

| gate | result |
|---|---|
| `tests/test_famgen_archetypes.py` | **150 passed** (46 → 71 → 104 → 131 → 150) |
| the vacuity probe | regression reintroduced in a scratch copy → the test **fails** |
| `test_router + test_frontdoor + test_famgen_factory` | **280 passed, 18 skipped** |
| `archetypes --check` / `sync_plugin --check` / `validate_plugin` / portable paths | 5/0 / in sync / PASS / **3044** |

**Five rounds, twenty-two defects.** The reviewer also fuzzed **65,168** override combinations
(per-parameter extremes, pairwise, 3,000 random sets × 4 prompts, prompt+override mixed) for
zero self-intersections and zero zero-volume parts, and confirmed `nominal` reaches every report
surface. What keeps failing is not the geometry — it is the text and the parsing of ordinary
English, and both now have tests that fail when they regress.
