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
#475 lands the path-owning ``_jsonsafe.write`` (parent dir + utf-8 + the walk)
and routes the remaining job-dir sinks through it -- ``scene-brief.json``,
the edit ``ops.json`` echo, ``tools/ifc_intent._jdump``, ``famfrom_ifc``'s
reports, ``tools/rvt_job``'s manifests -- plus ``_jsonsafe.dumps`` for the
``--json`` stdout documents of ``tools/rvt_job`` and ``tools/route``; #488
the last stdout sinks (``tools/frontdoor``, ``tools/rvt_edit``, and the
bootstrap's ``go`` envelope, which inlines the walk: it cannot import rvt).

Pinned below: the walk itself; that it is a byte-for-byte no-op on finite
data (the 6-panel prompt's manifest must not move); a synthetic payload
carrying inf / -inf / nan at several depths round-trips through each writer
and a strict ``json.loads(..., parse_constant=<fail>)`` accepts the file; and
one coarse tripwire that no touched module dumps to a file around the walk.

Fresh-clone safe: no samples/, no build, no viewer; the prompt layer's
in-repo catalog is all ``prompt_to_intent`` needs.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import inspect
import io
import json
import math
import os
import re

import pytest

from conftest import load_tool
from rvt import _jsonsafe as JS
from rvt.frontdoor import edit as E
from rvt.frontdoor import manifest as MF
from rvt.frontdoor import prompt_intent as PP
from rvt.frontdoor import router as R
from rvt.ifc import intent as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEKTON_ENV = os.path.join(ROOT, "plugin", "skills", "_shared", "tekton_env.py")   # hand-authored, tracked
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


def test_write_owns_the_whole_stanza_and_lands_strict_json(tmp_path):
    """``write`` makes the parent dir, writes utf-8, walks, returns the path."""
    target = tmp_path / "made" / "for" / "me" / "poison.json"
    p = JS.write(str(target), _poison(), indent=2)
    assert p == str(target) and target.is_file()
    got = _strict_load(p)
    assert got["seq"] == [["-inf", 2], ["nan", ["inf"]]] and got["fine"] == 1.5
    JS.write(str(tmp_path / "bare.json"), {"u": "µm", "x": NAN})   # a bare filename's dir is '.'-safe too
    assert _strict_load(str(tmp_path / "bare.json")) == {"u": "µm", "x": "nan"}
    assert JS.dumps({"x": (INF, 1)}, indent=None) == '{"x": ["inf", 1]}'


def test_a_default_hook_s_result_is_walked_too():
    """``tools/rvt_job._jsonable`` expands a dataclass / ``to_json()`` object
    at dump time; a non-finite float INSIDE that expansion must land as text,
    not trip ``allow_nan=False`` mid-delivery (hard rule 1)."""
    @dataclasses.dataclass
    class Timing:
        seconds: float
        parts: tuple

    def expand(o):
        return dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o)

    doc = {"t": Timing(INF, (NAN, 2.5)), "nested": [Timing(1.0, (Timing(-INF, ()),))]}
    buf = io.StringIO()
    JS.dump(doc, buf, default=expand)
    for text in (JS.dumps(doc, default=expand, indent=1), buf.getvalue()):
        got = json.loads(text, parse_constant=_refuse_constant)
        assert got["t"] == {"seconds": "inf", "parts": ["nan", 2.5]}
        assert got["nested"][0]["parts"][0] == {"seconds": "-inf", "parts": []}
    with pytest.raises(TypeError):               # default=None keeps json's own refusal of unknown types
        JS.dumps({"t": Timing(1.0, ())}, default=None)


def test_the_walk_is_a_byte_for_byte_no_op_on_finite_data(six_panels, tmp_path):
    """The 6-panel prompt's manifest carries no non-finite value, so routing it
    through the walk must not move one byte: same dict -> same text as the
    plain ``json.dump(..., default=str)`` every writer used before -- through
    ``dump``, ``dumps`` and the file ``write`` lands alike."""
    model, parsed = six_panels
    timings = {"seconds": 0.16, "timings": {"validate": 0.28, "status_gate": 0.23}}
    payloads = [I.intent_to_json(model), parsed.coverage.as_json(),
                PP.scene_brief(PROMPT, parsed=parsed, model=model),
                {"a": 1, "b": [1.25, 2, {"c": (3, 4.0)}], "t": timings, "z": None, "u": "µ"}]
    for n, obj in enumerate(payloads):
        for indent in (1, 2):                    # the two indents the writers use
            plain, walked = io.StringIO(), io.StringIO()
            json.dump(obj, plain, indent=indent, default=str)
            JS.dump(obj, walked, indent=indent)
            assert walked.getvalue() == plain.getvalue() == JS.dumps(obj, indent=indent, default=str)
            p = JS.write(str(tmp_path / f"p{n}-{indent}.json"), obj, indent=indent)
            with open(p, encoding="utf-8") as fh:
                assert fh.read() == plain.getvalue()


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


# --- the #475 sinks ---------------------------------------------------------

def test_write_handoff_s_scene_brief_lands_strict_json(six_panels, tmp_path, monkeypatch):
    model, parsed = six_panels
    real = PP.scene_brief
    monkeypatch.setattr(PP, "scene_brief", lambda *a, **k: dict(real(*a, **k), poison=_poison()))
    paths = PP.write_handoff(PROMPT, str(tmp_path / "handoff"), parsed=parsed, model=model)
    got = _strict_load(paths["scene_brief"])
    assert got["poison"]["nested"]["deeper"]["deepest"] == [1.0, "inf", {"again": "nan"}]
    assert os.path.isfile(paths["handoff"]) and os.path.isfile(paths["instructions"])


def test_the_edit_ops_echo_lands_strict_json_before_the_job_runs(tmp_path):
    """``run_edit`` echoes the normalised ops as ``ops.json`` FIRST; a missing
    input then makes the job runner refuse in one line -- the echo is what
    this pins, and it needs no .rvt."""
    spec = E.EditSpec(ops=[{"op": "set-level", "id": 311, "elevation_ft": INF}],
                      source="inline-json", understood=[{"op": "set-level", "ratio": NAN}])
    res = E.run_edit(str(tmp_path / "missing.rvt"), spec, str(tmp_path / "e"), quiet=True)
    assert res["rc"] != 0
    got = _strict_load(str(tmp_path / "e" / "ops.json"))
    assert got == {"ops": [{"op": "set-level", "id": 311, "elevation_ft": "inf"}],
                   "source": "inline-json", "understood": [{"op": "set-level", "ratio": "nan"}]}


def test_ifc_intent_jdump_lands_strict_json(tmp_path):
    T = load_tool("ifc_intent")
    p = tmp_path / "families" / "families_record.json"
    T._jdump(str(p), {"families": [_poison()], "seconds": INF})
    got = _strict_load(str(p))
    assert got["seconds"] == "inf" and got["families"][0]["neg"] == "-inf"


def test_rvt_job_manifests_and_its_one_json_stdout_document_are_strict(tmp_path, capsys):
    """The ops door: ``write_manifest`` / the stub manifest go through
    ``_jsonsafe.write`` keeping ``default=_jsonable`` (a dataclass inside is
    expanded AND walked), and ``--json``'s ONE stdout object is the on-disk
    manifest + ``exit_code`` (#456's contract), printed through ``dumps``."""
    J = E.load_job_module()

    @dataclasses.dataclass
    class Gate:
        status: str
        elapsed_s: float

    out = tmp_path / "job" / "edited.rvt"
    out.parent.mkdir()
    out.write_bytes(b"not really an rvt")
    mp = J.write_manifest(str(out), {"mode": "edit", "gates": {"structural": Gate("PASS", INF)},
                                     "timings": {"total": NAN}, "poison": _poison()})
    got = _strict_load(mp)
    assert got["gates"]["structural"] == {"status": "PASS", "elapsed_s": "inf"}
    assert got["timings"] == {"total": "nan"} and got["output"]["bytes"] == len(b"not really an rvt")
    stub = tmp_path / "job" / "never.rvt"
    J._write_stub_manifest(str(stub), {"mode": "edit", "status": "unit", "ratio": -INF, "_t0": 1.0})
    assert _strict_load(str(stub) + ".manifest.json")["ratio"] == "-inf"
    capsys.readouterr()
    # --json on a missing input: no manifest of its own -> main()'s stub IS the one document
    ops = JS.write(str(tmp_path / "ops.json"), {"ops": [{"op": "set-level", "id": 311, "elevation_ft": 5.0}]})
    gone = tmp_path / "j2" / "gone.rvt"
    rc = J.main(["edit", str(tmp_path / "absent.rvt"), "--ops", ops, "-o", str(gone), "--json"])
    printed = capsys.readouterr().out
    doc = json.loads(printed, parse_constant=_refuse_constant)
    assert rc != 0 and doc["exit_code"] == rc and doc["output"]["written"] is False
    assert {k: v for k, v in doc.items() if k != "exit_code"} == _strict_load(str(gone) + ".manifest.json")


def test_route_s_json_printer_is_strict(capsys):
    T = load_tool("route")
    T._print_json({"cell": _poison(), "seconds": INF})
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)
    assert doc["seconds"] == "inf" and doc["cell"]["seq"][1] == ["nan", ["inf"]]


