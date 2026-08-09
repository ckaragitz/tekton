# PROMPT-TAG-MENTION — naming a tag in a room prompt is ONE equipment item carrying that tag (issue #101)

Stream: `prompt-tag-mention` (engineer session on #101, started by the tech-lead
session). Territory: `src/rvt/frontdoor/prompt_intent.py`, `tests/test_frontdoor.py`,
this record; the `tools/sync_plugin.py` mirror `plugin/lib/src/rvt/frontdoor/prompt_intent.py`
regenerated. Nothing else touched (`tools/frontdoor.py`, `intent.py`, `build.py`,
`matrix.py`, `router.py` unchanged).

## 0. The defect, reproduced (fresh cloud clone, `origin/main` @ 21a9c49, before any change)

`PYTHONPATH=src .venv/bin/python -c 'from rvt.frontdoor.prompt_intent import parse_prompt; …[(it.tag, it.kind) for it in parse_prompt(p).items]'`
on `"an electrical room 20x15 ft with " + clause`:

| clause | before | after |
|---|---|---|
| `one 100 A lighting panel LP-1` | LP-1, **LP-2** | LP-1 |
| `one 100 A lighting panel named LP-1` | LP-1, **LP-1** (two items, one tag) | LP-1 |
| `one 100 A lighting panel` | LP-1 | LP-1 (unchanged) |
| `a 400 A distribution panel DP-1` | DP-1, **DP-2** | DP-1 |
| `two 100 A lighting panels LP-1 and LP-2` | LP-1 … **LP-5** (five) | LP-1, LP-2 |
| `lighting panels LP-1, LP-2 and LP-3` | LP-1 … **LP-5** | LP-1, LP-2, LP-3 |
| `a main switchboard MSB and two lighting panels` | MSB, **MSB-2**, LP-1, LP-2 | MSB, LP-1, LP-2 |
| `one distribution panel and one lighting panel, LP-1 fed from DP-1` | DP-1, **DP-2**, LP-1, **LP-2**; explicit feeder lost | DP-1, LP-1; `feeders == [("DP-1","LP-1")]` |
| `one 75 kVA transformer T1` | T1, but `T1` in `ignored_words` | T1, tag understood |
| `LP-1 and LP-2` (bare tags only) | LP-1, LP-2 | LP-1, LP-2 (unchanged) |
| `an MDP and two LPs` (abbreviations as nouns) | DP-1, LP-1, LP-2 | unchanged |
| worked prompt (`… a main switchboard, two 400 A distribution panels and four lighting panels`) | MSB, DP-1, DP-2, LP-1..4 | unchanged |
| `an electrical room with 6 panels` | PP-1..6 | unchanged |

**Root cause.** Each `_KIND_PATTERNS` regex carries the kind's *abbreviation*
as an alternative (`\blps?\b`, `\bdps?\b`, `\bmsb\b`, `\bxfmrs?\b`). `-` is a
word boundary, so the `lp` inside the tag token `LP-1` matched as a *second*
lighting-panel noun with its own count (the `one` before the real noun, or the
default), and `named LP-1` was applied to both. The tag text itself was never
consumed, so it also never reached `coverage.understood`.

## 1. What changed (`parse_prompt`, equipment pass only)

* **A noun consumes the tag list that follows it.** New `_RE_TAG_LIST` /
  `_TAG_TOKEN` (`LP-1`, `DP2`, `T1`, `PP-3A`, quoted or not, optionally led by
  `named/called/tagged/labelled/marked/designated`, joined by `,` / `and` / `&`;
  digit-less only for the lineup abbreviations `MSB`/`MDP`). It is matched
  *anchored at the noun's end* and deliberately reads across `and`/`,` — there
  they join tags, everywhere else they stay clause boundaries. The existing
  `_RE_NAMED` ("named X" elsewhere in the clause window) remains the fallback.
