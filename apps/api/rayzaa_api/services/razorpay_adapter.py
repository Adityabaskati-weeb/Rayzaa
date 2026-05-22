from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..config import settings
from ..schemas import RazorpayDemoOrderRequest, TransactionEvent


PRESET_OVERRIDES: dict[str, dict[str, Any]] = {
    "baseline": {
        "account_id": "ACC-PAYEASY-1024",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "city": "Bengaluru",
        "country": "IN",
        "from_bank": "bank_of_india",
        "to_bank": "hdfc_bank",
        "geo_distance_km": 8.0,
        "dormant_days": 2,
        "scenario_note": "PayEasy baseline checkout remains within the recent account rhythm.",
        "custom_copilot_focus": "Confirm that live checkout remains within baseline expectations",
    },
    "dormant_device_reuse": {
        "account_id": "ACC-PAYEASY-3301",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "city": "Delhi",
        "country": "IN",
        "from_bank": "icici_bank",
        "to_bank": "hdfc_bank",
        "geo_distance_km": 420.0,
        "dormant_days": 28,
        "scenario_note": "PayEasy checkout follows dormant reactivation and shared-device context.",
        "custom_copilot_focus": "Determine whether dormant reactivation and shared-device pressure justify manual review",
    },
    "merchant_retry_pressure": {
        "account_id": "ACC-PAYEASY-8822",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "city": "Mumbai",
        "country": "IN",
        "from_bank": "yes_bank",
        "to_bank": "hdfc_bank",
        "geo_distance_km": 210.0,
        "dormant_days": 11,
        "scenario_note": "PayEasy checkout lands during elevated merchant burst and retry pressure.",
        "custom_copilot_focus": "Compare merchant concentration against recent rapid retry activity",
    },
}


