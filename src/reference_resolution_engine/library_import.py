"""Manual ChatGPT Library import bridge for primary identity photographs.

ChatGPT Library remains the authoritative source. This module only imports a
user-selected Library download into a local working cache and records a
user-confirmed alias binding. It does not connect to or synchronize with the
ChatGPT Library service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import IdentitySourceRecord

_REGISTRY_SCHEMA_VERSION = 1
_IMAGE_SIGNATURES: tuple[tuple[str, str, bytes], ...] = (
    (".jpg", "image/jpeg", b"\xff\xd8\xff"),
    (".jpeg", "image/jpeg", b"\xff\xd8\xff"),
    (".png", "image/png", b"\x89PNG\r\n\x1a\n"),
    (".webp", "image/webp", b"RIFF"),
)


class LibraryImportError(ValueError):
    """Raised when a manual Library import cannot be safely completed."""


@dataclass(frozen=True, slots=True)
class LibraryImportReceipt:
    """Evidence describing one user-confirmed Library-to-cache import."""

    alias: str
    source_id: str
    asset_locator: str
    library_asset_name: str
    asset_sha256: str
    byte_size: int
    media_type: str
    imported_at: str
    status: str = "imported_copy_verified"

    def to_identity_source_record(self) -> IdentitySourceRecord:
        return IdentitySourceRecord(
            source_id=self.source_id,
            alias=self.alias,
            asset_locator=self.asset_locator,
            is_primary_original=True,
            provenance_status="user_confirmed_library_import",
        )


def default_state_dir() -> Path:
    """Return a per-user state directory outside the source repository."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ReferenceResolutionEngine"
    if os.name == "posix" and os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / "reference-resolution-engine"
    return Path.home() / ".local" / "share" / "reference-resolution-engine"


