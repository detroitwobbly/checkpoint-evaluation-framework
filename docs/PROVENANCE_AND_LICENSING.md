# Provenance and licensing decisions

The CEF code can be released under AGPL-3.0-or-later. That does not automatically authorize publication of checkpoints, LoRAs, reference images, generated images, names, or third-party metadata.

## Decisions required before a public demo

Candidate research and the recommended baseline-versus-fine-tune pair are documented in [Checkpoint provenance review for Demo 1](CHECKPOINT_PROVENANCE_REVIEW.md). The recommendation does not become final until the exact downloaded files and hashes are verified.

- [x] Choose checkpoint A and record its source URL, version, creator, license, and output-use terms.
- [x] Choose checkpoint B and record the same information.
- [x] Confirm that the checkpoints permit the intended generation and public display of outputs.
- [x] Confirm whether attribution or a model card link is required; retain both creator model-card links in the public report.
- [x] Confirm that neither checkpoint name creates an avoidable adult-content or artist-imitation distraction.
- [ ] Inspect every generated image for people, signatures, logos, watermarks, copyrighted characters, and unsafe surprises.
- [x] Record the exact checkpoint hashes used in the run.
- [x] Record the Forge/Forge-Neo version and relevant runtime settings.
- [ ] Decide whether generated PNG metadata should be retained publicly or replaced with a sanitized structured provenance record.
- [x] Obtain rights for every reference image, or use no reference images in the first demo; Demo 1 uses none.
- [ ] Approve the final contact sheet, report, and machine-readable artifacts together.

## Repository identity decisions

- [x] Repository URLs use the final GitHub account: `detroitwobbly`.
- [ ] Decide the author/maintainer name and contact metadata to publish.
- [ ] Decide whether to add a citation file and, if so, which public identity it should use.
- [ ] Confirm that AGPL-3.0-or-later remains the desired code license.

## Excluded by default

- Model and LoRA weight files
- Private or personal-image datasets
- Local filesystem paths and usernames
- API keys and endpoint credentials
- Unreviewed generated runs
- Artist-specific demonstrations
- Explicit-content demonstrations
- Third-party reference collections with uncertain rights

## Artifact ledger template

| Artifact | Source/creator | License or permission | Hash/version | Public? | Notes |
|---|---|---|---|---|---|
| Checkpoint A | Stability AI, [SDXL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | CreativeML Open RAIL++-M | `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b` | Link/credit only | Exact local and Forge hash verified; weights excluded |
| Checkpoint B | SG161222, [RealVisXL V5.0](https://huggingface.co/SG161222/RealVisXL_V5.0) | OpenRAIL++ declared by creator model card | `6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80` | Link/credit only | FP16 baked-VAE file; exact local and Forge hash verified; weights excluded |
| Demo manifest | CEF Project | Repository license | v1 | Yes | No third-party content |
| Evaluator directive | CEF Project | Repository license | v1 | Yes | No third-party content |
| Generated images | Private Demo 1 run | Reviewed checkpoint terms; final artifact approval pending | 12 images; hashes in private provenance index | No | Codex-assisted draft complete; Alex review required |
| HTML report | Private Demo 1 run | Mixed artifact | CEF v0.1 candidate | No | Publish only after adjudication and metadata approval |

If a right or term is unclear, keep the artifact private and record the unresolved question. Do not infer permission from public availability.
