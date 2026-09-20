"""test_specsheet_route_688.py -- the `pdf` INPUT: a spec sheet routes to a .rfa.

#688 DONE 1 (``route run --pdf sheet.pdf --output rfa``, and ``--pdf``
alongside ``--prompt``) and DONE 5 (the sheet's manufacturer / model land on
the family's identity parameters).  The reader itself is tested in
``test_specsheet_{pdftext,sheet,backend}_688.py``; this file is about what
the ROUTE does with what the reader found.

THE THREE CLAIMS WORTH BREAKING, because each one is a way the lane could
look right and be dishonest:

1. **The dimensions are FACT-tier and cite the document.**  If they came
   back ``given`` or ``nominal`` the file would still build and validate --
   and the one thing this lane exists to do, turn a user's document into
   sourced member data (steer S-2026-08-11-d), would not have happened.
2. **The prompt cannot outrank a number the sheet states.**  A ``--prompt``
   beside the ``--pdf`` is there to name the product for the archetype
   fallback.  If it could also override a dimension, a typed number would
   end up wearing a citation to the user's own document.
3. **The file still comes out when the sheet fails** (hard rule 1).  An
   image-only PDF is refused BY NAME and the archetype lane delivers a
   nominal family -- with the caveats saying, in the first line, that the
   sizes were not read from the sheet.

A synthetic fixture proves the parser, not the product: these PDFs are
written by ``tests/fixtures_pdf.py`` because no vendor document may be
committed (hard rules 3 and 6).  What they cannot prove is desktop
behaviour, and nothing here claims it -- a sheet-built ``.rfa`` is
validator-gated and PROOF-ONLY like every other family we generate.
"""
import json
import os

import pytest

import fixtures_pdf as FP

from rvt.frontdoor import matrix as MX, router as R          # noqa: E402
from rvt.specsheet import sheet as S                          # noqa: E402
from rvt.specsheet.famspec_from_sheet import plan_from_sheet  # noqa: E402


def _sheet_pdf(tmp_path, name="probeworks-pw400.pdf", **kw):
    return FP.build_pdf(str(tmp_path / name), [FP.spec_sheet_draws()], **kw)


def _run(tmp_path, out, **inputs):
    return R.route(inputs, "rfa", out=str(tmp_path / out), quiet=True)


# ===========================================================================
# 1. the matrix gained a real INPUT, not just a cell
# ===========================================================================

def test_pdf_is_an_input_kind_with_all_three_outputs_enumerated():
    assert "pdf" in MX.INPUT_KINDS
    for o in MX.OUTPUT_KINDS:
        assert MX.cell_for(["pdf"], o) is not None, o


def test_the_pdf_to_rfa_cell_claims_works_and_names_a_registered_route():
    for inputs in (["pdf"], ["pdf", "prompt"]):
        c = MX.cell_for(inputs, "rfa")
        assert c.status == MX.STATUS_WORKS, inputs
        assert c.route == "pdf_to_rfa" and c.route in R._IMPLS
        assert set(c.stages) <= set(MX.STAGES)


@pytest.mark.parametrize("output", ["rvt", "ifc"])
def test_the_unbuilt_pdf_cells_say_why_and_point_somewhere_real(output):
    """A missing cell is only honest if its 'closest' is a cell that works."""
    c = MX.cell_for(["pdf"], output)
    assert c.status == MX.STATUS_MISSING and c.route is None
    assert c.missing_reason and c.hint
    assert c.closest in MX.CELLS
    assert MX.CELLS[c.closest].status != MX.STATUS_MISSING


def test_an_unknown_input_kind_is_still_rejected_by_name():
    """Adding a kind must not have loosened the door."""
    with pytest.raises(R.RouteError) as e:
        R.route({"docx": "x"}, "rfa")
    assert "docx" in str(e.value) and "pdf" in str(e.value)


def test_a_pdf_path_that_does_not_exist_is_ONE_line_not_a_traceback(tmp_path):
    with pytest.raises(R.RouteError) as e:
        R.route({"pdf": str(tmp_path / "nope.pdf")}, "rfa")
    assert "--pdf file not found" in str(e.value)


# ===========================================================================
# 2. the built family, and where its numbers came from
# ===========================================================================

