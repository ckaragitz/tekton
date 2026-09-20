# specsheet-ingestion — a user's spec sheet is a SOURCE

Charter: **#688** (child of #687, steer S-2026-08-11-d). A PDF the user hands
us is the honest route to a manufacturer's real dimensions — the one thing
S-2026-08-11-c forbids the model to recall from memory. Read its table, build
the `.rfa`, cite the page.

Index + fragments (`docs/inbox/README.md`): one fragment per PR, nobody
appends to anyone else's.

- `688-reader.md` — the reader: a stdlib PDF extractor with positions, a
  layout layer, a label vocabulary as data, and cited values. DONE 2–4 and
  the reader half of DONE 6. Both backends measured against each other.
- `688-pdf-route.md` — the `pdf` INPUT kind, `route run --pdf`, and the
  identity lane. DONE 1 and DONE 5, plus #797's mutation probes. Fixes the
  single-prism `make_generic_model` path, which accepted `identity` /
  `text_params` / `numeric_params` and wrote none of them.

## Standing summary

The reader is `src/rvt/specsheet/` — four layers on purpose (`pdftext` →
`layout` → `vocab` → `sheet`), so the *extraction* and the *inference* can be
checked separately and either can be replaced without the other. The optional
`[pdf]` extra feeds the same `Page`/`Glyph` shape, so which backend is
installed changes the extraction and never the inference.

DONE 1–6 are now covered except the desktop half of "functional": a
sheet-built `.rfa` validates and carries its citations, and no desktop-Revit
verdict exists for it (hard rule 4). #687's constraints / visibility / tag
surfaces are separate streams and untouched here.
