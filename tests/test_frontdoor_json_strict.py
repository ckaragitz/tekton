"""tests/test_frontdoor_json_strict.py -- every JSON the front door writes is
strictly parseable (issue #461, follow-up of #442).

Python's ``json`` echoes a non-finite float as a bare ``Infinity`` / ``NaN``
token that browsers' ``JSON.parse``, jq and Go reject.  #442 closed the
pset-borne case at read time (``rvt.ifc.intent._finite_or_text``); #461 puts
ONE shared walk (``rvt._jsonsafe``) in front of every front-door writer --
``write_intent``, ``manifest.write_manifest``, the router's report / manifest
writers, ``standalone``'s report writer -- so a non-finite value from ANY
source lands as text, and the dump runs with ``allow_nan=False`` so a value
the walk missed fails HERE, never as an unparseable file in a user's run.

Pinned below: the walk itself; that it is a byte-for-byte no-op on finite
data (the 6-panel prompt's manifest must not move); a synthetic payload
carrying inf / -inf / nan at several depths round-trips through each writer
and a strict ``json.loads(..., parse_constant=<fail>)`` accepts the file; and
one coarse tripwire that no touched module dumps to a file around the walk.

Fresh-clone safe: no samples/, no build, no viewer; the prompt layer's
in-repo catalog is all ``prompt_to_intent`` needs.
"""
from __future__ import annotations

import io
import json
import math
import os
import re

import pytest

from rvt import _jsonsafe as JS
from rvt.frontdoor import manifest as MF
from rvt.frontdoor import prompt_intent as PP
from rvt.frontdoor import router as R
from rvt.ifc import intent as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INF, NAN = float("inf"), float("nan")
PROMPT = "an electrical room with 6 panels"


def _refuse_constant(tok):                       # json.loads' hook for Infinity/-Infinity/NaN
    raise ValueError(f"bare non-finite token {tok!r} in written JSON")