def test_a_spec_sheet_builds_a_family_whose_dimensions_are_FACTS(tmp_path):
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path))
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"])

    rep = json.loads(open(res.files["rfa_report"]).read())
    assert rep["validate"]["family_mode"]["verdict"] == "VALID"
    assert rep["validate"]["family_mode"]["n_errors"] == 0

    vals = rep["facts"]["values"]
    # SHEET_ROWS states 62.0 in / 20-1/2 in / 5.75 in
    assert vals["height_in"]["value"] == pytest.approx(62.0)
    assert vals["width_in"]["value"] == pytest.approx(20.5)
    assert vals["depth_in"]["value"] == pytest.approx(5.75)
    for key in ("height_in", "width_in", "depth_in"):
        assert vals[key]["provenance"] == "fact", key
        assert "probeworks-pw400.pdf" in vals[key]["source"], key


def test_every_used_value_carries_a_page_and_row_citation(tmp_path):
    parsed = S.read_sheet(_sheet_pdf(tmp_path))
    plan = plan_from_sheet(parsed)
    assert plan.buildable
    for line in plan.citations():
        assert " p1 r" in line, line     # document, page, row, and the raw text
    assert any(c.startswith("height_ft <-") for c in plan.citations())


def test_the_parse_is_delivered_BEFORE_it_is_trusted(tmp_path):
    """DONE 4: a wrong column must be visible, not silently built."""
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path))
    doc = json.loads(open(res.files["sheet"]).read())
    assert doc["tables"] and doc["values"]
    text = open(res.files["sheet_table"]).read()
    assert "as read" in text and "values taken" in text
    assert "Main Bus Rating" in text          # a row we did NOT map to a dimension
    plan = json.loads(open(res.files["sheet_plan"]).read())
    assert plan["buildable"] and plan["citations"]


def test_rows_read_but_not_used_are_SHOWN_not_dropped(tmp_path):
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path))
    # the fixture's banner lines name no field we know
    assert any("PROBEWORKS INDUSTRIES" in c for c in res.caveats)


# ===========================================================================
# 3. the identity lane (DONE 5)
# ===========================================================================

def _vendor_pdf(tmp_path, maker="Probeworks Industries", model="PW-400-42"):
    draws = [(72.0, 754.0, "Manufacturer"), (300.0, 754.0, maker),
             (72.0, 736.0, "Catalog Number"), (300.0, 736.0, model)]
    for i, (label, value) in enumerate(FP.SHEET_ROWS):
        y = 700.0 - i * 18.0
        draws += [(72.0, y, label), (300.0, y, value)]
    return FP.build_pdf(str(tmp_path / "vendor.pdf"), [draws])


def test_the_sheets_manufacturer_and_model_reach_the_TYPE_ROW(tmp_path):
    """DONE 5, asserted on the document rather than on the plan.

    The plan holding ``identity`` proves the mapping; only the type row
    proves the family carries it. ``make_generic_model``'s single-prism path
    accepted ``identity`` and wrote none of it until this lane needed it --
    exactly the gap a plan-level assertion would have missed.
    """
    from rvt.famgen import skeleton as SK
    parsed = S.read_sheet(_vendor_pdf(tmp_path))
    plan = plan_from_sheet(parsed)
    assert plan.kwargs["identity"] == {"Manufacturer": "Probeworks Industries",
                                       "Model": "PW-400-42"}
    from rvt.famgen import factory as FA
    prod = FA.make_generic_model(**plan.kwargs)
    _name, row = prod.doc.types[0]
    ids = SK._TYPE_TEXT_PARAMS
    assert row[ids["manufacturer"]] == "Probeworks Industries"
    assert row[ids["model"]] == "PW-400-42"


def test_the_sheets_other_readings_reach_the_family_WITH_THEIR_VALUES(tmp_path):
    """Authored AND filled.

    An earlier version of this asserted only that the captions existed, and
    a mutant that authored the parameters and wrote none of their values
    walked straight through it: a blank "Voltage" on the type row is not the
    sheet's voltage, it is a parameter that lost its reading.
    """
    from rvt.famgen import factory as FA
    res = _run(tmp_path, "out", pdf=_vendor_pdf(tmp_path))
    params = json.loads(open(res.files["rfa_report"]).read())["family"]["parameters"]
    for cap in ("Voltage", "Enclosure Rating", "Amps", "SCCR"):
        assert cap in params, (cap, params)

    plan = plan_from_sheet(S.read_sheet(_vendor_pdf(tmp_path)))
    prod = FA.make_generic_model(**plan.kwargs)
    _name, row = prod.doc.types[0]
    # the fixture's rows: 480Y/277 V, NEMA 1, 400 A, 65 kAIC
    assert row[prod.doc.params["Voltage"].elem_id] == "480Y/277 V"
    assert row[prod.doc.params["Enclosure Rating"].elem_id] == "NEMA 1"
    assert row[prod.doc.params["Amps"].elem_id] == pytest.approx(400.0)
    assert row[prod.doc.params["SCCR"].elem_id] == pytest.approx(65.0)


