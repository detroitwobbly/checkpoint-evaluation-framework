# CEF External Customer Evaluation — Assistant Visual Review

Status: **assistant review complete; human review and publication approval pending**  
Date: 2026-11-17  
Automated VLM evaluation: **not used**

## Evidence reviewed

- Standalone Repaired service run: 96 verified cases / 96 images.
- Dawnhewn × Repaired research annex: 56 complete cases / 56 images.
- Repaired × Lived-In cabin research annex: 45 complete cases / 45 images.
- Total: 197 generated images, all using Juggernaut XL Ragnarok at the frozen hash recorded in the manifests and per-image Forge receipts.
- Review basis: fixed-prompt, fixed-seed, profile-ordered comparison sheets plus per-image provenance records.

## Executive verdict

Repaired produces a real, weight-dependent visual direction, but the present evidence does **not** support describing that direction as a reliable general-purpose “functional repair” control. Positive weights often increase structural complexity, fittings, hardware, wear, or visible intervention. Those changes can resemble maintenance in a suitable context, but they frequently read as redesign, added equipment, weathering, or geometry drift instead of a localized repair.

The most defensible general-use range on Ragnarok is **+0.5 to +1.0 as a cautious exploratory range**, with explicit repair language recommended. The present matrix directly tested integer weights, so +0.5 is a conservative interpolation proposal rather than a validated point. **+2 and +3 are diagnostic/showcase strengths, not identity-preserving defaults.** Negative weights tend toward simplification or alternate construction but do not consistently produce a pristine or “never damaged” opposite pole.

For Dawnhewn, Repaired is technically compatible, but the identity-preservation cost becomes material. At +2 and +3, solar-array arrangement, end-cap geometry, engine presentation, hull details, and sometimes apparent viewing geometry change enough that the result should be treated as a redesign rather than a repaired instance of a stable vessel. +1 is less severe but still scene-dependent. For identity-sensitive Dawnhewn work, start below +1 and use matched controls.

The cabin exploration is visually useful but scientifically inconclusive. Lived-In and Repaired alter density, fittings, paneling, accents, and equipment, and higher combined weights often make the scene busier. They do not consistently separate “inhabited and maintained” from ordinary checkpoint variation, clutter, or increased technical detail.

## Standalone Repaired findings

### Activation and dose response

- Weight zero is **pixel-identical** to a truly unloaded control in all 12 matched standalone tests (ImageMagick RMSE `0 (0)` for every pair).
- Mean normalized pixel RMSE versus the true control rises with absolute weight:

| Profile | Mean RMSE | Maximum RMSE |
|---|---:|---:|
| −3 | 0.15 | 0.28 |
| −2 | 0.13 | 0.27 |
| −1 | 0.10 | 0.19 |
| 0 | 0.00 | 0.00 |
| +1 | 0.11 | 0.21 |
| +2 | 0.14 | 0.22 |
| +3 | 0.16 | 0.26 |

This confirms dose-dependent image change. It does not by itself establish semantic repair success.

### Directionality

- Positive weights often add or enlarge pipes, fittings, handles, braces, access-like details, and structural elements.
- Positive weights also introduce or increase wear/rust in some cases, most clearly on the steel toolbox. Wear is not equivalent to repair.
- Negative weights often simplify or substitute construction details, but do not form a consistent “new/pristine” pole across subjects.
- The two diesel-generator seeds show related but not identical effects, so activation is reproducible in broad direction rather than exact detail.

### Material behavior

- **Leather satchel:** positive weights increase straps, fasteners, and reinforced-looking hardware. This is one of the more repair-adjacent carriers, although the changes can also read as product redesign.
- **Steel toolbox:** positive weights increase wear/rust and alter hardware. The result reads more “used/weathered” than “repaired.”
- **Ceramic vessel:** weights change proportions, rim, and base, but no credible ceramic-specific repair language is consistently visible. No strong kintsugi, filled crack, staple repair, or replacement section appears.
- **Wooden barn:** modest siding/opening changes occur; visible local splices or replacement-board repairs are not consistently established.
- **Bridge and generator:** geometry and component changes occur, but localized functional repairs are weak or ambiguous.
- **Fishing trawler:** the subject remains a trawler, but paint, rigging, deck hardware, hull presentation, and surrounding vessels vary. These are not cleanly attributable as repairs.

