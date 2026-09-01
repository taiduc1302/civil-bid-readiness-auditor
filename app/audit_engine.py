"""Public audit-engine entrypoint with current product identity.

All deterministic audit behavior remains in ``audit_engine_hardened``. This wrapper
changes the user-visible management-summary product title and exposes optional
operational evidence fields for explicit mapping. Crew Code / Production Rate are
not used by deterministic audit rules and are never inferred.
"""
from __future__ import annotations

import audit_engine_hardened as _engine
from audit_engine_hardened import *  # noqa: F401,F403 - compatibility re-export

_LEGACY_TITLE = b"Civil Bid Readiness Auditor"
_PUBLIC_TITLE = b"Civil Estimate Review Auditor"
_original_management_summary_html = _engine.management_summary_html

_OPERATIONAL_OPTIONAL_FIELDS = ("crew_code", "production_rate")
_OPERATIONAL_ALIASES = {
    "crew_code": ("crew code", "crew", "crew id"),
    "production_rate": ("production rate", "prod rate", "prod. rate", "production"),
}

# Extend the public mapping vocabulary while preserving the audit rule set. The
# hardened audit function resolves OPTIONAL_FIELDS from its module globals, and
# the inherited column_map helper resolves ALIASES from the legacy module where
# it was defined; keep both namespaces synchronized deliberately.
OPTIONAL_FIELDS = tuple(field for field in _engine.OPTIONAL_FIELDS if field not in _OPERATIONAL_OPTIONAL_FIELDS) + _OPERATIONAL_OPTIONAL_FIELDS
ALIASES = dict(_engine.ALIASES)
ALIASES.update(_OPERATIONAL_ALIASES)
_engine.OPTIONAL_FIELDS = OPTIONAL_FIELDS
_engine.ALIASES = ALIASES
_engine._legacy.OPTIONAL_FIELDS = OPTIONAL_FIELDS
_engine._legacy.ALIASES = ALIASES


def management_summary_html(result, filename):
    """Return the existing report with only the public product title migrated."""
    return _original_management_summary_html(result, filename).replace(_LEGACY_TITLE, _PUBLIC_TITLE)
