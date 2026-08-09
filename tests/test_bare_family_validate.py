"""Bare-surface ECC verification + per-family validate (issue #75).

The bug: on the bare plugin surface (system Python, NO numpy) every generated
family's own report said ``validate.ok = false`` with
``ValueError('final block is not CRCIO-framed (raw stream?)')`` while the very
same ``.rfa`` was VALID under a dev checkout.  Root cause: the validator had
two ECC code paths -- a numpy syndrome decoder, and a numpy-free branch (#45)
that delegated to the strict codec inverse ``ecc.unframe_stream``, which
RAISES on any final block that does not re-encode exactly.
``skeleton.validate_family`` runs the arbiter a second time in raw project
mode, where a family's plain-XML ``PartAtom`` reaches the ECC tier: the numpy
path recorded a finding, the numpy-free path crashed the per-family report.

The fix deletes the divergence: ``ecc.lane_syndromes`` (stdlib, bit-sliced)
is now the validator's ONLY syndrome decoder on every surface.  Proven here,
sample-free (bundled genesis base only):

* ``lane_syndromes`` is exact: clean codewords are all-zero for every CRCIO
  parameter class, a flipped bit dirties exactly its lane with the signature
  that locates it, and damaged blocks match two independent oracles (a scalar
  per-lane CRC, and -- when numpy is installed -- the vectorised decoder the
  validator used to carry);
* ``final_block_candidates`` / ``unframe_stream`` round-trip ``frame_stream``
  for every size class (the samples-gated ``test_ecc.py`` cannot run in CI);
* ``ecc_verify_stream``: clean stream silent, single-bit damage repaired with
  a warning, a foreign trailer an ERROR, a non-CRCIO stream an ERROR finding
  with the raw bytes passed through -- never an exception;
* the three pinned bases validate 0 errors and nothing is "SKIPPED";
* an emitted ``.rfa`` passes ``skeleton.validate_family`` /
  ``famdoc_adoc.validate_family_file`` in-process AND in a genuinely
  numpy-less ``-I -S`` interpreter (engine + the plugin's vendored olefile).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
PLUGIN = os.path.join(ROOT, "plugin")
BUNDLED = {y: os.path.join(PLUGIN, "assets", "genesis", n)
           for y, n in ((2026, "G_ABPD.rvt"), (2025, "G_ABPD_2025.rvt"),
                        (2024, "G_ABPD_2024.rvt"))}
VENDOR = os.path.join(PLUGIN, "skills", "_shared", "_vendor")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(BUNDLED[2026]), reason="plugin bundle base absent")

from rvt import ecc                                   # noqa: E402
from rvt import validate as V                         # noqa: E402

try:
    import numpy as np
except ImportError:                                   # pragma: no cover
    np = None

# -I -S: isolated, no site -> no pip-installed extras at all (no numpy)
BARE_PY = [sys.executable, "-I", "-S"]

SIZES = [0, 5, 30, 100, 300, 1000, 3000, 20000, ecc.PAGE_PAYLOAD]


def _det_bytes(n: int, seed: int = 1) -> bytes:
    # deterministic xorshift payload (no os.urandom: reproducible failures)
    x, out = (seed & 0xFFFFFFFF) or 1, bytearray(n)
    for i in range(n):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        out[i] = x & 0xFF
    return bytes(out)


def _block(n: int, seed: int):
    """(encoded block, params, first, second) for an n-byte payload."""
    params = ecc.PARAM_CLASSES[0] if n == ecc.PAGE_PAYLOAD else ecc.select_params(n)
    m, _poly, period, align = params
    first, second = ecc.geometry(n, m, period, align, ecc.size_field_bits(period, align))
    return ecc.encode_block(_det_bytes(n, seed), params), params, first, second


# -- two independent oracles ---------------------------------------------------

def _scalar_syndromes(block: bytes, first: int, second: int, poly: int) -> list:
    """The CRCIO lane law stated the slow, obvious way: one reflected CRC
    (init 0) per lane over that lane's bits, parity rounds included."""
    out = []
    for lane in range(second):
        c = 0
        for r in range(first):
            p = r * second + lane
            fb = (c ^ (block[p >> 3] >> (p & 7))) & 1
            c >>= 1
            if fb:
                c ^= poly
        out.append(c)
    return out