### Negative controls and leakage

- The natural mountain remains a natural mountain across the full sweep; no mechanical repair motif is introduced.
- The flower remains an organic flower with no metal, patch, or machinery leakage. Positive weights alter scale/presentation slightly.
- These controls support low environmental/semantic leakage into subjects with poor repair affordance.

### Prompt activation

- Explicit repair wording materially changes the pump carrier through the checkpoint's native prompt response.
- Adding Repaired increases component and geometry variation, but the combined result still does not consistently read as a clearly localized, plausible repair.
- Explicit wording is therefore useful, but it does not convert all slider-induced changes into repair evidence.

## Dawnhewn compatibility findings

### Baseline and provenance caveat

Dawnhewn embedded metadata documents the triggers `jdhship` and `a small spaceship` and identifies a Juggernaut XL v9 / RunDiffusion Photo 2 training base. The local metadata does not document a numeric recommended weight; 1.0 was used as a conservative test assumption. Because the evaluation checkpoint is Ragnarok, these results are **cross-checkpoint compatibility evidence**, not native-base characterization.

### Identity preservation

- The Dawnhewn-only baseline consistently produces a cream cylindrical hull, orange stripe, large solar surfaces, dark windows, and rounded end geometry, but cross-seed details and orientation vary.
- Repaired at weight zero is pixel-identical to Dawnhewn-only in all eight matched scenes.
- Mean normalized RMSE versus Dawnhewn-only rises from 0.09 at ±1 to 0.12 at ±2 and 0.14 at +3.
- At +1, most images remain recognizably Dawnhewn-like, but panel count, solar arrangement, windows, end caps, or modules can shift.
- At +2/+3, multiple scenes show substantial solar-array changes, engine/end-cap replacement, or altered hull presentation. These exceed a conservative notion of “visible repair while preserving the same ship.”

### Recommended use

- Identity-sensitive use: begin below +1, use an explicit repair prompt, and compare against an identical-seed Dawnhewn-only control.
- +1: conditional compatibility strength; inspect each result for end-cap and solar-array drift.
- +2/+3: redesign or diagnostic strengths, not recommended defaults for preserving a recognizable vessel.
- Negative weights also modify geometry and should not be described as a reliable pristine/new pole.

## Cabin exploration findings

- Repaired +1/+3 modifies fixtures, panels, orange accents, technical density, and spatial arrangement more readily than it creates visible local repairs.
- Lived-In +1/+3 can increase small fittings, equipment, texture, and visual density, especially in engineering and cockpit carriers. It does not reliably add unmistakable personal occupation.
- Lived-In −2 often simplifies or cleans the scene, but the effect is not a universal “unused/new” transformation.
- Combined +2/+2 and +2/+3 often produce the busiest scenes. “Busy” is not automatically “inhabited and maintained.”
- The living and sleeping prompts already contain domestic objects, while dockside and cockpit prompts contain maintenance-adjacent detail. This reduces attribution clarity.
- A follow-up should use deliberately sparse generic cabins plus matched explicit habitation/repair prompts at lower half-step weights.

## Cabin repair activation follow-up

A focused 12-image follow-up used one engineering-compartment carrier, three fixed seeds, and four matched conditions per seed:

1. Neutral prompt, no slider.
2. Neutral prompt, Repaired +3.
3. Explicit repair prompt, no slider.
4. Explicit repair prompt, Repaired +3.

The explicit prompt requested mismatched replacement panels, welded reinforcement brackets, patched conduit, spliced cable harnesses, maintenance labels, and visibly repaired but operational machinery.

### Follow-up result

- The explicit prompt materially changes all three seeds toward exposed service conduits, open access areas, labels, dense cabling, and maintenance-oriented layouts. Ragnarok can therefore represent at least part of the requested concept family in a spacecraft engineering environment.
- Repaired +3 materially changes all three neutral-prompt seeds, most consistently by increasing exposed equipment, orange conduit/cabling, pipework, circular pressure-hull framing, and structural complexity.
- Explicit prompt plus Repaired +3 is sometimes denser than the explicit prompt alone, but it is not consistently more visibly *repaired*. One seed becomes more crowded; another mainly changes the compartment layout; the third increases conduit density.
- Mismatched replacement panels, conspicuous welds, patched material boundaries, and unmistakable local mending remain weak. Surfaces stay clean, integrated, and purpose-built.
- The result supports repeatable activation and some prompt/slider interaction, but the interaction is primarily technical-density amplification rather than reliable repair-semantic amplification.

