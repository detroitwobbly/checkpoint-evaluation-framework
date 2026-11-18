# Provenance, ownership, and redistribution

## Slider provenance

Repaired and Lived-In were developed from synthetic imagery generated with Juggernaut XL Ragnarok. No external image dataset or third-party artwork was introduced as slider training imagery according to the operator’s provenance statement.

This statement does not remove or supersede upstream obligations associated with the base checkpoint, software, or other dependencies.

## Customer material

Jason / SignalofSolarum retains ownership of his original Solarum worldbuilding, Dawnhewn design work, and independently owned assets. This package does not include Dawnhewn model weights or source reference images and does not infer permission to redistribute them.

The presence of Dawnhewn in generated comparison sheets is evaluation evidence, not a transfer of ownership or a model release.

## Package license boundary

The Checkpoint Evaluation Framework source repository has its own repository license. Generated evidence, customer material, model weights, and upstream checkpoints may have separate rights and obligations. Do not assume that the repository license grants rights to redistribute excluded model assets.

The creator of Repaired and Lived-In authorizes Jason / SignalofSolarum to download and use the supplied slider weights, including in authorized custom merges, without royalties or ownership claims on resulting creative works, subject to applicable upstream licenses. A credit mention is appreciated but no ownership interest in Jason’s resulting work is sought.

## Included slider weights

The package now includes the following authorized files through Git LFS:

- `models/Repaired_v1.safetensors` — SHA-256 `829f924aea08b8391db941a52f1da7a527952d98444170b647330657d516ea98`
- `models/LivedIn_v1.safetensors` — SHA-256 `e2d8804d6ce4bb9c8a9beebee24b3e4eee73433d40bb7bc927a50f30ee18b391`

This authorization applies to these supplied slider weights and does not grant redistribution rights for Dawnhewn, Juggernaut XL Ragnarok, or any other excluded model or customer asset.

## Character Foundry tool

`tools/character-foundry/Character_Foundry_Standalone_v0.1.0.zip` is an independently usable extraction of the Character Foundry prompt-generation surface. Its complete included source is distributed under the GNU Affero General Public License v3.0, reproduced inside the ZIP. The tool contains no checkpoint, LoRA, customer image, private character draft, or generation backend.

Its slider registry records prompt tags, ranges, warnings, and expected asset hashes as configuration metadata. That metadata does not redistribute or grant rights to the referenced external LoRAs. Users must obtain and install any selected slider separately under its applicable terms.

## Publication sanitation

This curated package excludes private filesystem paths, credentials, raw service logs, private intake history, broad local inventories, Forge response dumps, Dawnhewn weights, and upstream checkpoint weights. The only `.safetensors` files included are the two explicitly authorized sliders listed above. Package checksums cover the files actually published.
