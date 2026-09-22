# 807 — the donor byte scan counted OUR OWN ids

Stream: **famdoc-scan-fp** (fragment; the index is `../famdoc-scan-fp.md`, #12's
original charter). Issue **#807**, branch `cam/807-id-space-collision`.
Found by the standing test/debug loop (**#805**) while gating an unrelated
change (#808): `tests/test_famdoc_scan_fp.py::test_provenance_scan_on_the_real_bundled_universe_is_clean`
was **red on `main`** and had been for some time, because the file is not in
the CI shard.

#12 landed the corroboration machinery and it works. This fragment is a
**second false-positive class** that corroboration cannot reach, and the
process half — the gate was red where nobody was looking.

---

## The failure as found

```
tests/test_famdoc_scan_fp.py::test_provenance_scan_on_the_real_bundled_universe_is_clean
    assert rep["checks"]["zero_donor_id_byte_hits"] is True, scan
E   AssertionError: {'hits': 6, 'distinct': 3, 'examples': [18403, 18404, 18453],
                     'raw_window_hits': 6, 'false_positive_windows': [], ...}
```

`1 failed, 12 passed` on `main` at `a8c5e91`, reproduced from a clean
`git archive origin/main` export with `PYTHONPATH` at the export and
`rvt.__file__` printed to prove which engine ran (#802's recipe, because a
`git stash` "before/after" measures the same tree twice).

`false_positive_windows: []` is the tell: **every** window is corroborated by
a real integer leaf. This is not #12's straddling-window class.

## What the three ids are

```
family_document: n_elements=122, id_range=[18400, 18521]     # start_id = 18400
DONOR universe:  n=2883, min=6473, max=1472524
  18403  in_ours=True  in_donor=True
  18404  in_ours=True  in_donor=True
  18453  in_ours=True  in_donor=True
OURS ∩ DONOR: n=7 -> [18403, 18404, 18451, 18452, 18453, 18454, 18470]
```

All three are **our own elements**. The bundled base allocated ids in the same
numeric neighbourhood our family does; 7 of our 122 collide, 3 are referenced.

The six leaves holding them — 6 occurrences, 6 reported hits, so the scan is
neither over- nor under-counting:

```
18403  <-  m_appInfoArr/[52]/value/m_levelIdToPlanViewIds/[0]/first
18403  <-  m_appInfoArr/[32]/value/m_elems/[1]/m_elemIdSet/[0]
18403  <-  m_appInfoArr/[53]/value/m_elemIdSet/[0]
18404  <-  m_appInfoArr/[3]/value/m_DBViewProjectId
18404  <-  m_appInfoArr/[3]/value/m_DBViewsIndex/[0]
18453  <-  m_appInfoArr/[3]/value/m_aidSunAndShadowSettings/[2]
```

Every one is an element-id **reference** field, not an index. #807 as filed
offered the dichotomy *reference ⇒ genuine carry, index ⇒ false positive*;
that dichotomy is wrong, and the third class is **a reference to our own
element whose id numerically collides with a donor id.**

The surrounding structure makes it plain:

```
m_levelIdToPlanViewIds    : [{"first": 18403, "second": {"m_elementIds": [18409, 18417]}}]
m_DBViewsIndex            : [18404, 18409, 18417, 18425, 18431, 18437, 18443, 18450]
m_aidSunAndShadowSettings : [18412, 18420, 18453]
```

`18403` is **our Level**, keying our own plan views. `m_DBViewsIndex`'s eight
entries are the view constellation S-2026-08-10-a requires of every generated
family. **The siblings in those very lists are equally ours and equally
referenced, and are "clean" only because the donor happened not to use those
numbers** — 18409, 18417, 18425, 18431, 18437, 18443, 18450, 18412, 18420 are
all outside `OURS ∩ DONOR`. The three hits are a random subset of one coherent
authored structure, picked out by numeric coincidence.

## The measurement that rules out a real carry

```
integer leaves >= 4700 in the decoded ADocument : 48
  of those, NOT one of our elements             :  0
```

Zero exceptions. Above the scan floor our authored payload references nothing
but our own elements, so there is no carried donor reference to find. This is
the premise the fix rests on, and it is asserted in the suite rather than
assumed (`test_every_leaf_above_the_scan_floor_is_one_of_our_elements`) — if it
ever stops holding, that test says so and names the offending ids.

## The fix — one site, and why only one

`provenance_scan_v2` built its universe as the donor's whole set with no
subtraction of `ours` (`famdoc_adoc.py:2046`), even though `ours` was computed
37 lines earlier and a sibling `byte_scan_our_ids` already counts these very
windows as ours. Now:

```python
shared_ids  = donor_ids & ours
foreign_ids = donor_ids - ours
```

with the fatal check keyed on `foreign_ids` and `shared_ids` **scanned and
reported** as `own_id_space_collisions` — ids, hits, distinct, examples.
Nothing is dropped:

```
byte_scan_donor_ids     : hits 0, universe 2883, universe_scanned 2876
own_id_space_collisions : hits 6, distinct 3, examples [18403, 18404, 18453],
                          ids [18403, 18404, 18451, 18452, 18453, 18454, 18470]
```

The adjudicator `corroborated_donor_scan` is **deliberately left value-based**:
its caller supplies the universe, and `test_tree_corroborated_id_stays_a_hit`
rightly pins that. The fix belongs where the universe is built.

**The other raise site was measured, not assumed, and is out of scope.**
`author_family_adocument` scans `meta["donor_element_ids"]` — and on the
donor-free path (S-2026-08-10-c, the only supported one) that is literally
`[]`:

```python
if source_tree is not None:
    base_tree, meta = copy.deepcopy(source_tree), {"donor": "(supplied tree)",
                                                   "donor_element_ids": []}
```

so its scan returns `{"hits": None, "note": "no donor id universe (supplied
tree)"}` and the raise is unreachable there. Touching it would have weakened a
gate with no measured reason to.

## Why this is not a widened allowance

The thing #807 explicitly forbids is loosening the rule until the test goes
green. The exclusion is narrow and justified structurally:

* a reference is resolved **in the id space of the document that carries it**;
  in this file id 18403 *is* our record, and no donor element exists in it;
* references to ids that are **not** ours stay fatal here **and** are
  independently caught by the schema-typed dangling census
  (`zero_dangling_element_refs` / `naive_id_leaves_not_ours_gt99`), which this
  PR does not touch — that is the check that fires if a real donor reference
  ever survives;
* the excluded set is reported with the windows it accounts for, and a test
  ties those numbers back to an **unfiltered** scan, so the exclusion cannot
  be widened without failing.

## The trap in the existing suite

`test_provenance_scan_flags_a_genuine_donor_id` used `self_family_id` — *one
of ours* (18400) — as its stand-in for a genuine donor reference. Excluding the
collision class makes it **vacuous**: `0 >= 1`, which is how it surfaced. And
no natural substitute exists, since 0 of 48 leaves are non-ours.

Rebuilt on `provenance_scan_v2`'s existing `our_ids=` parameter, narrowing the
ownership set so the id really is foreign, and on a **non-owner** id so that
`owner_family_is_ours` cannot make `rep["ok"] is False` pass for the wrong
reason. The result is a mutant-killing pair: **the same id, fatal when foreign,
recorded when ours** — ownership alone separates them.

## Evidence

Mutation sweep, every anchor asserted from a script file with
`assert count == 1` (a mangled anchor silently applies nothing and reports the
baseline as a pass — that non-run happened three times on #808):

| mutant | dies in |
|---|---|
| the exclusion itself (scan the donor's whole universe) | 3 |
| **widen the exclusion to everything (blanket allowance)** | 4 |
| stop reporting the collisions | 3 |
| drop `universe_scanned` from the report | 2 |

Baseline **18 passed**; restored source re-measured at **18 passed**.

Gate set = every test file matching
`famdoc_adoc|provenance_scan_v2|corroborated_donor_scan|emit_family_rfa_v2|author_family_adocument`,
**13 files** (conftest excluded from the run list; pytest loads it anyway):

```
405 passed, 45 skipped in 103.75s
```

Zero failures — `main`'s three known reds drop to two, since this was one of
them (the other two are in `test_catchain.py`, filed separately and untouched).

`tools/sync_plugin.py --check`: *plugin in sync with source (deny-audit clean,
identity scan == allowlist, assets verified)*.
`check_portable_paths.py`: *ok: 3253 tracked paths are portable*.

## The process half — arguably the bigger finding

```
grep -n "test_famdoc_scan_fp" tests/ci_shard.txt tests/ci_shard.d/*.txt
→ (no match)
```

A **provenance gate** — the machinery that enforces hard rule 3 — was red on
`main` and session CI was green, because the file was outside the shard. Fixed
by `tests/ci_shard.d/807-famdoc-scan.txt` (never editing `tests/ci_shard.txt`,
#328), which puts both this module and `test_famdoc_scan_fp.py` in the shard;
`shard_list.py --print` now merges to **164** files and lists both.

That a gate can rot unnoticed matters more than these three ids did. It is
worth a sweep for other gate-bearing test files outside the shard — filed
separately rather than widened into this PR.

## Open questions

* **Should our id allocator avoid the donor's range entirely?** `start_id=18400`
  collides with the bundled base by coincidence. Not changed here: start_id
  selection affects the certified `.rfa` lineage and needs its own evidence
  (hard rule 4). The exclusion is correct independently of it.
* **What else is outside the shard?** See above.
* Hard rule 4 is untouched by any of this: nothing here is a statement about
  what Autodesk's reader accepts.

---

## BRANCH STATE

**Files written**
* `src/rvt/famgen/famdoc_adoc.py` — `provenance_scan_v2` splits the donor
  universe into `foreign_ids` (fatal) / `shared_ids` (reported), and reports
  `own_id_space_collisions` + `universe_scanned`.
* `tests/test_famdoc_scan_fp.py` — `_scan_with_universe` takes `our_ids`;
  new `our_element_ids` helper and `carried_non_owner_id` fixture;
  `test_provenance_scan_flags_a_genuine_donor_id` rebuilt so it is not vacuous.
* `tests/test_famdoc_scan_collision_807.py` — **new**, 5 tests: the premise,
  the collision is present, recorded-not-fatal, the same id fatal when not
  ours, and nothing dropped silently.
* `tests/ci_shard.d/807-famdoc-scan.txt` — **new**, both files into the shard.
* `docs/inbox/famdoc-scan-fp.d/807-id-space-collision.md` — this fragment.
* `docs/inbox/generated-size-bound.md` — **repair only**, carried from #808's
  round-5 nit: three stranded lines duplicating the paragraph above them, with
  an orphaned `**` that garbled the rendering. No claim changed. Carried here
  rather than merged unreviewed into #808, because a head no reviewer has seen
  is exactly what the #302 merge gate exists to prevent.

**Gates**: 13-file gate set 405 passed / 45 skipped / 0 failed; mutation sweep
4/4 die, baseline and restore both 18 passed; `sync_plugin --check` clean;
portable paths ok. Full suite **not** run.

**Shipped vs staged**: all shipped. No viewer batch — no claim about Autodesk's
reader is made or needed.
