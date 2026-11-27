"""Ports implemented by database, Notion, and asset-storage adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import (
    AssetEvidence,
    CreativeReferenceRecord,
    EditingTargetRecord,
    IdentitySourceRecord,
)


class IdentitySourceAdapter(Protocol):
    def find_by_alias(self, alias: str) -> Sequence[IdentitySourceRecord]:
        """Return all records associated with an alias, including supporting images."""


class CreativeReferenceAdapter(Protocol):
    def find_by_id(self, reference_id: str) -> Sequence[CreativeReferenceRecord]:
        """Return exact matches for a Creative References record ID."""


class EditingTargetAdapter(Protocol):
    def find_by_id(self, target_id: str) -> Sequence[EditingTargetRecord]:
        """Return exact matches for an editing-target ID."""


class AssetEvidenceAdapter(Protocol):
    def inspect(self, asset_locator: str) -> AssetEvidence:
        """Report retrieval/inspection evidence without claiming tool delivery."""
