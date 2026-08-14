# Evaluation methodology

CEF begins with a perceptual question and turns it into observable comparisons. Its unit of evidence is not “an image that looks convincing”; it is a documented run cell with known conditions, artifacts, criteria, and uncertainty.

## Why controls matter

CEF evaluates outputs against controlled counterfactuals rather than attributing every visible change to the model component under test. Fixed seeds, zero-weight controls, semantic controls, cross-model comparisons, and integrity checks are used where appropriate to distinguish prompt effects, checkpoint priors, adapter effects, and operational mistakes.

A fixed seed controls one source of variation, but it does not make images from different checkpoints pixel-equivalent. Conclusions must remain proportional to the control actually imposed.

## Recommended protocol

1. State one behavioral question in observable language.
2. Identify the variable being changed and the variables being held constant.
3. Add positive, negative, and counterfactual controls where they clarify attribution.
4. Define criteria before inspecting results.
5. Record prompts, seeds, generation settings, backend version, checkpoint identity, and adapter state.
6. Generate the full manifold or disclose missing cells.
7. Use evaluator directives that separate observation, evidence, interpretation, and uncertainty.
8. Preserve evaluator failures and disagreement.
9. Inspect contact sheets and individual images as a human reviewer.
10. Report limitations and plausible alternative explanations.

## Evaluator roles

- Observer: describes visible properties without scoring when premature quantification would erase useful detail.
- Judge: applies an explicit criterion contract and produces a score or decision.
- Auditor: inspects another evaluator’s records for unsupported claims, omissions, or inconsistency.
- Human reviewer: resolves ambiguous evidence and decides whether findings are fit for publication.

These roles can use the same underlying VLM, but their directives and evidence contracts should remain distinct.

## Evidence language

Prefer: “Under these prompts and fixed seeds, checkpoint A followed left/right lighting instructions in five of six evaluated images.”

Avoid: “Checkpoint A understands lighting” or “the training data taught the model physical reasoning.”

CEF supports progressively stronger behavioral claims when replication, controls, and independent review justify them. It does not provide mechanistic evidence by itself.

## Automated evaluation limits

Vision models can miss count errors, confuse reflection with material, reverse image-left and subject-left, import expectations from prompt text, or return malformed structures. CEF preserves uncertainty, raw responses, comparison artifacts, and human-review queues because automated evaluation is evidence—not ground truth.
