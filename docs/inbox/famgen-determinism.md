# famgen-determinism — two builds of one spec are byte-identical

Charter: **#168**. The family path minted `uuid4` on every build and stamped
the PartAtom from the wall clock, so no two runs produced the same `.rfa`.

## Why this is not housekeeping

Provenance and certification both lean on sha256-pinned artifacts, so a file
that changes every run cannot be pinned in a manifest or cached (#124). But
the expensive consequence is **evidence discipline** (`CLAUDE.md` §4): every
experiment in this repo compares two builds, and *"otherwise byte-identical"*
is not a statement anyone can make about a file that is different every time.
#787 DONE 4 asks for exactly such a pair.

## What was actually non-deterministic

Measured by instrumenting `uuid.uuid4` and running the job — **not** by
grepping, because the issue's cited line numbers were five weeks stale and
named the wrong set (seven sites, three of them the *load* path, which never
executes for a family build):

| site | mints |
|---|---|
| `famgen.skeleton.new_family_document` | the document GUID |
| `genesis.skeleton.minimal_globals` ×2 | the episode and workset GUIDs |
| `famgen.skeleton.build_part_atom` | a **wall-clock** `<updated>` stamp |

The last one is the half the issue missed, and it is why "use uuid5" is not
the fix. Pinning every GUID and rebuilding still differed:

```
@0x05385  a: ...<updated>2026-09-14T01:19:43Z</updated>...
          b: ...<updated>2026-09-14T01:19:44Z</updated>...
```

Two builds one second apart. A test written to the issue's DONE as given
would have passed inside a single second and certified a lie.

## What was built

- `family_document_guid` / `family_episode_guid` / `family_workset_guid` —
  `uuid5` in our namespace via the existing `genesis.skeleton.our_guid` (the
  same derivation #9 used for the geo-site GUID), over the canonical document
  key: category, name, host, origin, id base, part type, work-plane flag, the
  datum/plane geometry, the view switch and the family GUID.
- `FamilyDoc.globals_models` derives the episode and workset GUIDs and
  **passes them down**, rather than changing `minimal_globals`' own defaults.
  Deliberate: that function is shared with the genesis compose path, whose
  output is the three **certified** bases (hard rule 4). Making the family
  path reproducible must not move a byte of genesis. A test pins that its
  default still mints its own.
- `stable_updated_stamp()` — honours `SOURCE_DATE_EPOCH` (the
  reproducible-builds convention, so a build system that already sets it gets
  a real date free), otherwise the fixed `1970-01-01T00:00:00Z`. Not a
  derived-looking date: that would be a false claim about when the file was
  made. A malformed value falls back rather than failing the build.
- `FamilyDoc.guid_source` (`derived` / `caller`) and an `emit.determinism`
  block in the report JSON. It names the **sources** rather than reducing to
  a bare flag, because `deterministic: true` on a file whose GUID the caller
  minted with `uuid4` is a claim we are in no position to make.

## The review found a collision the creation-time key could not avoid

`family_document_guid` runs inside `new_family_document` — **before** any
parameter, type, shared-parameter binding or solid exists. Two documents
identical at that moment and different afterwards therefore shared a GUID,
silently and stably, which this module's own docstring calls worse than the
`uuid4` it replaced. Measured by the review on the real CLI:

| build | shared params | sha256 | `document_guid` |
|---|---|---|---|
| no `--shared-params` | 0 | `adf39fb1…` | `edee5f1d-324e-5757-…` |
| with `--shared-params` | 11 bound | `1ba16929…` | `edee5f1d-324e-5757-…` |

Different files, same document GUID, same episode GUID, same
`unique_document_guid`. My parametrised test never varied anything added
after creation, so it could not have caught it.

**Folding `shared_params` into the key would have fixed the one case and
left the class.** Types, parameters and geometry are all added after
creation too. So the GUID is now *sealed from the content* at
`FamilyDoc.finalize` — the one choke point every delivery passes — keyed on
the delivered bytes of the save unit. Two documents that produce identical
content are the same document and correctly share a GUID; anything that
changes a byte changes it. A caller-supplied GUID is never resealed, and the
seal is idempotent because `finalize` is.

After the fix, on the same three builds:

| build | sha256 | `document_guid` |
|---|---|---|
| no `--shared-params` | `a160d2a4…` | `f3404ba0-065f-5d9b-…` |
| with `--shared-params` | `30bf86de…` | `ff26cddd-8b4a-58f6-…` |
| with `--shared-params`, again | `30bf86de…` | `ff26cddd-8b4a-58f6-…` |

Different specs differ; the same spec repeats.

## Evidence

Two CLI runs, **same filename in different directories**:

```
a160d2a4e5b21f0b…  r1/panel.rfa
a160d2a4e5b21f0b…  r2/panel.rfa
BYTE-IDENTICAL
```

Before: `490369135f0c…` vs `d80033669a35…`, first difference at byte 16477.
(The post-fix digest changed from the first draft of this record — `adf39fb1…`
— when the GUID became content-derived. Re-measured, not carried over.)

| check | result |
|---|---|
| same spec, two CLI runs | byte-identical |
| `--mains 600` vs `--mains 400` | different sha, different document GUID |
| document / episode / workset GUIDs | three distinct values, each a function of the spec |
| `validate` | VALID, 0 errors, 0 warnings |
| `provenance` | all 11 checks true, `identity_is_ours` true |
| `SOURCE_DATE_EPOCH=1700000000` | `<updated>2023-11-14T22:13:20Z</updated>` |

A second, smaller finding from the same review: the report's
`updated_stamp` line tested whether `SOURCE_DATE_EPOCH` was *set*, not
whether it *parsed*, so a malformed value fell back to the fixed stamp while
the report claimed the environment had supplied it. A false provenance line
in a report this repo treats as evidence. Both callers now ask one parse
(`stable_updated_stamp_with_source`), so they cannot drift.

Two properties of the seal, measured rather than assumed, because the first
draft of the code asserted one of them as fact and was wrong:

* **Non-circular.** The document GUID does not appear anywhere in the
  partition payloads the digest is taken over (searched as ASCII and
  UTF-16LE, hyphenated and not, both cases), and changing `document_guid`
  by hand leaves the digest bit-identical — `345589223db79945` before and
  after. So hashing the payloads is a genuine content digest and not a
  function of the value it produces.
* **Moot as well as false.** The review added a fact I had not checked:
  `FamilyDoc.add()` already raises once `finalized` is set, so no
  re-entrant mutation is reachable at all — the ordering the invented
  comment justified could not have mattered either way.
* **Entered once.** `_guid_sealed` is set before the digest as a cheap
  termination guard, and an earlier draft of that line said it was set
  first *"because the digest calls back"*. Instrumented: `_seal_document_
  guid` is entered exactly **once** per `finalize`. Nothing calls back. The
  claim was invented, and it is the second invented comment I wrote in this
  session — the other was *"Nothing is lost by refusing"* in the spec-sheet
  reader (#789 round 3), also caught by measurement rather than by me.
  A wrong comment outlives the code it describes, because the next reader
  believes it instead of re-testing.

**And one of my own tests for the stamp nit was vacuous** — the third in this
session. It asserted on the new helper rather than on `_determinism_report`,
the consumer that actually had the bug, and passed with the report's line
reverted. Testing the code a fix added instead of the defect it fixes is no
test at all; rewritten to assert through the report.

The seal costs one payload build. The first version called
`partition_payloads()` once for the key list and again per key — four
rebuilds, 0.0369 s against 0.0105 s for a single build. Built once now:
0.0096 s, i.e. the digest itself is free.

A third finding from the same review, and the same family as the other two:
the probe in `test_two_documents_that_differ_only_AFTER_creation_still_differ`
read `SK.PARAM_TYPE_LENGTH if hasattr(SK, "PARAM_TYPE_LENGTH") else 1`.
`PARAM_TYPE_LENGTH` exists **nowhere in this repo**, so the branch was always
false and the probe passed the integer `1` where a spec-type id belongs. The
test still killed its mutant, so it was not vacuous — but a defensive
`hasattr` around a name I never looked up is a guess wearing a seatbelt. The
real constant is `SK.SPEC_LENGTH`, and it is now spelled out.

Gates: `tests/test_famgen_determinism_168.py` **27 passed**;
`test_famgen_factory` + `test_famgen_loader` + `test_geo_site_determinism` +
`test_hostsym_product` + `test_bare_family_validate` **127 passed, 18
skipped**.

## The probe's own bug, recorded because the lesson is the point

The first version of the pin-uuid4 experiment wrote `pin_a.rfa` and
`pin_b.rfa`. The output filename legitimately appears in the file (last-save
path, PartAtom title), so the probe had **two** variables and reported four
differing bytes where two were its own. It was only usable because the diff
was small enough to read by eye. Every test here writes the same filename in
different directories.

## Findings not fixed here

- **The load path is still non-deterministic.** `famgen/loader.py` and
  `famload.py` mint `uuid4` for `fam_doc_guid` and `session_guid_hex`, and
  `factory.py` for a host document GUID. None execute for a family *build*,
  which is what #168 asks about, so they are out of scope — but "two
  identical loads produce identical projects" is a real and separate claim
  nobody has made yet. Worth its own issue.
- **`birthright.py` mints `uuid4`** (its docstring says so deliberately).
  Not on this path; not touched.
- **No desktop or viewer round.** Nothing here is evidence about Revit's
  reader (hard rule 4) — in particular whether a PartAtom `<updated>` of
  `1970-01-01T00:00:00Z` is acceptable to it. It is honest ("no time
  recorded") and consistent with the 0-epoch default already shipping in
  `minimal_increment_table`, and any caller with a real date can pass one,
  but that is reasoning, not a verdict.

## BRANCH STATE

- Branch: `cam/168-famgen-determinism`, cut from `main` @ `50a89ef`.
- Files written: `src/rvt/famgen/skeleton.py` (the three derivations, the
  stamp, `guid_source`), `src/rvt/famgen/famdoc_adoc.py` (the report block),
  `tests/test_famgen_determinism_168.py`,
  `tests/ci_shard.d/168-famgen-determinism.txt`, this record, and the
  `plugin/lib/` mirrors (generated by `sync_plugin.py`).
- Shipped: the fix, gated as above.
- Staged, not shipped: nothing.
- Not done: the three findings above.
