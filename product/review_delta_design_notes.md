# Review Delta design notes

This file intentionally contains no implementation state. Implementation belongs in a feature branch/PR.

Key decision: compare archived evidence by stable review anchors rather than finding IDs. Finding IDs are deterministic only within one audit result ordering and are not a safe cross-snapshot identity. The comparator therefore aligns findings by sheet + source row + rule + field and fails closed on duplicate anchors.

Reference checks are aligned independently by reference type + sheet + source row + source code. Reference metadata drift is reported separately by role.
