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

## Evidence semantics

The following dimensions must not be collapsed into one confidence score:

- Record status: resolved, missing, ambiguous
- Asset retrieval: accessible, inaccessible, unverified
- Visual evidence: image inspected, metadata only, record only, none
- Execution delivery: confirmed, not verifiable
- Rights status: preserved from the source record

A resolved record does not prove that its image bytes are accessible. Asset accessibility does not prove that an execution tool received the exact asset.

## Current limitations

This initial P0 package supplies adapter protocols and deterministic resolution logic. Concrete Notion/database adapters, visual inspection, execution-tool receipt integrations, attribute authorization, manifest serialization, approval binding, and workflow integrations are not implemented yet. No production or end-to-end capability is claimed.
