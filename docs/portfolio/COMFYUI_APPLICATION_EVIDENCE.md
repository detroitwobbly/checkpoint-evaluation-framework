# ComfyUI application evidence

CEF integrates ComfyUI as a native, resumable generation backend while preserving the framework's manifest-driven experiment model. The paired workflow contract keeps an executable API graph and an editable UI graph synchronized, including signed LoRA weights, while persisting resolved graphs and prompt IDs for provenance and recovery. Validation on an RTX 3080 with 12 GB VRAM and approximately 16 GB system RAM demonstrated sequential SDXL generation, cache-safe idempotency, cross-process recovery, explicit resource release, and cold-process pixel repeatability for the tested graph. The artifacts below provide direct, inspectable evidence without requiring a recorded walkthrough.

## Primary links

1. [Editable single-LoRA ComfyUI workflow](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/workflows/comfy/sdxl_txt2img_single_lora_ui.json)
2. [Executable single-LoRA API workflow](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/workflows/comfy/sdxl_txt2img_single_lora_api.json)
3. [Semantic workflow binding contract](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/workflows/comfy/sdxl_txt2img_bindings.json)
4. [ComfyUI backend and recovery guide](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/docs/COMFY_BACKEND.md)
5. [Smoke report](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/examples/comfy_backend/SMOKE_REPORT.md) and [machine-readable verification](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/examples/comfy_backend/smoke_verification.json)
6. [Clean graph screenshot](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/docs/assets/comfy_sdxl_single_lora_graph.png)

The screenshot shows the same core-node single-LoRA topology with a locally selected example checkpoint, LoRA, and prompt. CEF's binding layer replaces those runtime values in both the executable and editable graphs while preserving their shared structure.

## Additional verification

- [Cold-process determinism verification](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/examples/comfy_backend/cold_determinism_verification.json)
- [Backend interface](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/checkpoint_evaluator/backend.py)
- [ComfyUI HTTP client](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/checkpoint_evaluator/comfy.py)
- [Paired workflow resolver](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/checkpoint_evaluator/comfy_workflow.py)
- [Resumable native runner](https://github.com/detroitwobbly/checkpoint-evaluation-framework/blob/main/scripts/run_generate_resumable.py)

## Scope of the claim

The repeat inside the smoke run used ComfyUI's execution cache and therefore validates cache-safe idempotency. The separate cold-repeat artifact records an operator restart, no cached nodes, a 23.149-second execution, and equality of the decoded RGBA pixel buffers against the reference. These results characterize the tested graph, software environment, and hardware; they do not claim cross-hardware or cross-version determinism, and they do not imply a demonstrated concurrent operating envelope.

Repository-wide verification of this curated integration completed with **75 tests passing**.
