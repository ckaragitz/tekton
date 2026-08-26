"""Issue #139: the family build escapes PartAtom XML text without importing
``xml.sax.saxutils`` -- in CPython that module drags ``urllib.request`` ->
``http.client`` -> ``ssl`` + ``socket`` + the whole ``email`` package (34
modules, ~13 ms warm) into every prompt/IFC job that generates a family,
for three ``str.replace`` calls.

Two guards: the zero-import helper stays BYTE-IDENTICAL to
``xml.sax.saxutils.escape`` (the oracle runs in this process, where importing
it is harmless), and a real family build in a fresh interpreter leaves the
network/mail stack out of ``sys.modules``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from xml.sax.saxutils import escape as saxutils_escape

import pytest

from conftest import ROOT, SRC, needs_schema
from rvt.famgen import skeleton as SK

#: THE family-build import budget (deny-list): ``xml.sax`` (any submodule) and
#: the roots of what ``saxutils`` pulled in before #139; the XML parsers and
#: ``zipfile`` that ``rvt.meta`` imported at module level before #747.  The next
#: stdlib chain cut off this path extends THIS tuple rather than growing another gate.
HEAVY = ("xml.sax", "urllib.request", "http.client", "ssl", "socket", "email.parser",
         "xml.dom.minidom", "xml.etree.ElementTree", "zipfile")

CASES = ["", "plain", "A&B", "<tag>", "a<b>c&d", "&amp;", "&lt;&gt;", "&&&", "<<>>",
         "R&D <Panel> 42\" x 20'", "ünïcödé & ß < >", "a\nb&\tc",
         "]]>", "'\"", "PRL1a 225A 3P4W", "42’ & ø"]


@pytest.mark.parametrize("text", CASES)
def test_xml_escape_is_byte_identical_to_saxutils(text):
    assert SK._xml_escape(text) == saxutils_escape(text)


def test_part_atom_escapes_title_category_types_and_product():
    xml = SK.build_part_atom("R&D <Lab>", "Gear & <Devices>", type_names=["225A & 3P<4W>", 42],
                             product_name="w&w", updated="2026-08-23T00:00:00Z").decode("utf-8")
    assert "<title>R&amp;D &lt;Lab&gt;</title>" in xml
    assert "<term>Gear &amp; &lt;Devices&gt;</term>" in xml
    assert "<A:title>225A &amp; 3P&lt;4W&gt;</A:title>" in xml and "<A:title>42</A:title>" in xml
    assert "<A:product>w&amp;w</A:product>" in xml
    assert "<updated>2026-08-23T00:00:00Z</updated>" in xml
    assert "& " not in xml and "<Lab>" not in xml          # nothing raw survived


@needs_schema
def test_family_build_import_budget(tmp_path):
    """Generate + write one panelboard family as the prompt job does
    (``FamilyProduct.write``: emit incl. PartAtom, verify, family-validate,
    provenance) in a fresh interpreter; none of HEAVY may be imported."""
    rfa = str(tmp_path / "pp_139.rfa")
    code = (
        "import sys\n"
        f"sys.path.insert(0, {SRC!r})\n"
        "from rvt.famgen import factory as F\n"
        "prod = F.make_panelboard(mains_a=225, spaces=30, voltage='208Y/120', mcb=False)\n"
        f"prod.write({rfa!r})\n"
        f"bad = [m for m in {HEAVY!r} if m in sys.modules]\n"
        "assert not bad, f'family-build import budget (HEAVY) exceeded: {bad}'\n"
        "print('PARTATOM-LIGHT-OK')\n")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    assert "PARTATOM-LIGHT-OK" in r.stdout
