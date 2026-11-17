# Repaired × Dawnhewn × Lived-In — CEF external evaluation

This package is the curated, human-reviewed evidence handoff for the November 17, 2026 Checkpoint Evaluation Framework study requested for Jason / SignalofSolarum.

The central question was whether visible evidence of repair, maintenance, and long-term habitation could be introduced without replacing or substantially distorting an existing subject.

## Short answer

`Repaired_v1` is a real, dose-responsive visual direction, but it is not a reliable universal “functional repair” control. Its most repeatable effects are wear, accumulated intervention, additional fittings, retrofitting, and redesign pressure. It is strongest in compatible workshop, machinery, and worn industrial contexts. It is weakest when the task requires a precise localized repair while preserving an object’s exact geometry.

With Dawnhewn, the adapters are technically compatible. Under the operator production profile, Repaired +1 and +2 preserved the recognizable ship concept in two fixed scenes better than earlier high-weight sweeps, but +1 remains the safer identity-sensitive starting point. Higher weights require matched controls.

For cabins, the clearest factor separation came from a sparse carrier prompt at the operator production profile: Repaired +2 emphasized wear and intervention history; Lived-In +2 emphasized functional occupancy and accumulated working objects; the combination was approximately additive on the tested seed.

## Package contents

- [`CUSTOMER_REPORT.md`](CUSTOMER_REPORT.md) — complete findings, failures, limitations, and supported claims.
- [`EVALUATION_INDEX.md`](EVALUATION_INDEX.md) — evidence map and experiment counts.
- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) — settings, hashes, manifests, and reproduction boundaries.
- [`PROVENANCE_AND_LICENSE.md`](PROVENANCE_AND_LICENSE.md) — provenance, ownership, and redistribution limits.
- [`manifests/`](manifests/) — frozen evaluation manifests for every published experiment.
- [`evidence/`](evidence/) — all curated comparison sheets, including the two production-profile refinements.
- [`package_manifest.json`](package_manifest.json) and [`checksums.sha256`](checksums.sha256) — package inventory and integrity hashes.

## Scope and exclusions

This is a research/evaluation package, not a model-weight release. It does **not** redistribute:

- Dawnhewn weights or Jason’s source assets;
- Repaired or Lived-In weights;
- Juggernaut XL Ragnarok;
- private service-job intake, logs, broad local inventories, or raw Forge responses;
- redundant raw generations already represented by the comparison sheets and frozen manifests.

The included images are generated evaluation evidence. No VLM or automated semantic judge was used for the published conclusions; the findings are human/assistant visual observations and operator-supplied manual evidence.

## Recommended starting points

- General Repaired exploration: begin around +1 and compare against a matched no-LoRA control.
- Worn industrial/workshop context: +2 may make the learned direction more legible, with greater redesign risk.
- Dawnhewn identity-sensitive work: start below or at +1; treat +2 as experimental.
- Sparse Space-Winnebago carrier: Repaired +2 and Lived-In +2 produced the clearest tested separation, but this is one seed and not a universal recipe.

The successful outcome of this evaluation is not that Repaired was declared universally effective. It is that its usable behavior and its failure boundary are now documented.