def _detect_image_type(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    supported = {extension: (media_type, signature) for extension, media_type, signature in _IMAGE_SIGNATURES}
    if suffix not in supported:
        raise LibraryImportError(
            "Only JPEG, PNG, and WebP identity photographs are supported."
        )

    media_type, signature = supported[suffix]
    with path.open("rb") as source:
        header = source.read(12)

    if suffix in {".jpg", ".jpeg"}:
        valid = header.startswith(signature)
    elif suffix == ".png":
        valid = header.startswith(signature)
    else:
        valid = (
            header.startswith(signature)
            and len(header) >= 12
            and header[8:12] == b"WEBP"
        )

    if not valid:
        raise LibraryImportError(
            f"The file extension {suffix!r} does not match a supported {media_type} image."
        )
    return media_type, suffix


def _empty_registry() -> dict[str, Any]:
    return {
        "schema_version": _REGISTRY_SCHEMA_VERSION,
        "authoritative_source": "chatgpt_library",
        "synchronization": "manual_user_confirmed_import",
        "records": {},
    }


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_registry()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryImportError(f"Cannot read identity registry: {exc}") from exc

    if (
        not isinstance(data, dict)
        or data.get("schema_version") != _REGISTRY_SCHEMA_VERSION
        or data.get("authoritative_source") != "chatgpt_library"
        or not isinstance(data.get("records"), dict)
    ):
        raise LibraryImportError("Identity registry has an unsupported or invalid schema.")
    return data


def _write_registry_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(data, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise LibraryImportError(f"Cannot safely write identity registry: {exc}") from exc


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size == 0:
        raise LibraryImportError("The selected identity photograph is empty.")
    return digest.hexdigest(), size


def _copy_file_atomic(source_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with source_path.open("rb") as source, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".identity-import-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            shutil.copyfileobj(source, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
    except OSError as exc:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise LibraryImportError(f"Cannot copy the selected Library image: {exc}") from exc


def import_library_identity_photo(
    *,
    alias: str,
    source_file: str | Path,
    cache_dir: str | Path | None = None,
    registry_path: str | Path | None = None,
    library_asset_name: str | None = None,
    replace_existing: bool = False,
) -> LibraryImportReceipt:
    """Import a manually downloaded Library image into the local working cache.

    The caller must have selected/downloaded the source image from ChatGPT
    Library. No Library API lookup, authentication, or synchronization occurs.
    Existing alias bindings are never replaced unless explicitly authorized.
    """
    if not isinstance(alias, str) or not alias.strip() or len(alias) > 128:
        raise LibraryImportError("alias must be a non-empty string of at most 128 characters.")
    alias = alias.strip()
    if any(character in alias for character in "\r\n\0"):
        raise LibraryImportError("alias cannot contain control characters.")

    source_path = Path(source_file).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise LibraryImportError("source_file must identify a regular image file.")

    media_type, extension = _detect_image_type(source_path)
    asset_sha256, byte_size = _hash_file(source_path)

    state_dir = default_state_dir()
    resolved_cache_dir = Path(cache_dir).expanduser() if cache_dir else state_dir / "identity-cache"
    resolved_registry_path = (
        Path(registry_path).expanduser()
        if registry_path
        else state_dir / "identity-registry.json"
    )
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = resolved_cache_dir.resolve() / f"{asset_sha256}{extension}"
    registry_path_obj = resolved_registry_path.resolve()
    registry = _load_registry(registry_path_obj)
    existing = registry["records"].get(alias)

    if existing:
        if existing.get("asset_sha256") == asset_sha256:
            recorded_cache = Path(str(existing.get("local_cache_path", ""))).expanduser()
            if recorded_cache.is_file():
                recorded_hash, _ = _hash_file(recorded_cache)
                if recorded_hash != asset_sha256:
                    raise LibraryImportError("The existing identity cache failed SHA-256 verification.")
                return LibraryImportReceipt(
                    alias=alias,
                    source_id=str(existing["source_id"]),
                    asset_locator=str(recorded_cache.resolve()),
                    library_asset_name=str(existing.get("library_asset_name") or source_path.name),
                    asset_sha256=asset_sha256,
                    byte_size=byte_size,
                    media_type=media_type,
                    imported_at=str(existing["imported_at"]),
                )
            if cache_path.exists():
                cached_hash, _ = _hash_file(cache_path)
                if cached_hash != asset_sha256:
                    raise LibraryImportError("A cache file exists at the expected hash path but failed verification.")
            else:
                _copy_file_atomic(source_path, cache_path)
            existing["local_cache_path"] = str(cache_path)
            _write_registry_atomic(registry_path_obj, registry)
            return LibraryImportReceipt(
                alias=alias,
                source_id=str(existing["source_id"]),
                asset_locator=str(cache_path),
                library_asset_name=str(existing.get("library_asset_name") or source_path.name),
                asset_sha256=asset_sha256,
                byte_size=byte_size,
                media_type=media_type,
                imported_at=str(existing["imported_at"]),
            )
        if not replace_existing:
            raise LibraryImportError(
                f"Alias {alias!r} already has a different primary photo. "
                "Use replace_existing=True only after confirming the replacement."
            )

    if cache_path.exists():
        cached_hash, _ = _hash_file(cache_path)
        if cached_hash != asset_sha256:
            raise LibraryImportError("A cache file exists at the expected hash path but failed verification.")
    else:
        _copy_file_atomic(source_path, cache_path)

    imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    source_id = f"chatgpt-library:{alias}:{asset_sha256}"
    display_name = (library_asset_name or source_path.name).strip()
    if not display_name:
        display_name = source_path.name

    registry["records"][alias] = {
        "alias": alias,
        "source_id": source_id,
        "is_primary_original": True,
        "authoritative_source": "chatgpt_library",
        "library_asset_name": display_name,
        "library_asset_identifier": None,
        "import_method": "manual_user_confirmed_download",
        "local_cache_path": str(cache_path),
        "asset_sha256": asset_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "imported_at": imported_at,
        "provenance_status": "user_confirmed_library_import",
        "sync_status": "not_synchronized",
    }
    _write_registry_atomic(registry_path_obj, registry)

    return LibraryImportReceipt(
        alias=alias,
        source_id=source_id,
        asset_locator=str(cache_path),
        library_asset_name=display_name,
        asset_sha256=asset_sha256,
        byte_size=byte_size,
        media_type=media_type,
        imported_at=imported_at,
    )


class ChatGPTLibraryIdentityAdapter:
    """Read user-confirmed manual Library import bindings from a JSON index."""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        state_dir = default_state_dir()
        self._registry_path = (
            Path(registry_path).expanduser()
            if registry_path
            else state_dir / "identity-registry.json"
        )

    def find_by_alias(self, alias: str) -> tuple[IdentitySourceRecord, ...]:
        registry = _load_registry(self._registry_path.resolve())
        record = registry["records"].get(alias)
        if not record:
            return ()
        return (
            IdentitySourceRecord(
                source_id=str(record["source_id"]),
                alias=str(record["alias"]),
                asset_locator=str(record["local_cache_path"]),
                is_primary_original=bool(record["is_primary_original"]),
                provenance_status=str(record["provenance_status"]),
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import a manually downloaded ChatGPT Library identity photo."
    )
    parser.add_argument("--alias", required=True, help="Identity alias, e.g. @me")
    parser.add_argument("--source", required=True, help="Path to the image downloaded from ChatGPT Library")
    parser.add_argument("--library-asset-name", help="Optional Library display name")
    parser.add_argument("--cache-dir", help="Local cache directory (defaults outside the repository)")
    parser.add_argument("--registry", help="JSON registry path (defaults outside the repository)")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace an existing alias binding after explicit user confirmation.",
    )
    args = parser.parse_args()

    try:
        receipt = import_library_identity_photo(
            alias=args.alias,
            source_file=args.source,
            cache_dir=args.cache_dir,
            registry_path=args.registry,
            library_asset_name=args.library_asset_name,
            replace_existing=args.replace_existing,
        )
    except (OSError, LibraryImportError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "status": receipt.status,
        "alias": receipt.alias,
        "source_id": receipt.source_id,
        "asset_locator": receipt.asset_locator,
        "library_asset_name": receipt.library_asset_name,
        "asset_sha256": receipt.asset_sha256,
        "byte_size": receipt.byte_size,
        "media_type": receipt.media_type,
        "imported_at": receipt.imported_at,
        "authoritative_source": "chatgpt_library",
        "sync_status": "not_synchronized",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
