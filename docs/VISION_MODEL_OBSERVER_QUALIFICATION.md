# Vision-model observer qualification

Date of research handoff: 2026-08-14  
Status: evidence-calibrated operating doctrine and qualification roadmap  
Document class: working public document; not a universal VLM benchmark  
Primary local observer represented in the evidence: Qwen3-VL 8B Instruct, commonly Q4_K_M through LM Studio

> Evaluator output is model behavior, not ground truth.

CEF evaluates one generative system partly through another generative system. The observer therefore has its own observable behavior: task comprehension, ontology comprehension, evidence extraction, interpretation, decision coherence, schema reliability, missing-information behavior, spatial reliability, prompt susceptibility, compression fidelity, runtime characteristics, and confidence calibration.

Observer qualification is part of the experiment. A fluent answer, a high confidence value, or agreement across retries does not establish correctness.

## Evidence labels

This document distinguishes the strength and scope of its claims.

| Label | Meaning |
|---|---|
| **Controlled observation** | Result from a frozen or explicitly controlled run with inspectable records. |
| **Repeated observation** | Behavior recurring across multiple operational datasets or passes, without a single formal factorial design. |
| **Dataset-specific observation** | Behavior observed in one named project and not yet generalized. |
| **Process response** | A workflow or validator change made because of an observed failure. |
| **Working hypothesis** | A plausible explanation that has not been isolated experimentally. |
| **Open question** | A proposed test, not a present conclusion. |

A repeated anecdote does not become a mechanism merely because it is familiar.

This document is expected to evolve as qualification sets and observer dossiers mature. Corrections to controlled findings, changes to role licenses, and newly identified limitations should remain visible in Git history rather than silently replacing earlier claims.

## Observer competence is multidimensional

At least six properties must be measured separately:

1. **Assignment comprehension** — whether the model understands the requested task.
2. **Ontology comprehension** — whether it understands field meanings, scopes, unknowns, and categories.
3. **Evidence extraction** — whether it correctly reads visible or supplied facts.
4. **Interpretation and claim fidelity** — whether its characterization follows from those facts.
5. **Decision coherence** — whether its final recommendation is internally defensible.
6. **Interface reliability** — whether it returns valid, correctly typed, schema-compliant output.

Outcome competence is a separate property when outcomes exist, and it should be evaluated later. A correct extraction can feed a poor interpretation. A defensible decision can have an unfaithful explanation. A correct conclusion can be reached for the wrong reason. A semantically correct response can still be operationally unusable because its structure is invalid.

A controlled, outcome-blind analyst study in the private research archive illustrates the separation. Across five sealed cases, the same Qwen family achieved 89/90 correct evidence extractions while choosing an incorrect missing-context policy in all five cases. This non-vision result does not qualify a visual observer by itself, but it demonstrates why extraction, ontology, missingness handling, and decision quality must not be collapsed into one score.

## Practical capability map

The entries below qualify observed roles; they are not universal claims about every VLM or Qwen configuration.