* **Abbreviation + `-N` is a tag *reference*, not a noun** (`ref_end`): each
  kind's abbreviation alternatives now sit in a named group `(?P<abbr>…)` inside
  `_KIND_PATTERNS` (no "short and alphabetic" guessing); an `abbr` match followed
  by `-N` (`lp` in `LP-1`), or a bare one inside an `X fed from Y` clause (`MSB`
  in `DP-1 fed from MSB`), is a reference. All noun clauses are processed before all references
  regardless of prompt order; a reference to a tag a noun clause already produced
  is just consumed; an unseen one stands for exactly ONE item carrying that tag
  (so `with LP-1 and LP-2 on the west wall` still builds two panels).
* **Counts:** an explicit count wins over the number of tags named
  (`three lighting panels LP-1 and LP-2` → LP-1, LP-2, LP-3); an uncounted plural
  takes `len(tags)` instead of the "assumed 2" default; a bare reference is 1.
* **One tag issuer** (`issue_tag` + `counters`/`used_tags`): explicit and auto
  tags share the per-prefix ordinal (`count_index` keeps one meaning), and an
  explicitly named tag is never re-issued: `one lighting panel LP-2 and one more
  lighting panel` → LP-2, LP-3 — never two LP-2s. (Text order still rules: an
  explicit tag that an *earlier* unnamed clause already auto-took falls back to
  auto-numbering — `two lighting panels and one lighting panel LP-2` → LP-1..3.)
* **Coverage:** the equipment entry gains `"tags": [...]`; the tag clause is its own
  `{"as": "equipment tag", "clause": "LP-1 and LP-2", "kind": …, "tags": [...]}` entry
  and its span is marked consumed (so it is neither an extra equipment clause nor
  an ignored word). No other coverage key changed shape.

## 2. Evidence

* `tests/test_frontdoor.py`: +3 tests / 10 cases, all `parse_prompt`-only (no
  catalog, no samples — fresh-clone/CI-shard runnable):
  `test_naming_the_tag_is_one_item_not_two[6 clauses]`,
  `test_named_tags_are_understood_as_tags_in_coverage`,
  `test_unnamed_counts_and_references_unchanged` (worked prompt, `6 panels`,
  `an MDP and two LPs`, fed-from reference, bare tags, no re-issued tag).
* Stream-local suites (final head): `tests/test_frontdoor.py tests/test_router.py
  tests/test_prompt_intent.py tests/test_convert_combo.py tests/test_plugin_sync.py`
  → **132 passed, 17 skipped** (skips = genesis/samples-gated, as on main); plus
  `tests/test_coldstart.py tests/test_lazy_ifc_import.py` green (the parser stays
  numpy-free / ifcopenshell-free at import). `tools/sync_plugin.py` run (1 file mirrored) and `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS (24 assertions);
  `tools/dev/check_portable_paths.py` ok (2702 paths).
* **Runtime, through the real CLI** (`tools/frontdoor.py author --prompt … --out … --json`,
  same `.venv`, `origin/main` worktree vs this branch, one run each, cloud VM):

  | prompt | before: families built / instances placed / wall | after |
  |---|---|---|
  | `an electrical room 20x15 ft with one 100 A lighting panel LP-1` | 2 `.rfa` (`lp1_…`, `lp2_…`), stages L1+L2, crud instances LP-1 + LP-2 / **7.5 s** | 1 `.rfa` (`lp1_eaton_prl2x_100a_42sp_480y_277.rfa`), stage L1, crud instance LP-1 / **4.6 s** (4.6 s again on the final head) |
  | `an electrical room 20x15 ft with a 400 A distribution panel DP-1` | 2 `.rfa`, DP-1 + DP-2 / **7.8 s** | 1 `.rfa` (`dp1_eaton_prl2x_400a_42sp_480y_277.rfa`), DP-1 / **5.3 s** (4.6 s on the final head) |

  Both *after* outputs: `tools/rvt_validate.py prompt_room.rvt --json …` →
  `ok: true, error 0, warning 1, info 2` (the one warning is the pre-existing
  DataStorage Extensible-Storage decode gap, present on the *before* outputs and
  the base too). Manifest `prompt_coverage.understood` now reads
  `[('lighting panel', count 1, tags ['LP-1']), ('LP-1', 'equipment tag')]`,
  `ignored_words == []`. Status stamp unchanged (`PROOF-ONLY …`, delivered).
  Steer #108: one phantom family fewer is ~2.5–3 s (≈35–40 %) off a named
  single-panel prompt job, with no engine change.

* `/verify` (this repo's build-and-drive recipe), final head: `tools/frontdoor.py author
  --prompt "an electrical room with 6 panels"` → PP-1..PP-6, `VALID errors 0` (unchanged
  guard); `--prompt ""` → exit 3 `FAILED (empty prompt)`; `"please make me something nice
  named LP-1"` → one LP-1 (a bare tag stands for one item — same as before the change);
  bare-unzip plugin, system `python3 skills/tekton-author/scripts/_bootstrap.py go author
  --prompt "…one 100 A lighting panel LP-1"` → `go.ready true`, 1 family
  (`lp1_eaton_prl2x_100a_42sp_480y_277.rfa`), PROOF-ONLY delivered, **4.2 s wall**.
  `tools/provenance.py` ran (0.8 s) but a fresh clone has no baselines (`unbaselined 3125`)
  — not evidence either way here; the change adds no bytes to any output (parser only).