class RazorpayAdapter:
    provider = "razorpay"
    orders_api_url = "https://api.razorpay.com/v1/orders"

    def is_configured(self) -> bool:
        return bool(settings.razorpay_key_id and settings.razorpay_key_secret)

    def is_webhook_configured(self) -> bool:
        return bool(settings.razorpay_webhook_secret)

    def is_test_mode(self) -> bool:
        return settings.razorpay_key_id.startswith("rzp_test_")

    def integration_status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "webhookConfigured": self.is_webhook_configured(),
            "testMode": self.is_test_mode(),
            "provider": self.provider,
            "accountName": settings.razorpay_account_name,
        }

    def _auth_header(self) -> str:
        token = f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(token).decode("utf-8")

    def _build_notes(self, request: RazorpayDemoOrderRequest) -> dict[str, str]:
        preset = PRESET_OVERRIDES.get(request.risk_preset, {})
        scenario_note = request.scenario_note or preset.get("scenario_note", "")
        custom_focus = request.custom_copilot_focus or preset.get("custom_copilot_focus", "")
        geo_distance_km = request.geo_distance_km if request.geo_distance_km != 420.0 else preset.get("geo_distance_km", request.geo_distance_km)
        dormant_days = request.dormant_days if request.dormant_days != 28 else preset.get("dormant_days", request.dormant_days)
        return {
            "account_id": str(preset.get("account_id") or request.account_id),
            "counterparty_id": request.counterparty_id or settings.payeasy_counterparty_id,
            "device_id": str(preset.get("device_id") or request.device_id),
            "merchant_id": str(preset.get("merchant_id") or request.merchant_id or settings.payeasy_merchant_id),
            "city": str(preset.get("city") or request.city),
            "country": str(preset.get("country") or request.country),
            "from_bank": str(preset.get("from_bank") or ""),
            "to_bank": str(preset.get("to_bank") or ""),
            "receiving_currency": request.currency,
            "geo_distance_km": f"{geo_distance_km:.2f}",
            "dormant_days": str(dormant_days),
            "scenario_note": scenario_note,
            "custom_copilot_focus": custom_focus,
            "payment_format_hint": "upi",
            "risk_preset": request.risk_preset,
        }

    async def create_order(self, request: RazorpayDemoOrderRequest) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Razorpay integration is not configured.")

        notes = self._build_notes(request)
        payload = {
            "amount": int(round(request.amount * 100)),
            "currency": request.currency,
            "receipt": f"rayzaa-{uuid4().hex[:10]}",
            "notes": notes,
        }
        body = json.dumps(payload).encode("utf-8")
        api_request = urllib.request.Request(
            self.orders_api_url,
            data=body,
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def send_request() -> dict[str, Any]:
            with urllib.request.urlopen(api_request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))

        response_payload = await asyncio.to_thread(send_request)
        return {
            "provider": self.provider,
            "keyId": settings.razorpay_key_id,
            "order": response_payload,
            "checkout": {
                "name": settings.razorpay_account_name,
                "description": "PayEasy test checkout routed into Rayzaa",
                "prefill": {
                    "name": request.payer_name,
                    "email": request.payer_email,
                    "contact": request.payer_contact,
                },
                "notes": notes,
            },
        }

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        if not self.is_configured():
            return False
        body = f"{order_id}|{payment_id}".encode("utf-8")
        digest = hmac.new(settings.razorpay_key_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> bool:
        if not self.is_webhook_configured():
            return False
        digest = hmac.new(settings.razorpay_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    def normalize_webhook(self, payload: dict[str, Any], *, event_id: str) -> dict[str, Any]:
        payment_entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
        order_entity = ((payload.get("payload") or {}).get("order") or {}).get("entity") or {}
        notes = {}
        notes.update(order_entity.get("notes") or {})
        notes.update(payment_entity.get("notes") or {})

        created_at = payment_entity.get("created_at") or payload.get("created_at")
        timestamp = datetime.fromtimestamp(created_at, tz=timezone.utc) if created_at else datetime.now(timezone.utc)
        amount = float(payment_entity.get("amount", 0.0)) / 100.0
        currency = str(payment_entity.get("currency") or "INR").upper()
        method = str(payment_entity.get("method") or notes.get("payment_format_hint") or "upi")
        payer_contact = payment_entity.get("contact") or payment_entity.get("email") or payment_entity.get("id") or "payer"
        account_id = str(notes.get("account_id") or f"ACC-{payer_contact}")
        counterparty_id = str(notes.get("counterparty_id") or settings.payeasy_counterparty_id)
        device_id = str(notes.get("device_id") or f"DEV-{payer_contact}")
        merchant_id = str(notes.get("merchant_id") or settings.payeasy_merchant_id)

        event_payload = TransactionEvent(
            transaction_id=str(payment_entity.get("id") or event_id),
            timestamp=timestamp,
            account_id=account_id,
            counterparty_id=counterparty_id,
            device_id=device_id,
            merchant_id=merchant_id,
            channel=method,
            amount=amount,
            city=str(notes.get("city") or "Bengaluru"),
            country=str(notes.get("country") or "IN"),
            payment_format=str(notes.get("payment_format_hint") or method),
            from_bank=str(notes.get("from_bank") or ""),
            to_bank=str(notes.get("to_bank") or ""),
            payment_currency=currency,
            receiving_currency=str(notes.get("receiving_currency") or currency),
            geo_distance_km=float(notes.get("geo_distance_km") or 0.0),
            dormant_days=int(notes.get("dormant_days") or 0),
            scenario_note=str(notes.get("scenario_note") or "PayEasy payment reached Rayzaa through Razorpay test mode."),
            custom_copilot_focus=str(notes.get("custom_copilot_focus") or ""),
        )

        normalized = event_payload.model_dump()
        normalized["integration"] = {
            "provider": self.provider,
            "event": payload.get("event", ""),
            "eventId": event_id,
            "orderId": payment_entity.get("order_id") or order_entity.get("id"),
            "paymentId": payment_entity.get("id"),
        }
        return normalized
