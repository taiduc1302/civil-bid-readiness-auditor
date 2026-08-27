"""Fixed synthetic onboarding fixtures exposed by the local demo UI."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRUCTURED_ESTIMATE = ROOT / "samples" / "synthetic_heavybid_style_resource_export.csv"
DEMO_REFERENCES = {
    "activity": ROOT / "samples" / "synthetic_activity_reference.csv",
    "resource": ROOT / "samples" / "synthetic_resource_reference.csv",
}


def structured_estimate() -> tuple[str, bytes]:
    """Return the single bundled fictional structured estimate fixture."""
    return STRUCTURED_ESTIMATE.name, STRUCTURED_ESTIMATE.read_bytes()


def reference_fixture(role: str) -> tuple[str, bytes]:
    """Return one explicitly allowed fictional reference fixture by role."""
    role = str(role or "").strip().casefold()
    path = DEMO_REFERENCES.get(role)
    if path is None:
        raise ValueError(f"Unsupported fictional reference role: {role}")
    return path.name, path.read_bytes()
