# Provenance and licensing decisions

The CEF code can be released under AGPL-3.0-or-later. That does not automatically authorize publication of checkpoints, LoRAs, reference images, generated images, names, or third-party metadata.

## Decisions required before a public demo

- [ ] Choose checkpoint A and record its source URL, version, creator, license, and output-use terms.
- [ ] Choose checkpoint B and record the same information.
- [ ] Confirm that the checkpoints permit the intended generation and public display of outputs.
- [ ] Confirm whether attribution or a model card link is required.
- [ ] Confirm that neither checkpoint name creates an avoidable adult-content or artist-imitation distraction.
- [ ] Inspect every generated image for people, signatures, logos, watermarks, copyrighted characters, and unsafe surprises.
- [ ] Record the exact checkpoint hashes used in the run.
- [ ] Record the Forge/Forge-Neo version and relevant runtime settings.
- [ ] Decide whether generated PNG metadata should be retained publicly or replaced with a sanitized structured provenance record.
- [ ] Obtain rights for every reference image, or use no reference images in the first demo.
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
| Checkpoint A | Decision required | Decision required | Pending | No | Placeholder only |
| Checkpoint B | Decision required | Decision required | Pending | No | Placeholder only |
| Demo manifest | CEF Project | Repository license | v1 | Yes | No third-party content |
| Evaluator directive | CEF Project | Repository license | v1 | Yes | No third-party content |
| Generated images | Pending run | Depends on model terms | Pending | No | Human review required |
| HTML report | Pending run | Mixed artifact | Pending | No | Publish only with approved inputs |

If a right or term is unclear, keep the artifact private and record the unresolved question. Do not infer permission from public availability.
