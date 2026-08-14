# Validation record

Date: 2026-08-14

This record covers the curated release tree and the private Demo 1 integration run. It does not alter the private canonical research archive and does not approve publication of generated artifacts.

## Automated tests

Command:

```powershell
python -m pytest -q
```

Result: `57 passed`.

The suite covers manifest/model handling, request generation, checkpoint-hash selection, resume behavior, manifest-drift refusal, incomplete-cell recovery, analysis response parsing, provenance extraction, reporting, evaluator comparison, observer qualification, semantic observers, dossiers, pipeline-review output, and release sanitation.

## Distribution build and clean install

A wheel was built from `pyproject.toml` with no dependency resolution and installed into a new virtual environment.

The private GitHub repository was also cloned into a separate temporary directory at commit `94a6050`. A new virtual environment installed the clone in editable mode using standard PEP 517 build isolation, and the installed `cef-eval` entry point started successfully. This verifies that the tracked remote tree does not rely on untracked workspace files.

Verified installed entry points:

- `cef-eval`
- `cef-review-run`
- `cef-release-audit`

The wheel contained only the reusable Python packages, command helpers, metadata, and license. It contained no generated runs, model weights, caches, private documents, or research archive.

## Safe demo dry run

The installed `cef-eval` expanded `controlled_materials_and_light.json` without contacting a backend.

Result:

- planned cells: 12
- completed dry-run cells: 12
- pending cells: 0
- run state: `complete`
- pipeline-review JSON and HTML: built successfully

## Sanitation audit

`cef-release-audit --root .` reported zero errors and zero warnings after the GitHub repository identity was finalized.

Additional scans found no personal username, personal absolute path, named private study, model-weight file, or copied generated artifact in the curated source tree.

## Private live integration

Verified on 2026-08-14:

- exact SHA-256 verification for SDXL Base 1.0 and RealVisXL V5.0 FP16;
- one Forge-Neo canary per checkpoint;
- one complete 12-cell generation run with 12/12 PNG provenance extractions;
- one complete Qwen3-VL 8B structured analysis run through LM Studio;
- preservation and targeted retry of one malformed evaluator response;
- top-level evaluator model, endpoint, settings, and directive-hash provenance;
- HTML, JSON, contact-sheet, and pipeline-review artifact generation.

See [Demo 1 run record](docs/DEMO_1_RUN_RECORD.md). Generated artifacts remain ignored and private pending final sanitized-bundle review and Pages activation.

## Sanitized public-demo export

The approved run was exported into a private Pages candidate with 12 losslessly re-encoded PNGs. For each image, the exporter:

- preserves and records the private source SHA-256;
- removes the raw Forge/A1111 `parameters` chunk;
- adds only the versioned CEF identity-and-hash envelope;
- verifies pixel equivalence after re-encoding;
- records both hashes and the exact transformation in `artifact_index.json`.

The Demo 1 raw Forge parameter keys retained privately are `Steps`, `Sampler`, `Schedule type`, `CFG scale`, `Seed`, `Size`, `Model hash`, `Model`, `RNG`, and `Version`. None of their values are copied into public PNG metadata.

## Not yet verified

- Python 3.10–3.12 CI matrix on GitHub Actions
- GitHub Pages rendering from the final hosted location
- Final human approval of generated images and sanitized publication metadata

These remain explicit release gates.
