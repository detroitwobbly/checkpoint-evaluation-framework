# Safe demo

This 12-cell demonstration compares two user-supplied checkpoints across three matched counterfactual pairs:

- polished chrome versus unfinished wood;
- light from the left versus light from the right;
- one glass cube versus three glass cubes.

Each pair keeps its seed and basic composition fixed while changing one primary instruction. This helps separate material, lighting, and count compliance from unrelated prompt or seed changes. Cross-checkpoint comparisons are behavioral observations, not claims about training data or model internals.

The release manifest records the exact checkpoint titles and SHA-256 values used for Demo 1. If reproducing the experiment with renamed local files, replace only the API-visible titles and verify that the full hashes still match. Before publishing generated images, complete the remaining decisions in `docs/PROVENANCE_AND_LICENSING.md`.

Dry-build the artifact tree without contacting a backend:

```powershell
cef-eval generate `
  --manifest examples\safe_demo\controlled_materials_and_light.json `
  --output-root runs `
  --run-id safe_demo_dry_run `
  --dry-run
```

The dry run should contain 12 cells, their request payloads, criteria, a run-local manifest snapshot, an incremental generation index, and a completed `run_state.json`.
