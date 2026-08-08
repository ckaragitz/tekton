# prompt-grammar — restore wall derivation + rating-class voltage vocabulary (issue #1)

Stream: `clkaragitz/1-prompt-grammar` · Territory: `src/rvt/frontdoor/prompt_intent.py`, `tests/test_prompt_intent.py` · 2026-08-07

## What was built

Two behaviours of the rules-first prompt parser, both flagged four times in
the campaign records (genesis-audit: "the current intent grammar derives 0
walls from the demo prompt (v3 had 4) — queue with the 250V vocab item"):

1. **Default room shell.** A NAMED room with no dimensions now yields the
   9.144 x 6.096 m (30 x 20 ft) default shell (`DEFAULT_ROOM_W_M/_D_M`)
   instead of silently degrading to an equipment-only row. The default is
   stated in `coverage.defaults_applied`. `no walls` / `equipment only` and
   prompts with no room noun keep their old behaviour (pinned by tests).
2. **Rating-class voltage vocabulary.** A new amp-less service-voltage
   clause (`_RE_RATED_VOLT`: "rated for 250V", "600V class") resolves the
   service system. UL RATING CLASSES map to the system they imply
   (`RATING_CLASS_TO_SYSTEM`: 250/240 → the 240 V-class system) and the
   mapping is ALWAYS stated in `defaults_applied` — never silent. Real
   systems pass through the existing vocabulary unmapped (480 → 480Y/277,
   600 → 600Y/347). "250V" no longer appears in `ignored_words`.

## Evidence (numbers)

`prompt_to_intent` on the three DONE prompts (was → is):

| prompt | walls | service_voltage | ignored_words |
|---|---|---|---|
| "a 30 by 20 ft electrical room rated for 250V with 6 panels" | 4 → 4 | 480Y/277 → **240** | ['250V'] → **[]** |
| "an electrical room with 6 panels" | **0 → 4** (default shell, stated) | 480Y/277 | [] |
| "an electrical room rated for 250V with 6 panels" (the demo) | **0 → 4** | 480Y/277 → **240** | ['250V'] → **[]** |

Coverage excerpts (demo prompt):
- `defaults_applied` now carries: "room dimensions: 9.144 x 6.096 m (30 x 20 ft)
  DEFAULT room shell — the room was named with no dimensions; say 'W by D ft'
  to size it" and "service voltage: 240 V-class system mapped from the
  prompt's '250 V' rating class (a 250 V rating names the equipment's
  maximum voltage class, not a system voltage)".
- `understood` carries `{"as": "service voltage", "voltage": "240", "rated": "250 V"}`.

End-to-end (Windows, fresh clone, plugin-bundled genesis base via
`RVT_GENESIS_BASE=plugin/assets/genesis/G_ABPD.rvt`): both prompts build
`prompt_room.rvt`, `ok: true`, PROOF-ONLY stamp; `tools/rvt_validate.py`
**0 errors** (2 warnings = the known fresh-clone decoder gaps: 1 DataStorage
ES blob, no `extracted/` corpus).

## Tests

- NEW `tests/test_prompt_intent.py`: 10 tests — rating-class mapped+stated,
  600V stays 600Y/347, 480V unmapped, amp-service clause untouched, default
  shell + stated, explicit dims win, `equipment only` still suppresses,
  no-room-noun stays equipment-only, both demo prompts end-to-end
  (`@needs_catalog`). 10/10 pass.
- `tests/test_frontdoor.py`: 36 passed / 4 skipped (catalog-gated) /
  1 failed = `test_handoff_only_route_writes_the_package`, which fails
  IDENTICALLY on clean main on Windows (cp1252 `UnicodeEncodeError` writing
  '→' in MANIFEST.md) — pre-existing, filed as a follow-up issue, NOT this
  stream.

## Findings (out of scope, filed as issues)

Windows fresh-clone portability, all reproduced on clean main:
1. Manifest writer uses the locale codec (cp1252) → `UnicodeEncodeError` on
   '→'/'®' (breaks `test_handoff_only_route_writes_the_package` and
   `test_bootstrap.py::test_run_launcher_frontdoor_prompt_handoff`).
2. `tools/sync_plugin.py` on Windows: (a) re-zip step dies
   `FileNotFoundError` (subprocess exec of a missing binary); (b) it
   regenerates `plugin/assets/schema_cache/index.json` `sources` with
   backslashes → `--check` permanently flags index.json drift on Windows.
3. `plugin/scripts/validate_plugin.py` fails `skills/_shared: SKILL.md
   missing` (23 other assertions pass) — platform-independent, likely a
   validator/skill-layout drift.

## BRANCH STATE

- Files written: `src/rvt/frontdoor/prompt_intent.py` (+56/-6),
  `plugin/lib/src/rvt/frontdoor/prompt_intent.py` (sync mirror),
  `tests/test_prompt_intent.py` (new), this record.
- Gates: stream-local tests 10/10 + frontdoor 36 pass (1 pre-existing
  Windows failure, baselined on main); `sync_plugin.py` run; `--check`
  clean EXCEPT the known Windows backslash churn in
  `assets/schema_cache/index.json` (finding 2b above — not committed);
  `rvt_validate.py` 0 errors on both built rooms.
- Staged vs shipped: no viewer round needed (`ready` issue, no
  certification claim). Outputs are PROOF-ONLY per the standing gates.
- Follow-ups: the three Windows findings above → new issues, not this PR.
