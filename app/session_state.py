"""Thread-safe temporary session lifecycle helpers.

The local server uses ``ThreadingHTTPServer``.  Review state therefore needs a
per-session synchronization boundary so simultaneous requests against one token
cannot interleave read/validate/write operations.  Different tokens keep
independent locks and may proceed concurrently.

Session lifetime is an idle timeout.  A successful lookup refreshes
``last_access``; the original ``created`` value remains provenance only.
"""
from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Any, Iterator, MutableMapping
from weakref import WeakValueDictionary

_REGISTRY_LOCK = threading.RLock()
# Weak values avoid retaining one lock forever for every historical token. Any
# request holding or waiting on a lock keeps its own strong reference, so all
# concurrent users of that token continue to share the same synchronization
# object. Once no thread references an unused lock, the registry entry may be
# collected safely without an explicit pop race.
_SESSION_LOCKS: WeakValueDictionary[str, threading.RLock] = WeakValueDictionary()


def _clock() -> float:
    return time.monotonic()


def _lock_for(token: str) -> threading.RLock:
    with _REGISTRY_LOCK:
        lock = _SESSION_LOCKS.get(token)
        if lock is None:
            lock = threading.RLock()
            _SESSION_LOCKS[token] = lock
        return lock


def _stamp(session: dict[str, Any]) -> float:
    raw = session.get("last_access", session.get("created", 0.0))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def register_session(
    sessions: MutableMapping[str, dict[str, Any]],
    token: str,
    session: dict[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Register one temporary session and initialize idle-timeout metadata."""
    if not token:
        raise ValueError("Session token must not be blank.")
    stamp = _clock() if now is None else float(now)
    session.setdefault("created", stamp)
    session["last_access"] = stamp
    with _REGISTRY_LOCK:
        sessions[token] = session
        # Ensure a lock exists while this registration operation is active. It
        # may later be garbage-collected if no request holds/waits on it; that
        # is safe because no concurrent user can then still reference it.
        lock = _SESSION_LOCKS.get(token)
        if lock is None:
            lock = threading.RLock()
            _SESSION_LOCKS[token] = lock
    return session


@contextmanager
def session_scope(
    sessions: MutableMapping[str, dict[str, Any]],
    token: str,
    ttl_seconds: float,
    *,
    touch: bool = True,
    now: float | None = None,
) -> Iterator[dict[str, Any] | None]:
    """Serialize access to one active session and optionally refresh idle time.

    The per-session lock stays held for the entire caller context.  This is the
    atomicity boundary for read-copy-validate-write operations such as review
    saves, reference replacement, audit replacement, and one-time bulk apply.
    """
    if not token:
        yield None
        return
    lock = _lock_for(token)
    with lock:
        current = _clock() if now is None else float(now)
        with _REGISTRY_LOCK:
            session = sessions.get(token)
            if session is None:
                active = None
            elif current - _stamp(session) > float(ttl_seconds):
                sessions.pop(token, None)
                active = None
            else:
                if touch:
                    session["last_access"] = current
                active = session
        yield active


def expire_sessions(
    sessions: MutableMapping[str, dict[str, Any]],
    ttl_seconds: float,
    *,
    now: float | None = None,
) -> list[str]:
    """Remove idle sessions without interrupting a request currently using one."""
    current = _clock() if now is None else float(now)
    with _REGISTRY_LOCK:
        tokens = list(sessions)

    expired: list[str] = []
    for token in tokens:
        lock = _lock_for(token)
        if not lock.acquire(blocking=False):
            # A live request owns the session; let that request refresh/access it
            # before a later expiry pass decides whether it is idle.
            continue
        try:
            with _REGISTRY_LOCK:
                session = sessions.get(token)
                if session is not None and current - _stamp(session) > float(ttl_seconds):
                    sessions.pop(token, None)
                    expired.append(token)
        finally:
            lock.release()
    return expired


def session_lock_registry_size() -> int:
    """Return current live lock count for tests/diagnostics only."""
    with _REGISTRY_LOCK:
        return len(_SESSION_LOCKS)


def clear_session_locks() -> None:
    """Test/support helper; active application code does not need to call this."""
    with _REGISTRY_LOCK:
        _SESSION_LOCKS.clear()
