# 794-load-path — two identical family LOADS produce byte-identical projects

PR fragment for **#794**, the load half of #168. `Refs #168`.

## Why the load half is the one users meet

#168 made the family **build** reproducible. The load path was left alone on
purpose — none of it executes for a build — and it still minted `uuid4`. But
`add_to_project` and the whole `rfa → rvt` lane come through here, so this is
the half a user hits, and the consequence is #168's own: a `.rvt` that changes
on every run cannot be pinned in a manifest, cached, or **diffed in a
single-variable round**. #787 DONE 4 wants a probe pair that is "otherwise
byte-identical"; if that pair is produced by loading a family into a host, it
was not available.

## What was actually non-deterministic

Instrumented `uuid.uuid4` with a stack-walking spy and ran each lane, rather
than grepping — which is how #168's own issue came to name the wrong lines, and
how this issue's table came to name the wrong set. A grep finds text; a stack
finds what ran.

| site | reached by | in this PR |
|---|---|---|
| `famload._plan_family` | `famspec → rvt` | **fixed** |
| `convert.rfa_load.BornRfaDoc.__init__` | ANY `.rfa` path → rvt | **fixed** |
| `famgen.loader.plan_load` | extract's own re-load check | **fixed** |
| `genesis.skeleton.minimal_globals` ×2 | the EXTRACT lane (`rvt → rfa`) | out of territory — see below |
| `factory.author_embedded_adocument` host-GUID fallback | nothing | dead — see below |

Two corrections to the issue's own table, both material:

- **`convert/rfa_load.py` was not in it at all**, and it is the site a user
  reaches by handing us a `.rfa` — both the standalone-born and the extracted
  lanes go through it, not through `famgen/loader.py` as the table implies.
- **`factory.py`'s host-document GUID fallback was in it and is dead.** famload
  passes `document_guid=plan.guid` explicitly, and since #793 a finalized
  document always carries a sealed GUID, so the `or str(uuid.uuid4())` arm is
  unreachable from any product lane. It is left alone rather than "fixed",
  because changing an unreachable line proves nothing and the next reader
  would have to re-derive why it was touched.

## The derivation — and the correction CI forced

