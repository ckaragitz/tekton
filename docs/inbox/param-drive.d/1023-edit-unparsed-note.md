# #1023 — a family edit with a clause the grammar cannot read says so

## What was built
- **The silent drop.** `parse_family_edit` (`src/rvt/convert/modify_family.py`) put unreadable clauses into `parsed["unparsed"]`, which nothing showed the user. So `set Length; set Material = PVC` applied Material and dropped the bare `set Length` silently. The `.rvt` lane shows its unparsed clauses in its manifest; the family lane did not.
- **Now:** each unparsed clause becomes a note, `not applied: '<clause>' was not understood, nothing was changed for it (say: …grammar…)`. `modify_family` already reports notes as degradations, so the note reaches the record and the status the skill relays.
- **The family is still delivered** with the clauses that did read (hard rule 1). The note is the honest label, and refusing the whole edit was the alternative not taken. An edit in which nothing reads is still refused, as before.
- **The optional nits from the PR #1022 review, carried here:**
  1. A caption inside a quoted value that is a near-miss of a parameter (`difflib` ratio of at least 0.8, e.g. `Widht`, `Notes`), or that several parameters contain (`Diameter`), counts as a further edit. So `"x; set Widht 600 mm"` is refused, as the old split refused it, while `set screw included` and `set up later` stay text.
  2. `rvt._quoted.split_clauses` reads a fragment both with and without the span's closing quote. So `rename … to "x then move 1466502 by 1,0,0 ft"` is refused again. That PR had rewritten the #1019 test case to `…ft then spare"` to keep it refusing; this record now says so.
  3. **Correction to the #1021 record.** It says `test_edit_quoted_split_1017.py` was "otherwise unchanged". Its `_inv()` also gained the captions `Finish` and `Length`, which changes which fragments read.

## Evidence
- `tests/test_edit_unparsed_note_1023.py`, 43 cases:
  - three "not applied" notes;
  - one fully read edit with no note;
  - three near-miss refusals;
  - two texts still stored;
  - the closing-quote fragment;
  - a delivered-record degradation on a generated conduit;
  - ten value texts stored whole on a generated conduit and junction box (review round 1).
- An ADOPTERS row is added, plus the drop-in `tests/ci_shard.d/1023-edit-unparsed-note.txt`.
- **Suites:** `tests/test_edit_*.py`, `test_rvt_edit_quoted_split_1019`, `test_modify_family*`, `test_conftest_scaffolding`, `test_convert`, `test_router`, `test_convert_combo`, `test_reduce`, `test_frontdoor`, `test_frontdoor_json_strict`, `test_one_job_module`, `test_release_ctx_refusal`, `test_stagelog` and `test_plugin_sync` give **892 passed / 41 skipped** with `RVT_SKIP_LARGE=1` at the first head. After review round 1, the same set plus `tests/test_route*.py` gives **937 passed / 41 skipped**. `tools/sync_plugin.py --check` is clean.
- **Fuzz differentials against main a1e8d54:**

  | Lane / instrument | Seed | Texts | Silent fewer ops | Now accepted | Now refused | Refusal wording changed |
  |---|---|---|---|---|---|---|
  | Family, `r15/fuzz.py` | 5 | 40,000 | **0** | 0 | 9 | 40 |
  | Family, `r15/fuzz.py` | 77 | 40,000 | **0** | 0 | 12 | 34 |
  | `.rvt`, `q19/fz.py` | 5 | 30,000 | **0** | 0 | 10 | 7 |
  | `.rvt`, `q19/fz.py` | 77 | 30,000 | **0** | 0 | 11 | 6 |
  | Real conduit, `r18/real/fz.py` | 7 | 20,000 | **0** | 0 | 10 | 44 |

  Every new refusal is the safe side of nits 1–2: a leading apostrophe that pairs with a later possessive, now read as a further edit once the closing quote is stripped (for example, `'90s; mark 742670 as workers'`), or a near-miss caption.

## Review round 1 (PR #1024, head dd3f225, 🛑)
- **Blocking.** `_near_caption` counted raw substrings with no minimum length, and its `difflib` check ran on short keys. So common value text was refused on every real generated family: `"PVC; set in concrete"` ("in" sits inside Nominal Diameter, Fitting Angle and Finish), `"epoxy coated; set with epoxy"` ("with" scores 0.89 against "width"), and `"surface; set at 48 in AFF"`. The reviewer counted 258 of 2,940 fragment/family pairs flipping across 21 real families.
- **Fixed in `_near_caption`:**
  - keys under 4 characters are never near-misses;
  - "several parameters contain it" now counts whole caption words, so CamelCase captions are split first;
  - the `difflib` check runs only on keys of 5+ characters.
