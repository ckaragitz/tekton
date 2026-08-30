# perf-surfaces / #760 -- the delivery report describes the delivered (hardened) file

Stream: PERF-SURFACES (index: `docs/inbox/perf-surfaces.md`). Issue #760 (Refs #754, #757, #758, #110).
Branch `cam/760-report-headline` from `main@1428331`.

## Why

`report.py validate.json --compare harden.json` -- the documented delivery command, and byte-identical
to `ifc_flow.py`'s `report.md` -- headlined the INPUT's validation (score, tier, element table) above
the before → after table, while the runbook's manual fallback described the FINAL file and step 10
delivers `hardened.ifc`. On the plugin sample the delivered report opened with "35.7 / Tier 0" for a
file that scores 77.0 / Tier 1 (partial). Found by the independent review of #759.

## What changed

* `skills/tekton-ifc/scripts/report.py`: `render(rep, compare, *, source)` -- the report describes
  `rep`; `source` (the input's name) is given when `rep` is the hardened file's report, and the
  first line then names both (`hardened.ifc` (hardened from `X.ifc`)`). `main()` picks the hardened
  file's report from `--after`, or from the `validate-after.json` beside `--compare harden.json` --
  taken only when it is the report of the file harden.json produced -- same path, score and size --
  so a stale one from an earlier run (another output, or the same path re-hardened with other
  options) is not headlined (both failure modes reproduced by the reviewers; the second on the real
  tools: re-`harden_ifc.py --no-extrusions` to the same path, skip the re-validate -> warning + the
  input's headline, not the old 77.0). An unreadable discovered sibling degrades the same way; an
  explicit `--after` is the operator's assertion (unreadable, or the input's own report -> exit 2).
  Without one: the input, first line "(the input, before hardening)", warning on stderr, exit 0
  (hard rule 1: delivered).
  A single `validation.json` renders byte-identically to before. `AFTER_REPORT` owns the name;
  `ifc_flow.FILES["validate_after"]` refers to it.
* `skills/tekton-ifc/scripts/ifc_flow.py`: `render(rep1, res, source=basename(input))` -- the
  hardened file's in-memory report, no re-read.
* `tools/surface_bench.py` (`ifc-harden`, the four-call row): keeps `validate-after.json` as an
  artifact and names it with `--after` (the bench renames artifacts, so the sibling rule cannot
  apply); the four-call and one-call rows now render the same document up to the hardened file's
  name (the bench keeps its artifact as `ifc-hardened.ifc`).
* `references/sop-harden-deliver.md` step 8 (+ mirror) and `scripts/README.md`: the tool command and
  the manual fallback describe the same file.
* Tests: `tests/test_ifc_report_760.py` (14 collected, stdlib-only synthetic reports, in-process `main()`:
  the three titles, errors-first with schema errors, sibling lookup == explicit `--after` bytes,
  five degrade cases (no sibling / unreadable / not a report / another output / same path re-hardened) with the
  warning, single-file unchanged, `--after` taken as given but exit 2 when unreadable or the input's
  own report, the positional-is-the-hardened-report form (a shipped job template's) == the canonical
  bytes, malformed positional/compare JSON exit 2, one real launch of the entry point) + `tests/ci_shard.d/760-report-headline.txt`;
  `tests/test_ifc_flow_754.py` stub `render` records `(rep, cmp, source)` and the flow's hand-off is
  pinned; `tests/test_ifc_skill_bench_113.py` pins `--after` == the re-validated report.
* SKILL.md untouched: its §5.4 command now yields the hardened file's report.

## Evidence

* Sample (`plugin/skills/tekton-author/examples/electrical-room-2500a.ifc`), first three lines of
  `delivery-report.md` -- before (main's `report.py`):
  `# Revit-readiness report: `electrical-room-2500a.ifc`` / `` / `**Score: 35.7/100** — **Tier 0
  (v1-like) -- imports as frozen DirectShape blobs with baked coordinates**`; after:
  `# Revit-readiness report: `hardened.ifc` (hardened from `electrical-room-2500a.ifc`)` / `` /
  `**Score: 77.0/100** — **Tier 1 (partial) -- imports usably but some elements come in as frozen
  blobs / at the origin**`; line 8 `- File size 996,653 bytes` (the hardened file's; was the input's
  686,804); footer `… from `electrical-room-2500a.ifc`, delivered as `hardened.ifc`.`
* `ifc_flow.py`'s `report.md` == `report.py validate.json --compare harden.json` == the same with
  `--after validate-after.json` (cmp: identical); single-file output cmp-identical to main's.
* `pytest tests/test_surface_perf.py tests/test_plugin_sync.py tests/test_ifc_skill_bench_113.py
  tests/test_ifc_flow_754.py tests/test_ifc_report_760.py tests/test_records_layout.py` -> 57 passed;
  `tests/test_bootstrap.py tests/test_coldstart.py` -> 23 passed.
* `surface_bench --jobs ifc-harden,go-ifc-harden --surfaces codeexec,local --python-bare .venv/bin/python`:
  all four PASS; kept `ifc-report.md` (four calls, stateless codeexec) and `go-ifc-report.md` both
  open with the hardened title; codeexec 4 calls 4.1 s vs 1 call 2.3 s (+0.5/+0.2 s extract), local
  4.2 s vs 1.9 s. Bare `/usr/bin/python3` surfaces stay BLOCKED (needs numpy) as in #754's record.
* `tools/sync_plugin.py --check` -> "plugin in sync with source (deny-audit clean, identity scan ==
  allowlist, assets verified)"; `plugin/scripts/validate_plugin.py` -> PASS; portable paths ok (3163).
* Bare unzip `go author --prompt "an electrical room with 6 panels"`: `ready: True`, preflight READY
  0.023 s, `prompt_room.rvt` delivered, our gate VALID 0 errors (PROOF-ONLY stamps as always).

## Findings / follow-ups

* The producer already has what the consumer hunts for: `harden_analysed` analyses its output and
  the CLI throws that report away, SKILL.md 5.3 re-creates it with a second `validate_ifc.py` call,
  and `report.py` now locates the file by convention. `harden_ifc.py --report` persisting its
  after-analysis (or its path) would make `--compare` self-sufficient -- filed as a follow-up.
* Independent reviews (🟡, 🟡): identity check tightened to score + size, `--after` guarded against the
  input's own report, an unreadable discovered sibling degrades instead of exit 2, README's third
  state (second commit); a JSON that is not a report (`[1]`) degrades / exits 2 instead of a traceback,
  the README synopsis's `validation-after.json` typo (now load-bearing) fixed, `--after` alone documented,
  the runbook says to pass `--after` when the after-report is not this run's `validate-after.json`
  beside `harden.json` (third commit). Third review (🛑): the shipped job template
  `plugin/docs/JOB-TEMPLATES/electrical-room-package.md` ran `report.py out/validate-after.json --compare
  out/harden.json` -- the positional already the hardened file's report -- which rendered "hardened from
  `hardened.ifc`"; `main()` now recognises that form (`rep.file == harden.output` -> it is the subject,
  the input named from harden.json's `input`; same bytes as the canonical command on the sample), the
  template moved to the canonical command, and a malformed positional / `--compare` JSON is exit 2
  instead of a traceback (fourth commit).
* /simplify (4 reviewers) applied: identity check on the discovered sibling, `source=` instead of an
  `after=` override, the CLI remedy out of the delivered document, one constant for the sibling name,
  `after_path` bound once, dead `instancing`/`units` unpack dropped, tests in-process (5 launches ->
  1), fixture layout from `test_ifc_flow_754.FILES`. Declined: making the positional optional under
  `--after` (changes the documented interface for ~1 ms).

## BRANCH STATE

* Branch `cam/760-report-headline` (from `main@1428331`). Files: `skills/tekton-ifc/scripts/{report,ifc_flow}.py`,
  `skills/tekton-ifc/scripts/README.md`, `skills/tekton-ifc/references/sop-harden-deliver.md` (+ their
  `plugin/skills/tekton-ifc/` mirrors via sync), `tools/surface_bench.py`, `tests/test_ifc_report_760.py`,
  `tests/ci_shard.d/760-report-headline.txt`, `tests/test_ifc_flow_754.py`, `tests/test_ifc_skill_bench_113.py`,
  this fragment + one index line.
* Gates: as above. `tekton-plugin.zip` rebuilt locally (git-ignored); bench JSON under git-ignored `out/verify/v760/`.
