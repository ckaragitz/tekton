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

**The other raise site — I got this wrong, and PR #810's reviewer caught it.**

I wrote here that `author_family_adocument`'s raise was "measured, not assumed,
and out of scope", on the strength of this excerpt:

```python
if source_tree is not None:
    base_tree, meta = copy.deepcopy(source_tree), {"donor": "(supplied tree)",
                                                   "donor_element_ids": []}
```

That is one branch of an `if`, and reading a branch is not running it. My
supporting probe called `family_template_tree()` with **no argument**, which
hit an absent vendor default and raised `FileNotFoundError` — I read that as
"no donor universe" when it only meant "wrong donor". Two errors compounding
into a confident false sentence with the word *measured* on it.

The reviewer executed the call. Reproduced directly afterwards:

```
family_template_tree(G_ABPD) -> donor_element_ids n = 2883
start_id=18400  -> RuntimeError: donor element ids survive in the payload:
                   {'hits': 6, 'distinct': 3, 'examples': [18403, 18404, 18453], ...}
start_id=6473   -> RuntimeError: {'hits': 9, 'distinct': 2, 'examples': [6473, 6553], ...}
```

It is a **product path**: `rfa_assemble.py:118` calls
`author_family_adocument(doc, mode=…, donor=adoc_archetype)` with no
`source_tree` and `adoc_archetype` defaulting to `bundled_base_path()`, and
`extract_family.py:226` reaches it on the `rvt → rfa` cell that
`matrix.py:581` declares `STATUS_WORKS`. The same collision class is a **hard
refusal** there, blaming our own ids on the donor. Filed as **#813**.

**It is still out of scope for this PR, but for a different and narrower
reason than I gave.** The `- ours` exclusion must NOT be extended there: that
lane's tree is derived from the donor, so a leaf holding one of our ids can
genuinely be a surviving donor leaf and value alone cannot separate them. The
unfiltered raise is a real guard there, not an oversight. The two sites differ
on purpose — which is what this record should have said the first time.

## Why this is not a widened allowance

The thing #807 explicitly forbids is loosening the rule until the test goes
green. The exclusion is narrow and justified structurally:

* a reference is resolved **in the id space of the document that carries it**;
  in this file id 18403 *is* our record, and no donor element exists in it;
* references to ids that are **not** ours stay fatal here;
* **and the reason the excluded ids are safe is the lane, not a second check.**
  I first wrote that the schema-typed dangling census independently catches
  them. It does not, and the reviewer was right to call it: that census tests
  `id not in ours`, and the excluded ids are by construction *in* `ours`, so
  for exactly those 7 ids neither check can fire. What actually makes it safe
  is that where `provenance_scan_v2` is the last word, `emit_family_rfa_v2`
  took its **project-donor** branch and authored from
  `constructive_family_host_tree(doc)` — schema-built from our own document,
  never copied from the donor — so no donor leaf can be present to hide. On
  the **family-donor** branch the tree *is* copied, and that lane is gated
  earlier by the unfiltered raise at `famdoc_adoc.py:1313`, before any file
  exists for this scan to read;
* the excluded set is reported with the windows it accounts for, and a test
  ties those numbers back to an **unfiltered** scan, so the exclusion cannot
  be widened without failing.

## The trap in the existing suite

`test_provenance_scan_flags_a_genuine_donor_id` used `self_family_id` — *one
of ours* (18400) — as its stand-in for a genuine donor reference. Excluding the
collision class makes it **fail** — `assert (0 >= 1)`, which is how it
surfaced. Worth the precision: *vacuous* would mean silently passing while
testing nothing, the dangerous shape; this one goes red and forces the
rewrite, which is the safe one. And
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
| revert the empty-`foreign_ids` shape fix (round 1) | 1 |

Baseline **19 passed**; restored source re-measured at **19 passed**. (Both were
18 before round 1 added a test.) PR #810's reviewer reproduced the first four
rows independently and got the same numbers.

Gate set = every test file matching
`famdoc_adoc|provenance_scan_v2|corroborated_donor_scan|emit_family_rfa_v2|author_family_adocument`,
**13 files** (conftest excluded from the run list; pytest loads it anyway):

```
406 passed, 45 skipped in 96.55s        (405/45 before round 1's added test)
```

Zero failures — `main`'s three known reds drop to two, since this was one of
them (the other two are in `test_catchain.py`, filed separately and untouched).

