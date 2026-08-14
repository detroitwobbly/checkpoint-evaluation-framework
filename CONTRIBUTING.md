# Contributing

This repository is a release candidate and is not yet accepting public contributions. The following standards describe how changes should be prepared before publication.

- Preserve manifest-driven, inspectable behavior.
- Add tests for bug fixes and new artifact contracts.
- Keep generation and analysis independently resumable.
- Do not add model weights, private runs, personal datasets, credentials, absolute personal paths, or unlicensed reference material.
- Separate direct observation from interpretation and mechanistic speculation.
- Document new external endpoints and what data they receive.
- Run `python -m pytest` and the release checks before proposing a change.

Generated examples require a completed provenance ledger and human review.
