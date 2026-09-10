# famgen-ci / #703 — a troffer size we hold no member for is refused by name

Fragment of the `famgen-ci` stream (index: `docs/inbox/famgen-ci.md`).
Nobody else appends to this file. Closes #703.

## What was wrong

`make_luminaire(kind="recessed-troffer", size="1x4")` produced a family called
**"Recessed Troffer 1x4"** whose body was the **2BLT2 member — 23.75 × 23.75 in**,
a 2x2. The resolver was binary: `2x4` → the 2BLT4 member, *anything else* → 2BLT2.
So `4x4`, `1x2`, `1x4` and even `zzz` all built a 2x2 wearing the caller's name.

A mislabelled body is the one thing this engine must not produce: a size in a
family name is a manufacturer claim, and S-2026-08-10-e reserves refusal for
exactly this — *"presenting a manufacturer's dimensions we do not hold"*.

## What was built

`_TROFFER_MEMBERS` holds `2x4` and `2x2`; anything else **refuses by name** and
lists the sizes the catalog line carries members for. #703's DONE allowed two
outcomes — add the members, or refuse the size — and the facts file
(`famgen/facts/lithonia/blt-led-troffer.json`) holds only `2BLT4-38W` and
`2BLT2`. Adding the others would have meant inventing dimensions.

Also #703 DONE 3: a type's CCT now agrees between the family **name** and its
**description** (3500.7 → 3501 in both, not 3500 vs 3501), and unpublished
W/lm/K are **blank** in the type catalog instead of `0` — an empty standard
parameter is correct, an invented one is not (S-2026-08-11-a).

## Hard rule 1 — verified by execution, not by argument

Refusing a *constructor argument* is not withholding *route output*. Measured at
the head, sandboxed:

| route | before | after |
|---|---|---|
| `route run --prompt "create a 1x4 troffer" --output rfa` | delivered a mislabelled 2x2 | `ok=True`, `recessed-troffer.rfa`, first caveat *"the default member is delivered … NOT a 1x4"* |
| `route run --rfa '{…,"size":"1x4"}'` (famspec) | mislabelled body | `FS.is_refusal → True`, `status FAILED`, no file |
| `tools/make_family.py luminaire --size 1x4` | mislabelled body | one-line refusal, `EXIT=2`, no traceback |

`taxonomy_build.plans()` emits `kw={"kind": "recessed-troffer"}` with **no**
`size`, so the prompt route never reaches the gate. The famspec outcome is the
pre-existing "refused by name" path the router is already written around
(`router.py:1599`), not a status gate turned into refusal logic.

## Evidence

| size | before | after |
|---|---|---|
| 2x4 | 47.75 × 23.75 in | unchanged |
| 2x2 | 23.75 × 23.75 in | unchanged |
| **1x4 / 4x4 / 1x2** | **23.75 × 23.75 in, mislabelled** | **refused by name, listing the held sizes** |

Anti-vacuity (#674 round 5): the head's test file run against `origin/main`'s
code gives **6 failed / 13 passed**; at the head, **23 passed**. Neighbours:
216 passed / 23 skipped, and a second batch 497 passed / 3 skipped.
`self_battery` 18/18, `prompt_battery --rows` 100/100.

Found by `tools/self_battery.py` plus a direct size sweep under steer #765
(sessions test and debug everything themselves) — not by a user hitting it.

## What the review changed, and why each mattered

- **"the sizes with *sourced* housing dims"** was a false provenance claim in a
  user-facing refusal: `2BLT2`'s `dims_in` carry `field_provenance: "assumed"`.
  In this repo `sourced` is a provenance term, so the line now says *"the sizes
  this catalog line carries members for"*.
- **`_CATALOG_SIZES` was a second hand-kept copy** of `_TROFFER_MEMBERS`. The
  failure it invited: add a sourced 1x4 member, watch the constructor build it,
  and the prompt route still silently drops the size and says "NOT a 1x4" —
  with every test green. It is now derived from `factory.held_troffer_sizes()`
  (lazily, so importing `taxonomy_build` does not pull in famgen — S-2026-08-09-g),
  and a test pins the two sides equal.
- **The spelling test pinned only spellings that already worked.** `2 x 4`,
  `2'x4'` and `2X2` all resolve identically on pre-change code. The genuinely
  new normalisations — `2×4` and `2-4`, both folding to `x` — were untested and
  are now pinned, with the docstring saying that acceptance is deliberately
  broader than the three spellings it used to advertise.
- `resolve_luminaire_facts`'s docstring gained the `:raises:` contract.

## This narrows what #682 asserted — flagged, not buried

#682 (merged) stopped `{None:g}` raising, and **its test parametrised `1x4` as a
size that BUILDS**. That crash class is untouched — `2x2` still builds and still
prints `? W, ? lm, ? K` — but `1x4` now refuses, so the parametrisation moved to
the held sizes and the unheld ones gained refusal cases.

`docs/inbox/famgen-ci.d/682-luminaire-sizes.md:56` still tabulates
`| 1x4 | 30 | TypeError | OK |`, which this PR makes false. It is another
stream's fragment in another voice, so it is **not** edited here (no cross-voice
writes); this paragraph is the correction, in this stream's voice.

## Open, found in review, not fixed here

Omitting a `None` photometric drops the whole **column**, not just the cell,
when no type publishes it: `make_luminaire(kind="recessed-downlight")`'s catalog
header has no `Wattage##ELECTRICAL_WATTAGE##WATTS` column at all, where `main`
wrote `0`. The family *parameter* still exists, so S-2026-08-11-a is satisfied
and nothing is invented — but a consumer keying on the header row sees a missing
column rather than an empty one. Nothing depends on it today; recorded so the
next person to write such a consumer knows.

## BRANCH STATE

- Branch: `cam/703-troffer-size-members`, from `main` @ `0119d6b`.
- Files written: `src/rvt/famgen/factory.py`, `src/rvt/frontdoor/taxonomy_build.py`
  (+ their mirrors), `tests/test_luminaire_sizes_682.py`,
  `tests/ci_shard.d/703-troffer-size-members.txt`, this record.
- Gates: module **23 passed**; neighbours **216 passed / 23 skipped**;
  `self_battery` 18/18; `prompt_battery --rows` 100/100; `sync_plugin --check`
  clean.
- Shipped: the refusal, the CCT/blank-value fixes, the derived size set.
- Staged, not shipped: nothing. No certification claim (hard rule 4).
- Not done: the downlight column-vs-cell question above.
