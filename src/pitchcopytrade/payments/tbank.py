from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx


class TBankPaymentError(ValueError):
    pass


@dataclass(slots=True)
class TBankCheckoutSession:
    payment_id: str
    order_id: str
    payment_url: str | None
    init_payload: dict[str, object]
    qr_payload: dict[str, object]


class TBankAcquiringClient:
    def __init__(
        self,
        *,
        terminal_key: str,
        password: str,
        base_url: str = "https://securepay.tinkoff.ru/v2",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.terminal_key = terminal_key
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def create_sbp_checkout(
        self,
        *,
        order_id: str,
        amount_rub: int,
        description: str,
        success_url: str | None = None,
        notification_url: str | None = None,
    ) -> TBankCheckoutSession:
        init_payload: dict[str, object] = {
            "TerminalKey": self.terminal_key,
            "Amount": amount_rub * 100,
            "OrderId": order_id,
            "Description": description,
        }
        if success_url:
            init_payload["SuccessURL"] = success_url
        if notification_url:
            init_payload["NotificationURL"] = notification_url

        init_result = await self._post("Init", init_payload)
        payment_id = str(init_result.get("PaymentId") or "")
        if not payment_id:
            raise TBankPaymentError("T-Bank Init response missing PaymentId")

        qr_result = await self._post(
            "GetQr",
            {
                "TerminalKey": self.terminal_key,
                "PaymentId": payment_id,
                "DataType": "PAYLOAD",
            },
        )
        return TBankCheckoutSession(
            payment_id=payment_id,
            order_id=order_id,
            payment_url=qr_result.get("Data"),
            init_payload=init_result,
            qr_payload=qr_result,
        )

    async def get_state(self, *, payment_id: str) -> dict[str, object]:
        return await self._post(
            "GetState",
            {
                "TerminalKey": self.terminal_key,
                "PaymentId": payment_id,
            },
        )

    async def _post(self, method: str, payload: dict[str, object]) -> dict[str, object]:
        signed_payload = dict(payload)
        signed_payload["Token"] = self._build_token(payload, password=self.password)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = await client.post(f"/{method}", json=signed_payload)
        response.raise_for_status()
        result = response.json()
        if not result.get("Success"):
            raise TBankPaymentError(str(result.get("Message") or result.get("Details") or f"{method} failed"))
        return result

    @staticmethod
    def _build_token(payload: dict[str, object], *, password: str) -> str:
        token_fields: dict[str, str] = {"Password": password}
        for key, value in payload.items():
            if key == "Token" or value is None or isinstance(value, (dict, list, tuple, set)):
                continue
            token_fields[key] = str(value)
        joined = "".join(token_fields[key] for key in sorted(token_fields))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()
