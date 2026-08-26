# ComfyUI backend verification artifacts

This directory contains curated, path-free evidence from the native ComfyUI backend gate.

- `SMOKE_REPORT.md` records the four-cell baseline / signed-LoRA / cached-repeat test.
- `smoke_verification.json` contains the corresponding graph, metadata, hash, and pixel checks.
- `cold_determinism_verification.json` records the separate post-restart cold repeat.

Generated PNGs remain outside this public bundle pending an explicit checkpoint/output provenance decision. The workflow JSON, graph screenshot, and verification records are sufficient to inspect the implementation and reproduce the gate with compatible local assets.
