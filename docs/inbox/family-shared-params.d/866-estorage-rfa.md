# 866 DONE 4: the Extensible-Storage catalog reads a family by its path

Stream **family-shared-params** (fragment). Issue #866 DONE 4. Territory: `src/rvt/estorage.py` (path branches only), `tests/test_estorage_rfa_866.py` and its drop-in, this fragment, and the `plugin/lib` mirror.

## What changed

`rvt.estorage.schemas()` took an `.rvt` path, a Document or a corpus project name. An `.rfa` path fell through to the project-name branch and raised `ESSchemaError("cannot locate Global/Latest")`, and its archive-schema decoder silently fell back to the default one.

A family is the same container, so three places now accept `.rfa` as well as `.rvt`:
- the catalog source (`_global_latest_bytes`);
- the decoder (`_decoder_for`);
- the CLI's path test (`_doc_path`), so a bare `name.rfa` is a path, as a bare `name.rvt` always was.

## Evidence

- **Our generated device:** `tests/test_estorage_rfa_866.py`, 5 passed.
  - The catalog reads it: empty, with its reason, because our families store no ES schema.
  - The CLI reports it.
  - Bare `x.rfa` / `X.RFA` / `x.rvt` are taken as paths.
  - On main, 3 of the 5 fail.
- **The owner's reference families** (private, counts only):
  - 6 of 6 sampled `.rfa` files read their catalog inside their own release, with 6 to 10 schemas each.
  - The CLI on one reports 7 schemas with its tracking table.
- **Suites:** `tests/test_estorage*.py` gives 35 passed / 12 skipped (the skips need `samples/`), and `tests/test_plugin_sync.py` 9 passed. `sync_plugin.py --check` is in sync.
  - Corrected in the #875 PR: this line first read "44 passed / 12 skipped" for the two runs together, a sum an independent reviewer could not reproduce.
- **Release context:** the CLI reads a file under its own release. A library call `schemas(path)` reads under whatever release is in force, as it always did for a `.rvt`; its docstring now says so (#875 PR).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`, from main `b9bdfb4`.
- Written: `src/rvt/estorage.py`, `plugin/lib/src/rvt/estorage.py`, `tests/test_estorage_rfa_866.py`, `tests/ci_shard.d/866-estorage-rfa.txt`, this fragment.
- Staged: nothing.
- No certification claim.
