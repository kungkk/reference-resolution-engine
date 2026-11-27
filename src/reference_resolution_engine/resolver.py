"""Deterministic source resolution with separate asset evidence."""

from __future__ import annotations

from .models import (
    AssetEvidence,
    CreativeReferenceRecord,
    DeliveryReceipt,
    EditingTargetRecord,
    ExecutionDelivery,
    IdentitySourceRecord,
    Operation,
    RecordStatus,
    ResolutionBundle,
    ResolutionRequest,
    SourceResolution,
    SourceRole,
)
from .ports import (
    AssetEvidenceAdapter,
    CreativeReferenceAdapter,
    EditingTargetAdapter,
    IdentitySourceAdapter,
)


class ReferenceResolutionEngine:
    """Resolve source records without executing image operations."""

    def __init__(
        self,
        *,
        identity_adapter: IdentitySourceAdapter,
        creative_reference_adapter: CreativeReferenceAdapter,
        editing_target_adapter: EditingTargetAdapter,
        asset_evidence_adapter: AssetEvidenceAdapter | None = None,
    ) -> None:
        self._identity_adapter = identity_adapter
        self._creative_reference_adapter = creative_reference_adapter
        self._editing_target_adapter = editing_target_adapter
        self._asset_evidence_adapter = asset_evidence_adapter

    def resolve(self, request: ResolutionRequest) -> ResolutionBundle:
        identity = self.resolve_identity(request.identity_alias)
        creative_reference = self.resolve_creative_reference(
            request.creative_reference_id
        )
        editing_target = None
        if request.operation is Operation.EDIT:
            # ResolutionRequest validates that this selector is present.
            assert request.editing_target_id is not None
            editing_target = self.resolve_editing_target(request.editing_target_id)

        return ResolutionBundle(
            identity=identity,
            creative_reference=creative_reference,
            editing_target=editing_target,
        )

    def resolve_identity(self, alias: str) -> SourceResolution:
        records = tuple(self._identity_adapter.find_by_alias(alias))
        primary_records = tuple(
            record for record in records if record.is_primary_original
        )

        if not primary_records:
            return self._unresolved(
                SourceRole.IDENTITY_ORIGINAL,
                alias,
                "No primary original identity photograph is registered for this alias.",
            )
        if len(primary_records) > 1:
            return self._ambiguous(
                SourceRole.IDENTITY_ORIGINAL,
                alias,
                "More than one primary original identity photograph matches this alias.",
            )

        primary: IdentitySourceRecord = primary_records[0]
        evidence = self._asset_evidence(primary.asset_locator)
        supporting_ids = tuple(
            record.source_id for record in records if record.source_id != primary.source_id
        )
        return SourceResolution(
            role=SourceRole.IDENTITY_ORIGINAL,
            selector=alias,
            record_status=RecordStatus.RESOLVED,
            source_id=primary.source_id,
            asset_locator=primary.asset_locator,
            asset_retrieval_status=evidence.retrieval_status,
            visual_evidence=evidence.visual_evidence,
            execution_delivery=ExecutionDelivery.NOT_VERIFIABLE,
            provenance_status=primary.provenance_status,
            supporting_source_ids=supporting_ids,
            message="Primary original identity photograph resolved.",
        )

    def resolve_creative_reference(self, reference_id: str) -> SourceResolution:
        records = tuple(self._creative_reference_adapter.find_by_id(reference_id))
        if not records:
            return self._unresolved(
                SourceRole.CREATIVE_REFERENCE,
                reference_id,
                "Creative reference ID was not found.",
            )
        if len(records) > 1:
            return self._ambiguous(
                SourceRole.CREATIVE_REFERENCE,
                reference_id,
                "More than one creative-reference record matches this ID.",
            )

        record: CreativeReferenceRecord = records[0]
        evidence = self._asset_evidence(record.asset_locator)
        return SourceResolution(
            role=SourceRole.CREATIVE_REFERENCE,
            selector=reference_id,
            record_status=RecordStatus.RESOLVED,
            source_id=record.reference_id,
            asset_locator=record.asset_locator,
            asset_retrieval_status=evidence.retrieval_status,
            visual_evidence=evidence.visual_evidence,
            execution_delivery=ExecutionDelivery.NOT_VERIFIABLE,
            rights_status=record.rights_status,
            review_status=record.review_status,
            transfer_scope=record.transfer_scope,
            transfer_strength=record.transfer_strength,
            message="Single primary creative-reference record resolved.",
        )

    def resolve_editing_target(self, target_id: str) -> SourceResolution:
        records = tuple(self._editing_target_adapter.find_by_id(target_id))
        if not records:
            return self._unresolved(
                SourceRole.EDITING_TARGET,
                target_id,
                "Editing target ID was not found.",
            )
        if len(records) > 1:
            return self._ambiguous(
                SourceRole.EDITING_TARGET,
                target_id,
                "More than one editing-target record matches this ID.",
            )

        record: EditingTargetRecord = records[0]
        evidence = self._asset_evidence(record.asset_locator)
        return SourceResolution(
            role=SourceRole.EDITING_TARGET,
            selector=target_id,
            record_status=RecordStatus.RESOLVED,
            source_id=record.target_id,
            asset_locator=record.asset_locator,
            asset_retrieval_status=evidence.retrieval_status,
            visual_evidence=evidence.visual_evidence,
            execution_delivery=ExecutionDelivery.NOT_VERIFIABLE,
            message="Explicit editing target resolved.",
        )

    def _asset_evidence(self, asset_locator: str | None) -> AssetEvidence:
        if not asset_locator or self._asset_evidence_adapter is None:
            return AssetEvidence()
        return self._asset_evidence_adapter.inspect(asset_locator)

    @staticmethod
    def _unresolved(role: SourceRole, selector: str, message: str) -> SourceResolution:
        return SourceResolution(
            role=role,
            selector=selector,
            record_status=RecordStatus.MISSING,
            message=message,
        )

    @staticmethod
    def _ambiguous(role: SourceRole, selector: str, message: str) -> SourceResolution:
        return SourceResolution(
            role=role,
            selector=selector,
            record_status=RecordStatus.AMBIGUOUS,
            message=message,
        )


def evaluate_delivery_receipt(receipt: object) -> ExecutionDelivery:
    """Return confirmed only for an explicit, exact source-ID echo."""
    if not isinstance(receipt, DeliveryReceipt):
        return ExecutionDelivery.NOT_VERIFIABLE
    if (
        receipt.expected_source_id
        and receipt.echoed_source_id
        and receipt.expected_source_id == receipt.echoed_source_id
    ):
        return ExecutionDelivery.CONFIRMED
    return ExecutionDelivery.NOT_VERIFIABLE
