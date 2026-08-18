# locale-gate — the bare `go` surface under a forced-ASCII locale (#210, Linux CI gate for #29)

Stream: #210 (test-only; territory `tests/`, this record, one comment on #29). Author: cam-karagitz
(persistent tech-lead session), 2026-08-18. Refs #29 (the fix, held by Ckaragitz12), #122 (Windows CI),
#209 (late exceptions survivable), #636 (new-module convention).

## What was built

- `tests/test_coldstart_locale_210.py` — three tests on the bare surface (`plugin/` copy driven by
  `sys.executable -I -S`, the fixtures `tests/test_coldstart.py` already builds, imported per
  `tests/ci_shard.d/README`), all under a child environment carrying the one load-bearing knob `LC_ALL=C` plus argv
  `-X utf8=0`:
  1. `test_preflight_is_ready_under_ascii_locale` — passes today.
  2. `test_go_author_delivers_cleanly_under_ascii_locale` — **the #29 gate**, `xfail(strict=True)`:
     ASCII prompt, `--out "…/job 1 (ascii locale)"`; requires exit 0/4, a non-`FAILED` status, no
     `Unicode*Error` in `result.errors`, the `.rvt` on disk, and `MANIFEST.md`/`manifest.json` non-empty,
     strictly UTF-8-decodable, the `.md` naming the delivered file.
  3. `test_non_ascii_prompt_keeps_the_one_json_contract` — passes today and after #29: German prompt +
     non-ASCII `--out`; requires exactly one pure-ASCII JSON document, `go.exit_code == returncode ∈
     {0,3,4}`, no wrapper `exception`, the job's own `result` document, the `.rvt` on disk if built, the
     out dir created.
- `tests/ci_shard.d/210-locale-gate.txt` — puts the module in the per-PR shard (never edited
  `tests/ci_shard.txt`).
