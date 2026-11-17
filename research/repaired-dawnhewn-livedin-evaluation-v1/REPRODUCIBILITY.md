# Reproducibility

## Models and hashes

- Base checkpoint: `sd\juggernautXL_ragnarokBy.safetensors`
- Base checkpoint SHA-256: `dd08fa32f98d05a2443ca1419e46df1575a0811f6e3b246d9dd47ff20f5eb66a`
- Repaired_v1 SHA-256: `829f924aea08b8391db941a52f1da7a527952d98444170b647330657d516ea98`
- LivedIn_v1 SHA-256: `e2d8804d6ce4bb9c8a9beebee24b3e4eee73433d40bb7bc927a50f30ee18b391`
- Dawnhewn SHA-256: `6e1d76dd2b2fed5ee4abe26c7dc3c79e3383f3241eb92b89049b4d762c0e6642`

Hashes identify the tested assets; the assets themselves are intentionally excluded.

## Generation profiles

### Compact CEF control profile

The original standalone, compatibility, and cabin matrices used their frozen manifests. Those manifests are authoritative for prompt, seed, resolution, sampler, step count, CFG, and LoRA configuration. Historical results were not rewritten after the production profile was introduced.

### Operator SDXL LoRA production profile

- Sampler: DPM++ 2M SDE
- Scheduler: Karras
- Steps: 32
- CFG: 7
- RNG: CPU where recorded by Forge
- Resolution: carrier-dependent; Dawnhewn follow-up used 1216×832

This profile is an empirical operator default for Juggernaut XL and DestinyXL slider, character-LoRA, and style-LoRA work. It is not claimed to be universally optimal.

## Reproduction procedure

1. Install the exact base checkpoint and required LoRAs, verifying the SHA-256 values above.
2. Load a manifest from `manifests/` in a compatible CEF checkout.
3. Confirm the backend resolves every requested model to exactly one matching asset.
4. Generate sequentially with the manifest’s fixed prompts, negative prompts, seeds, dimensions, sampler, scheduler, steps, and CFG.
5. Compare only matched cells. Do not attribute ordinary seed or checkpoint variation to a LoRA without a matched control.
6. Keep compact-profile and production-profile conclusions separate.

Forge-Neo 2.26 was used for the published generations. Returned generation metadata identified Ragnarok with model hash `dd08fa32f9`. One options response retained a stale checkpoint-hash field after a model switch; CEF validated the returned generation identity rather than silently normalizing that stale field.

## Evidence policy

The repository contains comparison sheets rather than every raw generation. This is deliberate: the complete manifests preserve reproducibility, while the curated sheets preserve the full visual comparisons needed to audit the report without committing redundant private run material.
