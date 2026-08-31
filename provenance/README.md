# Public snapshot provenance

This directory preserves historical release/staging evidence. It is **not** a current-tree integrity manifest and it is not consumed by the application runtime.

## Initial public snapshot — 2026-08-19

`initial_public_snapshot_2026-08-19/ALLOWLIST_MANIFEST.json` is the original allowlist/hash record generated on **2026-08-19** for the repository's initial public snapshot/release-staging process.

The file is intentionally preserved without regenerating its historical hashes or sizes. The repository changed substantially after that snapshot, so its recorded file identities must **not** be compared to the present source tree as though they were current release hashes.

The former root-level filename `ALLOWLIST_MANIFEST.json` was removed because its unqualified location could be misread as describing the current repository tree. No provenance evidence was discarded; the original manifest content remains under the dated historical path above.

## Current-release integrity status

There is currently **no generated current-release source-tree allowlist manifest**. If one is introduced later, it must have a separate versioned contract that records the exact commit/ref, generates hashes from that exact intended release tree, and provides a deterministic drift-verification step. Historical snapshot evidence must remain separate from current-release integrity evidence.
