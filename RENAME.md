# RENAME — the tekton rename plan (old working name / `rvt` → tekton)

> **Status as of 2026-08-09 — partly executed, policy still in force, the
> rest is a historical runbook.** Since this plan was written (2026-08-04)
> the *display-name* half has happened: prose, README titles, the repository
> / working-directory name, the plugin manifest and the genesis
> project-information strings all say **tekton** now, and Step 0 (no baked
> absolute paths in `src/`) is done — which is why several "now → after"
> cells in §2-B and the §4 inventory read identically today (the old name was
> swept out of this file along with everything else). What has **not** been
> done, and still waits on counsel exactly as §1 says: the author string
> (`PRODUCT_AUTHOR_PLACEHOLDER = "rvt-writer"`, counsel C1 — leave it alone,
> `CLAUDE.md` §1 rule 6), the Python package name `rvt` (§2-D, default: keep),
> the component names in §2-C, and trademark clearance for "tekton" itself.
> **The standing rule is unchanged and is cited by `docs/PROGRAM.md` ("Not
> goals"): no piecemeal renaming — whatever remains is one scripted sweep
> after clearance.** The counts in §4 are a 2026-08-04 snapshot from the
> owner's machine (hence the absolute paths in its commands); re-measure
> before any sweep rather than trusting them.

Status: **PLAN ONLY. The rename has NOT been performed and MUST NOT be
performed until the pre-requisite in §1 is met.** This document is the
runbook for a single scripted sweep, plus the dry-run inventory of every
string that would change (§4), so the sweep can be executed once, reviewed
once, and never dribbled out across sessions.

Naming convention until the sweep runs (from the user, 2026-08-04): the
product's DISPLAY name is **tekton** — use it in prose, docs, skill
descriptions and READMEs — but code paths stay `tekton` / `rvt` (the
directory, the Python package, the plugin manifest `name`). Do not rename
these piecemeal; a half-renamed tree is the failure mode this plan exists
to prevent.

---

## 1. Pre-requisite (blocking): trademark clearance for "tekton"

**Do not run the sweep until counsel returns a clearance opinion on the
name "tekton".** This is a counsel item (see `docs/product/COUNSEL-BRIEF.md`
§C6), and it sits on top of the existing recommendation in
`docs/product/content-strategy.md` §5.3: the current name "tekton"
incorporates Autodesk's registered mark REVIT and is "the highest-visibility
exposure and the first cease-and-desist" — hence a rename before any public
launch to a non-derivative brand, with "for use with Autodesk® Revit®" kept
as an attributed *referential* tagline.

The clearance ask has three parts, and the sweep waits on all three:

1. **Knock-out search on "tekton"** in the relevant classes (software for
   architecture/engineering/construction; downloadable and SaaS). "Tekton"
   (Greek: builder/carpenter; the root of "architect") is descriptive-
   adjacent and demonstrably in use elsewhere in AEC-tech, so a real
   likelihood-of-confusion search — not just an exact-match TESS query —
   is the deliverable.
2. **The "RVT" question** (feeds the §3 package decision): is `RVT` /
   `.rvt` itself asserted by Autodesk as a mark, or only a file-extension
   identifier? A Python package named `rvt` is defensible as
   format-descriptive (§3, option A) only if the answer is "extension, not
   mark." Get this in writing.
3. **Approved referential language** for the surviving product-facing
   strings: how we may say "opens in Autodesk Revit" / ".rvt files" with
   correct attribution, so the sweep writes the compliant form once.

If clearance fails, the sweep is unchanged in mechanism — only the target
string differs. That is exactly why this is a scripted sweep with the new
name as a parameter (§5), not a hand edit.

---

## 2. What CHANGES — by category

Ordered by risk. Category A strings persist inside files we DELIVER, so
they are the ones that matter to counsel; the rest are internal hygiene.

### A. Authored-into-deliverable strings — HIGHEST PRIORITY

These identifiers are written by the engine INTO the `.rvt` files, family
files and schedule outputs a customer receives. A rename that misses one
ships the old name in customer deliverables. Every entry is a specific
constant to rewrite, and one of them (the author string) is not ours to
choose — it is counsel C1.

| Constant | File | Lands in | Rename to |
|---|---|---|---|
| `PRODUCT_AUTHOR_PLACEHOLDER = "rvt-writer"` | `src/rvt/identity.py` | `BasicFileInfo` author / client-app of every emitted `.rvt` | **counsel C1 decides the exact wording** — a placeholder by design; the sweep parameterizes it, does not pick it |
| `"client_name": "tekton genesis"`, `"organization_name": "tekton"` | `src/rvt/genesis/house_standard.py` | project-information strings in genesis-built files | `tekton …` |
| builds default `"tekton genesis (Revit 2026 / 2662)"` | `src/rvt/adocument.py` (~line 805) | `Global/Latest` ADocument build list of genesis files | `tekton genesis (…)` |
| `DISCLAIMER` "tekton's calc engine" + `CalcBasis` strings | `src/rvt/electrical/render.py` | printed on generated panelboard schedules (HTML/CSV) | `tekton …` |
| JSON `kind: "tekton.electrical-job"` / `.electrical-summary` | `src/rvt/electrical/job.py` | electrical job/summary JSON handed to customers | `tekton.electrical-job` etc. — a schema-version bump, so bump the reader too |

Measured occurrences: `rvt-writer` 370 (140 files; ~29 in `src/`, rest
docs/experiment records); `tekton` inside `src/` 21 (of which 9 are the
absolute-path constants in §D, 12 are the strings above and their kin).

### B. Product identity — mechanical, must change

| Item | Now | After |
|---|---|---|
| repo / working directory | `~/dev/things/tekton/` | `~/dev/things/tekton/` |
| quarantine sibling directory | `~/dev/things/tekton-quarantine/` | `~/dev/things/tekton-quarantine/` (referenced by `docs/legal/provenance-memo.md` and the QUARANTINED note — update both) |
| plugin manifest `name` / `displayName` | `plugin/.claude-plugin/plugin.json` → `"tekton"` | `"tekton"` |
| local marketplace | `plugin/.claude-plugin/marketplace.json` (`name`, `owner`, plugin `name`, install instruction `tekton@tekton`) | `tekton` throughout |
| zip artifacts | `tekton-plugin.zip`, `tekton-share.zip` (built by `tools/sync_plugin.py`, constant `ZIP`) | `tekton.zip`, `tekton-share.zip` |
| root README title | `rvt-recon` (15 occurrences, 4 files) | `tekton` |
| prose "tekton" | 67 occurrences across 34 `.md` docs | `tekton` |

### C. Component names embedding revit / rvt — DECISION, not mechanical

Each of these is a *name a user sees* that embeds either the REVIT mark
or `rvt`. They are referential in intent ("the skill that bridges to
Revit"), which is the defensible posture — but that is a counsel judgment,
so the sweep treats them as switches, defaulting to KEEP until counsel
rules on referential component names.

| Component | Now | Options |
|---|---|---|
| IFC skill | `skills/tekton-ifc/`, `plugin/skills/tekton-ifc/` (415 occurrences, 138 files) | keep (referential: "bridge to Revit") · or `tekton-bridge` |
| native skill | `skills/tekton-native/` (52 occurrences, 18 files) | keep (format-descriptive) · or `tekton-native` |
| slash commands | `/tekton-harden`, `/tekton-job`, `/tekton-validate` (`plugin/commands/`) | keep · or `/tekton-*` |
| agent template | `plugin/agents/tekton-author-agent.md` | keep · or `tekton-author-agent` |
| tool scripts | `tools/rvt_job.py`, `rvt_edit.py`, `rvt_validate.py`, `rvt_inspect.py`, `rvt_selfcheck.py`, `rvt_reduce.py` (456 refs) | keep — these name the FORMAT they operate on (§3-D); `frontdoor.py` supersedes `rvt_job.py` regardless |

### D. Python package `rvt` → ? — THE OPEN QUESTION

This is the largest single change and the least clear-cut. Two options,
to be settled by the §1 "RVT" answer:

- **Option A — keep `rvt` as the package name.** Argument: the package
  handles the `.rvt` FORMAT, and format-named libraries are the norm
  (`python-docx` for `.docx`, `openpyxl` for `.xlsx`, `pypdf`); the mark is
  REVIT, not the extension. Cost: none. Risk: rests entirely on §1 item 2 —
  counsel confirming `.rvt`/RVT is an extension identifier and not itself an
  asserted mark.
- **Option B — rename the package to `tekton`.** Full brand alignment,
  zero dependence on the RVT question. Cost: the entire import graph —
  measured below.

Blast radius of Option B (dry run, §4): `from rvt import` / `from rvt.`
imports 741 across 158 files; dotted `rvt.<module>` references 1,913 in
`.py` + 892 in `.md`; `src/rvt` path references 589; `plugin/lib/src/rvt`
16; the `tools/sync_plugin.py` mappings (`src/rvt/** → plugin/lib/src/rvt/**`);
both `pyproject.toml` files (`name = "rvt"`, `packages.find where=src`,
console scripts `rvtinspect` / `rvt-roundtrip`); `plugin/lib/src/rvt.egg-info/`
(regenerated, not edited). It is mechanical — every hit is a
word-boundary-safe token — which is exactly why it is one script, run once.

**Recommendation:** decide from counsel's §1.2 answer; default to Option A
(keep `rvt`) if RVT is confirmed extension-only, because Option B buys
brand purity at the price of 2,800+ edits with no functional gain. The
sweep script takes `--package-name` so either answer is one flag.

---

## 3. What STAYS — file-format identifiers that genuinely ARE "rvt"

The rename does not, and must not, touch these. They are true statements
about the file format we read and write, not our product name:

- **File extensions:** `.rvt`, `.rfa`, `.rte`, `.rft` (6,635 / 1,210 / 29
  measured references). The format is called `.rvt`; every filename, glob,
  test fixture and doc example keeps its extension.
- **Format-descriptive API names:** `open_rvt()`, `RvtDocument`, `write_cfb`
  (479 refs for the first two) — they name the INPUT FORMAT, which does not
  change when the product does. (They move with the package only under
  Option B, and even then keep their names — `tekton.open_rvt` opens a
  `.rvt`.)
- **Nominative prose references to Autodesk's product:** "opens in Autodesk
  Revit," "the Revit `.rvt` format," "the Autodesk Viewer" (2,192 mentions
  of "Revit" in `.md`). These are the referential use Autodesk's own
  guidelines permit; the sweep does not remove them — it ADDS attribution
  where a doc is customer-facing ("Autodesk®", "Revit®", per counsel's
  approved language, §1 item 3).
- **The tagging contract / IFC identifiers:** `PanelName`, `Voltage`,
  `IfcElectricDistributionBoard`, etc. — third-party (buildingSMART / the
  user's own contract) identifiers, unrelated to our name.
- **Test names describing format behaviour** (`test_roundtrip.py`,
  `test_ecc.py`, …) — they describe the format under test.

---

## 4. Dry-run inventory (reproducible; run `bash` block to refresh)

Counts taken 2026-08-04 over the working tree, excluding `.venv/`,
`vendor/`, `samples/`, `extracted/`, `__pycache__/`, `node_modules/`,
`.git/`, `.pytest_cache/`, `build/`, `scratch/` and binary files. The
exact counting commands are reproduced below and preserved (with the
per-directory breakdown script) in `docs/inbox/docs-spine.md`; rerun them
before the sweep — the tree moves under active development and these
numbers will drift.

```
===== A. PRODUCT NAME 'tekton' (must change) =====
'tekton' literal (any case)                       occurrences=975   files=300
    breakdown: docs/ 220, experiments/ 567, plugin/ 83, usecases/ 25,
               src/ 21, tests/ 15, skills/ 18, root files 10, tools/ 7, spec/ 5
'tekton' in .md docs                              occurrences=67    files=34
'tekton' in .py source                            occurrences=95    files=64
'tekton' in .json (manifests/specs/records)      occurrences=771   files=179
'rvt-writer' identity string (identity.py)           occurrences=370   files=140
'rvt-recon' (README title)                           occurrences=15    files=4

===== B. PYTHON PACKAGE 'rvt' (decision: rename or keep) =====
'from rvt import' / 'from rvt.' imports              occurrences=741   files=158
    breakdown: tests/ 285, tools/ 262, experiments/ 112, plugin/ 73, src/ 29, docs/ 30
'import rvt' statements                              occurrences=2     files=1
'rvt.<module>' dotted references in .py              occurrences=1913  files=255
'rvt.<module>' dotted references in .md docs         occurrences=892   files=123
'src/rvt' path references                            occurrences=589   files=188
'lib/src/rvt' plugin path references                 occurrences=16    files=12
'PYTHONPATH=src' convention                          occurrences=3     files=3

===== C. COMPONENT NAMES with revit/rvt (decision) =====
skill name 'tekton-ifc'                            occurrences=415   files=138
skill name 'tekton-native'                              occurrences=52    files=18
slash commands '/revit-'                             occurrences=18    files=4
agent 'tekton-author-agent'                             occurrences=5     files=3
tool script names 'rvt_(job|edit|validate|…)'        occurrences=456   files=146
'spec_to_rvt' / 'ifc_to_spec' pipeline names         occurrences=152   files=47

===== D. FORMAT IDENTIFIERS (STAY) =====
'.rvt' file-extension references                     occurrences=6635  files=753
'.rfa' file-extension references                     occurrences=1210  files=152
'.rte'/'.rft' extension references                   occurrences=29    files=11
format API 'open_rvt' / 'RvtDocument'                occurrences=479   files=127
prose 'Revit' product mentions (in .md)              occurrences=2192  files=193
```

**The baked-absolute-path finding (important — read before running the
sweep).** 794 of the "tekton" hits are the absolute path
`/Users/ck/dev/things/tekton/…` baked into generated artifacts:
`experiments/` 562 (job manifests, probe JSONs, validation records),
`docs/` 191 (evidence in stream records), and — the one that is a real
bug — **9 hard-coded `ROOT = "/Users/ck/dev/things/tekton"` constants in
the engine itself**: `src/rvt/{schema_a, encode, strings_scan, adocument,
global_latest, objects, schema, estorage}.py` and `src/rvt/famgen/geometry.py`.
Those nine make the *corpus-bound* loaders non-portable independent of any
rename (already the documented `Document.load(project)` caveat in the
tekton-native skill). **Fix them to `Path(__file__)`-relative resolution as
Step 0 of the sweep** — it is a prerequisite for the directory rename not
to silently break the developer loaders, and it is worth doing even if the
rename never happens. The 753 baked paths inside `experiments/`/`docs/`
records are historical evidence, not code: the sweep rewrites them by plain
string substitution for consistency, but nothing executes them, and the
certification ledger (`docs/coverage/viewer-certified.json`) uses REPO-
RELATIVE paths already and survives the move untouched.

Reproduce the inventory (the exact commands behind the table; also
preserved with per-directory breakdowns in `docs/inbox/docs-spine.md`):

```bash
cd /Users/ck/dev/things/tekton
EXCL="--exclude-dir=.venv --exclude-dir=vendor --exclude-dir=samples \
      --exclude-dir=extracted --exclude-dir=__pycache__ --exclude-dir=node_modules \
      --exclude-dir=.git --exclude-dir=.pytest_cache --exclude-dir=build --exclude-dir=scratch"
cnt() { grep -rEo $EXCL --binary-files=without-match $3 -- "$2" . | wc -l; }
cnt A "tekton" -i                    # product name
cnt B "\brvt\.[a-z_]+" --include=*.py   # dotted package refs (py)
cnt B "from rvt(\.| import)" --include=*.py
cnt C "tekton-ifc"                    # component name
cnt D "\.rvt\b"                          # format identifiers (stay)
grep -rn --exclude-dir=__pycache__ '/Users/ck/dev/things/tekton' src/   # the 9 baked ROOT constants
```

---

## 5. The sweep — one script, one commit, run ONCE

The sweep is `tools/rename_sweep.py` — **to be written at execution time,
not now** (writing it now invites someone to run it). Its contract:

```
python tools/rename_sweep.py --to tekton --package-name {rvt|tekton} \
    --author-string "<counsel C1 approved wording>" \
    [--dry-run (default)] [--apply]
```

`--dry-run` reproduces §4 and prints the exact edit list. `--apply` runs
the steps below, in this order — order matters, and each step's exit gate
must be green before the next runs:

**Step 0 — de-bake absolute paths (prerequisite, independently valuable).**
Replace the 9 `ROOT = "/Users/ck/dev/things/tekton"` engine constants
with `Path(__file__)`-relative resolution. Gate: full test suite green with
the working directory copied to a differently-named path (proves nothing
still depends on the literal directory name).

**Step 1 — Category A: authored-into-deliverable constants.** Rewrite the
five constants in §2-A with the counsel-approved author string and the
tekton client/organization/build/disclaimer strings; bump the electrical
JSON `kind` version and its reader together. Gate: the identity, house-
standard, adocument and electrical test suites green; grep for any
surviving `rvt-writer` / `tekton` in `src/`.

**Step 2 — Category B: manifests and prose.** `plugin.json`,
`marketplace.json`, `pyproject.toml` display strings, README titles, and
the `.md` prose sweep (`tekton` → `tekton`, adding Autodesk®/Revit®
attribution to customer-facing docs per §1 item 3). Presenter cheat sheets
(`ANSWER_KEY.md`, `DEMO_RUNBOOK.md`, `demo-talk-track.md`) are excluded
from any shared output but still swept. Gate: `claude plugin validate
plugin/` passes.

**Step 3 — Category D decision: the package** (only if Option B). Token-
boundary rename `\brvt\b` → `tekton` across `.py`/`.md`/`.toml`/`.cfg`,
`git mv src/rvt src/tekton`, regenerate `*.egg-info`, update
`tools/sync_plugin.py`'s directory mapping (`src/tekton/** →
plugin/lib/src/tekton/**`) and console-script entry points. Gate:
`python -c "import tekton.container, tekton.ecc, tekton.cfb_writer"`,
then the full test suite.

**Step 4 — Category C switches** (only those counsel approved): skill /
command / agent directory `git mv`s plus their front-matter `name:`
fields; update the marketplace description and every SKILL cross-reference
("use the sibling tekton-ifc skill" ↔ new names). Gate: `claude plugin
validate plugin/`; each skill loads in a live session.

**Step 5 — the directory itself.** `mv tekton tekton` (and
`tekton-quarantine → tekton-quarantine`, updating the two docs that
name it). Rebuild the zips (`tekton.zip`, `tekton-share.zip`). Gate:
`tools/sync_plugin.py --check` reports "plugin in sync"; full suite green
from the new path; grep the tree for stragglers of every source pattern in
§4 — the sweep FAILS LOUD (exit non-zero) if any Category A/B string
survives, and prints the survivors.

**Step 6 — record.** Append the sweep's before/after grep counts and the
suite result to `docs/inbox/rename-sweep.md`; mark this file EXECUTED with
the commit hash. One commit contains the entire rename.

Non-goals of the sweep: it does not rename historical `experiments/`
proof-file names (`V15…`, `G_ABPD.rvt`, `M2_delete_cascade.rvt`) — those
are cited by the certification ledger and acceptance log and are evidence,
not branding. It does not rewrite `.rvt`/`.rfa` extensions. It does not
touch `vendor/`, `samples/`, or `extracted/` (third-party / gitignored
corpus data, outside the DENY-listed shipping tree anyway).

---

## 6. Verification checklist (the sweep is done when all pass)

- [ ] Trademark clearance received (§1) — recorded in `COUNSEL-BRIEF.md`.
- [ ] Counsel C1 author string received — recorded, passed to `--author-string`.
- [ ] Step 0 done: no absolute repo paths in `src/`; suite green from a
      renamed copy.
- [ ] `grep -rEi 'tekton|rvt-writer|rvt-recon' src/ plugin/ tools/ skills/`
      returns nothing (Category A/B clean).
- [ ] `claude plugin validate plugin/` passes; both skills enumerate.
- [ ] `python tools/sync_plugin.py --check` → "plugin in sync".
- [ ] Full test suite green (count recorded in the sweep record).
- [ ] Zips rebuilt under the new name; old zips deleted.
- [ ] `docs/inbox/rename-sweep.md` written with before/after counts.
