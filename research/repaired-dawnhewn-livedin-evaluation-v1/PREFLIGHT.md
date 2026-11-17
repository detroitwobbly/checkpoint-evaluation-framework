# Repaired × Dawnhewn × Lived-In — Preflight

Date: 2026-11-17

## Frozen resources

- Repaired v1: `829f924aea08b8391db941a52f1da7a527952d98444170b647330657d516ea98`, 185,717,696 bytes.
- Lived-In v1: `e2d8804d6ce4bb9c8a9beebee24b3e4eee73433d40bb7bc927a50f30ee18b391`, 185,717,696 bytes.
- Dawnhewn v2: `6e1d76dd2b2fed5ee4abe26c7dc3c79e3383f3241eb92b89049b4d762c0e6642`, 170,540,972 bytes.
- Evaluation checkpoint: Juggernaut XL Ragnarok, `dd08fa32f98d05a2443ca1419e46df1575a0811f6e3b246d9dd47ff20f5eb66a`.

## Metadata findings

- Dawnhewn trigger: `jdhship`.
- Dawnhewn was trained on `Juggernaut-XL_v9.safetensors` / RunDiffusion Photo 2 (`c9e3e68f...`), not Ragnarok. Ragnarok results are therefore an explicit cross-checkpoint compatibility test.
- Repaired and Lived-In expose SDXL identity and output names but no useful caption, pole, or trigger metadata.
- Dawnhewn must not be redistributed without customer authorization.

## Execution shape

The full directive would produce several hundred images. With 14.15 GiB free at preflight, execution is staged:

1. A 96-cell standalone Repaired study with true control, adapter-zero, signed weights, material variation, negative controls, and a prompt-activation pair.
2. Human review of the standalone evidence.
3. A compact Dawnhewn compatibility study only after the primary run verifies.
4. A compact cabin matrix only where Repaired and Lived-In show a useful operating range.

No VLM evaluation is authorized. Human observations and conclusions are the review authority.

## Publication boundary

The job is private. A verified customer package may be prepared, but public GitHub publication remains an explicit operator approval gate. Repaired may be included only after that approval; Dawnhewn is evidence-only and must not be redistributed.
