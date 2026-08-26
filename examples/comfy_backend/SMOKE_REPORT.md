# CEF ComfyUI Backend Smoke Report

Status: **PASS**  
Run ID: `run_comfy_sdxl_backend_smoke_v0`  
Backend: ComfyUI 0.34.0 / PyTorch 2.13.0+cu130 / RTX 3080 12 GB

## Scope

Four strictly sequential SDXL cells used Juggernaut XL Ragnarok, seed 42, 30 steps, CFG 7, DPM++ 2M SDE, Karras, and 1024×1024 output:

1. true no-LoRA baseline;
2. Near/Far LoRA at model/CLIP weight -1.0;
3. Near/Far LoRA at model/CLIP weight +1.0;
4. exact repeat of cell 3, with only the SaveImage prefix changed.

## Results

| Cell | Time | Pixel SHA-256 (RGBA) | Visual read |
|---|---:|---|---|
| baseline | 19.200 s | `7c74f8d…48d3c7` | medium/full portrait on plain backdrop |
| Near/Far -1 | 20.189 s | `bcc293ca…da0ec7` | wider environmental/full-body framing |
| Near/Far +1 | 20.163 s | `2fda375b…660a33` | distinctly closer portrait framing |
| Near/Far +1 repeat | 1.060 s | `2fda375b…660a33` | pixel-identical cache-backed repeat |

The polarity effect is visually legible and directionally coherent. The decoded RGBA pixel buffers for the two +1 outputs are byte-identical. The complete PNG files differ because their embedded workflow metadata contains different output prefixes.

Because the repeat used ComfyUI's execution cache, it validates cache-safe idempotency rather than independent cold-sampling determinism.

Every PNG contains both ComfyUI `prompt` and `workflow` text chunks. The embedded graphs independently confirm seed, sampler, scheduler, checkpoint, LoRA identity, and model/CLIP strengths. All graph checks passed.

The `torchsde` Brownian-interval warning observed during sampling was non-fatal: both affected jobs reached 30/30 steps and saved valid PNGs.

## Implementation evidence

- `checkpoint_evaluator/comfy.py`: standard-library HTTP client for submission, polling, history, error detection, and output retrieval.
- `checkpoint_evaluator/comfy_workflow.py`: paired UI/API workflow resolution and semantic hashing.
- `scripts/run_comfy_smoke_gate.py`: resumable, cell-granular runner with immediate prompt-ID persistence.
- `smoke_verification.json`: machine-readable final verification.
- `generation_index.json`: four completed generation records.
- `cells/*`: resolved UI/API graphs, request, submission, history, PNG, provenance, and generation record per cell.

Offline test result: **21 passed** across Comfy workflow, client, and PNG-provenance coverage.

## Resource observation

The run succeeded on the available ~16 GB system RAM without a crash or OOM. At final verification, Comfy reported roughly 2.43 GiB free system RAM and 4.32 GiB free VRAM. This is a successful smoke result, not yet a broad concurrency or endurance claim.
