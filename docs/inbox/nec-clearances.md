# NEC-CLEARANCES — working space about electrical equipment, as data and in the family

Stream: **nec-clearances**, opened by owner steer **#818** (2026-09-23), after the
lighting control panel built for the owner's test (#816):

> Very Good, but for the future you need to know NEC code in order to get the clearances on there
>
> And clearances need to be toggleable within the family parameters

Three parts, three issues:

- **#819** — NEC 110.26 working space as cited **data** (this record's first section).
- **#820** — the clearance solid in the electrical-equipment families, plus a
  *Show Clearance* Yes/No parameter, starting with the lighting control panel.
- **#690** (pre-existing) — a Yes/No parameter bound to a solid's visibility: the
  toggle's critical path, since nothing in `famgen/` authors visibility today.

---

## #819 — the table

> **Review round 1 on #826 changed this section; see "Round 1" below.** In
> particular: dedicated equipment space (110.26(E)) is now implemented, the
> default Condition is **2** (was 1), and `verified` is the AND of every rule an
> answer used.

**Built:** `src/rvt/famgen/clearance.py`, following the pattern of
`rvt.famgen.standards` — data with a written account of what is and is not
verified at the top of the module.

- **Depth** (110.26(A)(1), Table 110.26(A)(1)) by nominal voltage to ground and
  Condition 1 / 2 / 3; **width** (110.26(A)(2)) the greater of the equipment or
  30 in; **height** (110.26(A)(3)) the greater of 6½ ft or the equipment.
- **Keyed by edition** (2026 / 2023 / 2020 / 2017). The answer names the edition
  used.
- **Numbers and article references only.** No NFPA text: NFPA 70 is copyrighted
  and this repository is public (hard rule 6).
- **Residue, never a gate** (S-2026-08-11-c, hard rule 1). Voltage, Condition
  and edition default to 277 V, Condition 1 and NEC 2026, and every default goes
  into `assumed` for the caller to state. Condition 1 is the least demanding
  depth, and the assumption says so.
- **Refusals named, never guessed:** over 1000 V (that is 110.34), between bands,
  a Condition that does not exist, an edition not held.

### What is NOT verified — the most important fact in this record

**No row was checked against the NFPA 70 text.** This environment's egress
proxy blocked every source page tried:

```
expertce.com                       EGRESS_BLOCKED
www.ecmag.com                      EGRESS_BLOCKED
www.electricallicenserenewal.com   EGRESS_BLOCKED
iaeimagazine.org                   EGRESS_BLOCKED
```

Web *search* worked but returns a model-written summary, not quoted text, and
does not say which result a number came from. It gave:

| Nominal V to ground | Cond. 1 | Cond. 2 | Cond. 3 |
|---|---|---|---|
| 0–150 | 3 ft | 3 ft | 3 ft |
| 151–600 | 3 ft | 3½ ft | 4 ft |
| 601–1000 | 3 ft | 4 ft | 5 ft |

The first two rows agree with what I held from model knowledge. **Two
model-derived sources agreeing is corroboration, not verification**, and the
module labels it that way: rows 1–2 `corroborated`, row 3 `single-source`
(search summary only).

**Verification is derived, not declared.** `WorkingSpace.verified` is true only
if the row records `checked_against` (the edition text it was read from).
There is no separate flag a later edit could flip, and a test pins that. Every
answer's `status` carries *"not checked against the NFPA 70 text"* until a row is
really checked.

**I changed my own DONE 4, openly, on #819.** It said an unverifiable value
"stays out of the table". With egress blocked, that would have meant no
clearances at all — withholding what the owner asked for (hard rule 1). The
change is that such a value enters with its status and is reported as
unverified. The line that does not move is presenting any of it as checked.

**Two corrections to what I told the owner:** I said I would default to NEC
2023, but a 2026 edition exists (a search result is titled "NEC 2026 110.26"),
so 2023 was wrong as "newest". Per the same search, this table's depths are
unchanged 2017–2026, so for 110.26(A)(1) the edition mostly changes the label.

## Evidence

```
tests/test_nec_clearance_819.py   26 passed
```

Mutation sweep, every anchor asserted from a script file (`assert count == 1`):

| mutant | dies in |
|---|---|
| 151–600 V Condition 2 depth 3.5 → 3.0 | 2 |
| promote the single-source row to "corroborated" without a source | 1 |
| drop the "(single source)" suffix from the status | 1 |
| drop "not checked against the NFPA 70 text" from the status | 1 |
| drop the 30 in minimum width | 1 |
| default the Condition silently | 1 |
| make the 150 V band edge exclusive | 4 |

Baseline and restore both **26 passed**.

For the lighting control panel (20 × 30 in) at the defaults: originally
**3 ft deep** (Condition 1); after round 1's change to a Condition 2 default,
**3½ ft deep × 30 in wide × 6½ ft high**, three assumptions stated.

## Round 1 on #826 — `🛑 changes`, and the blocking one was a silent scope cut

**I dropped 110.26(E) without saying so.** #819 lists dedicated equipment space
and asks whether it applies *per kind*, but I changed DONE 4 openly on the issue
and then dropped this silently. Narrowing scope without saying so is the failure
the process exists to prevent. It is now implemented rather than re-scoped:
`dedicated_space(kind, …)` gives panelboard, switchboard, switchgear and MCC a
zone the width and depth of the equipment, up 6 ft. The lighting control panel
gets **none, and is told why**. A kind with no decision is refused by name.

**`verified` could over-claim once a row was checked.** It read only the depth
row, while an answer also uses the width and height minimums. It is now the AND
of every rule used, and a test pins both directions: checking the depth row
alone stays unverified, and checking every rule it used makes it verified.

