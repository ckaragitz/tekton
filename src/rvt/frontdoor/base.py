"""rvt.frontdoor.base -- the GENESIS BASE REGISTRY.

Every ``.rvt`` the front door authors is grown ON A BASE document.  The
product rule (docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #24) is
that the base is OUR composed genesis project (``G_ABPD``: settings / style
catalog / palette / datum / views / residue ALL our constructors' output,
composed with no Autodesk-authored base content) -- and NEVER an Autodesk
sample project.

This module owns that decision as data + code:

* :data:`PIN` -- the pinned default base (id, resolvable path, sha256,
  certification citation) read from ``assets/genesis_base.json`` beside this
  file, plus the SPECIMEN ANCESTOR the build step clones from (``R5``: the
  family-free genesis base carries no wall / instance specimen, so
  ``rvt.mutate`` clones a real one from the certified ancestor -- exactly the
  ifc-room stream's recipe).
* :func:`resolve_base` -- ``--base`` wins (user's authority; refused only
  when it is an Autodesk sample); otherwise the pinned genesis base is
  located (env ``RVT_GENESIS_BASE`` -> the repo path -> a plugin-bundled
  copy) and its sha256 MUST equal the pin.  A hash mismatch refuses the file
  as the DEFAULT: the pin is what makes "certified genesis base" true.
* :func:`is_autodesk_sample` -- the same test the job runner uses; a sample
  base is refused outright (it can never yield a deliverable and it
  contaminates the output with Autodesk-authored expression).

Nothing here reads or writes a ``.rvt``; it only NAMES the file the build
step opens.  Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

__all__ = ["BaseError", "BaseNotCertified", "GenesisPin", "ResolvedBase",
           "PIN", "load_pin", "resolve_base", "resolve_specimen_source",
           "is_autodesk_sample", "sha256_of", "repo_root", "release_status"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_PIN_PATH = os.path.join(_HERE, "assets", "genesis_base.json")

#: names of the six Autodesk sample projects the research corpus was built
#: on -- any file matching one of these is an Autodesk sample base
_SAMPLE_TOKENS = (
    "rmebasicsampleproject", "racbasicsampleproject", "racadvancedsampleproject",
    "rstbasicsampleproject", "rstadvancedsampleproject", "dach-sample-project",
    "sampleproject",
)


class BaseError(RuntimeError):
    """The base cannot be resolved / is refused (sample, missing, pin mismatch)."""


class BaseNotCertified(BaseError):
    """A target release was asked for whose genesis base is not yet
    certified+pinned (e.g. ``--target-version 2025`` while the 2025 campaign
    runs).  Distinct from :class:`BaseError` so the front door can DEGRADE
    HONESTLY (deliver the certified-release build + the fallback line + the
    version-agnostic IFC) instead of failing the whole request."""


# ---------------------------------------------------------------------------
# repo root discovery (the pin's relpaths are repo-relative)
# ---------------------------------------------------------------------------

def repo_root() -> str:
    """The tekton repo root: ``src/rvt/frontdoor`` is three levels down.
    Falls back to the current directory when the package is pip-installed
    outside a checkout (then only ``--base`` / ``$RVT_GENESIS_BASE`` /
    a bundled copy can resolve)."""
    cand = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
    if os.path.isdir(os.path.join(cand, "src", "rvt")):
        return cand
    return os.getcwd()


def sha256_of(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def is_autodesk_sample(path: Optional[str]) -> bool:
    """True if ``path`` is one of the Autodesk sample projects (or lives in
    the repo's ``samples/`` folder).  Mirrors ``tools/rvt_job.is_autodesk_sample``
    so the front door and the job runner agree on what is contaminated."""
    if not path:
        return False
    ap = os.path.abspath(path)
    samples_dir = os.path.abspath(os.path.join(repo_root(), "samples"))
    if ap.startswith(samples_dir + os.sep):
        return True
    base = os.path.basename(ap).lower()
    return any(tok in base for tok in _SAMPLE_TOKENS)


# ---------------------------------------------------------------------------
# the pin record
# ---------------------------------------------------------------------------

@dataclass
class GenesisPin:
    """The pinned default genesis base + the specimen ancestor (from
    ``assets/genesis_base.json``)."""
    raw: Dict[str, Any]

    # -- default base -------------------------------------------------------
    @property
    def base_id(self) -> str:
        return str(self.raw["default"]["id"])

    @property
    def base_relpath(self) -> str:
        return str(self.raw["default"]["relpath"])

    @property
    def base_sha256(self) -> str:
        return str(self.raw["default"]["sha256"])

    @property
    def base_bytes(self) -> Optional[int]:
        return self.raw["default"].get("bytes")

    @property
    def certification(self) -> Dict[str, Any]:
        return dict(self.raw["default"].get("certification") or {})

    @property
    def residue_disclosure(self) -> str:
        return str(self.raw["default"].get("residue_disclosure") or "")

    @property
    def revit_release(self) -> str:
        return str(self.raw["default"].get("revit_release") or "2026")

    # -- per-release slots (the B2025 lineage etc.) --------------------------
    def release_years(self) -> List[int]:
        """Every release year the registry carries a slot for (certified or
        pending).  The default base's own release is always included."""
        out = {int(self.revit_release)}
        for k in (self.raw.get("releases") or {}):
            if str(k).isdigit():
                out.add(int(k))
        return sorted(out)

    def release_slot(self, year: int) -> Optional[Dict[str, Any]]:
        """The registry slot for one release year (None when the registry has
        never heard of that release).  The default-release slot is synthesized
        from the ``default`` record so 2026 always resolves."""
        rel = (self.raw.get("releases") or {}).get(str(int(year)))
        if rel is not None and str(rel.get("uses") or "") == "default":
            d = dict(self.raw["default"])
            d.setdefault("status", "certified")
            return d
        if rel is None and int(year) == int(self.revit_release):
            d = dict(self.raw["default"])
            d.setdefault("status", "certified")
            return d
        return dict(rel) if rel is not None else None

    # -- specimen ancestor ---------------------------------------------------
    @property
    def specimen_id(self) -> str:
        return str(self.raw["specimen_ancestor"]["id"])

    @property
    def specimen_relpath(self) -> str:
        return str(self.raw["specimen_ancestor"]["relpath"])

    @property
    def specimen_sha256(self) -> Optional[str]:
        return self.raw["specimen_ancestor"].get("sha256")

    def candidate_paths(self, plugin_root: Optional[str] = None,
                        relpath: Optional[str] = None) -> List[str]:
        """Where a pinned base may live, in resolution order (after
        ``--base`` and ``$RVT_GENESIS_BASE``).  ``relpath`` defaults to the
        default base's; pass a release slot's relpath to locate that one."""
        rp = relpath or self.base_relpath
        name = os.path.basename(rp)
        out = [os.path.join(repo_root(), rp)]
        # dev/cloud checkout: the source-of-truth plugin tree ships the
        # pinned bases in-repo (plugin/assets/genesis) even when the research
        # compose (experiments/...) is git-ignored and absent -- still
        # sha-verified against the pin by every caller
        out.append(os.path.join(repo_root(), "plugin", "assets", "genesis", name))
        # the plugin mounts the engine at <plugin>/lib/src/rvt/** and the ONE
        # bundled .rvt at <plugin>/assets/genesis/ -- discover the bundle
        # relative to THIS package, then honour explicit roots
        pkg_plugin = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
        for pr in (plugin_root, os.environ.get("RVT_PLUGIN_ROOT"), pkg_plugin):
            if pr:
                out.append(os.path.join(pr, "assets", "genesis", name))
                out.append(os.path.join(pr, "lib", "genesis", name))
        return out

    def as_json(self) -> Dict[str, Any]:
        return {
            "id": self.base_id, "relpath": self.base_relpath,
            "sha256": self.base_sha256, "bytes": self.base_bytes,
            "revit_release": self.revit_release,
            "certification": self.certification,
            "residue_disclosure": self.residue_disclosure,
            "specimen_ancestor": {"id": self.specimen_id,
                                  "relpath": self.specimen_relpath,
                                  "sha256": self.specimen_sha256},
        }


def load_pin(path: str = _PIN_PATH) -> GenesisPin:
    with open(path) as fh:
        return GenesisPin(json.load(fh))


#: the shipped pin (loaded once; ``assets/genesis_base.json`` is data)
PIN: GenesisPin = load_pin()


# ---------------------------------------------------------------------------
# per-release status (the honest answer to "can you build me a Revit-N file?")
# ---------------------------------------------------------------------------

def release_status(year: int, *, pin: GenesisPin = PIN) -> Dict[str, Any]:
    """What this registry can honestly say about authoring for one Revit
    release.  ``certified`` is True ONLY when three sources agree: the slot
    says ``status: certified``, the slot carries a sha256 pin, and the
    version model (``rvt.versions.KNOWN_RELEASES[year].creation_certified``)
    concurs.  Anything less is ``pending certification`` (a slot exists, the
    campaign is running) or ``no slot`` (the registry has never heard of the
    release)."""
    year = int(year)
    slot = pin.release_slot(year)
    model_certified: Optional[bool] = None
    try:
        from .. import versions as _V
        model_certified = year in _V.SUPPORTED_CREATION_RELEASES
    except Exception:                                         # pragma: no cover
        model_certified = None                                # versions absent: slot-only
    slot_certified = bool(slot and str(slot.get("status") or "") == "certified"
                          and slot.get("sha256"))
    certified = bool(slot_certified and model_certified is not False)
    if certified:
        status = "certified"
    elif slot is not None:
        status = str(slot.get("status") or "pending certification")
    else:
        status = "no slot"
    return {
        "release": year,
        "certified": certified,
        "status": status,
        "id": (slot or {}).get("id"),
        "relpath": (slot or {}).get("relpath"),
        "sha256": (slot or {}).get("sha256"),
        "slot_certified": slot_certified,
        "version_model_certified": model_certified,
        "pending_reason": (slot or {}).get("pending_reason"),
        "lineage": (slot or {}).get("lineage"),
    }


def _certified_slot_for_digest(digest: str, *, pin: GenesisPin = PIN) -> Optional[Dict[str, Any]]:
    """The CERTIFIED registry slot whose pinned sha256 IS ``digest`` (a copy
    of ``G_ABPD_2025.rvt`` arriving by path is still our certified 2025 base),
    or None -- a firm's own base, a stale copy, a pending slot's bytes."""
    for year in pin.release_years():
        st = release_status(year, pin=pin)
        if st["certified"] and str(st["sha256"]).lower() == digest.lower():
            return pin.release_slot(year)
    return None


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------

@dataclass
class ResolvedBase:
    """The base file the build step will open, with WHY it is trusted."""
    path: str
    source: str                        # 'explicit' | 'env' | 'pinned-repo' | 'pinned-bundled'
    sha256: str
    pinned: bool                       # True = matched a certified release slot's pin
    is_autodesk_sample: bool = False
    certified: bool = False            # True only for a certified slot's pinned bytes
    certification: Dict[str, Any] = dc_field(default_factory=dict)
    warnings: List[str] = dc_field(default_factory=list)

    def as_json(self) -> Dict[str, Any]:
        return {
            "path": os.path.abspath(self.path), "source": self.source,
            "sha256": self.sha256, "pinned": self.pinned,
            "certified_genesis_base": self.certified,
            "is_autodesk_sample": self.is_autodesk_sample,
            "certification": self.certification if self.certified else None,
            "warnings": list(self.warnings),
        }


def _require_base_release(path: str, target: int, *, what: str) -> None:
    """A base offered for a version-N build MUST itself be release N -- the
    never-silent guard (``rvt.versions.require_release``).  Lazy import so a
    stripped install without the version model still resolves 2026."""
    try:
        from .. import versions as _V
    except Exception:                                         # pragma: no cover
        return
    actual = _V.detect_release(path)
    _V.require_release(actual, int(target), what=what)


def resolve_base(explicit: Optional[str] = None, *,
                 pin: GenesisPin = PIN,
                 allow_sample: bool = False,
                 target_release: Optional[int] = None) -> ResolvedBase:
    """Resolve the base ``.rvt`` to author on.

    ``explicit`` (the CLI's ``--base``) wins and is taken on the user's
    authority -- but an Autodesk sample project is REFUSED (unless the
    caller explicitly sets ``allow_sample`` for a research probe, in which
    case the output can only ever be PROOF-ONLY).  Otherwise the pinned
    genesis base is located and its sha256 verified against the pin; a
    mismatch or a missing file is a :class:`BaseError` (never a silent
    substitution).

    ``target_release`` (the CLI's ``--target-version``) selects WHICH
    release's certified base: the registry slot for that year must be
    certified + pinned + agreed by the version model, or the resolution
    raises :class:`BaseNotCertified` (the front door then degrades honestly
    -- it never silently authors a newer-release file for the target).  A
    user-supplied ``--base`` / ``$RVT_GENESIS_BASE`` combined with a target
    must itself BE that release (checked, refused on mismatch).
    """
    if explicit:
        p = os.path.abspath(explicit)
        if not os.path.isfile(p):
            raise BaseError(f"--base file not found: {explicit}")
        sample = is_autodesk_sample(p)
        if sample and not allow_sample:
            raise BaseError(
                f"--base {explicit!r} is an Autodesk sample project -- refused. "
                "The front door authors ONLY on our certified genesis base (default) "
                "or a base you supply that is not an Autodesk sample. Nothing "
                "grown on a sample is a product (P0 provenance gate G1).")
        digest = sha256_of(p)
        slot = _certified_slot_for_digest(digest, pin=pin)
        pinned = slot is not None
        rb = ResolvedBase(path=p, source="explicit", sha256=digest, pinned=pinned,
                          is_autodesk_sample=sample, certified=pinned,
                          certification=dict(slot.get("certification") or {}) if slot else {})
        if not pinned:
            rb.warnings.append(
                "explicit --base is not the pinned genesis base: accepted on the "
                "user's authority, provenance-ledgered, and never asserted certified")
        if sample:
            rb.warnings.append("Autodesk sample base allowed by allow_sample: "
                               "output is PROOF-ONLY by construction")
        if target_release is not None:
            _require_base_release(p, target_release, what="--base file")
        return rb

    # -- env var (a firm's own certified base) ---------------------------
    envp = os.environ.get("RVT_GENESIS_BASE")
    if envp:
        p = os.path.abspath(envp)
        if not os.path.isfile(p):
            raise BaseError(f"$RVT_GENESIS_BASE file not found: {envp}")
        if is_autodesk_sample(p):
            raise BaseError(f"$RVT_GENESIS_BASE {envp!r} is an Autodesk sample project -- refused")
        digest = sha256_of(p)
        slot = _certified_slot_for_digest(digest, pin=pin)
        pinned = slot is not None
        rb = ResolvedBase(path=p, source="env", sha256=digest, pinned=pinned,
                          certified=pinned,
                          certification=dict(slot.get("certification") or {}) if slot else {})
        if not pinned:
            rb.warnings.append("$RVT_GENESIS_BASE is not the pinned genesis base "
                               "(accepted on the environment's authority)")
        if target_release is not None:
            _require_base_release(p, target_release, what="$RVT_GENESIS_BASE file")
        return rb

    # -- a NON-default target release: the registry slot decides -------------
    if target_release is not None and int(target_release) != int(pin.revit_release):
        st = release_status(int(target_release), pin=pin)
        if not st["certified"]:
            raise BaseNotCertified(
                f"no certified Revit {int(target_release)} genesis base yet "
                f"(registry slot: {st['status']}"
                + (f"; id {st['id']}" if st.get("id") else "")
                + "). "
                + (str(st.get("pending_reason") or
                       "the per-release genesis campaign has not certified a base for "
                       "this target; see docs/writer/genesis-2025-plan.md")))
        slot = pin.release_slot(int(target_release)) or {}
        tried_r: List[str] = []
        for cand in pin.candidate_paths(relpath=str(slot.get("relpath"))):
            tried_r.append(cand)
            if not os.path.isfile(cand):
                continue
            digest = sha256_of(cand)
            if digest.lower() != str(slot.get("sha256") or "").lower():
                raise BaseError(
                    f"Revit {int(target_release)} genesis base pin MISMATCH at {cand}: "
                    f"sha256 {digest[:16]}... != pinned {str(slot.get('sha256'))[:16]}... "
                    "-- refusing to substitute it silently; re-pin after re-certification.")
            _require_base_release(cand, int(target_release),
                                  what=f"pinned Revit {int(target_release)} genesis base")
            src = ("pinned-repo" if cand == pin.candidate_paths(
                relpath=str(slot.get("relpath")))[0] else "pinned-bundled")
            return ResolvedBase(path=cand, source=src, sha256=digest, pinned=True,
                                certified=True,
                                certification=dict(slot.get("certification") or {}))
        raise BaseError(
            f"the pinned Revit {int(target_release)} genesis base {slot.get('id')} was "
            "not found (tried: " + "; ".join(tried_r) + "). Set $RVT_GENESIS_BASE or "
            "pass --base. The front door never falls back to an Autodesk sample.")

    # -- the pinned genesis base ---------------------------------------------
    tried: List[str] = []
    for cand in pin.candidate_paths():
        tried.append(cand)
        if not os.path.isfile(cand):
            continue
        digest = sha256_of(cand)
        if digest.lower() != pin.base_sha256.lower():
            raise BaseError(
                f"genesis base pin MISMATCH at {cand}: sha256 {digest[:16]}... != pinned "
                f"{pin.base_sha256[:16]}... -- the certified {pin.base_id} has changed on "
                "disk. Refusing to substitute it silently; re-pin (assets/genesis_base.json) "
                "after re-certification, or pass --base explicitly.")
        src = "pinned-repo" if cand == pin.candidate_paths()[0] else "pinned-bundled"
        return ResolvedBase(path=cand, source=src, sha256=digest, pinned=True,
                            certified=True, certification=pin.certification)
    raise BaseError(
        f"the pinned genesis base {pin.base_id} was not found (tried: "
        + "; ".join(tried) + "). Set $RVT_GENESIS_BASE or pass --base. "
        "The front door never falls back to an Autodesk sample.")


def resolve_specimen_source(explicit: Optional[str] = None, *,
                            pin: GenesisPin = PIN,
                            verify_hash: bool = False) -> str:
    """The SPECIMEN ANCESTOR ``.rvt`` the build clones scaffolding from (the
    family-free genesis base carries no wall / instance specimen; the certified
    ancestor R5 -- same lineage, ids continuous -- does).  Never emitted into
    the output; a clone TEMPLATE only."""
    if explicit:
        p = os.path.abspath(explicit)
        if not os.path.isfile(p):
            raise BaseError(f"--specimens file not found: {explicit}")
        return p
    cand = os.path.join(repo_root(), pin.specimen_relpath)
    if not os.path.isfile(cand):
        raise BaseError(f"specimen ancestor {pin.specimen_id} not found at {cand} "
                        "(pass --specimens <path>)")
    if verify_hash and pin.specimen_sha256:
        got = sha256_of(cand)
        if got.lower() != str(pin.specimen_sha256).lower():
            raise BaseError(f"specimen ancestor {pin.specimen_id} hash changed "
                            f"({got[:16]}... != {str(pin.specimen_sha256)[:16]}...)")
    return cand


if __name__ == "__main__":  # pragma: no cover
    import sys
    try:
        rb = resolve_base(sys.argv[1] if len(sys.argv) > 1 else None)
        print(json.dumps(rb.as_json(), indent=1))
        print("specimens:", resolve_specimen_source())
    except BaseError as e:
        print(f"BaseError: {e}")
        raise SystemExit(2)
