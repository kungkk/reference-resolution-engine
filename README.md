# Reference Resolution Engine

A dependency-light Python library for resolving image-operation source records before any image generation or editing occurs.

The engine is a **pre-generation decision service**. It does not generate or edit images, save assets, modify Notion records, or perform biometric identity verification.

## v1.0 architecture boundary

- `/portrait` remains the user-facing orchestrator.
- `/isolate` remains the attribute authorization and edit-boundary controller.
- Specialist Skills remain domain executors.
- `/portrait-qa` remains an independent, read-only reviewer.
- This package resolves source records and evidence. It does not replace those responsibilities.

## Approved policy baseline

- **D1 — Identity alias cardinality:** one primary original photograph per identity alias. Other photographs are supporting evidence only and are never automatically substituted or blended.
- **D2 — Creative-reference cardinality:** one primary creative reference per operation. Multi-reference composition is deferred.
- **D3 — Delivery evidence:** delivery is confirmed only by an explicit execution-tool receipt/source echo matching the expected source ID. Otherwise it is `not_verifiable`.
- **D4 — Rights:** unknown is not permission; personal-only remains restricted to personal use. Rights metadata is carried as evidence, not treated as a legal determination.
- **D5 — Persistence:** manifests are ephemeral by default; persistence requires separate authorization and an approved destination.

## P0 implementation

P0 defines source-role contracts and deterministic adapters for identity aliases, creative references, and editing targets. Record resolution is independent of asset retrieval and visual inspection. The engine does not infer that an asset was delivered to an execution tool.

### Runtime

- Python 3.12+
- Runtime dependencies: Python standard library only
- Development test dependency: `pytest`

### Development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

### Package layout

```text
src/reference_resolution_engine/
  models.py       # Typed source and evidence contracts
  ports.py        # Adapter protocols
  resolver.py     # Deterministic source resolution
tests/
  test_resolution.py
  test_delivery.py
```

## ChatGPT Library identity import bridge

ChatGPT Library is the authoritative source for the user's selected original identity photograph. The engine has no direct Library API integration and does not synchronize with Library.

The supported workflow is a deliberate manual handoff:

1. The user selects and downloads the intended original photograph from ChatGPT Library.
2. The user runs the import command and explicitly binds the downloaded file to an identity alias (for example, `@me`).
3. The engine validates the file signature for JPEG, PNG, or WebP, computes SHA-256, and copies the image into a per-user local cache.
4. A local JSON registry records the user-confirmed alias binding, Library display name, content hash, cache path, import timestamp, and unsynchronized status.
5. The identity adapter resolves the registered primary original from that local index. Asset retrieval remains a separate evidence check.

Example on Windows PowerShell:

```powershell
python -m reference_resolution_engine.library_import --alias "@me" --source "$HOME\Downloads\my-identity-photo.jpg"
```

The default registry and cache are stored outside the repository under the current user's application-data directory. They can be overridden with `--registry` and `--cache-dir`.

Important boundaries:

- The user must confirm that the downloaded file is the intended ChatGPT Library asset; the engine cannot independently verify Library provenance or retrieve a stable Library asset ID.
- The local JSON registry is an operational index/cache manifest, not a replacement authority for the original image.
- The cache is not synchronized. If the Library asset is replaced, removed, or reselected, the user must explicitly import it again.
- An existing alias cannot be rebound to different image bytes unless `--replace-existing` is explicitly supplied. Previous cache files are not automatically deleted.
- File signature checks are not full image decoding or visual identity verification.
- The image bytes and registry must remain local; do not commit either to Git.

## Evidence semantics

The following dimensions must not be collapsed into one confidence score:

- Record status: resolved, missing, ambiguous
- Asset retrieval: accessible, inaccessible, unverified
- Visual evidence: image inspected, metadata only, record only, none
- Execution delivery: confirmed, not verifiable
- Rights status: preserved from the source record

A resolved record does not prove that its image bytes are accessible. Asset accessibility does not prove that an execution tool received the exact asset.

## Current limitations

This P0 package supplies deterministic resolution logic and a manual ChatGPT Library import adapter. Concrete Creative References and editing-target adapters, visual inspection, execution-tool receipt integrations, attribute authorization, manifest serialization, approval binding, and workflow integrations are not implemented yet. No production or end-to-end capability is claimed.
