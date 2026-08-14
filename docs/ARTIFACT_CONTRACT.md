# Artifact contract

CEF uses ordinary files as its experiment ledger. The layout is designed to remain inspectable without a database or CEF process.

```text
runs/<run_id>/
├── run_manifest.json
├── forge_inventory.json
├── forge_inventory_resume_<timestamp>.json
├── run_state.json
├── generation_index.json
├── approved/
│   └── checkpoint_<id>/lora_<id>/<test_id>/
│       ├── request.json
│       ├── criteria.json
│       ├── generation.json
│       ├── <generated image>.png
│       └── <generated image>_analysis.json
├── analysis_index.json
├── png_provenance_index.json
├── report.json
├── report.html
├── report_assets/
│   └── contact_sheet.jpg
├── run_pipeline_review.json
└── run_pipeline_review.html
```

## Required generation artifacts

`run_manifest.json` is the suite snapshot against which resume attempts are checked. `generation_index.json` is the ordered ledger consumed by analysis. `run_state.json` is an operational summary, not a substitute for the index.

A non-dry cell is complete only when `generation.json` parses and all recorded image files exist. Requests and criteria alone do not mark completion.

## Evaluation artifacts

Per-image analysis records preserve normalized analysis plus raw response material. `analysis_index.json` aggregates records for reporting and comparison and records sanitized evaluator settings plus the evaluator-directive hash. Credentials are excluded. Evaluation can be partial when failure records or a deliberately selected `--test-id` subset are disclosed.

## Provenance artifacts

Backend inventories are point-in-time observations, not cryptographic attestations. PNG provenance extraction retains raw parameter text because extension metadata and future backend fields may exceed the parser’s current vocabulary.

## Public PNG publication profile

Private generated PNGs are immutable backend artifacts. CEF writes the decoded Forge response bytes directly and retains their raw PNG metadata and SHA-256 in the private run.

The `sanitized-v1` public profile creates a separate lossless PNG copy. It removes all source metadata, verifies pixel equivalence, and adds only these CEF-owned text fields:

- `cef_schema_version`
- `cef_publication_profile`
- `cef_run_id`
- `cef_cell_id`
- `cef_checkpoint_id`
- `cef_test_id`
- `cef_manifest_sha256`
- `cef_evidence_sha256`
- `cef_original_png_sha256`

`artifact_index.json` records the source and public hashes, pixel-equivalence result, and transformation declaration for every image. Different PNG hashes are therefore expected: the pixel content is unchanged, while the container bytes and metadata are intentionally different.

## Stability

The 0.1 release is alpha. Artifact names and major semantic roles are intentional, but no formal backward-compatibility guarantee exists until JSON Schemas and migration tests are added. Public consumers should preserve `schema_version` fields where present and retain raw source artifacts.

## Publication sanitation

Run artifacts can contain checkpoint titles, hashes, endpoint details, local paths, prompt text, and backend inventories. `cef-release-audit` checks the curated source tree; it does not by itself approve generated runs. Each public run still requires the provenance and licensing review.
