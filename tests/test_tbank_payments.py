from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.payments.tbank import TBankAcquiringClient


def test_tbank_token_uses_sorted_root_fields_and_password() -> None:
    token = TBankAcquiringClient._build_token(
        {
            "TerminalKey": "terminal",
            "Amount": 490000,
            "OrderId": "ORDER-1",
            "Description": "Momentum RU Monthly",
            "DATA": {"nested": "ignored"},
        },
        password="password",
    )

    assert len(token) == 64
    assert token == TBankAcquiringClient._build_token(
        {
            "OrderId": "ORDER-1",
            "Description": "Momentum RU Monthly",
            "Amount": 490000,
            "TerminalKey": "terminal",
        },
        password="password",
    )


@pytest.mark.asyncio
async def test_tbank_create_sbp_checkout_calls_init_and_get_qr(monkeypatch) -> None:
    client = TBankAcquiringClient(terminal_key="terminal", password="password", base_url="https://example.test")
    post_mock = AsyncMock(
        side_effect=[
            {"Success": True, "PaymentId": 777, "Status": "NEW"},
            {"Success": True, "Data": "https://pay.example/qr/777"},
        ]
    )
    monkeypatch.setattr(client, "_post", post_mock)

    result = await client.create_sbp_checkout(
        order_id="ORDER-1",
        amount_rub=4900,
        description="Momentum RU Monthly",
        success_url="https://pct.test.ptfin.ru/checkout/product-1",
    )

    assert result.payment_id == "777"
    assert result.payment_url == "https://pay.example/qr/777"
    assert post_mock.await_count == 2
