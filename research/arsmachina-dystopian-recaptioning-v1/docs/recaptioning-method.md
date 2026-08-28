# Recaptioning Method

## Objective

The experiment applies an A0-style responsibility doctrine to recovered style-LoRA captions:

> Caption what ordinary prompt language should control, and leave the recurring visual treatment for the trigger and LoRA to learn.

The goal is not to claim that the revised captions are superior without retraining evidence. It is to create an auditable alternative suitable for a controlled comparison.

## Source evidence

The model metadata contains 131 distinct lowercase natural-language caption keys beginning with `the image` under `metadata["ss_tag_frequency"]["img"]`. Metadata also records 655 training-image presentations and 1,640 training steps. The raw metadata dump is not redistributed because it contains an unnecessary local path; its relevant caption evidence is preserved in the package manifests.

Source captions were extracted in the JSON object's original insertion order. They were never alphabetically sorted. Because safetensors metadata does not preserve the original dataset filenames, ordinal-to-image mapping remains `ordinal_assumption_unverified`, and every record remains `source_text_only` until checked against the source images.

## Rewrite procedure

Each of the 131 captions was reviewed and rewritten individually. The process did not rely solely on blind regular-expression deletion.

The semantic captions retain, when the source text supports them:

- subject type and count;
- pose and directly described action;
- clothing, armor, anatomy, masks, headdresses, and accessories;
- held and nearby objects;
- setting and major structures;
- explicit spatial or contact relationships;
- salient object-specific colors;
- physically present light sources.

The rewrites remove:

- artist names, titles, franchises, fictional-character guesses, and provenance claims;
- medium and style labels;
- aesthetic praise and atmosphere judgments;
- inferred emotion, intention, and narrative;
- filler such as `the image shows`;
- unsupported named identities.

Where a named identity carried useful visible information, it was converted conservatively to phenotype—for example, `Anubis` became `a jackal-headed humanoid`. When the source did not describe enough visible evidence to support such a conversion, the identity was reduced to a generic subject or omitted. Ambiguous remnants are explicitly marked in `review_notes` rather than silently resolved.

## Caption format

Every caption file contains one lowercase natural-language sentence, without a terminal period. The semantic portion normally contains 8–35 words.

Unique-trigger edition:

```text
ArsDystopia_style, [image-local semantic description]
```

Legacy-trigger edition:

```text
dystopian mythology fantasy, [the same image-local semantic description]
```

## Audit trail

`caption_manifest.csv` and `caption_manifest.json` retain, for every ordinal:

- original source caption;
- rewritten semantic caption;
- both complete trigger editions;
- removed-claim record;
- manual review notes;
- mapping basis and verification status.

`validation_report.json` records structural validation and every caption requiring additional visual review.

## Limits and responsible use

The source images were unavailable, so even concrete nouns and relationships inherited from the original automated captions cannot be visually guaranteed. The package is a reconstructable, reviewable proposal—not verified image ground truth. Before training, the creator should match captions to images, resolve every review note, and set uncertain records to hold or reject under the included A0 directive.

Only a controlled retraining comparison can establish whether the unique trigger or revised responsibility assignment improves trigger ownership, promptability, or transfer.
