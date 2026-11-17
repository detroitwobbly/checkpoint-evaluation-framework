# Checkpoint Evaluation Framework

Checkpoint Evaluation Framework (CEF) turns qualitative questions about generative-image behavior into reproducible multimodal experiments. It builds controlled prompt manifolds, generates images through a Forge/A1111-compatible API, evaluates them with configurable vision-language models, and preserves the evidence as structured JSON, provenance records, contact sheets, and browsable reports.

CEF characterizes behavior under stated conditions. It does not rank a checkpoint as universally “best,” and it does not turn visible outputs into unsupported claims about training data or hidden mechanisms.

> CEF is a methodology for generating progressively stronger questions about observable behavior, not progressively stronger claims about hidden mechanisms.

**[View the live controlled materials, lighting, and count demonstration](https://detroitwobbly.github.io/checkpoint-evaluation-framework/)** — 12 fixed-seed generations across two SDXL checkpoints, with machine evaluation, human adjudication, structured evidence, and sanitized provenance.

## What it demonstrates

- Declarative test manifolds across checkpoints, prompts, seeds, settings, and LoRA profiles
- Fixed-seed controls and counterfactual comparisons
- Resumable generation and evaluation with manifest-drift protection
- Forge/A1111 or ComfyUI generation and OpenAI-compatible vision-model evaluation
- Run-local manifests, backend inventories, model hashes, PNG provenance, and integrity review
- Configurable criteria, references, evaluator roles, and human-review queues
- Machine-readable results alongside HTML reports and contact sheets
- Explicit uncertainty, failure records, and evaluator disagreement

## Designed for constrained hardware

CEF is designed under real hardware constraints rather than idealized cloud assumptions. SDXL generation and local vision-model evaluation run as separate, sequential stages so diffusion and VLM workloads do not compete for limited memory. Runs are divided into independently recoverable cells; completed work is not regenerated under resume; and resource telemetry, model release, and failure recovery are treated as first-class workflow concerns.

The ComfyUI backend resolves and saves its executable and editable graphs before submission, then persists the accepted prompt ID before CEF waits for or retrieves the result. This makes interrupted runner processes recoverable without silently submitting the same work twice. The backend was validated on an NVIDIA RTX 3080 with 12 GB VRAM and approximately 16 GB system RAM, including full SDXL generation, positive and negative LoRA weights, embedded workflow provenance, cache-safe idempotency, cross-process prompt recovery, explicit model/memory release, and cold-process pixel repeatability for the tested graph.

Constraint awareness is part of the architecture, not an accommodation added after an out-of-memory failure. The demonstrated operating envelope is sequential execution; concurrency is not implied.

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
2. Verify that the demo manifest's checkpoint hashes match your files. If your backend renamed the files, replace only the API-visible titles.
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
- [Vision-model observer qualification](docs/VISION_MODEL_OBSERVER_QUALIFICATION.md)
- [Resumability and artifact integrity](docs/RESUMABILITY_AND_INTEGRITY.md)
- [Artifact contract](docs/ARTIFACT_CONTRACT.md)
- [ComfyUI backend and recovery guide](docs/COMFY_BACKEND.md)
- [ComfyUI application evidence](docs/portfolio/COMFYUI_APPLICATION_EVIDENCE.md)
- [PNG metadata and publication model](docs/PNG_METADATA_AND_PUBLICATION.md)
- [Safe demo protocol](examples/safe_demo/README.md)
- [Provenance and licensing decisions](docs/PROVENANCE_AND_LICENSING.md)
- [Limitations](docs/LIMITATIONS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security](SECURITY.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Validation record](VALIDATION.md)

## ComfyUI evidence package

The application-ready ComfyUI package includes editable and executable workflow JSON, a semantic binding contract, the native backend implementation, machine-readable smoke and cold-repeat verification, and a clean graph capture. Start with the [ComfyUI application evidence index](docs/portfolio/COMFYUI_APPLICATION_EVIDENCE.md).

## External evaluation packages

- [Repaired × Dawnhewn × Lived-In](research/repaired-dawnhewn-livedin-evaluation-v1/README.md) — a 227-generation external-customer evaluation with 37 curated comparison sheets, production-profile refinements, complete manifests, and explicit identity-preservation limits. Model weights and private service artifacts are excluded.

## Current status

This is a curated public release extracted from a larger private research archive. The reusable core and tests are present; private runs, local paths, personal datasets, model files, explicit research material, and artist-specific investigations are intentionally excluded.

The [live public demonstration](https://detroitwobbly.github.io/checkpoint-evaluation-framework/) was exported from an approved private run. Raw Forge/A1111 PNG metadata remains private; public copies use a minimal CEF identity-and-hash envelope and a transformation index.

## License

Code is licensed under AGPL-3.0-or-later. This license does not grant rights to third-party checkpoints, LoRAs, reference images, generated outputs, model names, or trademarks. See [Provenance and licensing](docs/PROVENANCE_AND_LICENSING.md) before publishing artifacts.