- **Also fixed in `_reads`.** A short word named a parameter through `param_by_caption`'s unique-substring rule, so "at" matched Material and "on" matched Conduit Standard. A key under 4 characters now names a parameter only by an exact caption.
- **Re-measured with the reviewer's `r20/fp.py`** (140 "set …" fragments × 21 real families, against main):
  - 26 pairs flip from text to "further edit", across 6 fragments. All are real parameter words that several captions share (`set load class` 13, `set rating later` 8) or exact captions (`set type B`, `set length in field`). The old split refused those too.
  - 66 pairs flip back to text, such as `set of four`, `set at 48 in` and `set on pad`. Main refused these.
    - On the old quote-blind split, some of these would have **written** through the short-substring rule: `set of four` → a parameter containing "of". That is a mis-targeted write; it is the fuzzy `param_by_caption` matching listed as still open in the #1014 record, and it is not changed here.
  - **Corrected in review round 2:** not every short-key flip was a mis-target (see below).
- **Visibility (the review's optional nit 1, carried):**
  - The family-edit route status now ends with `N clause(s) NOT applied (see caveats)` (`src/rvt/frontdoor/router.py`).
  - `tools/route.py`'s text output and the `modify_family` CLI print `(+N more …)` when they cut the caveats at 8. The notes were in `route.json`, `ROUTE.md`, `MANIFEST.md` and the skill's `go` JSON already.
- **Fuzz against main a1e8d54, after the fix:**

  | Lane / instrument | Seed | Silent fewer ops | Now accepted | Now refused |
  |---|---|---|---|---|
  | Family | 5 | **0** | 0 | 9 |
  | Family | 77 | **0** | 0 | 12 |
  | `.rvt` | 5 | **0** | 0 | 10 |
  | `.rvt` | 77 | **0** | 0 | 11 |
  | Real conduit | 7 | **0** | 0 | 10 |

  The new refusals hold edit-looking text: the misspelled `set Finsh 10 ft`, the ambiguous `set Diameter 3 in`, or a rename.

## Review round 2 (PR #1024, head 58932d2, 🛑)
- **Blocking.** The round-1 rule ("a key under 4 characters names a parameter only by an exact caption") also caught abbreviations that `param_by_caption` resolves correctly and that the grammar applies outside quotes:
  - `Len` → Length, `Out` → Outside Diameter, `Mat` → Material;
  - `kVA` → kVA Rating, `IP` → IP Rating, `Bus` → BusRating.
- Inside a quoted span those were stored silently as text. `set Material = "PVC; set Len 10 ft"` wrote one op where main refused. Real-conduit fuzz seed 31 had 3 such texts newly accepted.
- **The round-1 record line "every short-key flip is a mis-target" was wrong;** this corrects it.
- **Fixed with new `_abbreviates`.** A short key also names its resolved parameter when it starts the caption, or (3+ characters) starts one of the caption's words, CamelCase split. `at` / `of` / `it` / `as` / `to` / `per` / `the` / `and` / `box` stay text.
- **Re-measured:**
  - `r20/fp.py`: the only change from round 1 is `set out by surveyor` (4 conduit-family pairs), now refused, which is the safe side. Text → edit stays 26; edit → text is 62.
  - Real conduit, seeds 31 and 7: 0 silent fewer ops, 0 newly accepted, 9 / 10 now refused.
  - Family fuzz, seeds 4242 and 9001: 0 silent, 0 accepted, 10 / 20 now refused.
  - Suites (the round-1 set): **941 passed / 41 skipped**. `sync_plugin --check` is clean.

## Review round 3 (PR #1024, head 812b406, 🛑)
- **Blocking.** `_abbreviates` (prefix of the caption or of a caption word) still missed short keys that the old split applies to the meant parameter, so they were swallowed into a quoted value:
  - inner abbreviations: `Ht` → Height;
  - one-letter keys: `W` → Width;
  - unit tokens inside a caption: `kA` → ShortCircuitRatingkA, `kVA` in "Rated kVA", because `_split_camel` broke "kVA" into "k VA".
- **Correction.** The round-2 line saying `IP` and `kVA` are covered held only where they start the caption.
- **Fixed by inverting the rule, as the reviewer preferred.** A key under 4 characters that `param_by_caption` resolves **is** a further edit, unless it is in `_FUNCTION_WORDS`, a fixed list of prose words: a, an, and, as, at, be, by, do, for, if, in, is, it, its, no, nor, not, of, off, on, or, our, per, so, than, that, the, then, to, too, up, us, via, vs, we, with.
  - `out` is deliberately not in the list, because `Out` → Outside Diameter is a real abbreviation (round 2).
  - The rule errs toward refusal, which is recoverable. `_abbreviates` is removed.
- **Re-measured:**
  - **Enumeration** (`r22/keyenum.py`: every 1–3 character substring of every caption on the 21 real families × 3 values): 245 keys that old applies still read as text, and all of them are function words. Examples: `of` → Number of Lamps, `to` → Distance to Wall, `no` → Nominal Diameter, `be` → Bend Radius, `us` → BusRating. Every one of those old writes is a mis-target **on these 21 families** (see round 4 for captions that are, or start with, a function word). At round 3's head the count was 5,148.
  - **`r20/fp.py`:** text → edit stays 26. Edit → text is now 60, because `set box flush` is refused on 2 families (`box` → Backbox Size), the safe side.
  - **Family fuzz, seed 2201:** 0 silent, 13 now refused, 1 newly accepted. The accepted one is `('q then set a r')`, where old wrote Mark = `r'` through "a" ⊂ Mark, a mis-target.
  - **Real conduit,** seeds 2203 and 31: 0 silent, 0 newly accepted, 10 / 9 now refused.
  - **Suites:** **948 passed / 41 skipped**. `sync_plugin --check` is clean.

## Review round 4 (PR #1024, head 65b68ab, 🛑)
- **Blocking.** A caption that is *exactly* a listed word (a single-letter dimension `A`, or `On`, `No`, `Up`) was swallowed into a quoted value: `set Mark = 'see note; set A 600 mm'` stored one op, where main refused and the unquoted clause applies A. The same happened to a function word that is the *first word* of the resolved caption (`no` → "No. of Poles", `Up` → "Up Light", `ON` → "ON Delay"), which the old split applied. None of the 21 real families has such a caption, so the round-3 measurements stood for them; the code comment's "never a further edit" did not hold in general.
- **Fixed with new `_leads(key, caption)`:** a function word still names the parameter when it **is** the caption or its first word. When `param_by_caption` resolves nothing (ambiguous, e.g. `A` with "Mark" and "A Phase Load"), a key that leads any caption is a further edit too; old refused those unquoted.
- **Re-measured:**
  - **`r23/fw.py`** (every listed word as an exact caption and as a leading word, in Title and UPPER case): all 95 quoted cases now refuse.
  - **`r23/fuzzA.py`** (fuzz with captions `A`, `On` and `No. of Poles` added), seeds 2718 and 3141: 0 newly accepted (10 at round 4's head), 0 silent; 8 and 16 now refused.
  - **`r20/fp.py`:** text → edit 27, edit → text 60. The only change is `set box flush` refused on one more family (`box` leads "Box …"), the safe side.
  - **Enumeration on the 21 real families:** unchanged, 245 function-word mis-targets read as text.
  - **Suites:** **954 passed / 41 skipped**.

## Review round 5 (PR #1024, head bff499b, 🛑)
- **Blocking.** This is the mirror image of round 4. A function word that is the *last* word of the caption was swallowed into a quoted value: `No` in "Circuit No" / "Item No" / "Panel No.", `AT` in "Breaker AT", `ON` in "Lamp ON", `In` in "Rated Current In". The old split applied those unquoted, and main refused them quoted. `r24/probe/fuzzL.py` (seed 4711) had 7 such texts newly accepted.
- **Fixed.** `_leads` now accepts the whole caption, its first word or its last word. Only an inner word (`of` in Number of Lamps, `to` in Distance to Wall) or a piece of a word (`at` in Material, `up` in Setup, `a` in Mark) stays text. Each of those is a mis-target when the old split writes it.
- **Optional nit 1, carried.** `than` / `that` / `then` / `with` are dropped from `_FUNCTION_WORDS`, because keys of 4+ characters never consult it. The comment now says so.
- **Known gap (optional nit 2).** A digit-led caption ("2nd Floor") cannot be named by `set 2nd …`. Unquoted that is now a "not applied" note, quoted it is text; the old split never applied it either.
- **Re-measured:**
  - **`r24/probe/lastw.py`:** the only quoted-stored, unquoted-applied cases left are `up` → Setup and `a` → Mark, both substring mis-targets.
  - **`fuzzL`, seed 4711:** 0 newly accepted (7 before), 5 now refused.
  - **Fresh seed 6067:** family fuzz 0 silent, 17 now refused; real conduit 0 silent, 7 now refused.
  - **`r20/fp.py`:** text → edit 29, edit → text 60. `set rating later` is refused on 2 more families, where Rating ends the shared captions (the safe side).
  - **Suites:** **958 passed / 41 skipped**.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py`, `src/rvt/_quoted.py` and `src/rvt/frontdoor/router.py`, with their `plugin/lib` mirrors;
  - `tools/route.py` (and its plugin copy);
  - `tests/test_edit_unparsed_note_1023.py` (new);
  - `tests/ci_shard.d/1023-edit-unparsed-note.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).
