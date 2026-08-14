# Checkpoint Evaluation Framework

Checkpoint Evaluation Framework (CEF) turns qualitative questions about generative-image behavior into reproducible multimodal experiments. It builds controlled prompt manifolds, generates images through a Forge/A1111-compatible API, evaluates them with configurable vision-language models, and preserves the evidence as structured JSON, provenance records, contact sheets, and browsable reports.

CEF characterizes behavior under stated conditions. It does not rank a checkpoint as universally “best,” and it does not turn visible outputs into unsupported claims about training data or hidden mechanisms.

> CEF is a methodology for generating progressively stronger questions about observable behavior, not progressively stronger claims about hidden mechanisms.

## What it demonstrates

- Declarative test manifolds across checkpoints, prompts, seeds, settings, and LoRA profiles
- Fixed-seed controls and counterfactual comparisons
- Resumable generation and evaluation with manifest-drift protection
- Forge/A1111 generation and OpenAI-compatible vision-model evaluation
- Run-local manifests, backend inventories, model hashes, PNG provenance, and integrity review
- Configurable criteria, references, evaluator roles, and human-review queues
- Machine-readable results alongside HTML reports and contact sheets
- Explicit uncertainty, failure records, and evaluator disagreement

## Five-minute dry run

Requirements: Python 3.10 or newer. No image backend or vision model is needed for this dry run.

```powershell
git clone https://github.com/detroitwobbly/checkpoint-evaluation-framework.git
cd checkpoint-evaluation-framework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

cef-eval generate `
  --manifest examples\safe_demo\controlled_materials_and_light.json `
  --output-root runs `
  --run-id safe_demo_dry_run `
  --dry-run

cef-review-run --run-root runs\safe_demo_dry_run
cef-release-audit --root .
python -m pytest
```

On macOS or Linux, activate with `source .venv/bin/activate` and use `/` in paths.

The dry run expands the 2-checkpoint × 1-profile × 6-test manifold into 12 auditable cells without contacting external services. Inspect `run_manifest.json`, `generation_index.json`, `run_state.json`, each `request.json`, and each `criteria.json`.

## Run a real experiment

1. Start a Forge/A1111-compatible backend with its API enabled.
2. Replace the placeholder checkpoint titles in the demo manifest with exact API-visible titles.
3. Probe the backend and generate:

```powershell
cef-eval probe-forge --base-url http://127.0.0.1:7860

cef-eval generate `
  --manifest examples\safe_demo\controlled_materials_and_light.json `
  --output-root runs `
  --run-id materials_and_light_v1 `
  --base-url http://127.0.0.1:7860 `
  --timeout 600
```

If generation stops, rerun the same command with `--resume`. CEF skips cells only when both `generation.json` and every expected image are present. It refuses to resume if the supplied manifest differs from the run-local snapshot.

4. Start an OpenAI-compatible vision endpoint, then evaluate:

```powershell
cef-eval analyze `
  --run-root runs\materials_and_light_v1 `
  --directive directives\safe_demo_evaluator.txt `
  --endpoint http://127.0.0.1:1234 `
  --model YOUR_VISION_MODEL `
  --timeout 600 `
  --continue-on-error
```

Analysis is resumable by default: existing per-image analysis records are reused unless `--overwrite` is supplied.

5. Extract embedded PNG provenance, rebuild the report, and review pipeline completeness:

```powershell
cef-eval extract-provenance --run-root runs\materials_and_light_v1
cef-eval report --run-root runs\materials_and_light_v1
cef-review-run --run-root runs\materials_and_light_v1
cef-eval serve-report --run-root runs\materials_and_light_v1
```

## Evidence products

A completed run can contain:

- `run_manifest.json` — immutable experimental snapshot
- `forge_inventory.json` — backend, checkpoint, and LoRA inventory at launch
- `run_state.json` — planned, completed, pending, and resumed cell counts
- `generation_index.json` — incrementally written generation ledger
- per-cell requests, criteria, generation metadata, images, and evaluator records
- `analysis_index.json` — machine-readable evaluation summary
- `png_provenance_index.json` — embedded-metadata extraction and hashes
- `report.json`, `report.html`, thumbnails, and contact sheet
- `run_pipeline_review.json` and `.html` — stage-by-stage completeness dashboard

Generated run folders are ignored by default. Publication must be an explicit curation decision.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Evaluation methodology](docs/EVALUATION_METHODOLOGY.md)
- [Resumability and artifact integrity](docs/RESUMABILITY_AND_INTEGRITY.md)
- [Artifact contract](docs/ARTIFACT_CONTRACT.md)
- [Safe demo protocol](examples/safe_demo/README.md)
- [Provenance and licensing decisions](docs/PROVENANCE_AND_LICENSING.md)
- [Limitations](docs/LIMITATIONS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security](SECURITY.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Validation record](VALIDATION.md)

## Current status

This is a curated release candidate extracted from a larger private research archive. The reusable core and tests are present; private runs, local paths, personal datasets, model files, explicit demo material, and artist-specific investigations are intentionally excluded.

No public demo images are bundled yet. Checkpoint selection and generated-output publication remain blocked on explicit provenance and licensing decisions.

## License

Code is licensed under AGPL-3.0-or-later. This license does not grant rights to third-party checkpoints, LoRAs, reference images, generated outputs, model names, or trademarks. See [Provenance and licensing](docs/PROVENANCE_AND_LICENSING.md) before publishing artifacts.