# --- the #488 stdout sinks -------------------------------------------------

@pytest.fixture(scope="module")
def frontdoor_tool():
    return load_tool("frontdoor")


def test_frontdoor_author_json_prints_one_strict_document(frontdoor_tool, monkeypatch, capsys):
    """The CLI path a skill session parses: ``author … --json`` prints
    ``AuthorResult.as_json()``; a non-finite timing / extent inside it lands
    as text and the exit code still follows ``ok`` (3 = did not complete)."""
    from rvt import frontdoor as FD
    res = FD.AuthorResult(route="prompt", ok=False, status="unit: build did not complete",
                          out_dir="/nowhere", files={"combined": "/nowhere/x.rvt"},
                          handoff={"poison": _poison()}, errors=["unit"], seconds=INF)
    monkeypatch.setattr(FD, "run", lambda req: res)
    rc = frontdoor_tool.main(["author", "--prompt", PROMPT, "--json"])
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)   # ONE document
    assert rc == frontdoor_tool.EX_INCOMPLETE and doc["ok"] is False and doc["route"] == "prompt"
    assert doc["seconds"] == "inf" and doc["handoff"]["poison"]["seq"] == [["-inf", 2], ["nan", ["inf"]]]
    assert doc["files"] == {"combined": "/nowhere/x.rvt"} and doc["errors"] == ["unit"]


