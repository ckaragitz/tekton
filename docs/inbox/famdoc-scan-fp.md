# FAMDOC-SCAN-FP — the donor-id byte-scan false positive, fixed at the raise sites

Stream: **famdoc-scan-fp** (2026-08-09, issue #12, branch `cam/12-famdoc-donor-scan`).
Charter: `docs/inbox/build-2025.md` §3 diagnosed that `author_family_adocument`'s
zero-donor byte scan can flag a monotone index table read one byte off as a
"donor id" (2025 base: element 18432 == 72<<8) and mitigated it with a
context-scoped monkeypatch in `release_ctx`; the permanent fix it PROPOSED —
corroborate a byte hit against the schema-decoded tree at the raise site
itself — is what this stream lands, so every release path (2026 included)
gets it and the mitigation goes away.

**DONE state (issue #12's three bullets): raise only on tree-corroborated ids,
cross-field windows reported as `false_positive_windows` — at BOTH scan sites
(`author_family_adocument` gate 6 and `provenance_scan_v2` check
`zero_donor_id_byte_hits`); the `release_ctx` step (8) mitigation REMOVED
(no-op comment left pointing here); a test that reproduces the misaligned
window from our own authored payload (fails on the pre-fix source with the
exact build-2025 error, passes after).**

---

## 1. What was built

`src/rvt/famgen/famdoc_adoc.py`

* `_tree_int_leaves(tree)` — every integer leaf of a decoded value tree
  under ANY key.  Deliberately a strict superset of the id-named census
  (`ADocument.element_ids`): counters, ordinals and sizes count too, so the
  corroboration can only err towards "genuine".
* `corroborated_donor_scan(payload, tree, donor_ids, *, trailer=None)`
  — runs `genesis_assemble.byte_scan_ids(payload, donor_ids)` (unchanged, still the independent instrument) and adjudicates its hits:
  1. **Premise verified locally, not trusted from the caller:**
     `encode_latest(tree, trailer) == payload` byte-for-byte.  If not, the raw
     scan is returned untouched (`"corroboration": "skipped: …"`) — hits stand.
  2. `carried = donor_ids ∩ int-leaves(tree)`.  Because every payload byte is
     produced from a tree leaf, an i64 window equal to a donor id is a real
     carried reference **iff** some integer leaf holds that value; a window no
     leaf holds straddles two fields — the scan's own documented
     false-positive class (`byte_scan_ids` docstring: "id-shaped windows
     inside doubles / adjacent fields").
  3. Genuine hits are **re-counted exactly** by re-scanning the payload
     against `carried` (so `byte_scan_ids`' top-12 `examples` truncation can
     never hide one).  They stay in `hits`/`distinct`/`examples` and remain
     fatal at every raise site, unchanged.
  4. Uncorroborated windows move to `false_positive_windows` with a
     `false_positive_note`; `raw_window_hits` keeps
     the unadjudicated numbers for the record.  Nothing is dropped silently.
* Wired at gate 6 of `author_family_adocument` (the `RuntimeError("donor
  element ids survive …")` site — the raise itself is untouched) and in
  `provenance_scan_v2` (feeds `checks.zero_donor_id_byte_hits`).

`src/rvt/frontdoor/release_ctx.py` — step (8), the process-local
`byte_scan_ids` monkeypatch, deleted; a 4-line comment names where the rule
now lives.  Nothing else in the context changed.

Why this does not weaken hard rule 3: the decoded tree has no opaque byte
leaves (primitives decode to int/float/bool, strings to `str`, GUIDs to
`str`, `char` containers to lists of ints < 256 < the 4700 id floor), the
payload is proven to be exactly the encoding of that tree before anything is
reclassified, and the schema-typed dangling census (the gate just above)
remains the authority for id-typed leaves.  The only windows reclassified are
ones no field of the document holds as a value.

## 2. Evidence (numbers)

* **Reproduction, from our own payload, in a fresh clone.**  The constructive
  panelboard family ADocument (1,333 B, schema from the bundled `G_ABPD.rvt`)
  carries the window value **61184 == 239<<8** — the AppInfo slot count read
  one byte off, the same `k<<8` mechanism as build-2025's 18432 — and no
  integer leaf 61184.  With a synthetic donor universe `{61184}` routed
  through `family_template_tree`:
  * pre-fix source (`git stash` of famdoc_adoc.py only):
    `RuntimeError: donor element ids survive in the payload: {'hits': 1,
    'distinct': 1, 'examples': [61184]}` — the build-2025 §3 error, verbatim
    class.
  * post-fix: authored; `gates.byte_scan_donor_ids = {hits: 0, universe: 1,
    false_positive_windows: [61184], raw_window_hits: 1, …}`.
* **Genuine stays fatal.**  Our self-Family id (start_id 18400, an i64
  ElementId leaf, 1 window hit) declared as a donor id → `RuntimeError:
  donor element ids survive` still raised; declared together with 61184 →
  still raised (a window never masks a genuine hit).  Same pair on
  `provenance_scan_v2` of the emitted `.rfa`: window → `zero_donor_id_byte_hits
  True` + recorded; genuine → `False`, `ok False`.
* `tests/test_famdoc_scan_fp.py` — **13 passed** in 2.3 s (fresh clone; needs
  only `plugin/assets/genesis/G_ABPD.rvt` + `tools/genesis_assemble.py`).
* Touched-area suites: `tests/test_famgen_adoc.py tests/test_famdoc_final.py
  tests/test_famdoc_blobs.py tests/test_target2025.py
  tests/test_frontdoor_standalone.py` — **76 passed, 44 skipped** (skips =
  vendor `.rfa` / experiments ladders absent, as designed) in 48 s.
* Front door, mitigation removed, both releases:
  `frontdoor.py author --prompt "a 400 A distribution panel" --target-version {2025,2026}`
  → `ok=True`, family `.rfa` family-mode **VALID**, `rvt_validate.py --family`
  ok, provenance **ok, 0 suspects**, `zero_donor_id_byte_hits True` on both.
  (The 2025 *combined* `.rvt` reports the pre-existing `FOUR-REGISTRY
  INCOHERENCE` semantic error — identical on a build made before this change;
  that is issue #14's 2025 famload lane, not this stream.)
* CI shard / plugin gates: see BRANCH STATE.

## 3. Findings

* Since PR #53 the bundled-base (cloud / plugin) path authors from the
  CONSTRUCTIVE famdoc tree with an empty donor universe, so on that path the
  author-site scan is inert and only `provenance_scan_v2` scans (against the
  project base's 2,883 ids).  The vendor-`.rfa` archetype path (dev machines,
  `$RVT_FAMILY_DONOR`) still scans at both sites.  The fix covers both.
* The `k<<8` window class is generic, not a 2025 quirk: any fixed table of
  small integers serialized as i64 produces `k<<8` at offset +1 (`k<<16` at
  +2 …).  Whether it *fires* depends only on whether the donor universe
  happens to contain such a value — which is why 2026 was silent and 2025 was
  not.

* Layer choice (checked in review): the consumer/raise site is the right
  depth.  `byte_scan_ids` is by contract "independent of the schema decode";
  folding the tree into it would collapse the cross-check into the thing it
  checks.  The helper is generic (no year / id literal), so any future donor-
  universe consumer can call it.
* Analogue outside the territory, deliberately not touched:
  `tools/genesis_assemble.py` `stage_own_latest` scans the project-scale
  authored payload against the SAMPLE id universe (`sample_ids_after`) with no
  corroboration — but it is report-only (its note already accepts the ~0.2 %
  window residual) and nothing gates on it, so no follow-up issue is filed.
  `tekton-eval-kit/tekton-plugin/lib/**` is a frozen initial-import snapshot,
  not a `sync_plugin` mirror; it keeps the old raw scan by design.

## 4. Open questions

None for this stream.  (Follow-ups not filed: #14 already owns the 2025
combined-file registry coherence; the genesis_assemble analogue above gates
nothing.)

## BRANCH STATE

* Branch `cam/12-famdoc-donor-scan` from `main` @ af59d26; PR closes #12.
* Files written: `src/rvt/famgen/famdoc_adoc.py` (+helper, 2 sites),
  `src/rvt/frontdoor/release_ctx.py` (step 8 removed),
  `tests/test_famdoc_scan_fp.py` (new, 13 tests), this record, and the
  `tools/sync_plugin.py` mirrors under `plugin/lib/`.
* Gates run (this session, fresh cloud clone): stream tests 13 passed;
  famdoc/famgen/target2025/standalone suites 76 passed / 44 skipped;
  `tools/sync_plugin.py` then `--check` clean; `plugin/scripts/validate_plugin.py`
  ok; `tools/dev/check_portable_paths.py` ok; CI shard (`tests/ci_shard.txt`,
  `RVT_SKIP_LARGE=1`) green — counts in the PR body.
* Nothing staged for the viewer; no `.rvt`/`.rfa` committed; no ledger change.

## Follow-up (review nit on #79, same branch name restarted from main)

`byte_scan_ids` names at most its 12 most common values, so with more than 12
distinct uncorroborated windows the `false_positive_windows` list was silently
partial.  The ledger now also carries `raw_window_distinct` and
`false_positive_windows_complete` (true iff every distinct uncorroborated
window is named), so a truncated list says so.  The fatal/non-fatal decision
was never affected (exact re-scan against `carried`).  Stream tests 13 passed;
CI shard 136 passed / 23 skipped; `sync_plugin.py --check` clean.
