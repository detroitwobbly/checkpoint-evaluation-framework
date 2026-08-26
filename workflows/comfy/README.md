# Canonical CEF ComfyUI SDXL Workflows

This directory contains the first core-node ComfyUI workflow family used by CEF.

## Variants

- `sdxl_txt2img_base_ui.json` — editable true-baseline graph with no LoRA loader.
- `sdxl_txt2img_base_api.json` — API-format baseline graph.
- `sdxl_txt2img_single_lora_ui.json` — editable graph with one `LoraLoader` applied to MODEL and CLIP.
- `sdxl_txt2img_single_lora_api.json` — API-format single-LoRA graph.
- `sdxl_txt2img_bindings.json` — stable mapping from backend-neutral CEF fields to API node inputs.

The baseline is intentionally a separate graph. A LoRA loaded at strength zero is not used as the canonical no-adapter control.

## Frozen initial defaults

- Checkpoint: `juggernautXL_ragnarokBy.safetensors`
- Resolution: 1024 × 1024
- Batch: 1
- Seed: 42, fixed after generation
- Steps: 30
- CFG: 7
- Sampler: `dpmpp_2m_sde`
- Scheduler: `karras`
- Denoise: 1
- Positive prompt placeholder: `a woman`
- Negative prompt placeholder: `text, watermark`

All placeholders are replaced from the CEF request through the binding manifest before submission.

## Live validation environment

Validated read-only against the installed local server on 2026-08-26:

- ComfyUI: 0.34.0
- Frontend: 1.49.6
- Python: 3.12.12
- PyTorch: 2.13.0+cu130
- Device: NVIDIA GeForce RTX 3080, 12 GB
- Deployment: local Git package managed by Stability Matrix

The installed `/object_info` schemas confirmed every bound node class, input name, checkpoint, LoRA, sampler, scheduler, negative LoRA strength, and `SaveImage` output designation.

## Canonical semantic SHA-256

Hashes below are calculated from canonical JSON serialization with sorted keys and compact separators, so harmless whitespace or line-ending changes do not alter identity.

| Artifact | Semantic SHA-256 |
|---|---|
| base API | `1d9ec0b6e4f58edbd21266cf96d6864bdf176798ce12a3b781de4c3e8061e523` |
| base UI | `6f605e41056fb8f67849046266bf15112042918187987582f6fb0890994233db` |
| single-LoRA API | `b0bac13fd5d1cd91849e09eb05e31e290396e43f425955c965395192db97c2b3` |
| single-LoRA UI | `32f1c264da319b588a25ea18044b9fda8f15be79f8e30d725ad8435d6cf05f8e` |
| bindings | `bf9777125acbb503f40eec73e710433d5197d97c42d655e6330a59785fed0ed0` |

## Provenance rule

CEF must retain the resolved API graph as submitted. It should also submit the correspondingly resolved editable UI graph as `extra_data.extra_pnginfo.workflow`, then verify the resulting PNG metadata rather than assuming browser-style embedding occurred.
