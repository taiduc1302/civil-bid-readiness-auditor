"""Public server entrypoint with the Civil Estimate Review Auditor title.

Runtime behavior remains in ``server_legacy``. This wrapper patches only
user-visible product-title strings and the startup banner.
"""
from __future__ import annotations

import server_legacy as _server
from server_legacy import *  # noqa: F401,F403 - compatibility re-export

_LEGACY_TITLE = b"Civil Bid Readiness Auditor"
_PUBLIC_TITLE = b"Civil Estimate Review Auditor"
_original_home = _server.home


def home(message: str = "") -> bytes:
    return _original_home(message).replace(_LEGACY_TITLE, _PUBLIC_TITLE)


_server.home = home


def run() -> None:
    print(f"Civil Estimate Review Auditor running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


_server.run = run


if __name__ == "__main__":
    run()
