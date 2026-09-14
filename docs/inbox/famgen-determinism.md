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

## Evidence

Two CLI runs, **same filename in different directories**:

```
adf39fb159ff0aaf86c37f676f42ac8cfab2a6e279310540397389607e664215  r1/panel.rfa
adf39fb159ff0aaf86c37f676f42ac8cfab2a6e279310540397389607e664215  r2/panel.rfa
BYTE-IDENTICAL
```

Before: `490369135f0c…` vs `d80033669a35…`, first difference at byte 16477.

| check | result |
|---|---|
| same spec, two CLI runs | byte-identical |
| `--mains 600` vs `--mains 400` | different sha, different document GUID |
| document / episode / workset GUIDs | three distinct values, each a function of the spec |
| `validate` | VALID, 0 errors, 0 warnings |
| `provenance` | all 11 checks true, `identity_is_ours` true |
| `SOURCE_DATE_EPOCH=1700000000` | `<updated>2023-11-14T22:13:20Z</updated>` |

Gates: `tests/test_famgen_determinism_168.py` **21 passed**;
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
