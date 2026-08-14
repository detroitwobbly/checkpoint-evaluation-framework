# PNG metadata and publication model

CEF treats PNG pixels, backend-native metadata, CEF records, and public artifacts as related but distinct evidence.

## Current private-run behavior

Forge returns base64-encoded PNG data and a separate response `info` record. CEF decodes each image and writes those bytes directly with `Path.write_bytes`; it does not open, re-encode, or annotate the private original.

The private chain is:

1. the immutable Forge-returned PNG and its SHA-256;
2. Forge/A1111's embedded PNG text, retained raw and parsed best-effort in `png_provenance_index.json`;
3. `request.json`, `generation.json`, the run-local manifest, generation index, and backend inventory;
4. machine-analysis records; and
5. approved human adjudication.

Sidecars remain authoritative because backend metadata varies by version and extension. CEF did not previously inject custom metadata into generated PNGs through the Forge API or after generation.

For Demo 1, the private `parameters` text contains these parsed fields: `Steps`, `Sampler`, `Schedule type`, `CFG scale`, `Seed`, `Size`, `Model hash`, `Model`, `RNG`, and `Version`.

## API boundary

The Forge/A1111-compatible `txt2img` request does not provide a standard field for arbitrary caller-owned PNG text chunks. The API returns image data and generation infotext; a client may write that infotext or other metadata into a PNG after receiving the response.

CEF therefore does not depend on a backend-specific extension hook for artifact identity. CEF-owned metadata is added only by an explicit post-generation publication or annotation step.

## `sanitized-v1` publication behavior

Public images are separate artifacts. The exporter:

1. decodes the private original losslessly;
2. removes all source PNG metadata;
3. adds the versioned CEF identity-and-hash envelope;
4. writes a lossless public PNG;
5. verifies pixel equality against the private original; and
6. records source/public hashes and the transformation in `artifact_index.json`.

This produces intentionally different file hashes with identical pixel content. `cef_original_png_sha256` connects a downloaded public image to the immutable private source. `cef_evidence_sha256` connects it to the public structured evidence.

## Future private annotation option

If CEF later needs self-identifying private originals, it should preserve the backend-returned file and create a second annotated copy. A Pillow re-save can preserve pixels and selected text semantically, but it cannot preserve the complete PNG byte-for-byte and may omit unknown ancillary chunks unless they are handled explicitly.

A chunk-level insertion tool could preserve every existing PNG chunk byte-for-byte while adding a CEF text chunk immediately before `IEND`. Even then, CEF should retain both hashes and never replace the backend original.