def test_frontdoor_matrix_json_prints_one_strict_document(frontdoor_tool, monkeypatch, capsys):
    from rvt.frontdoor import matrix as MX
    monkeypatch.setattr(MX, "audit", lambda: {"problems": [], "score": NAN, "extent": (INF, -INF)})
    rc = frontdoor_tool.main(["matrix", "--json"])
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)
    assert rc == frontdoor_tool.EX_OK and doc["cells"]
    assert doc["audit"] == {"problems": [], "score": "nan", "extent": ["inf", "-inf"]}


def test_rvt_edit_json_result_is_strict(monkeypatch, capsys):
    """``rvt_edit.py FILE VERB … --json`` (what ``go edit`` runs): its ONE
    result object goes through ``_jsonsafe.dumps``; the human-mode printers
    (``info`` / ``deps`` / the change report) keep plain ``json.dumps``."""
    T = load_tool("rvt_edit")

    class Doc:
        @staticmethod
        def from_file(path):
            return object()
    monkeypatch.setattr(T, "Document", Doc)
    monkeypatch.setattr(T, "_inventory_summary", lambda doc: {"levels": [{"elevation_ft": INF}]})
    monkeypatch.setattr(T, "_release_block", lambda i, o: {"input": None, "output": None, "ratio": NAN})
    rc = T._run_json(argparse.Namespace(cmd="info", file="unit.rvt"), "unit note")
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)
    assert rc == 0 and doc["ok"] is True and doc["release_note"] == "unit note"
    assert doc["levels"] == [{"elevation_ft": "inf"}] and doc["release"]["ratio"] == "nan"
    # rvt_edit is not a JSON_DOOR below (its human-mode printers keep json.dumps): pin the door itself
    assert not re.search(r"\bjson\.dumps\(", inspect.getsource(T._run_json))


@pytest.fixture(scope="module")
def tekton_env():
    """The hand-authored bootstrap, imported in-process (importing it has no
    side effects; ``preflight`` / ``run_script`` are stubbed per test)."""
    spec = importlib.util.spec_from_file_location("tekton_env", TEKTON_ENV)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_bootstrap_s_inline_walk_matches_jsonsafe(tekton_env, six_panels):
    """``tekton_env._json_doc`` cannot import ``rvt`` (it prints before -- or
    without -- an engine), so it inlines the walk: strict on poison, and
    byte-identical to plain ``json.dumps(…, indent=1, default=str)`` (what
    it printed before) AND to ``_jsonsafe.dumps`` on finite data."""
    got = json.loads(tekton_env._json_doc({"go": _poison(), "result": [INF]}),
                     parse_constant=_refuse_constant)
    assert got["go"]["nested"]["deeper"]["deepest"] == [1.0, "inf", {"again": "nan"}]
    assert got["result"] == ["inf"]
    model, parsed = six_panels
    for obj in (PP.scene_brief(PROMPT, parsed=parsed, model=model),
                {"go": {"ready": True, "seconds": 0.123, "inputs": []}, "result": {"t": (1, 2.5)}}):
        assert tekton_env._json_doc(obj) == json.dumps(obj, indent=1, default=str) \
            == JS.dumps(obj, indent=1)