| Task | Observed behavior | CEF qualification response |
|---|---|---|
| Broad subject class with controlled vocabulary | Usually strong | License for coarse observation; retain an uncertainty option. |
| Visible clothing, accessories, setting, and major objects | Usually strong in sparse or moderate scenes | License, with review when overlap creates ownership ambiguity. |
| Uncomplicated action or pose | Usually useful | License only at coarse granularity. |
| Unusual literal morphology | Often strong when asked literally | License; avoid forcing species or narrative interpretation. |
| Sparse scene summary | Strongest captioning regime observed | License. |
| Face or region visibility | Useful with controlled vocabulary | License with deterministic wording checks and human spot review. |
| Exact left/right anatomy | Repeatedly unreliable | Restrict; use metadata, mirrored controls, or human review. |
| Image-left/image-right illumination | Failed both right-light cells in Demo 1 | Restrict; prefer paired pixel measurement plus human review. |
| Coarse torso facing | Inconsistent when head and torso conflict | Prefer trusted human metadata where it matters. |
| Fine three-quarter orientation | Unreliable | Do not request as an unconstrained visual field. |
| Exact framing or lowest visible landmark | Repeated waist/thigh/knee/feet confusion | Prefer human pre-sort or landmark measurement. |
| Hand ownership, grip, contact, and hidden limbs | Confident invention under overlap | Restrict; simplify or route to human review. |
| Dense subject or object count | Unreliable and often overconfident | Use separate detector, segmentation, or human counting. |
| Material identification | Can recognize local cues while missing whole-object contradiction | Require part inventory before global judgment. |
| Reflection, translucency, and material identity | Readily confusable | Restrict broad claims; use references or specialist tests. |
| Rare text or comic artifacts | False positives can persist across retries | Use OCR, detectors, or human allowlists. |
| Statue versus living subject | Dataset-specific confusion | Require uncertainty or human review. |
| Gender in stylized subjects | Occasional confident errors | Avoid unless necessary, visible, and qualified. |
| Cosmetics versus scars or tattoos | Unreliable | Do not request without a specialized qualification set. |
| Event or transient state versus stable identity | Leakage in both directions | Separate evidence fields and retain human correction. |
| Structured observation compressed into prose | Lossy; correct evidence can be omitted or contradicted | Preserve and validate both layers independently. |
| Self-reported confidence | Poorly calibrated in demonstrated failures | Never use as correctness evidence by itself. |
| Same-model retry | Systematic errors often recur | Label as non-independent evidence. |

## Observed failure boundaries

### 1. Local recognition can support a false global proposition

**Controlled observation — CEF Demo 1.** Qwen's average reported confidence was 0.98. Corrected human adjudication found eight agreements and four disagreements across twelve cells.

- It passed an SDXL wood-lamp result after recognizing wood in the support and base, while the dominant glowing globe contradicted the instruction that the entire lamp be unfinished wood.
- It passed both requested right-lit vase cells although paired outputs remained image-left lit and nearly identical to the left-light controls.
- It gave a perfect count-criterion score to an SDXL “three cubes” cell containing four distinct cube bodies.

The supported conclusion is behavioral: local supporting features do not guarantee that the observer checked the complete object or scene proposition. A hidden-mechanism explanation is not established.

**Process response:** decompose universal claims into visible part inventories, compare counterfactual pairs, use deterministic side measurements where appropriate, and retain human adjudication as the publication gate.

### 2. Directional coordinate frames are unstable

**Repeated observation.** Captioning work produced left/right swaps, exact-hand errors, and confusion between head direction, torso facing, subject coordinates, and image coordinates. A visible face could cause a rear-facing body to be mislabeled.

**Controlled observation — CEF Demo 1.** Both right-light cells were judged correctly lit although image measurements and paired review showed that their brightest side and shadow behavior remained consistent with image-left illumination.

**Working hypotheses:** the observer may shift between image, subject, prompt-relative, and semantic coordinate frames; face salience may overpower torso evidence. These explanations remain hypotheses.

**Process response:** qualify `image-left` and `image-right` explicitly, include mirror controls, separate illumination origin from shadow direction, keep head and torso orientation separate, and prefer trusted metadata for consequential facing labels.

### 3. Topology and ownership degrade under overlap

**Repeated observation.** Exact hand placement, grips, contact points, object ownership, limb ownership, and subtle body geometry attracted confident invention. Increasing directive detail increased the number of precise claims without reliably increasing perception.

**Process response:** complexity should reduce requested detail. Prohibit hidden-limb reconstruction and exact left/right anatomy. Route high-overlap cells to human review. Prefer a short correct relationship to complete speculative geometry.

### 4. Counting is a separate qualification domain

**Repeated observation.** Dense heads, processions, repeated textures, and overlap encouraged invented exact counts or exhaustive enumeration.

**Controlled observation — CEF Demo 1.** The observer reported exactly three cubes with maximum criterion confidence where four were visible.

