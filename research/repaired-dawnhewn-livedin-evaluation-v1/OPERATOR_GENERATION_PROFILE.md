# Operator generation profile — SDXL LoRA production

Profile ID: `alex_sdxl_lora_production_v1`  
Status: operator-validated working default  
Scope: SDXL slider, character-LoRA, and style-LoRA generation

## Settings

- Sampler: DPM++ 2M SDE
- Scheduler: Karras
- Steps: 32
- CFG: 7
- RNG: CPU where Forge records that mode
- Resolution: selected for the carrier composition; 1216×832 was used for the cabin evidence

## Interpretation

This is an empirical operator default developed through repeated successful use with Juggernaut XL and DestinyXL. It is not asserted to be universally optimal for every checkpoint, LoRA architecture, or subject.

## CEF integration policy

CEF should keep two named lanes rather than silently replacing one profile with another:

1. **Control-comparability lane** — frozen settings selected for consistency with an existing evaluation series.
2. **Production-behavior lane** — the operator's normal settings, used to characterize how the LoRA behaves under its intended working conditions.

The active lane and profile ID must be recorded in the manifest and report. If the profiles differ materially, a small bridge test should compare representative control, moderate-weight, and high-weight cells before a negative conclusion is generalized.

Historical Repaired results generated at 24 steps, CFG 5, and DPM++ 2M remain valid evidence for that profile. The manual sparse-prompt evidence generated at 32 steps, CFG 7, and DPM++ 2M SDE is a separate production-profile annex and must not be presented as if only the prompt changed.