def test_go_s_one_json_envelope_is_strict_even_around_a_non_strict_job(tekton_env, monkeypatch,
                                                                       capsys, tmp_path):
    """``go SCRIPT.py …`` re-parses the job's stdout with ``json.loads``,
    which ACCEPTS a bare ``Infinity``/``NaN`` -- so a sibling script that
    still prints one must not leak it through the envelope; and the NOT
    READY branch (no engine importable at all) prints strict JSON too."""
    monkeypatch.setattr(tekton_env, "preflight",
                        lambda root=None: {"ok": True, "line": "tekton: READY | unit", "seconds": 0.01})

    def fake_run(script, args, base_dir=None):
        print('{"x": Infinity, "t": [NaN, 1.5], "name": "%s"}' % os.path.basename(script))
        return 0
    monkeypatch.setattr(tekton_env, "run_script", fake_run)
    rc = tekton_env.go(["poison.py", "--flag"], base_dir=str(tmp_path))
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)
    assert rc == 0 and doc["go"]["ready"] is True and doc["go"]["exit_code"] == 0
    assert doc["result"] == {"x": "inf", "t": ["nan", 1.5], "name": "poison.py"}
    assert "stdout" not in doc["go"]                 # the job's output WAS one JSON object

    monkeypatch.setattr(tekton_env, "preflight",
                        lambda root=None: {"ok": False, "line": "tekton: NOT READY | unit",
                                           "seconds": INF, "checks": [{"ratio": NAN}]})
    rc = tekton_env.go(["author", "--prompt", PROMPT], base_dir=str(tmp_path))
    doc = json.loads(capsys.readouterr().out, parse_constant=_refuse_constant)
    assert rc == 3 and doc["result"] is None and doc["go"]["ready"] is False
    assert doc["go"]["preflight"]["seconds"] == "inf" and doc["go"]["preflight"]["checks"] == [{"ratio": "nan"}]


# --- tripwires ------------------------------------------------------------

#: every module #461 / #475 / #488 switched; the ``--json`` doors additionally
#: print their ONE stdout document through ``_jsonsafe.dumps``, so a bare
#: ``json.dumps(`` is banned there too (elsewhere it still renders dev /
#: progress output legitimately: prompt_intent's __main__, ifc_intent's echo,
#: rvt_edit's human-mode ``info`` / ``deps`` / change-report printers).
WRITERS = ("src/rvt/ifc/intent.py", "src/rvt/frontdoor/manifest.py", "src/rvt/frontdoor/router.py",
           "src/rvt/frontdoor/standalone.py", "src/rvt/frontdoor/prompt_intent.py",
           "src/rvt/frontdoor/edit.py", "src/rvt/ifc/famfrom_ifc.py", "tools/ifc_intent.py",
           "tools/rvt_job.py", "tools/route.py", "tools/frontdoor.py", "tools/rvt_edit.py")
JSON_DOORS = ("tools/rvt_job.py", "tools/route.py", "tools/frontdoor.py")


@pytest.mark.parametrize("rel", WRITERS)
def test_no_switched_module_dumps_around_the_walk(rel):
    """Coarse on purpose: the round trips above pin the behaviour; this only
    catches a bare ``json.dump(`` (or, on a --json door, ``json.dumps(``)
    re-appearing in a switched module, or the strict writer dropped from it."""
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    assert not re.search(r"\bjson\.dump\(", src), f"{rel}: a bare json.dump( bypasses rvt._jsonsafe"
    if rel in JSON_DOORS:
        assert not re.search(r"\bjson\.dumps\(", src), f"{rel}: a bare json.dumps( bypasses rvt._jsonsafe"
    assert re.search(r"\b_jsonsafe\b", src), f"{rel}: no longer goes through rvt._jsonsafe"


def test_the_bootstrap_dumps_only_through_its_inline_walk(tekton_env):
    """``tekton_env.py`` keeps exactly ONE ``json.dump(s)(`` -- the one inside
    ``_json_doc`` -- so the ``go`` envelope, the NOT READY branch and
    ``--json`` preflight cannot regrow a bare printer; and it stays
    engine-free at module level."""
    src = open(TEKTON_ENV, encoding="utf-8").read()
    assert len(re.findall(r"\bjson\.dumps?\(", src)) == 1
    assert re.search(r"\bjson\.dumps\(", inspect.getsource(tekton_env._json_doc))
    assert not re.search(r"^(?:from|import)\s+rvt\b", src, re.M)


def test_jsonsafe_is_a_stdlib_leaf():
    """Imported by rvt.ifc AND rvt.frontdoor modules and by repo tools: it
    must never pull either package (cycle) or anything third-party (bare
    surface)."""
    src = open(JS.__file__, encoding="utf-8").read()
    imported = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M))
    assert imported <= {"__future__", "json", "math", "os", "typing"}, imported