**Process response:** qualify counting independently across isolated objects, mild occlusion, overlap, repeated textures, and dense crowds. Use detection, segmentation, or human enumeration when count is material to the conclusion.

### 5. Material cues and object-wide material intent differ

**Controlled observation — CEF Demo 1.** The observer correctly described wood grain on part of a lamp and still passed a result whose major globe contradicted the all-wood criterion.

**Process response:** require a visible-part inventory before evaluating a universal material claim. Ask which parts were checked. Use reference-assisted calibration where appropriate, while recording that the reference changes the measurement condition.

### 6. Directive vocabulary changes the measurement

**Repeated observation.** Long menus and examples induced fixation on offered vocabulary. Rare artifact examples could prime false positives. Less inhibited model variants could become more willing to invent precise facts.

The observer directive is not neutral: it supplies an ontology, names expected evidence, and can invite concept completion.

**Working hypothesis:** some apparent perception may be prompt-conditioned completion rather than pixel-led observation.

**Process response:** compare prompt-blind and prompt-conditioned passes, use short controlled vocabularies, preserve directive text and hashes, and counterbalance category wording when testing susceptibility.

### 7. Missing information tends to be completed

**Controlled non-vision corroboration.** The private analyst qualification found highly accurate extraction alongside systematically incorrect missing-context handling.

**Repeated visual analogue.** Captioning runs reconstructed hidden limbs, inferred grips, named indistinct forms, and confidently explained details supported only as uncertain.

**Process response:** mix impossible or genuinely unanswerable controls with answerable questions. Score correct abstention separately. Make `unknown`, `not_visible`, and `ambiguous` first-class schema states.

### 8. Event, transient state, and stable identity can leak together

**Dataset-specific observation.** One captioning project asked the observer to record a target event privately while omitting it from public identity captions. The observer often noticed and selectively omitted the event, showing useful role-bounded behavior, but reverse impressions, residue, facial state, and temporary deformation could be promoted to additional subjects or stable anatomy.

In a 42-image run, 30 records initially passed deterministic checks and 12 entered review. Human review produced 85 preserved audit events before all 42 passed the deterministic gate. This demonstrates a productive human-plus-model workflow, not fully reliable raw output.

**Process response:** separate noticed evidence from emitted claims, ask whether a description would remain true before or after the event, and retain human review for ambiguous identity/state boundaries.

### 9. Structured extraction and prose compression are distinct stages

**Repeated observation.** A substantially correct structured record could lose, alter, or contradict facts when compressed into a caption. Models also renamed nested fields, used incorrect types, populated forbidden slots, or emitted malformed JSON.

**Process responses:** recursive schema validation; cardinality enforcement; independent prose-versus-structure checks; preservation of failed raw responses; corrected re-audits rather than silent replacement; retry and elapsed-time provenance; and resumable partial output.

**CEF implication:** raw observation, validated structure, compressed prose, and final judgment should remain linked but separately inspectable. Compression fidelity deserves its own gate.

### 10. A same-model retry is not independent corroboration

**Dataset-specific observation.** False text artifacts and geometry misunderstandings sometimes persisted through focused verification prompts.

**Process response:** use retries for format repair, sensitivity testing, or stability measurement. Independent corroboration requires a different qualified model, deterministic instrument, trusted metadata, or human review.

### 11. Self-reported confidence is not calibration

**Controlled observation — CEF Demo 1.** Average evaluator confidence was 0.98 despite four human disagreements involving count, direction, and material intent.

**Process response:** calculate empirical calibration by task family and difficulty. Preserve confidence as model output, never as proof of correctness.

## Positive operating envelope

The restrictions do not erase the observer's usefulness. Across several operational captioning datasets, Qwen was repeatedly productive at:

- broad subject, creature, animal, and object categories under controlled vocabulary;
- visible clothing, accessories, settings, and major scene nouns;
- uncomplicated actions and coarse poses;
- sparse composition summaries;
- unusual literal morphology;
- detecting subtle figures in some paintings;
- producing inspectable structured evidence;
- selective omission of a target phenomenon when the event/identity boundary was clear;
- local performance fast enough for canary, review, correction, and full-run iteration.