This reduces the likelihood that the first cabin result was merely an unlucky seed. The stronger explanation is a combination of Ragnarok's clean-spacecraft prior and a Repaired direction that is easier to express as intervention/complexity than as visually legible functional mending in this domain.

## Operator manual sparse-prompt evidence

The operator subsequently supplied a matched four-condition sweep using seed `2403602369` and the deliberately sparse prompt:

> A 2324 Model Year Winnebago Space Vehicle cabin interior, photorealistic vintage Winnebago-inspired spaceship cabin interior with orbiting planet view through the windshield

All four images use Ragnarok, 1216×832, 32 steps, CFG 7, DPM++ 2M SDE Karras, CPU RNG, and Forge-Neo 2.26. Embedded PNG metadata verifies the following factorial:

| File | Repaired | Lived-In |
|---|---:|---:|
| 32074-2403602369.png | 0 | 0 |
| 32072-2403602369.png | +2 | 0 |
| 32073-2403602369.png | 0 | +2 |
| 32071-2403602369.png | +2 | +2 |

This seed provides the clearest factor separation observed so far:

- **Control:** comparatively clean, sparse, coherent vintage spacecraft/RV cabin.
- **Repaired +2:** worn and marked ceiling panels, rougher and more visibly used cabinetry, stronger orange/blue material contrast, exposed or substituted fittings, and a more retrofitted appearance without the same degree of countertop occupation.
- **Lived-In +2:** additional countertop vessels, appliances, small equipment and domestic-functional objects while surfaces remain comparatively coherent and maintained.
- **Combined +2/+2:** both accumulated objects and pronounced wear/intervention are present; the worn seat, marked ceiling and floor, equipment accumulation, and heterogeneous fittings make the cabin read as an actively used working vehicle.

This evidence materially narrows the earlier interpretation. Under a sparse carrier prompt, Repaired is more coherently characterized as **wear, accumulated intervention, rough maintenance history, and retrofitting** than as precise localized repair. Lived-In is more coherently characterized as **functional occupancy, storage, appliances, and accumulated working objects**. The combination is legible and approximately additive at +2 on this seed.

Prompt sparsity is not the only changed variable relative to the automated cabin matrix: CFG increased from 5 to 7, steps from 24 to 32, and the sampler changed from DPM++ 2M to DPM++ 2M SDE. These settings are not an arbitrary post-hoc adjustment: the operator identifies them as the established default used across prior SDXL slider, character-LoRA, and style-LoRA work. The stronger result therefore supports an operator-validated production recipe, while still not isolating which individual parameter caused the improvement.

For future CEF slider work, this profile should be preserved separately from the compact CEF control profile. Historical results should not be rewritten. New evaluations should declare whether they target cross-run control comparability or production-behavior characterization and, where practical, include a small bridge comparison between the two profiles.

## Production-profile object follow-up

A bounded 12-image bridge probe applied the operator production profile (DPM++ 2M SDE, Karras, 32 steps, CFG 7) to three representative object/setting carriers. Each carrier retained its original seed and was tested with both the original CEF prompt and a sparser prompt, comparing an unloaded control against Repaired +2.

- **Wooden barn:** Repaired changes roof line, doors, windows, side structures, and overall construction more readily than it depicts a localized repair. The sparse prompt does not remove this redesign tendency.
- **Leather satchel:** Repaired adds or substitutes straps, pockets, buckles, seams, and handle geometry. The result reads as increased construction complexity or a different product design, not an obviously repaired instance of the same bag.
- **Steel toolbox:** The sparse workshop carrier shows the clearest wear/history response: more rust, paint loss, markings, and accumulated surface intervention. The cleaner original carrier instead changes box proportions, handle, latch, and panel construction with little visible repair narrative.

Prompt sparsity therefore helps the learned direction become legible in a compatible worn-workshop context, but it does not make the effect reliably local or identity-preserving. The production profile strengthens the earlier interpretation of Repaired as a mixture of **wear, intervention history, retrofitting, and redesign pressure** rather than a universal functional-repair operator.

