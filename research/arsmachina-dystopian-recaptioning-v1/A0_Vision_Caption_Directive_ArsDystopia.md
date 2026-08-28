# A0 Vision Caption Directive — ArsDystopia

## Purpose

Create image-grounded training captions for an SDXL style/concept LoRA. Caption only the visible semantic content that ordinary prompt language should control. Leave the recurring visual identity—rendering, atmosphere, palette, aesthetic, genre fusion and artistic treatment—for the trigger and LoRA to own.

Recommended trigger:

```text
ArsDystopia_style
```

## Inputs

For each record you may receive:

- the source image;
- its filename;
- an optional old caption.

The image is authoritative. The old caption is audit evidence only. Never use an old caption to infer something that is not visible.

## Required procedure

### Pass 1: blind visual inventory

Inspect the image without relying on the old caption. Record:

- visible subject count and type;
- pose and directly visible action;
- concrete clothing, armor, anatomy and accessories;
- visible objects;
- setting and major structures;
- explicit spatial relationships;
- clear framing or viewpoint;
- uncertainty caused by cropping, occlusion or ambiguity.

### Pass 2: old-caption audit

Compare the old caption with the visual inventory. Identify:

- supported concrete facts worth preserving;
- unsupported named identities;
- artist, title, franchise or provenance claims;
- medium and style language;
- aesthetic praise and atmosphere judgments;
- inferred emotion, intention or story;
- contradictions or details that cannot be verified.

Do not restore a removed claim merely because it appears in the old caption.

### Pass 3: final caption

Write one lowercase natural-language sentence, normally 8–35 semantic words after the trigger:

```text
ArsDystopia_style, [visible semantic description]
```

Use no terminal period.

## Preserve

- subject type and count;
- pose and visible action;
- concrete anatomy when clearly visible;
- clothing, armor, masks, headdresses and accessories;
- held and nearby objects;
- setting and major structures;
- foreground/background and contact relationships that are clearly visible;
- clear framing or viewpoint;
- object-specific colors when salient;
- physically present light sources such as fire, moon, lamp or glowing orb.

## Exclude

- artist names, artwork titles, logos and provenance;
- films, games, franchises and fictional-character guesses;
- release dates or claims about where an image originated;
- `digital art`, `animated`, `concept art`, `painting`, `illustration`, `realistic`, `fantasy`, `science fiction`, `steampunk`, `monochrome`, `sepia` and similar medium/style labels;
- `intricate`, `detailed`, `beautiful`, `captivating`, `majestic`, `vibrant` and other aesthetic praise;
- `mysterious`, `powerful`, `surreal`, `dreamlike`, `ethereal`, `chaotic` and other atmosphere judgments;
- `determined`, `ready to strike`, `deep contemplation`, `appears to be`, `giving the impression` and other inferred emotion, intent or narrative;
- filler such as `the image shows`, `the background is` and `wearing a costume`;
- booru-tag syntax or mixed tag/prose captions.

## Identity policy

Prefer visible phenotype to speculative identity.

| Unsupported label | Image-grounded form |
|---|---|
| `Anubis` | `a jackal-headed humanoid` |
| `pharaoh` | `a person wearing a tall headdress` |
| `goddess` | `a woman` plus visible crown, robe or wings |
| franchise character | visible man, woman, person, statue or creature |
| cultural warrior label | visible armor, weapon and headdress |
| `mermaid` | `a woman` unless a tail is clearly visible |

Use a named deity or culture only when the iconography is unambiguous and a human reviewer verifies it.

## Material and relationship policy

- Use `statue` or `sculpture` only when the subject is visibly inanimate.
- Name stone, bronze, metal, glass or another material only when visually supported.
- Do not infer hidden hand-object contact.
- Do not invent rope, weapon or limb continuity through occlusion.
- Do not assign an exact count when figures cannot be separated reliably.
- Do not invent a lower-body pose when the image is cropped.
- Prefer omission over confident error.

## Output schema

Return exactly one JSON object:

```json
{
  "filename": "source-image.ext",
  "caption": "ArsDystopia_style, ...",
  "visible_subjects": ["..."],
  "visible_objects": ["..."],
  "setting": ["..."],
  "relationships": ["..."],
  "uncertainties": ["..."],
  "preserved_old_claims": ["..."],
  "removed_old_claims": [
    {
      "claim": "...",
      "reason": "provenance | named_identity | medium_style | aesthetic | interpretation | unsupported"
    }
  ],
  "status": "pass | hold | reject"
}
```

## Status rules

### Pass

- caption agrees with the visible image;
- major subject count, objects and relationships are supported;
- no excluded language remains;
- uncertainties do not materially change the caption.

### Hold

- uncertain identity, count, material, anatomy, contact or spatial relationship;
- old caption and image materially disagree;
- important text or logo requires inspection;
- another independent caption pass disagrees on a major fact.

### Reject

- image is missing, corrupt or an exact duplicate;
- no useful semantic caption can be supported;
- contradictions remain after human review.

## Examples

Old caption:

```text
the image shows a woman in a long dress holding a plant in her hand standing in front of a wall. she appears to be a character from the game of thrones as indicated by the title of the image "the witcher 3 wild hunt".
```

Final caption:

```text
ArsDystopia_style, a woman in a long dress stands in front of a wall holding a plant
```

Old caption:

```text
the image shows anubis the god of the underworld sitting in front of a group of statues in a temple. he is surrounded by pillars and lights. the image is animated and is part of the elder scrolls online tamriel unlimited pc game.
```

Final caption:

```text
ArsDystopia_style, a jackal-headed humanoid sits among statues inside a temple, surrounded by pillars and lights
```

## Final self-check

Before returning the JSON, verify:

1. Is every caption claim visible?
2. Did any style, provenance or aesthetic language survive?
3. Did I infer a famous character, culture, emotion or story?
4. Did I preserve useful concrete objects and spatial relationships?
5. Would ordinary prompt language be able to change the captioned content while the trigger retains the recurring visual identity?

If any answer reveals uncertainty that could materially change the caption, set `status` to `hold`.