def test_a_mass_fills_the_CATEGORY_STANDARD_parameter_in_internal_units(tmp_path):
    """The sheet says 145 lb; Revit's internal mass unit is the kilogram.

    Weight goes through ``standard_values`` rather than a plain numeric
    parameter precisely so it keeps the #601 standards table's ``mass``
    storage class -- authoring a second "Weight" would have won the name and
    demoted it to a bare number.
    """
    from rvt.famgen import factory as FA
    parsed = S.read_sheet(_sheet_pdf(tmp_path))
    plan = plan_from_sheet(parsed)
    assert plan.kwargs["standard_values"]["Weight"] == pytest.approx(
        145.0 * FA.KG_PER_LB)
    assert "Weight" not in (plan.kwargs.get("numeric_params") or {})
    prod = FA.make_generic_model(**plan.kwargs)
    _name, row = prod.doc.types[0]
    assert row[prod.doc.params["Weight"].elem_id] == pytest.approx(
        145.0 * FA.KG_PER_LB)


def test_the_identity_caveat_says_WHOSE_claim_it_is(tmp_path):
    res = _run(tmp_path, "out", pdf=_vendor_pdf(tmp_path))
    joined = " ".join(res.caveats)
    assert "DOCUMENT'S OWN words" in joined
    assert "not a claim by this engine" in joined


def test_the_manufacturer_identity_does_not_become_OUR_author_string(tmp_path):
    """Hard rule 6 / the counsel brief: a sheet's maker rides as a parameter
    VALUE and never as the file's own identity."""
    res = _run(tmp_path, "out", pdf=_vendor_pdf(tmp_path, maker="Eaton Corporation"))
    rep = json.loads(open(res.files["rfa_report"]).read())
    assert rep["provenance"]["ok"] is True
    assert rep["provenance"]["checks"]["identity_is_ours"] is True


# ===========================================================================
# 4. what the prompt may and may not do (the pdf+prompt cell)
# ===========================================================================

def test_a_prompt_beside_the_pdf_NEVER_overrides_a_stated_dimension(tmp_path):
    """The claim the pdf+prompt cell's caveat makes, made falsifiable.

    A prompt that names different sizes must not move the body: the sheet's
    62 in is the fact this lane delivers, and a typed number quietly winning
    would put it behind a citation to the user's own document.
    """
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path),
               prompt="a 12 in cable tray, 10 ft long")
    assert res.ok, res.status
    rep = json.loads(open(res.files["rfa_report"]).read())
    vals = rep["facts"]["values"]
    assert vals["height_in"]["value"] == pytest.approx(62.0)
    assert vals["height_in"]["provenance"] == "fact"


def test_an_image_only_sheet_still_DELIVERS_through_the_archetype_lane(tmp_path):
    """Hard rule 1: the refusal is a label on a delivered file, not a refusal."""
    scan = FP.build_pdf(str(tmp_path / "scan.pdf"), [FP.spec_sheet_draws()],
                        no_text=True)
    res = _run(tmp_path, "out", pdf=scan, prompt="create a cable tray family")
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"])
    assert res.caveats[0].startswith("THE SHEET DID NOT SIZE THIS FAMILY:")
    assert "scanned or image-only" in res.caveats[0]
    assert "NOMINAL" in res.caveats[1] and "NOT read from scan.pdf" in res.caveats[1]


def test_the_fallback_family_is_NOT_dressed_in_the_sheets_numbers(tmp_path):
    """The archetype stand-in must carry nominal provenance, not fact."""
    scan = FP.build_pdf(str(tmp_path / "scan.pdf"), [FP.spec_sheet_draws()],
                        no_text=True)
    res = _run(tmp_path, "out", pdf=scan, prompt="create a cable tray family")
    rep = json.loads(open(res.files["rfa_report"]).read())
    kinds = {v["provenance"] for v in rep["facts"]["values"].values()}
    assert "fact" not in kinds, rep["facts"]["values"]
    assert "nominal" in kinds


def test_an_unreadable_sheet_with_no_words_to_fall_back_on_says_so(tmp_path):
    """No prompt, and a file stem naming no product: the honest end.

    The parse is still delivered -- there is simply no size that could be
    claimed, and inventing one is the thing this lane exists to not do.
    """
    scan = FP.build_pdf(str(tmp_path / "scan.pdf"), [FP.spec_sheet_draws()],
                        no_text=True)
    res = _run(tmp_path, "out", pdf=scan)
    assert not res.ok
    assert "could size a family" in res.status
    assert "names no product the archetype registry generates" in res.line
    assert os.path.isfile(res.files["sheet"])
    assert os.path.isfile(res.files["sheet_table"])
    assert "rfa" not in res.files


