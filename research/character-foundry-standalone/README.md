# Character Foundry Standalone

Portable, local browser builds of the Character Foundry prompt-generation application. No checkpoint, LoRA, generated-image collection, private character draft, or image-generation backend is bundled.

## Downloads

- `Character_Foundry_Standalone_v0.2.0.zip` — current version; adds structured ancestry/background controls, evidence-backed initial descriptors, catalog/mixed/custom/unspecified modes, independent locks, DNA persistence, legacy migration, and updated validation.
- `Character_Foundry_Standalone_v0.1.0.zip` — previous version retained for reproducibility and comparison.

Each ZIP has a neighboring `.sha256` file. Verify the archive before extraction, then run `Test Character Foundry.bat` before launching it.

The ancestry/background feature stores declared character metadata separately from visible traits. It does not infer ancestry from images or guarantee a particular morphology. Mixed-ancestry prompting is explicitly documented as checkpoint-dependent and dominance-prone.
