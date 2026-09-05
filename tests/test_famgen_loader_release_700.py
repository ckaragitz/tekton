"""test_famgen_loader_release_700.py -- famgen's host survey enters the host's
OWN release, so a BARE call works on the 2025 / 2024 certified bases (#700).

Before: ``survey_host`` relied on the CALLER having entered the file's release.
``rvt.partitions.CONTAINER_CLASS`` is rebound by name per release (2026 0x3a3,
2025 0x391, 2024 0x37b -- ``rvt/versions/__init__.py``), so with no context in
force the 2026 value was compared against a 2025/2024 header and the walker
raised before any family work began::

    ValueError: unexpected Partitions header: v=9 cls=0x391   (2025)
    ValueError: unexpected Partitions header: v=9 cls=0x37b   (2024)

That made the whole rfa -> rvt load lane look 2026-only from any entry that
surveys first, while ``route matrix`` advertises ``rfa -> rvt WORKS``.

After: ``survey_host`` is a thin wrapper that puts the host's own release in
force via ``rvt.global_framing.enter_own_release`` (the lenient ladder every
read-only instrument uses) and delegates to ``_survey_host_impl``, moved
byte-for-byte.  ``partitions.py``, ``versions/``, ``global_framing`` and
``release_ctx`` are untouched.

Scope note: ``load_family_into_project`` already entered the host release in
its own body (#14) and is deliberately NOT wrapped -- verified bare on the
2025 base before this change, so a second context would be redundant.

Evidence tiers: (1) the split itself; (2) bare survey on all three certified
bases; (3) nest-safety -- inside a caller's context the result is identical;
(4) 2026 is unchanged (regression pin on the watermark main produced).
"""
import os

import pytest

from rvt import versions as V
from rvt.famgen import loader as L

BASES = {
    2026: "plugin/assets/genesis/G_ABPD.rvt",
    2025: "plugin/assets/genesis/G_ABPD_2025.rvt",
    2024: "plugin/assets/genesis/G_ABPD_2024.rvt",
}

#: watermarks main produces for each base (2026 bare; 2025/2024 only reachable
#: on main by wrapping the call, which is the bug this issue fixes)
WATERMARKS = {2026: 1472524, 2025: 1472448, 2024: 1472509}


def _base(release: int) -> str:
    path = os.path.join(os.environ.get("TEKTON_ROOT", "."), BASES[release])
    if not os.path.exists(path):
        pytest.skip(f"certified base for {release} not in this clone")
    return path


# ---------------------------------------------------------------------------
# (1) the public/_impl split
# ---------------------------------------------------------------------------

def test_survey_host_is_a_wrapper_over_an_untouched_impl():
    assert callable(L._survey_host_impl), "the survey body must survive by name"
    assert L.survey_host is not L._survey_host_impl


# ---------------------------------------------------------------------------
# (2) a BARE call works on every certified base -- the regression
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_bare_survey_host_works_on_every_certified_base(release):
    ctx = L.survey_host(_base(release))
    assert ctx.watermark == WATERMARKS[release]


# ---------------------------------------------------------------------------
# (3) nest-safe: a caller's own context is joined, not fought
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("release", [2025, 2024])
def test_survey_inside_a_callers_context_is_identical(release):
    path = _base(release)
    bare = L.survey_host(path)
    with V.reading(path):
        wrapped = L.survey_host(path)
    assert bare.watermark == wrapped.watermark == WATERMARKS[release]


# ---------------------------------------------------------------------------
# (4) 2026 is unchanged
# ---------------------------------------------------------------------------

def test_2026_survey_is_unchanged():
    ctx = L.survey_host(_base(2026))
    assert ctx.watermark == 1472524
    assert ctx.category != 0