* `/simplify` pass run before the final commit (4 review agents): applied — `abbr`
  named groups instead of an `isalpha()/len<=4` heuristic, `ref_end` evaluated once
  per match + one stable sort, shared `_NAMING_VERBS`, hoisted `_RE_COUNT_WORD/_TOK`
  (were inline literals compiled per clause), one `issue_tag`, plain dedupe loop, no
  redundant `wlow`. Skipped on purpose — calling `rvt.ifc.intent._norm_tag` for tag
  canonicalisation (another stream's private helper, and it would rewrite the
  user's literal `LP1` to `LP-1`), and hoisting one repo-wide tag-token regex shared
  with `convert/rvt_to_ifc.py` / `ifc/intent.py` (outside territory → follow-up).

## 3. Findings / open questions (filed, not fixed here — out of territory or out of scope)

* Three tag-token grammars now exist (`prompt_intent._TAG_TOKEN`,
  `convert/rvt_to_ifc._TAG_TOKEN_RX`, `ifc/intent._norm_tag`) and differ at the
  edges (letter suffix `PP-3A`, `MDP-2`, hyphen-less `DP1`). Worth one shared
  definition next to `_norm_tag` → follow-up task issue, `Refs #101`.

* `an MDP panel` / `a DP panelboard` (abbreviation *followed by* the generic noun)
  still yields two items (DP-1 + PP-1): the generic `panels?` kind and the
  abbreviation each match once. Same family of grammar bug, different mechanism
  (noun–noun apposition, not tag mention) → follow-up task issue, `Refs #101`.
* Mounting words (`flush`, `surface`) are parsed into `item.mounting` but never
  marked consumed, so they show up in `coverage.ignored_words` — pre-existing,
  cosmetic, noted for the same follow-up.
* A digit-less bare `MSB` *outside* a fed-from clause is still read as the noun
  "an MSB" (by design — it is indistinguishable from the abbreviation); it only
  double-counts if the same prompt also says "main switchboard" without naming it,
  and then auto-numbering yields MSB + MSB-2 exactly as before.

## BRANCH STATE

* Branch `cam/101-prompt-tag-mention` from `origin/main` @ 21a9c49; issue #101
  claimed (`/claim s=eng101`, assignee cam-karagitz).
* Files: `src/rvt/frontdoor/prompt_intent.py`, `tests/test_frontdoor.py`,
  `docs/inbox/prompt-tag-mention.md`, mirror `plugin/lib/src/rvt/frontdoor/prompt_intent.py`.
* Gates run this session: listed in §2 (all green). Not run: the full suite
  (SUITE-COORDINATION), viewer round (parser-only change; output bytes for an
  *unnamed* prompt are unchanged — same items, same tags).
* Shipped vs staged: everything is in the PR; nothing staged for the viewer;
  `tekton-plugin.zip` regenerated locally, not committed (git-ignored).