In one 163-image fantasy-art workflow, failures clustered around ornate armor, dragons, dense census, statues, overlapping heads, processions, and forbidden style language. After human review, 158 images passed and five retained uncertainty flags. The workflow succeeded because the role was bounded and the output was reviewed.

## Trusted metadata and hybrid measurement

Human-created metadata is not a concession that invalidates an experiment. It assigns questions to instruments that have demonstrated competence.

A repeatedly useful pattern is:

1. Humans sort images by a weak visual dimension such as framing or coarse facing.
2. Folder or manifest labels become authoritative, provenance-bearing metadata.
3. The observer is told not to re-infer that dimension.
4. The observer handles stronger domains such as clothing, setting, broad pose, visibility, and simple action.
5. Validators enforce controlled vocabulary and forbid known high-risk claims.

Operational results from pre-sorted datasets were strong, but they do not isolate sorting as the sole cause; curation, caption quality, repeats, and training configuration also changed. Trusted metadata itself can contain error and therefore needs definitions, provenance, and spot checks.

## Role licenses

CEF should publish task-specific observer licenses rather than one global quality score. Candidate roles include:

- `coarse_semantic_observer`;
- `sparse_scene_observer`;
- `prompt_adherence_judge`;
- `count_observer`;
- `directional_observer`;
- `material_observer`;
- `topology_and_contact_observer`;
- `artifact_ocr_observer`;
- `style_reference_observer`;
- `compression_auditor`;
- `schema_reliable_interface`.

A model can be licensed for some roles and restricted from others. Restrictions are scientific metadata, not a universal rank.

## Recommended pass separation

1. **Prompt-blind visible-evidence pass** — report what is visible without knowing the desired answer.
2. **Prompt-conditioned criterion pass** — compare evidence with the declared criterion.
3. **Claim-fidelity audit** — label explanations as supported, contradicted, unsupported, or unknown.
4. **Schema/interface audit** — validate types, names, cardinality, required fields, and prose/structure consistency.
5. **Human or deterministic adjudication** — publication gate for restricted or disputed domains.

Do not silently feed qualification answers into the main judgment pass. Diagnostic competence and experimental judgment must remain observable as different stages.

## Observer provenance

Record at least:

- model family, exact build, and quantization;
- runtime, image preprocessing, and maximum input resolution;
- system and directive text with hashes;
- temperature, seed when supported, token limit, and structured-output mode;
- whether the generation prompt was visible;
- whether reference images or trusted metadata were supplied;
- retry and correction history with elapsed time;
- raw response, parsed response, validation result, and corrected response;
- human adjudication and adjudicator identity;
- ground-truth source and its uncertainty.

Candidate evidence fields:

```json
{
  "input_context_mode": "image_only | prompt_conditioned | reference_conditioned",
  "claim_basis": "directly_visible | trusted_metadata | inferred | unknown | deliberately_omitted",
  "task_license": "coarse_semantics | count | direction | material | topology | artifact | style",
  "ground_truth_source": "human_adjudication | deterministic_measure | trusted_metadata | consensus | none",
  "abstention_reason": "not_visible | ambiguous | outside_license | insufficient_resolution | none",
  "compression_source_record_id": "...",
  "compression_fidelity_status": "faithful | omission | contradiction | unsupported_addition",
  "independence_class": "same_model_retry | different_model | deterministic | human"
}
```

These are roadmap fields, not a claim that the current artifact schema implements all of them.

## Qualification-suite roadmap

### Direction and coordinate frames

- mirror-paired image-left/image-right lighting;
- subject-left versus image-left wording;
- head direction decoupled from torso direction;
- rear torso with face visible over shoulder;
- rotated-page controls;
- paired pixel measurements where appropriate.

### Framing and visibility

