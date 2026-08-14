# Resumability and artifact integrity

Long image and VLM runs fail for ordinary reasons: backend restarts, VRAM pressure, model swaps, timeouts, malformed responses, and operator interruptions. CEF treats recovery information as part of the evidence product.

## Generation recovery

Generation writes `generation_index.json` and `run_state.json` atomically after every completed cell. A temporary file is replaced only after valid JSON has been written, reducing the chance that interruption leaves a partially written index.

Use `--resume` with the same manifest, output root, and run ID. CEF then:

- compares the supplied manifest with `run_manifest.json`;
- refuses to mix changed experimental conditions into the existing run;
- treats a cell as complete only when `generation.json` parses and every recorded image exists;
- regenerates incomplete cells;
- preserves the original backend inventory and writes a timestamped resume inventory;
- records reused-cell counts in `run_state.json`.

Without `--resume` or `--overwrite`, CEF refuses to write into a non-empty run directory. `--overwrite` is also restricted to an unchanged run-local manifest; use a new run ID when the experiment changes.

## Analysis recovery

Analysis records are stored beside each generated image. A repeated analysis command reuses those records unless `--overwrite` is supplied. `--continue-on-error` preserves a structured evaluator-failure record and continues to the next image.

## Integrity layers

- Manifest snapshot: exact declared conditions for the run.
- Request record: payload actually sent for each cell.
- Backend inventory: observable backend, checkpoint, and LoRA state.
- Generation metadata: backend response and image paths.
- Model hashes: generation-response identity preferred over potentially stale post-switch options.
- PNG provenance: embedded parameter text, parsed fields, and file hashes where available.
- Pipeline review: stage completeness, artifact links, missing evidence, and human-review readiness.

## Remaining hardening opportunities

- Write a formal JSON Schema for every public artifact.
- Add a command that verifies all referenced files and hashes in one pass.
- Add retry/backoff policies configurable by endpoint and error class.
- Capture package, OS, GPU, driver, and backend commit versions in a normalized environment record.
- Add optional content-addressed artifact storage for large comparative runs.
- Add blinded/randomized review queues for confirmation studies.

These are roadmap items, not claims about the current release.
