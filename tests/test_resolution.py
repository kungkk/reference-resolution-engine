from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from reference_resolution_engine import (
    AssetEvidence,
    AssetRetrievalStatus,
    CreativeReferenceRecord,
    EditingTargetRecord,
    IdentitySourceRecord,
    Operation,
    RecordStatus,
    ReferenceResolutionEngine,
    ResolutionRequest,
    RightsStatus,
    VisualEvidence,
)


@dataclass
class FakeIdentityAdapter:
    records: list[IdentitySourceRecord] = field(default_factory=list)

    def find_by_alias(self, alias: str):
        return [record for record in self.records if record.alias == alias]


@dataclass
class FakeCreativeAdapter:
    records: list[CreativeReferenceRecord] = field(default_factory=list)

    def find_by_id(self, reference_id: str):
        return [record for record in self.records if record.reference_id == reference_id]


@dataclass
class FakeTargetAdapter:
    records: list[EditingTargetRecord] = field(default_factory=list)

    def find_by_id(self, target_id: str):
        return [record for record in self.records if record.target_id == target_id]


@dataclass
class FakeAssetAdapter:
    evidence_by_locator: dict[str, AssetEvidence] = field(default_factory=dict)

    def inspect(self, asset_locator: str):
        return self.evidence_by_locator.get(asset_locator, AssetEvidence())


def build_engine(
    identity_records=(),
    creative_records=(),
    target_records=(),
    asset_evidence=None,
):
    return ReferenceResolutionEngine(
        identity_adapter=FakeIdentityAdapter(list(identity_records)),
        creative_reference_adapter=FakeCreativeAdapter(list(creative_records)),
        editing_target_adapter=FakeTargetAdapter(list(target_records)),
        asset_evidence_adapter=FakeAssetAdapter(asset_evidence or {}),
    )


def test_identity_alias_missing_is_reported_as_missing():
    result = build_engine().resolve_identity("@Charlotte")
    assert result.record_status is RecordStatus.MISSING
    assert result.source_id is None


def test_supporting_identity_photo_cannot_replace_primary_original():
    records = [
        IdentitySourceRecord(
            "support-1", "@Charlotte", "asset://support", is_primary_original=False
        )
    ]
    result = build_engine(identity_records=records).resolve_identity("@Charlotte")
    assert result.record_status is RecordStatus.MISSING
    assert result.source_id is None


def test_multiple_primary_identity_photos_are_ambiguous():
    records = [
        IdentitySourceRecord("id-1", "@Charlotte", "asset://one"),
        IdentitySourceRecord("id-2", "@Charlotte", "asset://two"),
    ]
    result = build_engine(identity_records=records).resolve_identity("@Charlotte")
    assert result.record_status is RecordStatus.AMBIGUOUS
    assert result.source_id is None


def test_one_primary_identity_and_supporting_photos_resolves_primary_only():
    records = [
        IdentitySourceRecord("original-1", "@Charlotte", "asset://original"),
        IdentitySourceRecord(
            "support-1", "@Charlotte", "asset://support", is_primary_original=False
        ),
    ]
    result = build_engine(identity_records=records).resolve_identity("@Charlotte")
    assert result.record_status is RecordStatus.RESOLVED
    assert result.source_id == "original-1"
    assert result.supporting_source_ids == ("support-1",)


def test_record_resolution_does_not_imply_asset_accessibility():
    records = [IdentitySourceRecord("original-1", "@Charlotte", "asset://missing")]
    evidence = {
        "asset://missing": AssetEvidence(
            retrieval_status=AssetRetrievalStatus.INACCESSIBLE,
            visual_evidence=VisualEvidence.RECORD_ONLY,
        )
    }
    result = build_engine(
        identity_records=records, asset_evidence=evidence
    ).resolve_identity("@Charlotte")
    assert result.record_status is RecordStatus.RESOLVED
    assert result.asset_retrieval_status is AssetRetrievalStatus.INACCESSIBLE
    assert result.execution_delivery.value == "not_verifiable"


def test_creative_reference_missing_is_reported():
    result = build_engine().resolve_creative_reference("CR-404")
    assert result.record_status is RecordStatus.MISSING


def test_duplicate_creative_reference_id_is_ambiguous():
    records = [
        CreativeReferenceRecord("CR-1", "asset://one", "Approved"),
        CreativeReferenceRecord("CR-1", "asset://two", "Approved"),
    ]
    result = build_engine(creative_records=records).resolve_creative_reference("CR-1")
    assert result.record_status is RecordStatus.AMBIGUOUS


def test_creative_reference_preserves_rights_and_transfer_metadata():
    records = [
        CreativeReferenceRecord(
            "CR-1",
            "asset://creative",
            "Approved",
            rights_status=RightsStatus.PERSONAL_ONLY,
            transfer_scope=("Hairstyle", "Lighting"),
            transfer_strength=75,
        )
    ]
    result = build_engine(creative_records=records).resolve_creative_reference("CR-1")
    assert result.record_status is RecordStatus.RESOLVED
    assert result.rights_status is RightsStatus.PERSONAL_ONLY
    assert result.review_status == "Approved"
    assert result.transfer_scope == ("Hairstyle", "Lighting")
    assert result.transfer_strength == 75


def test_edit_operation_requires_explicit_target():
    with pytest.raises(ValueError, match="editing_target_id is required"):
        ResolutionRequest(
            identity_alias="@Charlotte",
            creative_reference_id="CR-1",
            operation=Operation.EDIT,
        )


def test_request_rejects_non_enum_operation_value():
    with pytest.raises(TypeError, match="operation must be an Operation"):
        ResolutionRequest(
            identity_alias="@Charlotte",
            creative_reference_id="CR-1",
            operation="edit",
        )


def test_edit_target_missing_is_reported_in_bundle():
    engine = build_engine(
        identity_records=[IdentitySourceRecord("id-1", "@Charlotte", "asset://id")],
        creative_records=[CreativeReferenceRecord("CR-1", "asset://creative", "Approved")],
    )
    bundle = engine.resolve(
        ResolutionRequest(
            identity_alias="@Charlotte",
            creative_reference_id="CR-1",
            operation=Operation.EDIT,
            editing_target_id="target-missing",
        )
    )
    assert bundle.editing_target is not None
    assert bundle.editing_target.record_status is RecordStatus.MISSING


def test_duplicate_editing_target_is_ambiguous():
    engine = build_engine(
        target_records=[
            EditingTargetRecord("target-1", "asset://target-a"),
            EditingTargetRecord("target-1", "asset://target-b"),
        ]
    )
    result = engine.resolve_editing_target("target-1")
    assert result.record_status is RecordStatus.AMBIGUOUS
