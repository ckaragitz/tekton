# 768 — the #767 merge review's three nits, fixed and pinned

Refs #768 (filed from the #767 independent review). Stream: `prompt-archetypes`.

## What was fixed

1. **The dead gate** (`src/rvt/frontdoor/taxonomy_build.py`): `TX.builder_available(row)`
   returns `(bool, why)`; truth-testing the tuple made `if not …: continue` unreachable —
   the same tuple-truthiness bug class the #766 battery fixed, surviving one module over.
   Unpacked (`ok, _why = …`); pinned by a test that forces a hint-carrying row unbuildable
   and asserts no plan (the pre-existing VAV test passed only because VAV has no hint).
2. **The vacuous battery law** (`tools/prompt_battery.py`): `"no family plan"` counted as
   "held the line", so the battery would have PASSed the original #766 failure itself and
   a delivery→generic-refusal regression passed silently. Dropped from the honest set;
   the plain battery still passes **17/17** because every fixed refusal prompt carries the
   taxonomy's own line ("nothing to author here", "recognised, NOT built"). Also
   `except BaseException` → `except Exception` so Ctrl-C aborts instead of logging CRASH.
3. **Sibling mislabeling + file overwrite** (`src/rvt/frontdoor/router.py` taxonomy lane):
   errors appended by a FAILED sibling plan were demoted under the label `scene grammar:`;
   now `intent_errors` (snapshotted before the lane) splits the labels — scene errors keep
   `scene grammar:`, later ones get `taxonomy plan:`. And each built kind stores its file
   under `rfa:<label>` so a second build no longer silently drops the first from
   `res.files` ("rfa" itself stays the last-built, as before).

## Evidence

`tests/test_taxonomy_build_768.py` — 7 tests (gate forced-unbuildable, battery law
matrix incl. KeyboardInterrupt propagation, two-built-kinds route simulation);
neighbourhood green: 107 passed across test_taxonomy_build_{766,768} + wiring_692;
plain battery 17/17; sync --check clean.

## BRANCH STATE

Files: src/rvt/frontdoor/taxonomy_build.py, src/rvt/frontdoor/router.py (taxonomy
lane block only), tools/prompt_battery.py, tests/test_taxonomy_build_768.py,
tests/ci_shard.d/768-taxonomy-build-nits.txt, mirrors via sync. Gates: 107 passed
local, battery 17/17. Staged: nothing; all shipped in this PR.