# ===========================================================================
# 4b. the file is delivered when the sheet is PARTIAL, not only when it fails
#     outright -- #798's review found both halves of this broken
# ===========================================================================

def _partial_pdf(tmp_path, keep, name="partial.pdf"):
    """A sheet stating only the rows in ``keep`` (plus the non-dimension ones)."""
    rows = [(lab, val) for lab, val in FP.SHEET_ROWS
            if lab in keep or lab not in ("Height", "Width", "Depth")]
    draws = []
    for i, (label, value) in enumerate(rows):
        y = 700.0 - i * 18.0
        draws += [(72.0, y, label), (300.0, y, value)]
    return FP.build_pdf(str(tmp_path / name), [draws])


@pytest.mark.parametrize("keep", [
    ("Height",),                 # no width, no depth
    ("Height", "Width"),         # no depth
    ("Width", "Depth"),          # no height
    (),                          # no dimension at all
])
def test_a_sheet_SHORT_OF_A_DIMENSION_still_delivers(tmp_path, keep):
    """The hard-rule-1 hole #798's reviewer found, in all four shapes.

    ``buildable`` asked only about ``height_ft`` while ``make_generic_model``
    needs height AND width AND depth. A height-only sheet therefore took the
    buildable branch, the constructor raised, and ``_r_pdf_to_rfa`` returned
    before the archetype fallback ever ran -- delivering **nothing**. Measured
    at the time: ``res.ok=False``, ``files=['sheet','sheet_plan','sheet_table']``,
    no ``rfa`` key and no file on disk, on a prompt that demonstrably builds a
    16-part nominal tray on its own.
    """
    pdf = _partial_pdf(tmp_path, keep)
    res = _run(tmp_path, "out", pdf=pdf, prompt="create a cable tray family")
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"]), res.files
    assert res.caveats[0].startswith("THE SHEET DID NOT SIZE THIS FAMILY:")
    # and it must be the NOMINAL family, not the sheet's numbers on a wrong body
    rep = json.loads(open(res.files["rfa_report"]).read())
    assert "fact" not in {v["provenance"] for v in rep["facts"]["values"].values()}


@pytest.mark.parametrize("keep", [("Height",), ("Height", "Width")])
def test_a_sheet_SHORT_OF_A_DIMENSION_is_not_called_buildable(tmp_path, keep):
    """`buildable` means what the constructor needs, not what we hoped."""
    plan = plan_from_sheet(S.read_sheet(_partial_pdf(tmp_path, keep)))
    assert not plan.buildable
    assert plan.missing_dimensions()
    joined = " ".join(plan.refused)
    assert "a solid needs height, width and depth together" in joined
    # the old wording claimed "the body uses what it does state", which was
    # false in exactly the case that produced it
    assert "the body uses what it does state" not in joined


def test_a_BUILD_FAILURE_also_falls_through_to_the_archetype_lane(tmp_path,
                                                                  monkeypatch):
    """The structural half, independent of `buildable` being right.

    `buildable` is now honest, so no sheet reaches a raising constructor by
    that route. This forces the other one: whatever the reason the famspec
    lane produces no file, the archetype lane still gets its turn.
    """
    from rvt.frontdoor import famspec as FS
    real = FS.build

    def boom(kind, kw, **k):
        # only the SHEET's constructor -- the archetype lane goes through the
        # same dispatcher, and breaking it too would prove nothing
        if kind == "generic_model":
            raise RuntimeError("probe: the constructor refused")
        return real(kind, kw, **k)

    monkeypatch.setattr(FS, "build", boom)
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path),
               prompt="create a cable tray family")
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"])
    assert "could not be built from them" in res.caveats[0]


# ===========================================================================
# 4c. a field we KNOW but do not use is SHOWN, not dropped
# ===========================================================================

