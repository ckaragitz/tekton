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

For the lighting control panel (20 × 30 in) at the defaults:
**3 ft deep × 30 in wide × 6½ ft high**, three assumptions stated.

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
- `src/rvt/famgen/clearance.py` — new: the table, `working_space()`, the
  verification status.
- `plugin/lib/src/rvt/famgen/clearance.py` — mirror (via `sync_plugin.py`).
- `tests/test_nec_clearance_819.py` — new, 26 tests.
- `tests/ci_shard.d/819-nec-clearance.txt` — new.
- this record.

**Gates**: 26 passed; 7/7 mutants die; `sync_plugin.py --check` in sync; portable
paths ok. Full suite **not** run.

**Shipped vs staged**: shipped as data; nothing draws it yet (#820).