Evidence: `repaired_production_profile_followup_v01_live` contains 12 verified PNGs, six matched review sheets, complete per-cell requests/responses, and the frozen manifest.

## Dawnhewn production-profile follow-up

A second bounded probe used the same production profile on the two original Dawnhewn seeds (planetary exterior and orbital service dock), comparing Dawnhewn-only with Repaired +1 and +2. All six generations completed and passed the CEF checkpoint/LoRA provenance gates.

- Dawnhewn's cylindrical hull, orange band, primary end-cap language, and general vessel identity remain recognizable in all six cells.
- Repaired +1/+2 introduces restrained panel, stripe, fitting, support-frame, and surface-history changes. These changes are directionally consistent with intervention or aging, but none reads as a clearly localized completed repair.
- The dock view shows more collateral change than the planetary view: support geometry and vessel framing shift along with surface details.
- In this small production-profile sample, +1 and +2 preserve the core Dawnhewn concept better than the earlier high-weight compatibility cases. This is useful evidence for a cautious working range, not proof of identity preservation across seeds or views.

The follow-up supports technical stack compatibility and suggests that a production-profile range at or below +1 is the safer starting point when Dawnhewn identity matters. Repaired +2 remains a research setting requiring matched controls.

Evidence: `dawnhewn_production_profile_followup_v01_live` contains six verified PNGs, two three-column review sheets, complete per-cell requests/responses, and the frozen manifest.

## Known limitations

- The standalone matrix is a compact representative manifold, not the directive's exhaustive list of every object class.
- Most standalone carriers use one fixed seed; the core generator carrier uses two. Dawnhewn uses two seeds per scene.
- The cabin matrix uses one seed per prompt family and no dedicated generic-versus-explicit prompt quartet.
- The 12-image activation follow-up remedies the missing prompt quartet for the engineering carrier, using three seeds, but does not generalize that result to domestic cabin spaces.
- The production-profile object bridge uses only three carriers and one seed per carrier; prompt sparsity and production settings are evaluated together rather than as a full factorial attribution study.
- The Dawnhewn production-profile follow-up uses two fixed seeds and only +1/+2 positive weights; it establishes a bounded compatibility observation, not a universal safe range.
- The tested integer weights leave the likely useful low range under-sampled.
- Dawnhewn is evaluated off its documented training base.
- No VLM was run, by operator instruction. All semantic findings are human/assistant visual observations.
- Forge-Neo's post-switch options object retained a stale `sd_checkpoint_hash` from the previously loaded DestinyXL checkpoint even while `sd_model_checkpoint`, the returned generation `sd_model_name`, and returned generation `sd_model_hash` correctly identify Ragnarok. CEF's generation hash gate used the returned generation hash and verified every service case. The stale options field should be disclosed rather than silently normalized.

## Claims supported by this evaluation

1. Repaired produces weight-dependent visual changes on Ragnarok.
2. Weight zero is operationally identical to an unloaded adapter in the tested Forge-Neo path.
3. Positive weights often increase structural intervention, fittings, complexity, or wear.
4. The effect is not reliably distinguishable from redesign, added hardware, weathering, or geometry drift across materials.
5. Negative weights do not form a consistent pristine/new pole.
6. Repaired can be stacked with Dawnhewn; +1/+2 under the production profile preserved the core vessel concept in two fixed scenes, while the broader high-weight evidence still shows material identity risk.
7. The present cabin matrix demonstrates visual interaction between Repaired and Lived-In, but not a reliable semantic separation of repair and habitation.

## Claims not supported

1. Repaired universally creates plausible functional repairs.
2. +2 or +3 is a safe general-purpose or identity-preserving range.
3. The negative pole reliably removes repairs or produces factory-new objects.
4. Repaired preserves Dawnhewn geometry across all tested weights.
5. Lived-In alone reliably creates unmistakable evidence of personal occupation in every cabin type.
6. Combined Repaired and Lived-In weights necessarily produce an inhabited cabin maintained through repairs.

## Publication gate

This assistant review is evidence for the human evaluator and did not itself authorize model-weight redistribution. The package's later, limited authorization for Jason to receive Repaired and Lived-In is documented in `PROVENANCE_AND_LICENSE.md`. Dawnhewn weights remain excluded from every package unless Jason explicitly authorizes redistribution.
