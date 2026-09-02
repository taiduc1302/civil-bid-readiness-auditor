"""Deterministic startup contract for public runtime features.

Feature modules expose idempotent installers, but importing unrelated content
(such as onboarding text) must not decide runtime behavior.  The public server
calls ``compose_public_runtime`` explicitly once during startup/import.
"""
from __future__ import annotations

from collections.abc import Callable

from accessibility import install_accessibility_semantics
from archived_review_ui import install_archived_review_ui
from bulk_review_ui import install_bulk_review_ui
from operational_reference_ui import install_operational_reference_ui
from review_delta_ui import install_review_delta_ui
from review_delta_verification import install_review_delta_verification_ui
from review_evidence_navigation import install_review_evidence_navigation
from review_timeline_ui import install_review_timeline_ui
from review_view_context import install_review_view_context

Installer = Callable[[], None]

_PUBLIC_FEATURES: tuple[tuple[str, Installer], ...] = (
    ("accessibility_semantics", install_accessibility_semantics),
    ("bulk_review_ui", install_bulk_review_ui),
    ("review_view_context", install_review_view_context),
    ("operational_reference_ui", install_operational_reference_ui),
    ("archived_review_ui", install_archived_review_ui),
    ("review_delta_ui", install_review_delta_ui),
    ("review_delta_verification_ui", install_review_delta_verification_ui),
    ("review_timeline_ui", install_review_timeline_ui),
    # Keep this last so it wraps the final composed page renderer without
    # changing any evidence route's independent verification behavior.
    ("review_evidence_navigation", install_review_evidence_navigation),
)


def public_feature_names() -> tuple[str, ...]:
    """Return the explicit deterministic feature order used by the public runtime."""
    return tuple(name for name, _ in _PUBLIC_FEATURES)


def compose_public_runtime() -> tuple[str, ...]:
    """Install all public runtime features in one explicit deterministic order."""
    for _, installer in _PUBLIC_FEATURES:
        installer()
    return public_feature_names()