def _numpy_syndromes(block: bytes, first: int, second: int, poly: int) -> list:
    """The vectorised decoder validate.py carried before #75 (kept here as an
    oracle only; the product no longer imports numpy for ECC)."""
    arr = np.frombuffer(block, dtype=np.uint8)[None, :]
    nb = first * second
    bits = np.unpackbits(arr[:, :(nb + 7) // 8], axis=1, bitorder="little")[:, :nb]
    bits = bits.reshape(1, first, second).transpose(1, 0, 2).reshape(first, second)
    c = np.zeros(second, dtype=np.uint16)
    p16 = np.uint16(poly)
    for r in range(first):
        fb = (c ^ bits[r]) & np.uint16(1)
        c >>= np.uint16(1)
        c ^= fb * p16
    return [int(x) for x in c]


# ---------------------------------------------------------------------------
# 1. the stdlib decoder is exact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", SIZES)
def test_clean_codeword_is_all_zero_and_one_flip_locates_itself(n):
    blk, params, first, second = _block(n, n + 7)
    m, poly, period, _align = params
    syn = ecc.lane_syndromes(blk, first, second, poly, m)
    assert len(syn) == second and not any(syn)
    bad = bytearray(blk)
    p = min(11, first * second - 1)
    bad[p >> 3] ^= 1 << (p & 7)
    syn = ecc.lane_syndromes(bytes(bad), first, second, poly, m)
    dirty = [i for i, s in enumerate(syn) if s]
    assert dirty == [p % second]
    d = V._signature_table(m, poly, period)[syn[dirty[0]]]
    assert first - 1 - d == p // second


@pytest.mark.parametrize("n", [5, 30, 100, 300, 1000, 3000])
def test_damaged_block_matches_the_scalar_oracle(n):
    blk, params, first, second = _block(n, n)
    bad = bytearray(blk)
    for k in (0, len(bad) // 3, len(bad) - 1):          # data, middle, parity area
        bad[k] ^= 0x5A
    assert ecc.lane_syndromes(bytes(bad), first, second, params[1], params[0]) == \
        _scalar_syndromes(bytes(bad), first, second, params[1])


@pytest.mark.skipif(np is None, reason="numpy absent: second oracle unavailable")
@pytest.mark.parametrize("n", [1000, 20000, ecc.PAGE_PAYLOAD])
def test_damaged_block_matches_the_numpy_oracle(n):
    blk, params, first, second = _block(n, n)
    bad = bytearray(blk)
    for k in (0, len(bad) // 3, len(bad) - 1):
        bad[k] ^= 0x5A
    assert ecc.lane_syndromes(bytes(bad), first, second, params[1], params[0]) == \
        _numpy_syndromes(bytes(bad), first, second, params[1])


@pytest.mark.parametrize("n", SIZES + [ecc.PAGE_PAYLOAD + 1, 2 * ecc.PAGE_PAYLOAD + 4321])
def test_unframe_roundtrips_frame_for_every_size_class(n):
    logical = _det_bytes(n, 3)
    raw = ecc.frame_stream(logical)
    assert ecc.unframe_stream(raw) == logical
    tail = raw[(len(raw) - 1) // ecc.PAGE_STRIDE * ecc.PAGE_STRIDE:] if raw else b""
    if tail:
        cands = ecc.final_block_candidates(tail)
        assert cands and all(ecc.select_params(dl) == p for p, dl in cands)


def test_unframe_still_raises_on_a_raw_stream():
    """The codec inverse keeps its strict contract; only the VALIDATOR must
    not use it as a degrade path."""
    with pytest.raises(ValueError, match="not CRCIO-framed"):
        ecc.unframe_stream(b"<?xml version='1.0'?><entry/>" * 20)
    assert ecc.final_block_candidates(b"<?xml version='1.0'?><entry/>" * 20) == []


# ---------------------------------------------------------------------------
# 2. ecc_verify_stream: findings, never exceptions
# ---------------------------------------------------------------------------

def _stream(tail_len=3000):
    logical = _det_bytes(2 * ecc.PAGE_PAYLOAD + tail_len, 99)
    return logical, ecc.frame_stream(logical)


def test_clean_stream_is_silent():
    logical, raw = _stream()
    rep = V.Report(path="(synthetic)")
    res = V.ecc_verify_stream("Global/Latest", raw, rep)
    assert res.logical == logical and res.pages == 3
    assert not rep.findings


@pytest.mark.parametrize("where", ["page", "tail"])
def test_single_bit_damage_is_repaired_with_a_warning(where):
    logical, raw = _stream()
    bad = bytearray(raw)
    off = ecc.PAGE_STRIDE + 1234 if where == "page" else 2 * ecc.PAGE_STRIDE + 77
    bad[off] ^= 0x08
    rep = V.Report(path="(synthetic)")
    res = V.ecc_verify_stream("Global/Latest", bytes(bad), rep)
    assert res.logical == logical, "single-bit data damage must be repaired downstream"
    assert res.data_bits_repaired == 1 and res.uncorrectable_blocks == 0
    assert [f.severity for f in rep.findings] == [V.SEV_WARNING]


def test_foreign_trailer_is_an_error_not_a_guess():
    logical, raw = _stream()
    bad = bytearray(raw)
    bad[ecc.PAGE_PAYLOAD:ecc.PAGE_STRIDE] = bytes(ecc.PAGE_STRIDE - ecc.PAGE_PAYLOAD)
    rep = V.Report(path="(synthetic)")
    res = V.ecc_verify_stream("Global/Latest", bytes(bad), rep)
    assert res.uncorrectable_blocks == 1
    assert [f.severity for f in rep.findings] == [V.SEV_ERROR]
    # beyond the repair envelope the ORIGINAL page bytes go downstream
    assert res.logical[:ecc.PAGE_PAYLOAD] == logical[:ecc.PAGE_PAYLOAD]


def test_non_crcio_stream_is_a_finding_never_an_exception():
    """THE #75 regression: a plain (unframed) stream handed to the ECC tier
    -- a family's PartAtom in project mode -- is an ERROR finding with the
    raw bytes passed through."""
    xml = (b'<?xml version="1.0" encoding="UTF-8"?><entry xmlns="http://www.w3.org/'
           b'2005/Atom"><title>panel</title>' + b"<x/>" * 190 + b"</entry>")
    rep = V.Report(path="(synthetic)")
    res = V.ecc_verify_stream("PartAtom", xml, rep)
    assert res.logical == xml
    assert [f.severity for f in rep.findings] == [V.SEV_ERROR]
    assert "not CRCIO-framed" in rep.findings[0].message


# ---------------------------------------------------------------------------
# 3. the pinned bases: verified (not skipped), clean, numpy never imported
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", sorted(BUNDLED))
def test_pinned_base_validates_clean_and_verifies_its_pages(year):
    if not os.path.isfile(BUNDLED[year]):
        pytest.skip(f"{year} base absent")
    rep = V.validate_file(BUNDLED[year])
    assert rep.ok, [f.message for f in rep.errors]
    assert not any("SKIPPED" in f.message for f in rep.findings), \
        "the ECC pages must be VERIFIED on every surface, not skipped"
    assert rep.stats["pages_checked"] > 0


def test_validator_never_imports_numpy(tmp_path):
    """One engine on every surface: even where numpy IS installed the
    validator does not touch it (so dev runs exercise the shipped path)."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {SRC!r})\n"
        "from rvt import validate as V\n"
        f"rep = V.validate_file({BUNDLED[2026]!r})\n"
        "assert rep.ok, [f.message for f in rep.errors]\n"
        "assert 'numpy' not in sys.modules, 'the validator pulled numpy'\n"
        "print('PAGES', rep.stats['pages_checked'])\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]
    assert int(r.stdout.split()[-1]) > 0


# ---------------------------------------------------------------------------
# 4. the family path: emitted .rfa, both arbiter passes, bare interpreter
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emitted_rfa(tmp_path_factory):
    """OUR constructive panelboard family, emitted once from the bundled
    base's schema (no vendor .rfa, no samples)."""
    from rvt.frontdoor import standalone as SA
    from rvt.famgen import factory as F, famdoc_adoc as FA
    SA.install_schema(BUNDLED[2026])
    doc = F.make_panelboard(start_id=18400).doc
    if not doc.finalized:
        doc.finalize()
    path = str(tmp_path_factory.mktemp("barefam") / "panel.rfa")
    FA.emit_family_rfa_v2(doc, path, donor=BUNDLED[2026], timestamp=0, write_reports=False)
    return path


def test_project_mode_on_a_family_reports_findings_not_a_traceback(emitted_rfa):
    rep = V.validate_file(emitted_rfa)                 # raw project mode, on purpose
    wheres = {f.where for f in rep.errors}
    assert "PartAtom" in wheres and "ProjectInformation" in wheres
    fam = V.validate_file(emitted_rfa, family=True)
    assert fam.ok, [f.message for f in fam.errors]


def test_validate_family_file_reports_both_verdicts(emitted_rfa):
    from rvt.famgen import famdoc_adoc as FA, skeleton as SK
    rep = SK.validate_family(emitted_rfa)
    assert rep["ok"] is True and rep["family_mode"]["verdict"] == "VALID"
    assert rep["project_mode"]["verdict"] == "INVALID"      # the honest raw comparison
    val = FA.validate_family_file(emitted_rfa, with_donor_parity=False)
    assert val["ok"] is True and val["family_mode"]["verdict"] == "VALID"


def test_validate_family_in_a_numpyless_interpreter(emitted_rfa, tmp_path):
    """End to end on a genuinely bare interpreter (``-I -S``: no
    site-packages, so no numpy; the engine + the plugin's vendored olefile
    only) -- the surface a stranger runs."""
    if not os.path.isdir(os.path.join(VENDOR, "olefile")):
        pytest.skip("vendored olefile absent from plugin/")
    out = str(tmp_path / "fam.json")
    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {SRC!r}); sys.path.insert(0, {VENDOR!r})\n"
        "try:\n    import numpy\n    raise SystemExit('premise broken: numpy importable under -I -S')\n"
        "except ImportError:\n    pass\n"
        "from rvt.famgen import skeleton as SK\n"
        f"rep = SK.validate_family({emitted_rfa!r})\n"
        f"json.dump(rep, open({out!r}, 'w'))\n")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    r = subprocess.run(BARE_PY + ["-c", code], capture_output=True, text=True,
                       env=env, timeout=300)
    assert r.returncode == 0, (r.stdout[-500:], r.stderr[-3000:])
    rep = json.load(open(out))
    assert rep["ok"] is True
    assert rep["family_mode"]["verdict"] == "VALID"
    assert rep["family_mode"]["n_errors"] == 0
    assert rep["project_mode"]["verdict"] == "INVALID"
