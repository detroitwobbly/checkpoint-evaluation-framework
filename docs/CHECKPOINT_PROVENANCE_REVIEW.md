# Checkpoint provenance review for Demo 1

Review date: 2026-08-14

Scope: select two checkpoints for the controlled materials, lighting, and object-count demo. This is an engineering provenance review, not legal advice. No model weights will be redistributed by this repository.

## Recommendation

Use the following pair, subject to final human approval after download and hash verification:

1. **Checkpoint A — Stable Diffusion XL Base 1.0** by Stability AI. This is the documented baseline.
2. **Checkpoint B — RealVisXL V5.0 (FP16)** by SG161222. This is a general-purpose photorealistic SDXL fine-tune.

This pair gives the demo an understandable baseline-versus-fine-tune comparison while avoiding LoRAs, artist-style adapters, merge branding, and adult-content branding. Both are published in official creator-controlled Hugging Face repositories as standard SDXL single-file checkpoints.

### Exact files to acquire

| Role | Repository and file | Expected size | Expected SHA-256 | License evidence |
|---|---|---:|---|---|
| A | [stabilityai/stable-diffusion-xl-base-1.0 — `sd_xl_base_1.0.safetensors`](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/sd_xl_base_1.0.safetensors) | 6.94 GB | `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b` | [CreativeML Open RAIL++-M](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md) |
| B | [SG161222/RealVisXL_V5.0 — `RealVisXL_V5.0_fp16.safetensors`](https://huggingface.co/SG161222/RealVisXL_V5.0/blob/main/RealVisXL_V5.0_fp16.safetensors) | 6.94 GB | `6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80` | [Model card declares OpenRAIL++](https://huggingface.co/SG161222/RealVisXL_V5.0) |

Direct downloads:

- [Download SDXL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true)
- [Download RealVisXL V5.0 FP16](https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors?download=true)

Download only these named files. The repository does not need the diffusers-format folders or alternate VAE-baked variants for this run.

## Candidate review

| Candidate | Provenance and output-use finding | Compatibility and portfolio finding | Decision |
|---|---|---|---|
| Stable Diffusion XL Base 1.0 | Official Stability AI model card and CreativeML Open RAIL++-M license. The license does not claim rights in generated output, while leaving the operator responsible for lawful use and compliance with its use restrictions. | Standard SDXL baseline and the clearest control condition. | **YES — Checkpoint A** |
| RealVisXL V5.0 FP16 | Official creator repository declares OpenRAIL++. We will link the creator/model card, identify the exact file and hash, and redistribute no weights. | Standard SDXL fine-tune with enough behavioral contrast to make the comparison useful without changing the experimental story. | **YES — Checkpoint B**, with the model-card link retained in public provenance |
| Animagine XL 3.1 | The [official model card](https://huggingface.co/cagliostrolab/animagine-xl-3.1) declares CreativeML Open RAIL++-M and describes permitted uses. | Anime specialization would turn the first demo into a style-domain comparison and could distract from CEF itself. | **CAUTION — reserve for a later domain-shift study** |
| Playground v2.5 1024px Aesthetic FP16 | The [official model card](https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic) and [license](https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic/blob/main/LICENSE.md) clearly document permitted use and additional conditions. | It uses a specialized noise schedule. Forge-Neo compatibility and equivalent sampling behavior require a separate canary before it belongs in a controlled first demo. | **CAUTION — technically interesting, not the low-risk first run** |
| Local Juggernaut XL Ragnarok | Local sidecar metadata identifies Civitai model 133005, version 1759168, and includes informal permissions, but not a durable formal license text for this exact historical version. Current Juggernaut releases cannot establish the terms of the older file retroactively. | The version description foregrounds merged NSFW training data. That is an avoidable provenance and portfolio distraction. | **NO for Demo 1** |
| Local JibMix Realistic XL v18 | Exact local hash is available, but the retained metadata is insufficient to establish a clean, version-specific public-output and attribution record. | Merge provenance and naming do not improve the baseline-versus-fine-tune story. | **NO pending stronger evidence** |
| Local UnrealVision XL Photoreal Cinematic Edition | Exact local hash is available, but retained metadata does not provide a sufficiently clear formal-license record for this release decision. | Its uncensored/adult-content branding is unnecessary for a controlled object demo and weakens the portfolio framing. | **NO for Demo 1** |

## Installed-weight inventory considered

| Local filename | SHA-256 recorded in local sidecar | Demo 1 status |
|---|---|---|
| `jibMixRealisticXL_v180SkinSupreme.safetensors` | `501235c0cde87b64a15bda378bb1c917c924ae7ec7d484b529b778f58d270a2f` | Excluded pending clearer version-specific terms |
| `juggernautXL_ragnarokBy.safetensors` | `dd08fa32f98d05a2443ca1419e46df1575a0811f6e3b246d9dd47ff20f5eb66a` | Excluded from the flagship demo |
| `unrealvisionXLPhotoreal_cinematicEdition.safetensors` | `33ac4740e10cb307bd04246c7396f923fb198d3d9573e74b0711a0749b9773e0` | Excluded from the flagship demo |

## Conditions before generation

- Download both exact recommended files into the Forge-Neo checkpoint directory.
- Compute local SHA-256 values and compare them with this document before loading either checkpoint.
- Ask Forge-Neo for its exact checkpoint titles; place those returned titles in the demo manifest rather than guessing filenames.
- Record the Forge-Neo version, backend URL, sampler, scheduler, dimensions, steps, CFG, seeds, and resolved checkpoint hashes in the run artifacts.
- Run one canary cell per checkpoint before starting all 12 cells.
- Keep the generated run private until all images and structured artifacts pass human review.
- Publish links and attribution for both source model pages even where attribution may not be mandatory.
- Do not publish or redistribute checkpoint files.

## Output review gate

License compatibility is necessary but not sufficient. Before publication, inspect every output for people, signatures, logos, watermarks, copyrighted characters, unsafe material, prompt leakage, incorrect counts, reversed lighting, and misleading material appearance. Failures that are safe to show should remain visible as evaluation evidence; unsafe or rights-uncertain outputs must not be published.

## Storage note

The two checkpoint files require about 13.9 GB before generation artifacts and temporary download space. The last measured free space on the model drive was about 28 GB. Download sequentially and preserve extra operating-system headroom; freeing space before the run is preferable. Do not remove or relocate existing model files without an explicit backup and migration decision.
