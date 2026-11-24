# Character Foundry Standalone

Portable, local browser builds of the Character Foundry prompt-generation application. No checkpoint, LoRA, generated-image collection, private character draft, or image-generation backend is bundled.

## Downloads

- `Character_Foundry_Standalone_v0.2.1.zip` — current version; retains the v0.2 ancestry/background feature set, removes the standalone DNA module's unresolved Factory-only project dependency, clarifies draft-schema versus application versions, and adds an actual-ZIP module/dependency clean-room audit.
- `Character_Foundry_Standalone_v0.2.0.zip` — previous ancestry/background release retained for reproducibility and comparison.
- `Character_Foundry_Standalone_v0.1.0.zip` — previous version retained for reproducibility and comparison.

Each ZIP has a neighboring `.sha256` file. Verify the archive before extraction, then run `Test Character Foundry.bat` before launching it.

The ancestry/background feature stores declared character metadata separately from visible traits. It does not infer ancestry from images or guarantee a particular morphology. Mixed-ancestry prompting is explicitly documented as checkpoint-dependent and dominance-prone.
