from reference_resolution_engine import (
    DeliveryReceipt,
    ExecutionDelivery,
    evaluate_delivery_receipt,
)


def test_exact_source_echo_confirms_delivery():
    result = evaluate_delivery_receipt(
        DeliveryReceipt(expected_source_id="source-123", echoed_source_id="source-123")
    )
    assert result is ExecutionDelivery.CONFIRMED


def test_missing_or_mismatched_echo_is_not_verifiable():
    assert evaluate_delivery_receipt(
        DeliveryReceipt(expected_source_id="source-123", echoed_source_id=None)
    ) is ExecutionDelivery.NOT_VERIFIABLE
    assert evaluate_delivery_receipt(
        DeliveryReceipt(expected_source_id="source-123", echoed_source_id="source-999")
    ) is ExecutionDelivery.NOT_VERIFIABLE


def test_untyped_receipt_cannot_confirm_delivery():
    assert evaluate_delivery_receipt({"source_id": "source-123"}) is ExecutionDelivery.NOT_VERIFIABLE
