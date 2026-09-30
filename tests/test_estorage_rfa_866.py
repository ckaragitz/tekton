"""#866 DONE 4: the Extensible-Storage catalog reads a FAMILY document by its path.

``rvt.estorage.schemas()`` took an ``.rvt`` path, a Document or a corpus project
name; an ``.rfa`` path fell through to the project-name branch and raised
``ESSchemaError("cannot locate Global/Latest")``, and its decoder silently fell
back to the default archive schema.  A family is the same container, so the path
branch (catalog source and archive-schema decoder alike) now accepts both
extensions -- and the CLI takes a bare ``name.rfa`` as a path, as it always did
a bare ``name.rvt``.  Synthetic: the family is our own
generated device (no ES content, so the catalog is honestly empty with a reason).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import estorage as ES                 # noqa: E402
from rvt.famgen import factory as F            # noqa: E402


@pytest.fixture(scope="module")
def device_rfa(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("es866") / "device.rfa")
    F.make_device("duplex-receptacle", standards=False).write(path, validate=False, provenance=False)
    return path


def test_schemas_reads_a_family_by_path(device_rfa):
    cat = ES.schemas(device_rfa)                # main: ESSchemaError (treated as a project name)
    assert cat.source == device_rfa
    assert len(cat) == 0 and cat.note           # our family carries no ES schema: empty, with the reason


@pytest.mark.parametrize("arg", ["device.rfa", "DEVICE.RFA", "x.rvt"])
def test_cli_takes_a_bare_family_name_as_a_path(arg):
    assert ES._doc_path(arg) == arg


def test_cli_reports_a_family(device_rfa, capsys):
    assert ES.main([device_rfa, "--report"]) == 0
    out = capsys.readouterr().out
    assert "ES schema catalog: 0 schemas (" in out and "ES report: 0 schemas" in out