`famload.load_doc_guid(family_guid)` — `our_guid` over the **family's
content-document GUID** (itself content-derived since #793). That is it.

**This is a deviation from #794 DONE 1, which asked for a key over the host as
well** ("its sha256 or its own document GUID"), and the first version of this
change did exactly that. It passed every stream-local gate I ran. Then the
sandboxed CI failed one test 600 lines away:

```
FAILED tests/test_famload_batch.py::test_chain_and_batch_are_logically_identical
At index 1 diff:
  chain: fam_doc_guid a3d9e057-e070-5fae-af0e-f125b4eec296
  batch: fam_doc_guid 6e0c4e8f-7b88-5b11-986a-a8ab5e1b2d9c
  (guid, host_family_id, symbol_id and all 21 twin ids identical on both sides)
```

That test encodes an invariant **older than the issue**: loading two families
ONE AT A TIME — each into the previous output — must produce the same plans as
loading both in ONE batch. In the chain the second family's host is the
intermediate file; in the batch it is the original base. Any key over host
bytes therefore *must* differ between the two, and the invariant is the one
that is right.

It is also the better semantics, which is the part worth keeping in mind next
time: `m_famDocGUID` identifies the family **document**, and the same family
loaded into two projects genuinely *is* the same family document — that
identity is how Revit recognises a family across a reload, and how a shared
family library works at all. The host never belonged in the key. The issue's
DONE was written by a session that had not read that test; the test won, and
should have.

DONE 2 survives the correction intact, and is worth restating because it was
the argument *for* the host term: two DIFFERENT families in one host get
different GUIDs (their content GUIDs differ), and the SAME family loaded twice
gets the same one. The family half was always doing that work alone.

The target release is not a term either: a family's content GUID already
covers the release-specific content it was built with.

Because the host digest is now in no key, `HostContext.digest` and the
`host_digest` helper were **removed** rather than left as a field nothing
reads — that is the same defect #800 exists to fix, and shipping a fresh
instance of it in the same week would be hard to defend.

**`convert/rfa_load.py` needed a different key, and its old comment explains
why.** It read: *"a standalone file's unit 0 carries no separator GUID and the
same .rfa may be loaded twice into one host: mint the content GUID."* That
reason is real — two copies must not claim one identity — and minting was just
the blunt way to honour it. The key is now the `.rfa`'s own bytes **plus the
id block it is rebased into** (`start_id`): two copies in one host cannot share
an id block, so `start_id` already separates them. The distinctness survives
without costing reproducibility, using the thing that distinguishes the copies
rather than throwing randomness at it.

## Evidence

Before, on `main` at `b645cc5` (this branch's actual base; an earlier draft
said `5ddcc16`, which was the base before #798 merged), measured the way
#794 DONE 3 specifies —
**same output filename in different directories**, because the output path is
written into the file and that is how #168's first probe produced a false
reading:

```
eaton_prl1x_225a_42sp_208y_120_loaded.rvt
  famspec -> rvt      run a 14134c3e56caf8ff…   run b 1eb4b50d89d6fa36…   DIFFER
  .rfa path -> rvt    run a cb1e1189a9a676d9…   run b 14952e44cbca6b15…   DIFFER
```

After (re-measured once the host term came out of the key — the first
after-values, `a1c71ba2…` and `6f873ce2…`, were from the version CI rejected,
and quoting them here would be quoting a build that no longer exists):

```
  famspec -> rvt      061245fe04a83076…  twice   IDENTICAL
  .rfa path -> rvt    3905b0d44f5a94c7…  twice   IDENTICAL
```

The mint census across the product lanes, same instrument:

```
famspec->rvt   ok=True  mints: NONE
famspec->rfa   ok=True  mints: NONE
prompt->rfa    ok=True  mints: NONE
rfa-path->rvt  ok=True  mints: NONE
```

DONE 2's two properties, measured on real plans against the pinned base rather
than on the helper alone:

```
panelboard  fam_doc 0300b58f-01da-51c1-8c8a-72f771582d38
transformer fam_doc c56e8dca-b141-53a5-bcc7-c7e9dd317832
panelboard  again   0300b58f-01da-51c1-8c8a-72f771582d38
distinct across families: True   same family twice: True
```

DONE 4: the loaded project validates with **0 errors** (one pre-existing
warning, the known Extensible-Storage decoder gap). Its provenance identity
findings — `unique_document_guid` and `central_episode_guid` inherited from the
baseline — are **unchanged from main**, verified by running the same probe on a
stashed tree. They are #19's territory (the genesis identity scrub), not
something this PR introduced or resolved.

Every fix dies to its own mutant:

| mutant | dies in |
|---|---|
| `famload` mints again | 4 tests (both lane cases, both census cases) |
| `rfa_load` mints again | 2 tests (the `.rfa` path lane and its census) |
| drop `start_id` from the born key | `test_the_standalone_born_guid_separates_two_copies_in_one_host` |
| re-introduce a host term | `test_the_HOST_is_NOT_in_the_key_and_that_is_load_bearing` |

That the first mutant also kills the `.rfa`-path cases is correct coupling, not
a leak: that lane's document is loaded *through* famload.

## What is NOT fixed, and is pinned so it cannot drift

**The extract lane (`rvt → rfa`) is still non-deterministic.** It reaches
`genesis.skeleton.minimal_globals`, which #794 puts out of territory **by
name**: it is shared with the genesis compose path, whose output is the three
certified bases (hard rule 4), and #168 has a test pinning its defaults. So
rather than leave that as prose, `test_the_EXTRACT_lane_is_still_nondeterministic_and_that_is_on_purpose`
asserts the current boundary — if someone later makes it derived, that test
fails and the decision gets re-made deliberately instead of drifting.

`famgen/birthright.py` mints `uuid4` by its own docstring and was **not**
reached by any lane probed here, which is the check #794's notes asked for
rather than an assumption either way.

## The process lesson, which cost a CI round

My stream-local run covered `test_famload`, `test_rfa_load`, `test_convert`,
`test_router_load_release`, `test_famgen_determinism_168`, `test_router` and
`test_plugin_sync` — and not `test_famload_batch`, which is the one that
failed. Picking test files by *what I had edited* misses the files that assert
**relationships between** the things I edited.

The rule that would have caught it, used for the re-run and worth keeping:
before pushing a change to a shared module, run every test file that names
that module —

```
.venv/bin/python -m pytest $(grep -ln "famload\|famgen.loader\|rfa_load" tests/*.py) -q
```

That is 32 files and 2.5 minutes here, against a 7.5-minute CI round plus a
review round. It also surfaced that `tests/test_catchain.py` is red on `main`
already (2 failures, verified against a stashed tree) — pre-existing, outside
the CI shard, and not this PR's.

## A claim in an earlier draft of this record that was simply wrong

It said *"`famgen.loader.plan_load` is fixed by the same derivation but no
route exercises it… its tests here are helper-level."* **False**, and #801's
reviewer caught it. `plan_load` is reached by the main authoring lane:

```
frontdoor/build.py:590 stage_load_batched
  -> famgen/loader.py load_families_into_project
    -> _load_families_into_project -> _author_load -> plan_load
```

Instrumented on `prompt → rvt` ("an electrical room with 6 panels"):

```
plan_load calls: 6
via: stage_load_batched | load_families_into_project | _load_families_into_project
mints: NONE
```

So that site is route-reaching *and* CI-covered — the reviewer's own mutant,
re-introducing a host term into `loader.py`, killed
`test_famload_batch.py::test_chain_and_batch_are_logically_identical`. The
change there is better covered than this record claimed, not worse. I had
written the sentence from reading call sites instead of running the lane,
which is the same mistake this record spends two sections warning about.

**And a correction to my own correction, caught by the round-2 reviewer.** An
earlier draft of this section claimed `prompt → rvt` was *already*
byte-deterministic on `main` and that this PR left it untouched — "the
regression control for the whole change". **That was false in both halves,
and the way it went wrong is worth more than the claim was.**

I measured `main` by running `git stash`, taking the numbers, then
`git stash pop`. My tree was **clean** at that moment — everything was
committed — so `git stash` created nothing, the working tree still held my
branch, and I measured *my own branch twice* and labelled one of them `main`.
(The `pop` then picked up a *different* session's stash that was sitting in
this shared clone, which is how I noticed at all.) Re-measured properly, with
`git archive` into two separate directories and `PYTHONPATH` pointed at each
export's own `src/` — verified by printing `rvt.__file__` on both sides:

```
main (b645cc5)   81e571efff2c9bb4  4091031d0015ae0b   DIFFER
head (8ec8fc1)   696a5d1cc523b453  696a5d1cc523b453   IDENTICAL
```

And the mint census on that lane, same instrument:

```
main   prompt->rvt   12 mints, all at loader.py plan_load  (6 calls x 2)
head   prompt->rvt    0 mints
```

So: **`prompt → rvt` was NOT deterministic on `main`, and this PR fixes it.**
That is a third lane fixed, not a control — the main authoring lane, the one
most users actually run. The follow-on sentence in that draft ("the minted
GUIDs on that lane never reached the delivered bytes, which is why nobody had
noticed them") was false too: they reached the bytes, which is exactly why the
hashes differ on `main`.

| lane | `main` (b645cc5) | head (8ec8fc1) |
|---|---|---|
| `prompt → rvt` | `81e571ef…` / `4091031d…` **DIFFER** | `696a5d1c…` twice **IDENTICAL** |
| `famspec → rvt` | DIFFER | twice **IDENTICAL** |
| `.rfa path → rvt` | DIFFER | twice **IDENTICAL** |

The **property** (DIFFER → IDENTICAL) is what this PR claims and what the
tests assert. The absolute sha256 values are environment-dependent — the
round-2 reviewer got different absolute numbers from a clean sandbox export
while reproducing the property exactly — so they are recorded as what this
machine produced, never as constants anything should pin.

**Never use `git stash` to measure a "before" state**, in this clone above all:
it is shared with other sessions, and on a clean tree it silently measures the
present. Export both revisions with `git archive` and point `PYTHONPATH` at
each, then *prove which engine ran* by printing `rvt.__file__`. That last step
is what turns a measurement into evidence, and it is the step I skipped.

## Open questions

- The born-`.rfa` key includes `start_id`, which makes that document's GUID
  host-dependent, while `famload`'s key deliberately is not. Both are argued
  in their docstrings and the asymmetry is real rather than accidental — the
  rebased elements genuinely differ between two copies — but it is the kind
  of thing worth re-reading if a third load lane ever appears.
- No measurement on a genuinely large foreign host. Everything here is the
  568 KB pinned base.

## BRANCH STATE

Branch `cam/794-load-determinism`, `Closes #794`, `Refs #168`.

Files written:

- `src/rvt/famload.py` — `load_doc_guid`, `load_session_guid_hex`, and the
  derived `LoadPlan` (no `host_digest`, no `HostContext.digest`: both were
  written and then removed within this PR when the host term came out of the
  key — see the correction above)
- `src/rvt/famgen/loader.py` — the same derivation at its own `plan_load`
- `src/rvt/convert/rfa_load.py` — `RfaSource.content_digest` /
  `document_guid_at`, and `BornRfaDoc` taking the derived GUID
- `tests/test_famload_determinism_794.py` (new), `tests/ci_shard.d/794-load-determinism.txt`

Gates: on the PR's CI comment, pinned to the head SHA.

Staged, not shipped: nothing.
