# Character Foundry standalone

This directory provides the lightweight standalone Character Foundry browser application separately from the CEF evaluation evidence and slider weights.

## Download

- `Character_Foundry_Standalone_v0.1.0.zip` — validated Windows distribution.
- `Character_Foundry_Standalone_v0.1.0.zip.sha256` — external SHA-256 checksum.

Expected ZIP SHA-256:

`55cd5d34e2056e603322ed7495bacf3630a5ae2d69bcc57aa81ab3aeb4c3ac06`

## Requirements and launch

1. Install Python 3.11 or newer. No pip packages are required.
2. Extract the ZIP to a writable directory.
3. Run `Test Character Foundry.bat`.
4. Run `Launch Character Foundry.bat`.
5. Use the local browser interface at `http://127.0.0.1:8793/`.

The app generates reproducible portrait and full-body prompts, supports trait locks and rerolls, saves Character DNA drafts, exports wildcards, and can emit optional LoRA slider tags. Slider model files are not bundled; any selected slider must be installed separately in the generation UI.

The descriptor vocabulary is owner-editable in `config/descriptors.json`. Add, modify, reorder, or remove feature descriptors while keeping every JSON section present and non-empty.

The ZIP includes its own README, file manifest, validation record, complete included source, and AGPL-3.0 license.
