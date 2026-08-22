# #742 — model tokens in qualifier gaps, work-on-existing-gear context, `all equipment: X <noun>`, `both by X`, brand-vs-parent cells

Stream: MEP taxonomy / maker attachment (index: `docs/inbox/mep-taxonomy.md`). Follow-up of the sixth
(🟡) independent review of PR #741 (#739). Territory: `src/rvt/frontdoor/prompt_intent.py`
(`_attach_makers` and its regex block), `src/rvt/famgen/vendors.py` (`_declared`), tests.

## What was built

1. **Model / configuration tokens ride like ratings.** A token with a digit *and* a letter / `%` / `#`
   (`PRL1a`, `N3R`, `4X`, `NEMA-3R`, `3P4W`, `1P3W`, `K-13`, `P1`, `200%`, `Cat# PRL1A`) between a
   place-word qualifier and its noun no longer turns the qualifier into a place, and between a maker
   and its noun it counts as adjacent — ONE token classifier (`_model_token`) serves both
   `_only_ratings` (adjacency) and `_qualifier_gap` (place vs qualifier); `_RE_RATING_WORDS` also
   learned `nema-3r`, `3P4W`, `3Ø`, `200% (rated) neutral`, `Cat#`. Both gap tests are now **token
   loops** over the rating-stripped gap instead of one large regex: the first attempt at a shared
   model-token *regex* (`\d[\w%#./-]*[a-z%#][\w%#./-]*` under an outer `*`) backtracked
   catastrophically on `two Trane 1111…(40)… custom panels` (probe hung > 5 min); the token loop does
   the same prompt in 2.8 ms and has no nested quantifier to blow up.
2. **Work on existing gear is context.** `_RE_CONTEXT_BEFORE` also takes `replace/replacing`,
   `remove/removing`, `demo/demolish(ing)`, `salvage`, `relocate`, `reuse`, `refeed`, `coordinate with`
   (+ optional `the|an|our|all` + `existing|old`): `salvage the Square D equipment; provide 4 new
   panels`, `demo the Siemens gear; …`, `remove Siemens equipment. Provide …`, `coordinate with
   Siemens equipment supplier; …`, `replace the Siemens equipment with 4 panels` → nothing stamped +
   "maker X names existing or neighbouring equipment, not the new work" (`main`: X on every panel,
   silently, or an "outside any clause" warning). `replace the existing Eaton panel with two new
   Kohler panels` keeps Eaton on the replaced panel and Kohler (declared, said) on the new ones — the
   context branch reaches the noun it qualifies first.
3. **`all equipment: X <noun>` introduces a list.** The `is|are|:|=` connector of `all equipment …` /
   `everything …` is a named group; when the maker after it is adjacent to an equipment noun
   (`all equipment: Eaton panels and a 45 kVA transformer`, `all equipment is Eaton panels and Hammond
   transformers`) the cue is dropped and each maker rides its noun (T1 `None` / Hammond); `all
   equipment: Eaton. two panels …` and `all equipment by Eaton: …` still name the whole job.
4. **`both by X`.** The group before it when that group holds the two (`two panels, both by Eaton`,
   `a switchboard feeding two panels, both by Eaton` → the panels only), else the two groups before it
   (`two panels and a transformer, both by Eaton, and 6 receptacles` → panels + transformer, receptacles
   none), else — three or more candidates — nothing, with "maker Eaton: 'both' follows more than two
   pieces of equipment -- applied to nothing; name the two". `X only` keeps binding the last noun.
5. **Brand vs parent in one cell.** `X by Y` / `X, an Y brand` / `X, a division of Y` collapses to X
   only when Y is X's recorded parent (`Square D by Schneider Electric`) or the two share no equipment
   kind (`Cooper Lighting Solutions by Eaton`, on any contract kind); two makers of the same equipment
   (`Eaton by Siemens`, `Siemens by Eaton`) name two makers and declare neither, said.
6. Record wording of #739's item 2 corrected (one sentence, marked).

## Evidence

