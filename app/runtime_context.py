"""Explicit render context for public runtime feature composition.

User-visible page titles are presentation text and must never decide whether
review-only controls are installed.  A small ContextVar carries stable internal
page identity through the shared page-renderer wrapper chain instead.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

PAGE_KIND_GENERIC = "generic"
PAGE_KIND_REVIEW_FINDINGS = "review_findings"

_PAGE_KIND: ContextVar[str] = ContextVar("civil_estimate_review_page_kind", default=PAGE_KIND_GENERIC)


def current_page_kind() -> str:
    """Return the stable internal identity of the page currently being rendered."""
    return _PAGE_KIND.get()


@contextmanager
def page_context(kind: str) -> Iterator[None]:
    """Temporarily set explicit page identity for nested renderer wrappers."""
    value = str(kind or PAGE_KIND_GENERIC)
    token = _PAGE_KIND.set(value)
    try:
        yield
    finally:
        _PAGE_KIND.reset(token)
