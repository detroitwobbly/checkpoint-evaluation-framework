# Public release checklist

Status legend: `[x]` verified in this curated tree, `[ ]` pending, `BLOCKED` requires a human provenance or publishing decision.

## Repository curation

- [x] Reusable package copied into a separate curated tree.
- [x] Canonical research archive left unchanged.
- [x] Private generated runs excluded.
- [x] Model and LoRA weights excluded.
- [x] Artist-specific and explicit demo material excluded.
- [x] Personal names removed from copied test fixtures and heuristic keyword lists.
- [x] Generated run directories ignored by default.
- [x] Review final Git status immediately before first commit.
- [x] Create intentional initial Git history after approval.

## Installation and behavior

- [x] Python package metadata present.
- [x] Console entry points declared.
- [x] Safe demo supports backend-free dry-run expansion.
- [x] Generation resume requires the same run-local manifest.
- [x] Incomplete generation cells are regenerated.
- [x] Generation index and run state are written incrementally and atomically.
- [x] Analysis reuses per-image results unless overwrite is requested.
- [x] Structured evaluator failures can be preserved with `--continue-on-error`.
- [ ] Verify clean editable install in a fresh environment.
- [x] Verify built wheel installation in a fresh environment.
- [x] Verify Forge preflight, per-checkpoint canaries, and one 12-cell real generation run.
- [x] Verify one OpenAI-compatible local Qwen3-VL analysis run, including preserved failure and targeted retry.

## Automated verification

- [x] All tests pass in the curated tree: 56 passed on 2026-08-14.
- [x] Safe demo and test JSON parse successfully.
- [x] README-local links resolve.
- [x] CLI help works from the installed entry point.
- [x] Run-review entry point works from the installed package.
- [x] Release-audit entry point works from the installed package.
- [x] Scan returns no credential-like values.
- [x] Scan returns no personal absolute paths or usernames.
- [x] Built wheel contains no cache, generated run, or model files.
- [ ] GitHub Actions workflow passes after repository creation.

## Documentation

- [x] Problem and design explained in README.
- [x] Five-minute dry-run path documented.
- [x] Architecture and provider boundaries documented.
- [x] Evaluation methodology and controls documented.
- [x] Resumability and integrity behavior documented.
- [x] Limitations documented.
- [x] Security and data-disclosure behavior documented.
- [x] Portfolio blurbs grounded in inspected code and tests.
- [x] GitHub description, topics, and pinned ordering proposed.
- [ ] Add screenshots after the approved real demo exists.
- [ ] Add a hosted report link after GitHub Pages review.

## Provenance and licensing — BLOCKED

- [x] Public-demo pair selected: SDXL Base 1.0 and RealVisXL V5.0 FP16.
- [x] Each checkpoint’s license evidence and output-use terms reviewed.
- [x] Exact checkpoint files, hashes, names, and model-card attribution approved.
- [x] Generate all 12 demo images and prepare a full-resolution adjudication draft.
- [ ] BLOCKED: Alex completes and approves the 12-image human-review checklist.
- [ ] BLOCKED: decide whether to publish raw PNG metadata or sanitized provenance.
- [ ] BLOCKED: approve all report images and machine-readable artifacts.
- [ ] BLOCKED: confirm AGPL-3.0-or-later as the final code license.

## Repository identity and publication — BLOCKED

- [x] GitHub owner/account selected: `detroitwobbly`.
- [x] Repository identity placeholders replaced.
- [ ] BLOCKED: choose public author and maintainer metadata.
- [x] Repository created privately and initial curated tree pushed after approval.
- [ ] BLOCKED: configure GitHub Pages only after demo provenance approval.

## Final manual review

- [ ] Clone the future repository into a clean directory.
- [ ] Follow README commands exactly without relying on the private archive.
- [ ] Open every HTML report and verify images, labels, and relative links.
- [ ] Validate representative JSON against documented semantics.
- [ ] Confirm the demo report matches its manifest and methodology text.
- [ ] Confirm no unsupported claims appear in README, portfolio copy, or application copy.
- [ ] Review the repository as a hiring manager with five minutes and no project history.