| prompt | `main` (`85615b6`) | this branch |
|---|---|---|
| `an Eaton house PRL1a panel and six tenant panels` | PP-1 `None`, `Eaton` ignored | PP-1 Eaton |
| `two Eaton lab 3P4W 225A panels`, `an Eaton house 1P3W 200A panel`, `two Eaton lab 3Ø 4W panels`, `two Eaton site 3R / N3R / 4X / NEMA-3R lighting panels`, `an Eaton house Cat# PRL1A panel`, `two Siemens data center P1 panels 400 A`, `an Eaton station K-13 45 kVA transformer`, `two Eaton lab 200% neutral panels` | `None`, name ignored | maker on the noun |
| `two Kohler 3P4W / N3R / K-13 panels` | Kohler ignored | Kohler declared + "never presented as that maker's product" |
| `salvage the Square D equipment; provide 4 new panels` | PP-1..4 Square D | nothing + context warning |
| `demo the Siemens gear; provide …`, `remove Siemens equipment. Provide …`, `coordinate with Siemens equipment supplier; …`, `replace the Siemens equipment with 4 panels` | Siemens job-wide or "outside any clause" | nothing + context warning |
| `replace the existing Eaton panel with two new Kohler panels` | PP-1 Eaton, PP-2/3 Kohler | same (kept) |
| `all equipment: Eaton panels and a 45 kVA transformer` | T1 Eaton too | T1 `None`, PP Eaton |
| `everything: Eaton panels and a Hammond 45 kVA transformer` | T1 Eaton | T1 Hammond, PP Eaton |
| `two panels and a transformer, both by Eaton, and 6 receptacles …` | T1 only, silent | PP + T1 Eaton, receptacles none |
| `4 panels, a transformer and a switchboard, both by Eaton, …` | last noun only | nothing + "'both' follows more than two…" |
| cell `Eaton by Siemens` on `transformer_dry` | collapsed to Eaton | two makers, neither |
| hostile gaps: 40 digits / `A1`×30 / `A1-/`×20 / 60× `480/277V` | 0.7 / – / – / 3.9 ms | 2.8 / 0.8 / 1.1 / 22 ms (linear; the 60× voltage case is the extractor loop, unchanged in shape) |

Item counts in two of those prompts (`K-13` → 13 transformers, `5-20R` → 5 receptacles) are the
pre-existing count grammar (#740), not judged or changed here.

Gates: `tests/test_maker_qualifiers_742.py` 46 passed (new, + `tests/ci_shard.d/742-maker-qualifiers.txt`);
`tests/test_maker_adjacency_739.py tests/test_taxonomy_wiring_692.py tests/test_prompt_intent.py tests/test_taxonomy_692.py`
371 passed; `tests/test_frontdoor.py tests/test_plugin_sync.py tests/test_ifc_intent.py` 122 passed / 5 skipped;
`tools/sync_plugin.py` validation passed (mirrors committed); `make_family.py vendors --check` 50 vendors / 120 lines / 0 problems.

## Findings

- A shared *regex* for "model token" is a trap: any `\d[…]*[a-z][…]*` shape under an outer star is
  exponential on digit runs. Classifying split tokens in Python is both simpler and linear; the
  rating extractors still run first, so "adjacent" keeps meaning "what the clause reads as ratings".
- `pkill -f <pattern>` in the same shell line as a heredoc containing the pattern kills the shell
  itself (cost one re-run here) — worth remembering for probe hygiene.

## Open questions

- `X only` after two nouns (`two panels and a transformer, Eaton only, …`) still binds the last noun;
  symmetrical treatment with `both` would need evidence of how people write it.

## BRANCH STATE

- Branch `cam/742-maker-qualifiers` from `main` @ `85615b6`; files: `src/rvt/frontdoor/prompt_intent.py`,
  `src/rvt/famgen/vendors.py`, their `plugin/lib` mirrors, `tests/test_maker_qualifiers_742.py`,
  `tests/ci_shard.d/742-maker-qualifiers.txt`, this fragment, one sentence in `739-maker-adjacency.md`.
- Nothing staged for the viewer; no certification claim; no hot file touched.
