# ArsMachina Dystopian Mythology Fantasy — Provisional Recaptioning Experiment

This release is an unsolicited, good-faith research artifact inspired by ArsMachina's **Dystopian Mythology Fantasy** SDXL LoRA. The existing LoRA works and contributes a recognizable visual treatment. This package asks a narrower experimental question: what might the same image set teach if ordinary prompt language described only image-local content while a trigger carried responsibility for the recurring visual identity?

## Downloads and documentation

- [`ArsMachina_Dystopian_Provisional_Captions_v1_AES256.zip`](ArsMachina_Dystopian_Provisional_Captions_v1_AES256.zip) — AES-256 encrypted package containing 131 numbered captions in two trigger editions, complete source-to-rewrite manifests, and validation report
- [`A0_Vision_Caption_Directive_ArsDystopia.md`](A0_Vision_Caption_Directive_ArsDystopia.md) — reusable image-grounded captioning directive
- [`docs/recaptioning-method.md`](docs/recaptioning-method.md) — method, assumptions, exclusions, and limitations

## Editions

- `ArsDystopia_style` — experimental unique trigger intended to leave *dystopian*, *mythology*, and *fantasy* available as ordinary prompt controls
- `dystopian mythology fantasy` — legacy-trigger edition for compatibility and comparison

The semantic text following the trigger is identical between editions.

## Important limitation

The original image files and filename mapping were not available. The 131 prose captions were recovered from the model's embedded metadata and numbered in their original JSON insertion order. That order is preserved exactly, but its correspondence to source-image filenames is **unverified**. The captions are provisional and must be visually checked against the original dataset before training.

This repository does not redistribute the LoRA, training images, or the local raw metadata dump.

The archive password is supplied privately to ArsMachina and is intentionally absent from this public repository. The AES-encrypted ZIP can be opened with [7-Zip](https://www.7-zip.org/) or another tool that supports WinZip AES-256 encryption.

## Validation summary

- 131 distinct source prose captions recovered
- 131 unique-trigger caption files
- 131 legacy-trigger caption files
- contiguous filenames `001.txt` through `131.txt`
- identical semantic payloads between trigger editions
- complete CSV and JSON audit manifests
- no local filesystem paths in the public package
- raw metadata JSON excluded

This artifact is offered to ArsMachina for inspection, modification, use, or disregard.