**Why my number differed from the reviewers'**, because an unexplained delta is
not evidence. I got `406 passed / 45 skipped`; the sandboxed exports got `399`
then `400 passed / 51 skipped`. Same 451 total every time, 0 failures every
time.

I gave two wrong explanations before measuring it. The first said `experiments/`
is git-ignored; it is not (1448 tracked files). The second said the delta was
git-ignored **artifacts inside** `experiments/` plus the ignored `out/`. Round 3
showed that is not merely unsupported but **impossible**:

```
find experiments -type f \( -name '*.rvt' -o -name '*.rfa' -o -name '*.bin' -o -name '*.gz' \)
  -> 0          # there are none in this checkout to be missing from an export
```

and no gate file reads `out/`. I had replaced one unverified causal story with
another.

**The measured cause is the environment, not the fixtures.** The sandbox sets
`RVT_SKIP_LARGE=1` (`tools/dev/session_ci.sh:86`); my local runs did not. Same
checkout, same 13 files, only that variable added:

```
.venv/bin/python -m pytest <13 files> -q            -> 406 passed, 45 skipped
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest <same>  -> 399 passed, 52 skipped
```

Seven tests, from one environment variable, with zero fixture difference — which
is larger than the delta I was inventing fixture reasons for.

**One test remains unattributed** and I am not going to explain it away: round 2's
export gave `400/51` where I get `399/52` under the same flag, so one case passes
there and skips here. It is not in this PR's favour and it does not touch the
fix; naming it beats a tidy story.

Since session CI sets the flag and is the authoritative gate, **my 406/45 was the
anomalous run**, not theirs.

For the record, the tracked/export counts (which were right, just not the cause):
`git ls-files experiments` = **1448**; `git archive | grep '^experiments/'` =
**1723**, being those same 1448 files plus **275** directory entries — an export
carries no more of the tree than the tree has.

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
worth a sweep for other gate-bearing test files outside the shard — filed as
**#811** rather than widened into this PR (247 test files, 164 in the shard, 83
outside, 16 of those gate-bearing, including `test_reduce_law.py` which pins
hard rule 5).

## Review round 1 — one false claim, one wrong justification, one latent crash

No finding touched the fix's correctness; the reviewer independently confirmed
the premise (48 leaves above the floor, 0 non-ours), the leaf trace field by
field, every mutation row, and that the exclusion removes 7 of 2883 ids and
reports them. What it found was three things I had asserted rather than run.

1. **The scope claim was false** (blocking). Corrected above and filed as
   **#813**. I quoted a code excerpt under the words "measured, not assumed".
2. **The safety-net justification was wrong.** I said the dangling census
   independently catches a real donor reference among the excluded ids; it
   tests `id not in ours` and the excluded ids are *in* `ours`, so for exactly
   those 7 neither check can fire. The correct, narrower reason — the lane
   authors from a constructive tree, and the copied-tree lane is gated earlier
   by the unfiltered raise — now stands in the code comment, the reported
   `own_id_space_collisions.note` and the section above.
3. **A latent crash I introduced.** With `foreign_ids` empty, `scan_donor` fell
   back to `{"hits": 0}` with no `distinct`/`examples`, so any caller reading
   `examples` got a `KeyError`. The old `if donor_ids` guard could only reach
   that with an empty donor universe; the new split makes it reachable whenever
   the donor's ids are a subset of ours. Fixed to the full shape, with a test
   that dies to the revert.

Also corrected: "vacuous" → **fails**. The old test goes red (`assert (0 >= 1)`),
it does not pass while testing nothing — the distinction matters, because only
the second shape is dangerous, and calling a red test vacuous overstates the
problem I found.

## Review round 2 — two more wrong claims of mine, and one stale blocker

Round 2 verified round 1's three fixes and did not re-litigate settled ground:
it confirmed #813 is real and accurately describes the defect, checked in the
code that the replacement justification is **true** rather than merely
different (`famdoc_adoc.py:1782` branches on `container_is_family(donor)`;
`:1792-1794` is the project-donor branch using `constructive_family_host_tree`;
the family-donor branch's unfiltered raise at `:1311-1312` fires before
`emit_family_rfa_v2` writes, and the one post-emit product caller,
`standalone.py:1002`, only ever sees a file that already cleared it), and
re-measured the new mutant itself (baseline **19 passed**; revert → **1 failed,
18 passed** with `KeyError: 'distinct'`; restore → **19 passed**).

