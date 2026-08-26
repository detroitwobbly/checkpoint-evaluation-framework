# ComfyUI generation backend

CEF's resumable manifest runner supports Forge and ComfyUI through the same ordinary command path. Forge remains the default.

## Canonical invocation

```powershell
.\.venv\Scripts\python.exe scripts\run_generate_resumable.py `
  --manifest COMFY_NATIVE_BACKEND_GATE.json `
  --run-id run_comfy_native_backend_gate_v0 `
  --backend comfy `
  --output-root cef_runs `
  --resume
```

The default Comfy URL is `http://127.0.0.1:8188`. Use `--base-url` only when the server differs.

## Artifact contract

Before submission, each case receives:

- `request.json` and `criteria.json`;
- `backend_request.json`;
- `resolved_api_workflow.json`;
- `resolved_ui_workflow.json`.

Immediately after successful submission, `backend_submission.json` records the `prompt_id` and both graph hashes. On completion, CEF stores `backend_history.json`, the downloaded PNG, and the normal `generation.json`/`generation_index.json` records.

The API graph is executable. The paired UI graph is embedded in the PNG and remains editable in ComfyUI. Both are resolved from the same semantic bindings.

## Recovery gate

`--pause-after-submit` intentionally exits after persisting one Comfy `prompt_id`:

```powershell
.\.venv\Scripts\python.exe scripts\run_generate_resumable.py --manifest COMFY_NATIVE_BACKEND_GATE.json --run-id recovery_test --backend comfy --output-root cef_runs --only-lora near_far_plus_one --pause-after-submit --stop-after 1
```

Resume in a separate process:

```powershell
.\.venv\Scripts\python.exe scripts\run_generate_resumable.py --manifest COMFY_NATIVE_BACKEND_GATE.json --run-id recovery_test --backend comfy --output-root cef_runs --only-lora near_far_plus_one --resume --stop-after 1
```

CEF verifies that the current resolved API and UI hashes match the persisted submission before reattaching. It then retrieves or waits for that exact `prompt_id`; it does not resubmit.

`POST /interrupt` is cancellation. It is not used to simulate recovery. The installed Comfy server supports targeted interruption by `prompt_id`, but an interrupted job is expected to terminate without a valid image.

## Lifecycle release

Add `--release-resources` to a completed or resumed run. CEF calls `POST /free` with both `unload_models` and `free_memory`, then records before/after system statistics in `backend_resource_release.json`.

## Current supported envelope

- strict sequential execution;
- core-node SDXL baseline or one LoRA;
- positive or negative model and CLIP LoRA strength, kept equal;
- `n_iter=1` (use `batch_size` for multiple outputs);
- sampler and scheduler names must use ComfyUI vocabulary;
- no Qwen invocation is implied by generation.

Multiple LoRAs, independent model/CLIP weights, graph families beyond SDXL txt2img, concurrency, and server-restart recovery are explicit future extensions.