- lowest-visible-landmark ladder from face through feet;
- occluded versus cropped lower body;
- full body with feet hidden by a foreground object;
- deterministic image bounds plus human labels.

### Count and topology

- one to five isolated objects;
- occlusion ladder;
- touching versus fused objects;
- repeated-texture distractors;
- overlapping heads and crowds;
- declared count versus populated schema slots and prose.

### Material and global proposition checking

- single-material objects;
- one deliberately contradictory part;
- reflective metal versus glass versus translucent plastic;
- function that tempts rationalization;
- part inventory before global pass/fail.

### Missingness and hallucination resistance

- answerable controls mixed with impossible questions;
- hidden limbs and unseen reverse sides;
- missing metadata;
- ambiguous low-resolution details;
- separate scoring of invention and reflexive abstention.

### Event versus identity

- the same subject before, during, and after an event;
- expression versus stable morphology;
- mud, blood, paint, scars, tattoos, and cosmetics;
- temporary deformation versus anatomy;
- reverse impressions, shadows, reflections, and duplicates.

### Prompt contamination

- prompt-blind versus prompt-visible evaluation;
- correct, incorrect, and adversarial generation prompts;
- plausible distractors in category menus;
- artifact examples present versus absent from the directive.

### Compression and schema reliability

- structured evidence followed by separate prose compression;
- same-model versus deterministic-template compression;
- nested types, renamed fields, cardinality, and unknown handling;
- retained malformed attempts and separately measured correction success.

### Repetition and independence

- identical retry for stability;
- paraphrased retry for directive sensitivity;
- different qualified model;
- deterministic or human adjudication;
- agreement labeled by independence class.

## Immediate CEF doctrine

1. Treat evaluator output as model behavior, not ground truth.
2. Publish observer dossiers by role rather than a single quality score.
3. Add prompt-blind observation before prompt-conditioned judgment where expectation is a risk.
4. Make claim basis, uncertainty, and genuine unknown states explicit.
5. Qualify count, direction, material, and topology independently.
6. Display empirical disagreement beside average confidence.
7. Label same-model retries as non-independent.
8. Preserve failed, malformed, corrected, and superseded responses.
9. Use deterministic side instruments when they outperform language judgment.
10. Require human adjudication for publication in restricted or disputed domains.
11. Keep hypotheses visibly separate from observations.
12. Treat directive vocabulary as part of the experimental condition.

## Scope limits and non-findings

- Most operational observations concern one local Qwen3-VL 8B Instruct configuration, often Q4_K_M. They do not automatically generalize to every model size, release, quantization, or runtime.
- The captioning datasets were operational projects, not one preregistered benchmark. They guide qualification design but do not provide population error rates.
- Human review is fallible. Demo 1's four-cube correction occurred after publication; adjudication therefore needs revision history rather than an aura of finality.
- Trusted metadata can contain labeling error and needs provenance and spot checks.
- Strong downstream LoRA results do not isolate pre-sorting or captioning as the sole cause.
- Event-associated learning in one subject domain does not establish subject-independent transfer.
- Coordinate-frame confusion, prompt-conditioned perception, local-versus-global checking, and prior completion are explanatory hypotheses. The present evidence establishes behaviors, not hidden mechanisms.

The detailed local captioning records and controlled analyst dossiers remain in the private research archives. This public document carries their calibrated findings without publishing private paths, source images, or unrelated project artifacts. Public CEF evidence is available in the [Demo 1 run record](DEMO_1_RUN_RECORD.md) and the [live controlled demonstration](https://detroitwobbly.github.io/checkpoint-evaluation-framework/).

## Closing doctrine

The productive question is not “Is Qwen a good evaluator?” It is:

> For which observable questions, under which directives and inputs, with which validators and adjudicators, has this observer demonstrated reliable behavior?

That question produces a dossier instead of a reputation. It preserves the observer's real usefulness while preventing fluency, confidence, or repeated self-agreement from masquerading as ground truth.