- An autouse `ascii_locale` module fixture probes the child first; when the interpreter cannot be forced
  to an ASCII preferred encoding it **fails loudly on glibc** (the CI reference platform, where this is
  measured to work — a silent skip there would retire the gate unnoticed) and **skips** elsewhere with the
  measured value (a libc that pins UTF-8; Windows' cp1252 — Windows gets the real thing through #122).

## The physics, measured (why the gate looks the way it does)

| probe (system CPython 3.11.15, glibc; same env as the tests) | result |
|---|---|
| `codecs.lookup(locale.getpreferredencoding(False)).name`, `sys.getfilesystemencoding()`, `sys.flags.utf8_mode` | `ascii ascii 0` |
| same without `-X utf8=0` | `utf-8 utf-8 1` — UTF-8 mode switches itself **on** for the C locale; `-I` ignores `PYTHONUTF8`, only the `-X` flag turns it off |
| `LANG=C PYTHONCOERCECLOCALE=0` (no `LC_ALL`) under `-I` / without `-I` | `utf-8` (coerced to C.UTF-8) / `ascii` — `-I` ignores `PYTHONCOERCECLOCALE` too; what defeats PEP 538 coercion in the tests is that **`LC_ALL` is set** (coercion is skipped whenever it is), so `LC_ALL=C` is the single load-bearing env knob and the `PYTHON*` spellings were dropped as inert |
| `sys.argv[1]` for argv `Größe – 5×4` | `'Gr\udcc3\udcb6\udcc3\udc9fe \udce2\udc80\udc93 5\udcc3\udc974'` — surrogate-escaped, undecodable by construction |
| child `sys.stdout.errors` / `sys.stderr.errors` | `surrogateescape` / `backslashreplace` |

So an ASCII locale is *stricter* than cp1252 for everything the product writes itself (cp1252 encodes
`—`, `“ ”`, `…`, `·`, `×` and dies only on `→`; ASCII dies on all of them — a strict superset, the right
direction for a gate whose fix is codec-independent), but it adds one thing Windows does not have: non-ASCII **argv** cannot be decoded at all
(Windows argv is UTF-16). A German prompt in argv therefore can never round-trip into a strict UTF-8
manifest under this simulation, whatever #29 does — which is why the issue's literal DONE ("MANIFEST.md
… contain the prompt text" for `Elektroraum – Größe 5×4 m`) was split: the **flip condition uses an
ASCII prompt** (the renderer's own output is already non-ASCII, see below), and the German prompt is
pinned as the one-JSON/delivery contract instead. `go --json` itself is safe on any console because
`tekton_env._json_doc` is `json.dumps(…)` with the default `ensure_ascii=True` (test 3 pins that too).

## Evidence — BEFORE (main `644c8f9`, bare copy of `plugin/`, forced-ASCII child)

| run | exit | what came back |
|---|---|---|
| `_bootstrap.py --json` (preflight) | 0 | one JSON, `ok: true`, `tekton: READY \| python 3.11.15 \| engine bundled \| genesis verified (Revit 2026) \| … \| 0.043s` |
| `go author --prompt "an electrical room 5x4 m with 2 panels" --out "…/job 1 (ascii)"` | **3** (2.9 s) | `FAILED (post-build error: UnicodeEncodeError: 'ascii' codec can't encode character '—' in position 23 …; delivered anyway: prompt_room.rvt, families/)`; `result.errors` = [`handoff package failed: UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 in position 9`, `prompt route raised UnicodeEncodeError … '—' …`, traceback]; `.rvt` + families delivered (#209); **`MANIFEST.md` 0 bytes**, `manifest.json` 76,179 bytes (pure ASCII); stderr 0 bytes |
| `go author --prompt "Elektroraum – Größe 5×4 m with 2 panels" --out "…/job ä 1"` | 3 | ONE pure-ASCII JSON (3,190 bytes); same two errors (it dies on the renderer's own `—` before reaching the prompt text); files delivered — the paths come back surrogate-escaped (`job \udcc3\udca4 1/prompt_room.rvt`) and resolve on disk; the directory on disk is `job ä 1` |

Two #29-class sites are live on the bare prompt lane today, not one: the MANIFEST.md **write**
(`src/rvt/frontdoor/manifest.py:653`, and `:650` for the json) and the handoff package's encoding-less
**read** of `PROMPT_TO_IFC.md` (`src/rvt/frontdoor/prompt_intent.py:1923`; writes at `:1927`, `:1930`).

## Evidence — the gate flips (simulated #29 stage 1, mirror only, reverted)

`encoding="utf-8"` added at exactly those five sites in a throwaway state of `plugin/lib/src/…`
(restored with `git checkout`, `tools/sync_plugin.py --check` clean afterwards):

| run | result |
|---|---|
| ASCII prompt, `--out "…/job fix 4 (ascii)"` | **exit 0**, `PROOF-ONLY (self-checks PASS; …)`, `errors: []`, `MANIFEST.md` 10,044 chars containing U+2014 `—`, U+201C/U+201D `“ ”`, U+2026 `…`, U+2192 `→`, U+00B7 `·`, U+00D7 `×` |
| the module | `1 failed, 2 passed in 7.47s` — the failure is `[XPASS(strict)] #29 stage 1 not merged: …` = the designed reminder to delete the marker in the fixing PR |
| German prompt with the fix | still exit 3: `UnicodeEncodeError: 'utf-8' codec can't encode characters in position 606-608: surrogates not allowed` (handoff and manifest) — the argv physics above, not a product bug; files delivered, one JSON. (If #29 wants a C-locale terminal's UTF-8 bytes to round-trip into the files we author, `errors="surrogateescape"` on those writes does exactly that — #29's call, noted on the issue, not required by this gate.) |

So the five sites are the *complete* set for the bare `go author --prompt` lane: with them the gate
passes; without them it cannot.

## Gates run

- `.venv/bin/python -m pytest tests/test_coldstart_locale_210.py -q -rxs` → **2 passed, 1 xfailed in 6.09s**
  (first version); **2 passed, 1 xfailed in 5.31s** (final)
- with the neighbours sharing fixtures/laws: `tests/test_coldstart_locale_210.py tests/test_coldstart.py
  tests/test_conftest_scaffolding.py tests/test_shard_list.py` → **61 passed, 1 xfailed in 27.04s** (first version), **61 passed, 1 xfailed in 14.80s** (final)
- `python3 tools/dev/shard_list.py --print` lists `tests/test_coldstart_locale_210.py` (entry 60)
- `tools/sync_plugin.py --check` → in sync (nothing under `src/`/`tools/`/`skills/` touched)
- cost in the shard: one plugin copy + one preflight + two ~3 s prompt builds (≈ 6 s here)

## Review passes before the PR left draft

`/simplify` (four independent reviewers: reuse, simplification, efficiency, altitude) on the first
version (139 lines) → applied: the env dict shrank to `LC_ALL=C` and the two mis-attributed causal
sentences were corrected (measured: `PYTHONCOERCECLOCALE`/`PYTHONUTF8` are inert under `-I`; cp1252
fails only on `→`); assertions implied by a neighbour dropped (wrapper `exception` ⇒ exit 1, `FAILED…`
⇒ exit 3, empty manifest ⇒ the content check); a 7-line `_go_author` helper replaced the copy-paste
between the two build tests; the manifest loop unrolled; the probe became an autouse fixture with no
dead return, failing loudly on glibc / skipping elsewhere (altitude); `xfail(strict=True,
raises=AssertionError)` so only the asserted contract counts as the expected failure (altitude); one
`timeout=180` literal instead of 60/120/600 plumbing (efficiency: a hung bare build now fails
diagnosably inside `session_ci.sh`'s 1500 s shard cap instead of consuming 2×600 s of it); the flip
note stated once (in the xfail reason, which is what prints on the day); test 3's delivery check made
a hard assertion. Kept on the reviewers' advice: both builds (different variable under test; folding
the must-pass into the xfail body would silence it), the module's own plugin copy (<0.5 s; a
session-scoped shared copy for all five bare-surface modules is a separate `area:process` cleanup, not
this PR's), the exit-code literals (same convention as the sibling module). Result: 101 lines; both
directions re-proven on the rewritten body — simulated fix → `[XPASS(strict)] … 1 failed, 2 passed in
5.30s`; probe variant without `-X utf8=0` on glibc → `Failed: cannot force an ASCII locale on this
interpreter (probe said b'utf-8\n', exit 0)` at setup.

## Deviations from the issue text (and why)

- New module + drop-in instead of appending to `tests/test_coldstart.py`: the #636 convention in
  `CLAUDE.md` §4 / `tests/ci_shard.d/README` postdates the issue; fixtures are imported from the big
  module as the README prescribes.
- The strict-xfail flip condition uses an ASCII prompt; the German prompt moved to its own always-on
  contract test — see *physics*. The spaced `--out` stayed in the gate; the non-ASCII `--out` moved with
  the German prompt (same surrogate reason: the manifest embeds paths).
- The gate also requires *no `Unicode*Error` in `result.errors`*, so the handoff READ found here is part
  of #29 stage 1's bar, not only the manifest write.

## Follow-ups

None filed: both live sites belong to #29's existing sweep (comment left there with the exact lines and
the flip procedure). #122 (Windows job) remains the real-platform confirmation.

## BRANCH STATE

- branch `cam/210-locale-gate` from `main` @ `644c8f9`
- files: `tests/test_coldstart_locale_210.py` (new), `tests/ci_shard.d/210-locale-gate.txt` (new),
  `docs/inbox/locale-gate.md` (this record)
- nothing generated, nothing under `src/`, `tools/`, `skills/`, `plugin/`; no hot file
- shipped: the tests + record; staged: nothing (no viewer claim — rule 4 untouched)