**Its blocking finding was stale, and I checked rather than complied.** It
reported the PR body still carrying all three round-1 false claims. The live
body (fetched at the same head) already carried every correction — `updated_at`
17:59:51, and the reviewer fetched early in its 281-second run. I had edited
the body immediately after spawning it. A race, not a defect; the blocker is
void. Worth recording precisely because the reflex under a `🛑` is to comply,
and complying here would have meant "fixing" text that was already right.

**Two nits were real, and both were mine:**

1. **The skip-delta explanation was partly false** — and my replacement for it
   was wrong too; see round 3 below. `experiments/` is not git-ignored (1448
   tracked files). I generalised from "the tests skip without it" to "the
   directory is ignored" without running `git ls-files`.
2. **"Every product caller passes the document's own element ids" was untrue
   as worded.** `standalone.py:1002` and `render_probes.py:776` pass no
   `our_ids` and take the file-derived default. Harmless — a default cannot be
   a superset of itself — but the sentence claimed more than it checked.

Nit 2 has a second edge the review did not name, and it belongs in the record
because it is a **new** failure mode rather than a repeat: that sentence came
from **round 1's** grep, which reported that every caller passes the document's
own ids. I put it in the PR body as established fact without running the grep
myself. Having been caught eight times asserting my own unverified claims, I
then propagated someone else's. A subagent's measurement is evidence of the
same kind as my own — it needs re-running before it is quoted, not because the
reviewer is unreliable, but because "an agent told me" is not a measurement.

## Review round 3 — I replaced a wrong causal story with another one

Round 3 confirmed both round-2 fixes and read the PR body **fresh as its last
action** (18:19:29Z against `updated_at` 18:16:07Z, head matching), so there was
no repeat of round 2's stale read. It re-measured A1's counts (1448 / 1723 /
`.gitignore:17-22` / `out/` ignored whole at `:42` / `samples`,`vendor`,
`extracted` ignored at `:11-13`), verified the `our_ids=` docstring against a
grep of every `provenance_scan_v2(` call site, and confirmed the source and its
`plugin/lib` mirror are byte-identical.

Its finding that mattered: **my corrected skip-delta explanation was itself
unsupported.** I had said the delta was git-ignored artifacts inside
`experiments/`. There are **zero** such files in this checkout, so that cannot
produce any delta at all — not "unproven", *impossible*. The measured cause is
`RVT_SKIP_LARGE=1`, which the sandbox sets and my local runs did not; it moves
seven tests on its own. Corrected above, with the one remaining unattributed
test named rather than absorbed.

This is the eleventh claim in this PR's lineage that did not survive
re-running, and its shape is new: the first ten were unverified claims. This
one was a **correction** — I was already on notice that the sentence was wrong,
rewrote it, and did not measure the rewrite either. Being caught is not the
same as having checked. The fix for the class is mechanical, not attitudinal:
a causal sentence about numbers needs the command that produced it printed
beside it, or it should say "unattributed".

Two presentation nits also fixed: `1723` is `1448` files **plus 275 directory
entries** (as printed it read as though an export carried more than the tree),
and the `WORKED_RVT` example was dropped — that file is absent from this
checkout too, so it could not have been part of any delta between the two runs.

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
  `test_provenance_scan_flags_a_genuine_donor_id` rebuilt so it exercises a
  genuinely foreign id (it goes red under the fix, it does not pass emptily).
* `tests/test_famdoc_scan_collision_807.py` — **new**, 6 tests: the premise,
  the collision is present, recorded-not-fatal, the same id fatal when not
  ours, nothing dropped silently, and (round 1) a donor universe entirely
  inside ours still reporting a whole scan shape.
* `tests/ci_shard.d/807-famdoc-scan.txt` — **new**, both files into the shard.
* `docs/inbox/famdoc-scan-fp.d/807-id-space-collision.md` — this fragment.
* `docs/inbox/generated-size-bound.md` — **repair only**, carried from #808's
  round-5 nit: three stranded lines duplicating the paragraph above them, with
  an orphaned `**` that garbled the rendering. No claim changed. Carried here
  rather than merged unreviewed into #808, because a head no reviewer has seen
  is exactly what the #302 merge gate exists to prevent.

**Gates**: 13-file gate set 406 passed / 45 skipped / 0 failed (this checkout;
a fresh export skips 6 more — see Evidence); mutation sweep 5/5 die, baseline
and restore both 19 passed; `sync_plugin --check` clean; portable paths ok.
Full suite **not** run.

**Shipped vs staged**: all shipped. No viewer batch — no claim about Autodesk's
reader is made or needed.
