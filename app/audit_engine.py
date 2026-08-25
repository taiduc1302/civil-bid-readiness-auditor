"""Public audit-engine entrypoint with current product identity.

All deterministic audit behavior remains in ``audit_engine_hardened``. This wrapper
changes only the user-visible management-summary product title.
"""
from __future__ import annotations

import audit_engine_hardened as _engine
from audit_engine_hardened import *  # noqa: F401,F403 - compatibility re-export

_LEGACY_TITLE = b"Civil Bid Readiness Auditor"
_PUBLIC_TITLE = b"Civil Estimate Review Auditor"
_original_management_summary_html = _engine.management_summary_html


def management_summary_html(result, filename):
    """Return the existing report with only the public product title migrated."""
    return _original_management_summary_html(result, filename).replace(_LEGACY_TITLE, _PUBLIC_TITLE)
