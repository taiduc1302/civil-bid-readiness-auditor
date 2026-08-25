# Pre-write hash revalidation

Any future candidate writer must re-hash the reviewed evidence immediately before writing a new test artifact.

This step exists to catch evidence drift between review/planning and file creation. It operates on bytes supplied by the caller and does not read or write project files by itself.

## Inputs

- the passing output-gate manifest;
- the passing versioned artifact plan;
- current bytes for every source role recorded in the gate manifest;
- current bytes for the approved schema/template authority.

## Required checks

1. every registered source role must have current bytes;
2. current SHA-256 must equal the reviewed SHA-256;
3. duplicate source roles are ambiguous at pre-write and block the step;
4. the `baseline_activities_import` identity carried in the artifact plan must still match the gate manifest;
5. current schema/template SHA-256 must equal the planned approved schema SHA-256;
6. the artifact plan must still be writer-ready;
7. mandatory safety flags must remain unchanged.

Any mismatch produces a blocker such as `source changed since review` or `schema authority changed since planning`.

## Output state

A successful verification reports only that the reviewed bytes still match the planned evidence. It deliberately preserves:

- `write_performed=false`
- `NOT_PRODUCTION_READY=true`
- `NOT_ESTIMATOR_VALIDATED=true`
- `HEAVYBID_IMPORT_VALIDATED=false`

A future candidate writer must consume a successful verification result in the same controlled operation and must not silently re-use a stale verification after source bytes change.
