"""Typed contracts for source resolution and evidence tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RecordStatus(StrEnum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


class AssetRetrievalStatus(StrEnum):
    ACCESSIBLE = "accessible"
    INACCESSIBLE = "inaccessible"
    UNVERIFIED = "unverified"


class VisualEvidence(StrEnum):
    IMAGE_INSPECTED = "image_inspected"
    METADATA_ONLY = "metadata_only"
    RECORD_ONLY = "record_only"
    NONE = "none"


class ExecutionDelivery(StrEnum):
    CONFIRMED = "confirmed"
    NOT_VERIFIABLE = "not_verifiable"


class RightsStatus(StrEnum):
    UNKNOWN = "unknown"
    PERSONAL_ONLY = "personal_only"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    PERMISSION_GRANTED = "permission_granted"
    DENIED = "denied"


class SourceRole(StrEnum):
    IDENTITY_ORIGINAL = "identity_original"
    CREATIVE_REFERENCE = "creative_reference"
    EDITING_TARGET = "editing_target"


class Operation(StrEnum):
    PREVIEW = "preview"
    GENERATE = "generate"
    EDIT = "edit"


@dataclass(frozen=True, slots=True)
class IdentitySourceRecord:
    """One image record associated with an identity alias."""

    source_id: str
    alias: str
    asset_locator: str | None
    is_primary_original: bool = True
    provenance_status: str = "unverified"


@dataclass(frozen=True, slots=True)
class CreativeReferenceRecord:
    """A single Creative References database record."""

    reference_id: str
    asset_locator: str | None
    review_status: str
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    transfer_scope: tuple[str, ...] = ()
    transfer_strength: int | None = None


@dataclass(frozen=True, slots=True)
class EditingTargetRecord:
    """The explicit image being modified by an edit operation."""

    target_id: str
    asset_locator: str | None


@dataclass(frozen=True, slots=True)
class AssetEvidence:
    """Evidence returned by an asset retrieval/inspection adapter."""

    retrieval_status: AssetRetrievalStatus = AssetRetrievalStatus.UNVERIFIED
    visual_evidence: VisualEvidence = VisualEvidence.NONE


@dataclass(frozen=True, slots=True)
class SourceResolution:
    """Resolution result with independent record and asset evidence."""

    role: SourceRole
    selector: str
    record_status: RecordStatus
    source_id: str | None = None
    asset_locator: str | None = None
    asset_retrieval_status: AssetRetrievalStatus = AssetRetrievalStatus.UNVERIFIED
    visual_evidence: VisualEvidence = VisualEvidence.NONE
    execution_delivery: ExecutionDelivery = ExecutionDelivery.NOT_VERIFIABLE
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    provenance_status: str = "unverified"
    supporting_source_ids: tuple[str, ...] = ()
    message: str = ""

    @property
    def record_resolved(self) -> bool:
        return self.record_status is RecordStatus.RESOLVED


@dataclass(frozen=True, slots=True)
class ResolutionRequest:
    """Normalized input required for one resolution operation."""

    identity_alias: str
    creative_reference_id: str
    operation: Operation = Operation.PREVIEW
    editing_target_id: str | None = None

    def __post_init__(self) -> None:
        if not self.identity_alias.strip():
            raise ValueError("identity_alias must not be empty")
        if not self.creative_reference_id.strip():
            raise ValueError("exactly one creative_reference_id is required")
        if self.operation is Operation.EDIT and not (
            self.editing_target_id and self.editing_target_id.strip()
        ):
            raise ValueError("editing_target_id is required for edit operations")


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Explicit source echo returned by an execution tool.

    A receipt is valid only when the tool explicitly echoes the exact source ID
    expected by the caller. Merely passing a locator or receiving a success
    response without a source echo is not delivery evidence.
    """

    expected_source_id: str
    echoed_source_id: str | None


@dataclass(frozen=True, slots=True)
class ResolutionBundle:
    identity: SourceResolution
    creative_reference: SourceResolution
    editing_target: SourceResolution | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
