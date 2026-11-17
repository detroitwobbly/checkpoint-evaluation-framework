# Evaluation index

## Published evidence sets

| Evidence set | Generated cells | Curated sheets | Purpose |
|---|---:|---:|---|
| Standalone Repaired manifold | 96 | 12 | Seven-weight direction and material/subject behavior |
| Dawnhewn × Repaired compatibility | 56 | 8 | Four scenes, matched controls, identity and geometry risk |
| Repaired × Lived-In cabin matrix | 45 | 5 | Independent and combined cabin behavior |
| Cabin repair-activation follow-up | 12 | 3 | Neutral/explicit prompt activation at three seeds |
| Repaired production-profile bridge | 12 | 6 | Original vs sparse prompts for barn, satchel, and toolbox |
| Dawnhewn production-profile follow-up | 6 | 2 | Dawnhewn-only vs Repaired +1/+2 on two fixed scenes |
| Manual sparse Space-Winnebago annex | 4 selected cells | 1 | Operator-supplied factor separation at +2 |

Total automated CEF generations represented: **227**. The four-cell manual annex is reported separately because it was generated interactively rather than through the frozen CEF runner.

## Evidence map

- `evidence/repaired_standalone/` — full standalone review sheets.
- `evidence/dawnhewn_compatibility/` — original Dawnhewn compatibility sheets.
- `evidence/cabin_slider/` — five cabin-family comparison sheets.
- `evidence/cabin_repair_activation/` — three activation-control sheets.
- `evidence/repaired_production_profile/` — six matched control/Repaired +2 sheets.
- `evidence/dawnhewn_production_profile/` — two three-column Dawnhewn sheets.
- `evidence/manual_sparse_cabin/` — operator-selected four-cell comparison.

Every automated evidence directory includes its sheet index where one was produced. Exact prompts, seeds, settings, checkpoint identities, and LoRA hashes are preserved in `manifests/` and the corresponding JSON indexes.

## Interpretation hierarchy

1. Matched within-run comparisons support the strongest claims.
2. Production-profile follow-ups refine, but do not rewrite, the compact-profile evidence.
3. The manual annex is useful operator evidence but is not represented as a frozen automated CEF run.
4. Attractive isolated images are never treated as proof of controllability.
