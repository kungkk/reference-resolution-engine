from __future__ import annotations

import json
from pathlib import Path

import pytest

from reference_resolution_engine import RecordStatus, ReferenceResolutionEngine
from reference_resolution_engine.library_import import (
    ChatGPTLibraryIdentityAdapter,
    LibraryImportError,
    import_library_identity_photo,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image-payload"


def test_manual_library_import_registers_one_primary_original(tmp_path: Path):
    source = tmp_path / "library-download.png"
    source.write_bytes(PNG_BYTES)
    cache = tmp_path / "cache"
    registry = tmp_path / "identity-registry.json"

    receipt = import_library_identity_photo(
        alias="@me",
        source_file=source,
        cache_dir=cache,
        registry_path=registry,
        library_asset_name="My original identity photo",
    )

    assert receipt.status == "imported_copy_verified"
    assert receipt.media_type == "image/png"
    assert receipt.asset_sha256
    assert Path(receipt.asset_locator).read_bytes() == PNG_BYTES

    adapter = ChatGPTLibraryIdentityAdapter(registry)
    records = adapter.find_by_alias("@me")
    assert len(records) == 1
    assert records[0].is_primary_original is True
    assert records[0].provenance_status == "user_confirmed_library_import"
    assert records[0].asset_locator == receipt.asset_locator

    stored = json.loads(registry.read_text(encoding="utf-8"))
    assert stored["authoritative_source"] == "chatgpt_library"
    assert stored["synchronization"] == "manual_user_confirmed_import"
    assert stored["records"]["@me"]["library_asset_identifier"] is None
    assert stored["records"]["@me"]["sync_status"] == "not_synchronized"


def test_library_import_is_idempotent_for_same_alias_and_content(tmp_path: Path):
    source = tmp_path / "identity.png"
    source.write_bytes(PNG_BYTES)
    registry = tmp_path / "registry.json"

    first = import_library_identity_photo(
        alias="@me", source_file=source, cache_dir=tmp_path / "cache",
        registry_path=registry,
    )
    second = import_library_identity_photo(
        alias="@me", source_file=source, cache_dir=tmp_path / "cache",
        registry_path=registry,
    )

    assert second.source_id == first.source_id
    assert second.asset_sha256 == first.asset_sha256
    assert len(list((tmp_path / "cache").iterdir())) == 1


def test_library_import_refuses_alias_replacement_without_explicit_opt_in(tmp_path: Path):
    first_source = tmp_path / "first.png"
    second_source = tmp_path / "second.png"
    first_source.write_bytes(PNG_BYTES)
    second_source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"different-image")

    kwargs = {
        "alias": "@me",
        "cache_dir": tmp_path / "cache",
        "registry_path": tmp_path / "registry.json",
    }
    first = import_library_identity_photo(source_file=first_source, **kwargs)

    with pytest.raises(LibraryImportError, match="already has a different primary photo"):
        import_library_identity_photo(source_file=second_source, **kwargs)

    replacement = import_library_identity_photo(
        source_file=second_source, replace_existing=True, **kwargs
    )
    assert replacement.asset_sha256 != first.asset_sha256
    # Replacing a binding does not delete the previous cache file.
    assert Path(first.asset_locator).exists()


def test_library_import_rejects_non_image_and_mismatched_extensions(tmp_path: Path):
    invalid = tmp_path / "not-an-image.png"
    invalid.write_bytes(b"plain text")

    with pytest.raises(LibraryImportError, match="does not match"):
        import_library_identity_photo(
            alias="@me",
            source_file=invalid,
            cache_dir=tmp_path / "cache",
            registry_path=tmp_path / "registry.json",
        )


def test_library_identity_adapter_returns_no_records_for_unknown_alias(tmp_path: Path):
    adapter = ChatGPTLibraryIdentityAdapter(tmp_path / "missing-registry.json")
    assert adapter.find_by_alias("@unknown") == ()


def test_manual_library_adapter_integrates_with_identity_resolver(tmp_path: Path):
    source = tmp_path / "identity.png"
    source.write_bytes(PNG_BYTES)
    registry = tmp_path / "registry.json"
    import_library_identity_photo(
        alias="@me",
        source_file=source,
        cache_dir=tmp_path / "cache",
        registry_path=registry,
    )

    class EmptyCreativeAdapter:
        def find_by_id(self, reference_id: str):
            return ()

    class EmptyTargetAdapter:
        def find_by_id(self, target_id: str):
            return ()

    engine = ReferenceResolutionEngine(
        identity_adapter=ChatGPTLibraryIdentityAdapter(registry),
        creative_reference_adapter=EmptyCreativeAdapter(),
        editing_target_adapter=EmptyTargetAdapter(),
    )
    result = engine.resolve_identity("@me")

    assert result.record_status is RecordStatus.RESOLVED
    assert result.provenance_status == "user_confirmed_library_import"
    assert result.asset_locator == str(next((tmp_path / "cache").iterdir()))
