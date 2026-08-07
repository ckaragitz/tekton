# tekton — vendored third-party dependency

This folder holds the ONE third-party module the bundled `rvt` engine
imports at read time, so that a tekton skill never has to `pip install`
anything on the hot path:

| Package | Version | License | Why it is here |
|---|---|---|---|
| `olefile` | 0.47 | BSD-2-Clause style (see `olefile/LICENSE.txt`, incl. the historical PIL notice) | `rvt.container.open_rvt` reads the `.rvt` compound file (OLE2/CFB) through `olefile` — the engine's only third-party import |

Files are an unmodified copy of the released `olefile` 0.47 package
(`__init__.py`, `olefile.py`, `LICENSE.txt`, `CONTRIBUTORS.txt`).
`skills/_shared/tekton_env.py` adds this folder to `sys.path` ONLY when
`import olefile` fails, so an environment that already has `olefile`
installed keeps using its own copy.

Do not add engine code or product data here; this folder is strictly for
license-checked third-party runtime dependencies.