def _strict_load(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    assert not re.search(r"\b-?Infinity\b|\bNaN\b", text), path
    return json.loads(text, parse_constant=_refuse_constant)


def _poison():
    """inf / -inf / nan at several depths, inside dicts, lists and tuples."""
    return {"top": INF, "neg": -INF, "nan": NAN, "fine": 1.5, "n": 3, "s": "x",
            "flag": True, "none": None,
            "nested": {"deeper": {"deepest": [1.0, INF, {"again": NAN}]}},
            "seq": [(-INF, 2), [NAN, [INF]]]}


@pytest.fixture(scope="module")
def six_panels():
    return PP.prompt_to_intent(PROMPT)          # (model, parsed)


# --- the walk --------------------------------------------------------------

def test_json_safe_turns_every_non_finite_float_into_its_text_at_any_depth():
    out = JS.json_safe(_poison())
    assert out["top"] == "inf" and out["neg"] == "-inf" and out["nan"] == "nan"
    assert out["nested"]["deeper"]["deepest"] == [1.0, "inf", {"again": "nan"}]
    assert out["seq"] == [["-inf", 2], ["nan", ["inf"]]]
    # finite scalars and non-container leaves come back as they were, not coerced
    assert out["fine"] == 1.5 and isinstance(out["fine"], float)
    assert out["n"] == 3 and isinstance(out["n"], int) and out["flag"] is True and out["none"] is None
    buf = io.StringIO()
    JS.dump(_poison(), buf, indent=1)
    assert json.loads(buf.getvalue(), parse_constant=_refuse_constant)["seq"][1][1] == ["inf"]


def test_dump_refuses_loudly_if_the_walk_ever_misses_a_value(monkeypatch):
    class Sneaky:                                # not a float: default=str renders it as text,
        def __str__(self):                       # so it can never become a bare token either
            return "sneaky"
    buf = io.StringIO()
    JS.dump({"x": Sneaky()}, buf)
    assert json.loads(buf.getvalue()) == {"x": "sneaky"}
    monkeypatch.setattr(JS, "json_safe", lambda obj: obj)      # a walk that misses everything ...
    with pytest.raises(ValueError):                             # ... is caught by allow_nan=False
        JS.dump({"x": INF}, io.StringIO())


def test_the_walk_is_a_byte_for_byte_no_op_on_finite_data(six_panels):
    """The 6-panel prompt's manifest carries no non-finite value, so routing it
    through the walk must not move one byte: same dict -> same text as the
    plain ``json.dump(..., default=str)`` every writer used before."""
    model, parsed = six_panels
    timings = {"seconds": 0.16, "timings": {"validate": 0.28, "status_gate": 0.23}}
    payloads = [I.intent_to_json(model), parsed.coverage.as_json(),
                {"a": 1, "b": [1.25, 2, {"c": (3, 4.0)}], "t": timings, "z": None}]
    for obj in payloads:
        for indent in (1, 2):                    # the two indents the writers use
            plain, walked = io.StringIO(), io.StringIO()
            json.dump(obj, plain, indent=indent, default=str)
            JS.dump(obj, walked, indent=indent)
            assert walked.getvalue() == plain.getvalue()


# --- each writer -----------------------------------------------------------

def test_write_intent_lands_strict_json_even_with_non_finite_values_outside_psets(tmp_path):
    model, _ = PP.prompt_to_intent(PROMPT)       # a fresh model: this test mutates it
    model.audit["poison"] = _poison()            # a computed block, not a pset (#442 covers those)
    model.census = {"ratio": INF, "rows": [NAN, 1]}
    model.notes.append({"extent": (-INF, INF)})
    p = I.write_intent(model, str(tmp_path / "intent.json"))
    got = _strict_load(p)
    assert got["audit"]["poison"]["nested"]["deeper"]["deepest"][1] == "inf"
    assert got["census"] == {"ratio": "inf", "rows": ["nan", 1]}
    assert got["notes"][-1] == {"extent": ["-inf", "inf"]}


def test_write_manifest_lands_strict_json(tmp_path):
    man = {"route": "prompt", "status": "unit", "tool": MF.TOOL, "tool_version": MF.TOOL_VERSION,
           "generated_at": "unit", "inputs": {"prompt": "unit", "ratio": INF},
           "build": {"seconds": NAN, "timings": {"validate": INF}}, "poison": _poison()}
    paths = MF.write_manifest(man, str(tmp_path))
    got = _strict_load(paths["json"])
    assert got["build"] == {"seconds": "nan", "timings": {"validate": "inf"}}
    assert got["inputs"]["ratio"] == "inf" and got["poison"]["top"] == "inf"
    assert os.path.isfile(paths["md"])
    assert math.isnan(man["build"]["seconds"])   # the caller's dict is walked into a copy, not edited


def test_the_router_manifest_lands_strict_json(tmp_path):
    res = R.RouteResult(ok=True, status="unit", out_dir=str(tmp_path), seconds=INF,
                        steps=[{"step": "unit", "seconds": NAN, "extent": [INF, -INF]}],
                        caveats=["unit"], cell={"status": "works", "evidence": {"score": NAN}})
    R._write_route_manifest(res, {"prompt": "unit"}, "rvt", {"out": str(tmp_path), "k": INF})
    got = _strict_load(res.manifest_paths["route.json"])
    assert got["seconds"] == "inf" and got["steps"][0]["seconds"] == "nan"
    assert got["steps"][0]["extent"] == ["inf", "-inf"]
    assert got["request"]["opts"] == {"k": "inf"} and got["evidence"] == {"score": "nan"}
    assert os.path.isfile(os.path.join(str(tmp_path), "ROUTE.md"))


# --- tripwires ------------------------------------------------------------

WRITERS = ("src/rvt/ifc/intent.py", "src/rvt/frontdoor/manifest.py",
           "src/rvt/frontdoor/router.py", "src/rvt/frontdoor/standalone.py")


@pytest.mark.parametrize("rel", WRITERS)
def test_no_touched_writer_dumps_to_a_file_around_the_walk(rel):
    """Coarse on purpose: the round trips above pin the behaviour; this only
    catches a new ``json.dump(`` to a file handle re-appearing in a module
    #461 switched (``json.dumps`` for strings / stdout is not a file writer)."""
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    assert not re.search(r"\bjson\.dump\(", src), f"{rel}: a bare json.dump( bypasses rvt._jsonsafe"
    assert "_jsonsafe.dump(" in src, rel


def test_jsonsafe_is_a_stdlib_leaf():
    """Imported by rvt.ifc.intent AND three rvt.frontdoor modules: it must
    never pull either package (cycle) or anything third-party (bare surface)."""
    src = open(JS.__file__, encoding="utf-8").read()
    imported = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M))
    assert imported <= {"__future__", "json", "math", "typing"}, imported
