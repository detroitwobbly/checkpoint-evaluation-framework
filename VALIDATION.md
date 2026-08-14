# Validation record

Date: 2026-08-14

This record covers the curated release tree, not the private canonical research archive and not a live model/backend integration.

## Automated tests

Command:

```powershell
python -m pytest -q
```

Result: `55 passed`.

The suite covers manifest/model handling, request generation, checkpoint-hash selection, resume behavior, manifest-drift refusal, incomplete-cell recovery, analysis response parsing, provenance extraction, reporting, evaluator comparison, observer qualification, semantic observers, dossiers, pipeline-review output, and release sanitation.

## Distribution build and clean install

A wheel was built from `pyproject.toml` with no dependency resolution and installed into a new virtual environment.

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

## Not yet verified

- Forge/A1111 live generation using the final public-demo checkpoints
- OpenAI-compatible live VLM analysis using the final public evaluator
- Python 3.10–3.12 CI matrix on GitHub Actions
- GitHub Pages rendering from the final hosted location
- Generated-image rights and checkpoint output-use terms
- Clean editable install with dependencies fetched from a public package index

These remain explicit release gates.