**The default Condition is 2, not 1.** The reviewer argued it and I agree: a
drawn clearance exists to catch obstructions, and a missed clash costs a code
violation where a false one costs a click. Equipment most often faces a concrete
or block wall, which is Condition 2. This departs from #819's rule 5 as I wrote
it; recorded on #819. The lighting control panel's default depth is now
**3½ ft** (277 V).

**Also:** every rule carries its article, and each answer's `source` names the
edition and the articles. The tier is `nominal`: the ledger has no "standard"
tier, and a code minimum's source is a named standard, which is what `nominal`
means (S-2026-08-10-e). Negative/NaN voltages and a non-integer or bool Condition
are refused. The over-1000 V pointer is hedged by edition, and DC is out of
scope. Two test docstrings that claimed more than they checked were narrowed.

**The reviewer's independent read of the numbers**, also unable to reach any
source (egress blocked): 0–150 and 151–600 V rows *high confidence*, 601–1000 V
*~80%*, width and height *high*. Their search summary hinted 3½ ft for Condition
2 in the 601–1000 V band against the 4 ft here. That disagreement is exactly why
that row stays `single-source`.

**Mutation sweep, round 1**, with bytecode caching disabled and `__pycache__`
cleared before every run. The reviewer found that a same-size mutant written in
the same second can load stale bytecode; my earlier mutations all changed the
file size, so those readings stand. All **11** die, including both of the
reviewer's survivors:

| mutant | dies in |
|---|---|
| 601–1000 V Condition 1 cell 3.0 → 2.5 *(survived round 0)* | 1 |
| `source` loses its edition *(survived round 0)* | 1 |
| `verified` from the depth row only | 1 |
| `verified` always True | 2 |
| default Condition back to 1 | 2 |
| dedicated space applied to the lighting control panel | 1 |
| an unknown kind guessed instead of refused | 1 |
| a bool Condition accepted | 2 |
| negative / NaN voltage accepted | 2 |
| the >1000 V edition hedge dropped | 1 |
| tier becomes `fact` | 1 |

Baseline and restore both **42 passed**.

## Round 2 on #826 — `nits`, three of them over-claims, fixed before merge

The module exists to not over-claim, so these were fixed rather than deferred:

- **`dedicated_space()` never checked the edition.** It returned
  "NEC 2014 110.26(E)(1)", "NEC True …", "NEC x …" — a citation of an edition
  not held, the same bug round 1 fixed in `working_space`, and the one mutant
  that survived round 2. Both functions now share one edition guard.
- **The ceiling cap was not carried.** "6 ft above the equipment *or to the
  structural ceiling, whichever is lower*" lived only in the docstring, so a
  caller drawing the zone (#820) would overshoot a low ceiling silently. Every
  answer now carries `height_limit` in words; an optional `ceiling_above_ft`
  applies the cap when known.
- **"A lighting control panel gets no dedicated space" was half right.** The
  rule does not name the kind, but many lighting control panels are built and
  listed as panelboards (remote-operated breakers), and for those it does apply.
  The answer now says so and points to kind `panelboard`. The owner is an MEP
  designer and would have caught this immediately; better it is caught here.

Also: "Condition 3 is deeper" is now "can be deeper" (below 151 V all three are
3 ft); **verification is per edition** (`Rule.checked` holds `(edition, what was
read)` pairs, so a check of the 2026 text no longer marks a 2017 answer
verified); the non-applying branch validates its inputs; and the module docstring
names both single-source rules.

| mutant (bytecode caching off, `__pycache__` cleared, anchor asserted) | dies in |
|---|---|
| dedicated `source` drops its edition *(survived round 1)* | 4 |
| `dedicated_space` skips the edition guard | 3 |
| verification not edition-aware | 1 |
| ceiling ignored when known | 1 |
| ceiling-unknown text dropped | 1 |
| "can be deeper" back to "is deeper" | 1 |
| the lighting control panel's panelboard caveat dropped | 1 |
| non-applying branch skips the dimension check | 1 |
| round 1's two: depth row only / default Condition 1 | 1 / 2 |

Baseline and restore both **47 passed**.

## What #820 found that changes the plan (recorded here because it constrains how this table is used)

The factory has **no subcategory support** (`grep -i subcategor
src/rvt/famgen/factory.py` → nothing), and #690 records that nothing authors
visibility today. So a clearance solid cannot currently be hidden, and built into
the default family it would draw a solid 3 ft × 30 in × 6½ ft block in every
view. #820 therefore ships it as an **opt-in "with clearance" variant** until
#690 and a subcategory exist, never in the default family.

## How a row becomes verified

Allow a code-reference domain in the environment's network policy (the owner's
configuration), or read the text from an environment with open egress; then set
`checked_against`. Never by editing the status alone.

---

## BRANCH STATE

**Files written (#819)**
- `src/rvt/famgen/clearance.py` — new: working space (depth / width / height),
  dedicated equipment space per kind, the verification status per rule.
- `plugin/lib/src/rvt/famgen/clearance.py` — mirror (via `sync_plugin.py`).
- `tests/test_nec_clearance_819.py` — new, 47 tests (26 at round 0, 42 after round 1).
- `tests/ci_shard.d/819-nec-clearance.txt` — new.
- this record.

**Gates** (after round 2): 47 passed; round-1 11/11 and round-2 10/10 mutants
die (bytecode caching disabled); `sync_plugin.py --check` in sync; portable
paths ok. Full suite **not** run.

**Shipped vs staged**: shipped as data; nothing draws it yet (#820).
