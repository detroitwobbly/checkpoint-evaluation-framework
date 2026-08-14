# Security

CEF sends prompts and generated images to the endpoints explicitly supplied by the operator. Local defaults use loopback addresses, but a remote OpenAI-compatible endpoint will receive image content and evaluation context.

## Safe operation

- Review endpoint URLs before each run.
- Treat API keys as secrets; pass them at runtime and never place them in manifests, directives, reports, or committed shell history.
- Do not evaluate private images through a third-party endpoint without authorization.
- Keep generated runs ignored until their metadata and images have been reviewed.
- Inspect `forge_inventory*.json`, `generation.json`, PNG metadata, and reports for local paths before sharing.
- Bind report serving to `127.0.0.1` unless you intentionally want network access.
- Treat manifests and directives from untrusted sources as data requiring review. They can cause expensive generation or send sensitive context to the configured evaluator.

## Reporting vulnerabilities

Please report security issues privately to the maintainer once public contact information is chosen. The repository deliberately leaves maintainer contact unresolved until that publication decision is made.

Do not include private images, credentials, or model files in a public issue.