def test_a_recognised_field_this_lane_cannot_place_is_still_reported(tmp_path):
    """`length_in` and `diameter_in` are in `vocab.FIELDS` and in none of this
    module's maps, so they were read, understood and dropped in silence -- while
    the caveat promised "every row read but not used". For a cable-tray or
    conduit sheet, Overall Length is the headline dimension.
    """
    rows = list(FP.SHEET_ROWS) + [("Overall Length", "120 in"), ("Diameter", "4 in")]
    draws = []
    for i, (label, value) in enumerate(rows):
        y = 700.0 - i * 18.0
        draws += [(72.0, y, label), (300.0, y, value)]
    pdf = FP.build_pdf(str(tmp_path / "extra.pdf"), [draws])

    parsed = S.read_sheet(pdf)
    assert {"length_in", "diameter_in"} <= set(parsed.by_key())   # it WAS read
    plan = plan_from_sheet(parsed)
    joined = " ".join(plan.refused)
    for key in ("length_in", "diameter_in"):
        assert key in joined, plan.refused
    assert "'Overall Length' = '120 in'" in joined     # with its citation

    res = _run(tmp_path, "out", pdf=pdf)
    assert res.ok
    assert any("length_in" in c for c in res.caveats)


# ===========================================================================
# 4d. the delivered FILE must not contradict the delivered REPORT
# ===========================================================================

def test_a_sheet_built_family_does_not_describe_itself_as_GIVEN(tmp_path):
    """The type row and the document notes are what a person reads in Revit.

    They said "geometry GIVEN" on this lane while the fact sheet, the product
    note and every route caveat said FACT.
    """
    from rvt.famgen import factory as FA
    plan = plan_from_sheet(S.read_sheet(_sheet_pdf(tmp_path)))
    prod = FA.make_generic_model(**plan.kwargs)
    _name, row = prod.doc.types[0]
    desc = row[-1010109]
    assert "READ from spec sheet: probeworks-pw400.pdf" in desc
    assert "geometry GIVEN" not in desc
    assert not any("geometry GIVEN" in n for n in prod.doc.notes)


def test_a_caller_supplied_body_STILL_describes_itself_as_GIVEN(tmp_path):
    """...and the control: the IFC / caller lane is unchanged."""
    from rvt.famgen import factory as FA
    prod = FA.make_generic_model(height_ft=5.0, width_ft=1.7, depth_ft=0.5,
                                 name="P", source="an IFC body")
    _name, row = prod.doc.types[0]
    assert "geometry GIVEN (an IFC body)" in row[-1010109]


def test_material_and_finish_fill_the_STANDARDS_rows_not_shadow_them(tmp_path):
    """They are `generic_model` standards-table entries (group `materials`).

    Authored as plain text parameters they landed under group `identity` and
    the table skipped its own rows as "already authored by the constructor".
    """
    from rvt.famgen import factory as FA
    rows = list(FP.SHEET_ROWS) + [("Material", "Galvanized Steel"),
                                  ("Finish", "ANSI 61 Gray")]
    draws = []
    for i, (label, value) in enumerate(rows):
        y = 700.0 - i * 18.0
        draws += [(72.0, y, label), (300.0, y, value)]
    pdf = FP.build_pdf(str(tmp_path / "mat.pdf"), [draws])

    plan = plan_from_sheet(S.read_sheet(pdf))
    assert plan.kwargs["standard_values"]["Material"] == "Galvanized Steel"
    assert "Material" not in (plan.kwargs.get("text_params") or {})

    prod = FA.make_generic_model(**plan.kwargs)
    groups = {a["name"]: a["group"] for a in (prod.standards or {})["authored"]}
    assert groups["Material"] == "materials" and groups["Finish"] == "materials"
    assert (prod.standards or {}).get("skipped") == []
    _name, row = prod.doc.types[0]
    assert row[prod.doc.params["Finish"].elem_id] == "ANSI 61 Gray"


# ===========================================================================
# 5. the route's own record
# ===========================================================================

def test_the_route_manifest_names_the_cell_and_the_stages(tmp_path):
    res = _run(tmp_path, "out", pdf=_sheet_pdf(tmp_path))
    man = json.loads(open(res.manifest_paths["route.json"]).read())
    assert man["route"] == "pdf_to_rfa"
    assert man["cell"]["inputs"] == ["pdf"]
    ran = [s["stage"] for s in man["steps"]]
    assert "pdf->sheet" in ran and "sheet->famspec" in ran


def test_two_runs_of_ONE_sheet_produce_the_SAME_bytes(tmp_path):
    """#793's determinism law, on the newest lane: a document that has not
    changed must not produce a family that has."""
    pdf = _sheet_pdf(tmp_path)
    a = _run(tmp_path, "a", pdf=pdf)
    b = _run(tmp_path, "b", pdf=pdf)
    assert a.ok and b.ok
    assert open(a.files["rfa"], "rb").read() == open(b.files["rfa"], "rb").read()
