# Demo 1 run record

Run date: 2026-08-14

Run ID: `materials_and_light_v1`
Status: **published; corrected human adjudication, sanitized-only publication, and AGPL are approved**

## Experimental question

Can two SDXL checkpoints follow matched counterfactual instructions for object material, image-space lighting direction, and object count under fixed seeds and otherwise fixed generation settings?

The six tests were run across both checkpoints for a 12-cell manifold:

- polished chrome versus unfinished pale wood;
- hard light from image-left versus image-right;
- exactly one translucent blue glass cube versus exactly three.

## Generation provenance

| Field | Recorded value |
|---|---|
| Checkpoint A | Stable Diffusion XL Base 1.0 |
| Checkpoint A SHA-256 | `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b` |
| Checkpoint B | RealVisXL V5.0 FP16, baked VAE |
| Checkpoint B SHA-256 | `6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80` |
| Backend | Stable Diffusion WebUI Forge-Neo `neo-2.26` |
| Backend runtime marker | `PY313`; Forge preset `xl` |
| Sampler / scheduler | DPM++ 2M / Karras |
| Steps / CFG | 28 / 5.0 |
| Dimensions | 768 × 768 |
| Seeds | 41001 material, 41002 lighting, 41003 count |
| LoRAs | None |
| VAE setting | Automatic; RealVisXL uses its baked VAE |

Both checkpoints were verified by local SHA-256 and by the Forge API. One canary image per checkpoint was completed before the 12-cell run. The dry expansion produced exactly 12 planned cells. The live run completed 12/12 cells, six per checkpoint, with incremental state and generation indexes.

## Evaluator provenance

| Field | Recorded value |
|---|---|
| Runtime | LM Studio local OpenAI-compatible server |
| Evaluator | Qwen3-VL 8B Instruct, Q4_K_M GGUF |
| API identifier | `cef-qwen3-vl-8b` |
| Context | 16,384 tokens |
| GPU offload | 100%; approximately 7.47 GiB estimated before load |
| Temperature | 0.1 |
| Primary max output | 3,000 tokens |
| Response mode | JSON with requested response schema |
| Evaluator directive | `safe_demo_evaluator.txt`, SHA-256 recorded in `analysis_index.json` and `report.json` |

Forge was unloaded before Qwen was loaded. Qwen was unloaded immediately after analysis because combined application, GPU, and pagefile pressure left only about 500 MB free. Future reproductions should run generation and vision evaluation as separate runtime phases.

The first SDXL wood evaluation returned truncated, malformed JSON. CEF preserved that failure record. A single retry used a 4,000-token allowance, succeeded, and the final 12-image index contains no null scores. The failed attempt remains in the private run as `analysis_failed_attempt_01.json`.

## Machine evaluation summary

- SDXL Base average: 8.00 across six scored images.
- RealVisXL average: 8.08 across six scored images.
- Machine outcomes: nine passes, three failures.
- Machine failures: both chrome tests and the RealVisXL wood test.
- No final evaluator transport failures or malformed records remain in the report.

The near-equal averages should not be presented as a universal checkpoint ranking. The useful evidence is criterion-specific.

## Human adjudication

Status: **approved by Alex on 2026-08-14**.

The corrected approval record confirms five passes, seven failures, eight machine/human agreements, and four disagreements:

1. Qwen passed SDXL's wood test despite the large glowing globe reading as glass or plastic rather than wood.
2. Qwen passed SDXL's right-light test even though the image remains left-lit with a rightward shadow.
3. Qwen passed RealVisXL's right-light test under the same contradiction.
4. Qwen passed SDXL's three-cube count test despite four distinct cube bodies being visible (left, rear-center, front-center, and right).

Approximate grayscale diagnostics support the lighting review:

| Checkpoint | Mean absolute difference between left/right prompt images (0–255) | Left-minus-right object luminance, left prompt | Left-minus-right object luminance, right prompt |
|---|---:|---:|---:|
| SDXL Base | 1.33 | +72.73 | +73.05 |
| RealVisXL | 1.65 | +81.14 | +79.31 |

Both fixed-seed pairs are nearly unchanged and remain much brighter on image-left under both prompts. These measurements are corroborative diagnostics supporting the approved human reading.

## Directional-language limitation

Vision-language models do not use directional language reliably enough to treat an unqualified “left” or “right” judgment as ground truth. Image-left, image-right, subject-left, subject-right, camera-left, and the direction of illumination versus the direction of a cast shadow can be conflated.

For CEF:

- prompts and criteria should explicitly say **image-left** and **image-right**;
- illumination origin and cast-shadow direction must be separate criteria;
- paired outputs should be inspected together rather than independently;
- evaluator agreement should be checked against simple image diagnostics where practical;
- Qwen should not be the sole adjudicator for directional claims;
- the broader VLM-limitations inventory from the Image Caption project is now incorporated in [Vision-model observer qualification](VISION_MODEL_OBSERVER_QUALIFICATION.md).

## Publication record

- Sanitized-only structured provenance was approved; raw Forge/A1111 metadata remains private.
- The contact sheet, report, machine-readable artifacts, AGPL-3.0-or-later code license, and public identity were approved together.
- The static report and all local targets were verified from the hosted GitHub Pages path.
- The four-cube correction was regenerated from the approved source record, republished with updated hashes, and verified live.
