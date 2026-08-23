# #139 — PartAtom escape without `xml.sax.saxutils` (prompt-path import diet)

Stream: PERF-COLDSTART fragment (issue #139, `Refs #110` latency epic, steer #108). One PR, one voice:
the persistent tech-lead session, 2026-08-23.

## What was built

1. `src/rvt/famgen/skeleton.py` — `build_part_atom` (the `.rfa`'s Atom-XML manifest) no longer does
   `from xml.sax.saxutils import escape`; a module-level `_xml_escape` performs the same three
   `str.replace` calls in the same order (`&` first, then `>` / `<`). In CPython 3.11 the stdlib
   module imports `urllib.request` → `http.client` → `ssl` + `socket` + the whole `email` package:
   **34 modules** that every prompt/IFC job generating a family paid for, for nothing.
2. `tests/test_partatom_escape_139.py` (+ drop-in `tests/ci_shard.d/139-partatom-escape.txt`):
   the helper is byte-identical to `xml.sax.saxutils.escape` on 16 edge strings (oracle imported in
   the *test* process, where it is harmless); `build_part_atom` escapes title / category / type names /
   product; and `test_family_build_import_budget` — a real `make_panelboard(...).write()` in a fresh interpreter — leaves
   `xml.sax` (any submodule), `urllib.request`, `http.client`, `ssl`, `socket`, `email.parser`
   out of `sys.modules` (negative control: against `origin/main`'s `skeleton.py` that test fails with
   "family build imported [...]"). `tests/test_lazy_ifc_import.py`'s HEAVY gate was *not* the place:
   it parses a prompt and never reaches a family build.
3. Plugin mirror re-synced (`plugin/lib/src/rvt/famgen/skeleton.py`), zip rebuilt.

## Evidence — before/after (cloud session VM, 4 vCPU, Python 3.11.15; `.venv` has numpy, no ifcopenshell; system `/usr/bin/python3` has neither)

Protocol as in `docs/inbox/lazy-ifc-import.md`: `-X importtime`, "import sum" = sum of depth-0
cumulative times, 3 runs per side (run 1 is the cold one — page cache / fresh unzip), same prompt
`"an electrical room with 6 panels"` (6 generated + loaded + placed panelboard families).

### (a) repo: `.venv/bin/python -X importtime tools/frontdoor.py author --prompt … --out … --json`

| | before (`main` @ 11d336d) | after |
|---|---|---|
| modules imported | 259 | **225** (−34: `xml.sax*` ×5, `urllib.request/response/error`, `http`, `http.client`, `ssl`, `_ssl`, `socket`, `_socket`, `select`, `selectors`, `email*` ×15, `base64`, `quopri`, `calendar`; nothing added) |
| `xml.sax.saxutils` cumulative (runs 1/2/3) | 14.7 / 12.9 / 12.7 ms (`urllib.request` 11.9, `http.client` 9.5, `email.parser` 4.8, `ssl` 2.8) | **not imported** (nor any of the chain) |
| import sum (runs 1/2/3) | 726.3 (cold) / 160.0 / 183.9 ms | 153.2 / 159.9 / 161.4 ms |
| job wall (runs 1/2/3) | 4.18 (cold) / 3.16 / 3.19 s | 3.18 / 3.27 / 3.31 s |
| `status` / `errors` | PROOF-ONLY (self-checks PASS) / `[]` | same / `[]` |

### (b) bare unzip: `env -i … /usr/bin/python3 -X importtime skills/tekton-author/scripts/_bootstrap.py go author --prompt … --out out/jN --json` from a fresh unzip of `tekton-plugin.zip` (built from `origin/main` vs this branch; private HOME/TMPDIR, dead proxies; `go` dispatches in-process via `runpy`, so one log covers preflight + job)

| | before | after |
|---|---|---|
| modules imported | 265 | **231** (the same 34 gone) |
| `xml.sax.saxutils` cumulative (runs 1/2/3) | 12.5 / 23.1 / 26.0 ms (`ssl` *self* 1.8 / 12.8 / 15.0 ms on this interpreter) | **not imported** |
| import sum (runs 1/2/3) | 574.1 (cold) / 167.2 / 170.9 ms | 571.4 (cold) / 177.6 / 156.6 ms |
| wall (runs 1/2/3) | 3.55 / 3.06 / 2.96 s | 3.52 / 3.20 / 2.99 s |
| `go.ready` / `result.status` / `errors` | True / PROOF-ONLY (self-checks PASS) / `[]` | same |

### (c) output identity and validity

* `_xml_escape(s) == xml.sax.saxutils.escape(s)` on 16 edge strings (`&&&`, `]]>`, quotes, non-ASCII, …).
* `build_part_atom` **byte-identical** to `origin/main`'s implementation (exec'd from `git show`) on
  80 title × category × type-list × product combinations with a pinned `updated` stamp; the emitted
  `PartAtom` stream of `pp1_…rfa` before vs after is identical modulo `<updated>` (771 bytes).
* `tools/rvt_validate.py`: `prompt_room.rvt` VALID, 0 errors (1 pre-existing warning — the known
  Extensible-Storage `DataStorage` decoder gap), all six `.rfa` VALID 0 errors / 0 warnings in
  `--family` mode, before and after alike. Validator green is necessary, not a Revit verdict (rule 4);
  nothing here changes emitted bytes, so no viewer round is implied.

Honest framing: this removes a per-process constant — ~13 ms (repo) / 12–26 ms (bare) and 34 modules —
from every job that generates a family; the run-to-run noise of the whole import bill is itself
±10 ms, and the job is build-dominated (~3 s wall for six families + placement + self-check), so
wall time is unchanged within noise. It is the "worth one look" item from `lazy-ifc-import.md`
§Findings 2, now closed with numbers.

## Gates run

* `pytest tests/test_partatom_escape_139.py` → 18 passed (1.0 s); against `origin/main`'s
  `skeleton.py` → 17 failed (negative control), restored → 18 passed.
* `RVT_SKIP_LARGE=1 pytest` over `test_famgen_factory`, `test_famgen_skeleton`, `test_famgen_adoc`,
  `test_bare_family_validate`, `test_families`, `test_rfa_load`, `test_lazy_ifc_import`,
  `test_convert_combo`, `test_ecc`, `test_ecc_encode`, `test_partition_header_verdict`,
  `test_rewrite_entries_646`, `test_rvt_analyze`, `test_plugin_sync`, `test_records_layout`,
  `test_partatom_escape_139` → **452 passed, 68 skipped** (sample-gated), 35 s.
* `tools/sync_plugin.py` → synced 1 file, deny-audit clean, identity scan == allowlist;
  `--check` clean; `plugin/scripts/validate_plugin.py` → PASS (25 assertions).
* `/verify` front-door drive = the (a) runs above (READY-equivalent `PROOF-ONLY (self-checks PASS)`,
  `errors []`, outputs validate 0 errors); bare-surface `go author` = the (b) runs.

## Review round 1 (head 0769e97, independent reviewer, 🟡 nits — all taken)

| nit | change |
|---|---|
| index line sat under the old record's triage bullets | moved under a `## Fragments` header in `perf-coldstart.md` |
| BRANCH STATE said `skeleton.py (+9/−1)` | corrected to +7/−1 (the docstring was trimmed during `/simplify`) |
| a future unrelated import tripping `HEAVY` would blame #139 | the child's assert now says "family-build import budget (HEAVY) exceeded" |

The reviewer also re-derived the numbers independently in the sandbox: `_xml_escape == saxutils.escape`
on 219,608 strings (exhaustive over `&<>;amp` to length 5 + 200k random incl. astral/non-ASCII),
`build_part_atom` SHA-256 identical to `origin/main`'s over 336 combinations, chain absent on
CPython 3.11.15 / 3.12.3 / 3.13.14 (201/203/204 modules for one family write), full prompt job
259 → 225 modules with `xml.sax.saxutils` 13.3 ms cumulative before.

## Findings

1. The next stdlib weight on this path is `rvt.meta` (imported by `rvt.stream_encoders`): 9–10 ms
   cumulative, of which module-level `xml.dom.minidom` 2.2–2.5 ms, `urllib.parse` 2.2 ms and
   `xml.etree.ElementTree` 1.5 ms serve only its XML pretty-print/parse helpers — a lazy import there
   is the same kind of free, byte-neutral diet (filed as a follow-up with these numbers rather than
   widened into this PR's territory).
2. After that the warm import bill is ~150 ms and its top entries are ours (`rvt.frontdoor.build`
   30–35, `rvt.frontdoor.prompt_intent` 20–25, `rvt.frontdoor` 15–24, `rvt.famgen.factory` 10 ms):
   further wins are in-module work at import time, not stdlib chains.

## BRANCH STATE

* Branch `cam/139-partatom-escape` from `main` @ 11d336d. Files: `src/rvt/famgen/skeleton.py`
  (+7/−1), `plugin/lib/src/rvt/famgen/skeleton.py` (mirror), `tests/test_partatom_escape_139.py`
  (new), `tests/ci_shard.d/139-partatom-escape.txt` (new), this fragment + one index line in
  `docs/inbox/perf-coldstart.md`. No binaries; all outputs in the session scratchpad / `out/verify/`.
* Shipped vs staged: code + test ship with the PR; nothing staged for the viewer (byte-neutral).
