# Troubleshooting

## Forge cannot be reached

Confirm the API is enabled and probe the exact base URL:

```powershell
cef-eval probe-forge --base-url http://127.0.0.1:7860 --timeout 30
```

If the web interface works but the probe does not, API startup options or a different port are the likely causes.

## Checkpoint switching fails

Manifest checkpoint titles must exactly match the titles exposed by `/sdapi/v1/sd-models`. Filenames remembered from disk are not always identical to API-visible titles. Probe the backend and inspect its model inventory before editing the manifest.

## Sampler or scheduler is rejected

Backends vary in accepted names. Use the exact sampler and scheduler labels exposed by the active backend. A manifest is declarative evidence, but it cannot make an unsupported backend option valid.

## A run directory already exists

CEF refuses ambiguous reuse:

- Use `--resume` to reuse complete cells under the unchanged manifest.
- Use `--overwrite` to regenerate all cells under the unchanged manifest.
- Use a new `--run-id` when prompts, criteria, checkpoints, or settings change.

If CEF reports manifest drift, do not replace `run_manifest.json`. The refusal protects experimental history.

## Resume regenerates a cell

A cell is reusable only when `generation.json` parses and every recorded image exists. A missing, renamed, or inaccessible image makes that cell incomplete. Relative paths are safest when runs remain inside the repository’s ignored `runs/` directory.

## Vision-model JSON fails

Different OpenAI-compatible servers support different response-format features. Try:

- `--no-response-format` when schema-constrained output is rejected;
- `--response-mode markdown` only with a compatible structured Markdown directive;
- a smaller `--max-tokens` or shorter directive for limited-context models;
- `--continue-on-error` to preserve failures and finish the batch.

Do not silently discard malformed responses. Failure frequency is part of evaluator qualification.

## VRAM is insufficient

Generation and analysis are separate stages. Complete generation, unload the image checkpoint/backend if necessary, then start the vision model and analyze the saved run. Resume behavior allows either stage to continue after interruption.

## Report images are unavailable

Reports resolve the paths recorded during generation and analysis. Moving a run can break absolute paths. Prefer relative output roots, keep a run directory intact, and perform a final link check on the exact curated copy intended for publication.

## Contact sheet is missing

Contact sheets require the optional Pillow dependency:

```powershell
python -m pip install -e ".[reporting]"
cef-eval report --run-root runs\YOUR_RUN
```

JSON and HTML reporting otherwise degrade without failing the analysis run.
