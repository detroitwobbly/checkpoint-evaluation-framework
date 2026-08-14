# Limitations

- Image generation currently targets Forge/A1111-compatible APIs. No ComfyUI, hosted diffusion, or vendor-specific backend is implemented.
- Vision evaluation expects an OpenAI-compatible image-message interface, but local servers and models vary in schema support and response behavior.
- Fixed seeds improve control but do not establish equivalence across checkpoint architectures or implementations.
- VLM judgments can be prompt-biased, directionally confused, inconsistent, or structurally invalid.
- Scores are directive- and evaluator-dependent; they are not universal psychometric measurements.
- Resume validation compares manifest snapshots and artifact presence but does not yet hash every JSON artifact into a signed ledger.
- The pipeline review reports completeness; it does not prove that every experimental design decision was scientifically adequate.
- Reports can contain local paths if a user deliberately runs CEF with absolute output paths. Public artifacts require a sanitation pass.
- Backend inventory can expose local model and LoRA paths. It must be reviewed before publication.
- The current demo is scaffolding. No checkpoint or generated output has yet passed the public provenance gate.
- CEF supports human review but does not yet provide a full interactive adjudication UI in this repository.

These limitations should appear beside published findings, not only in developer documentation.
