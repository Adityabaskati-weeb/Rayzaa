from __future__ import annotations

import asyncio
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import settings


TRUST_STATE_ORDER = {
    "Healthy": 0,
    "Watch": 1,
    "Fractured": 2,
    "Escalated": 3,
}


@dataclass(slots=True)
class AlertDispatchResult:
    ok: bool
    provider: str
    status: str
    message: str
    delivered_at: str
    error: str = ""


class TelegramAlertDispatcher:
    provider = "telegram"

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    def should_alert(self, trust_state: str) -> bool:
        minimum = TRUST_STATE_ORDER.get(settings.telegram_min_trust_state, TRUST_STATE_ORDER["Fractured"])
        current = TRUST_STATE_ORDER.get(trust_state, TRUST_STATE_ORDER["Healthy"])
        return current >= minimum

    def integration_status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "minimumTrustState": settings.telegram_min_trust_state,
            "provider": self.provider,
        }

    @staticmethod
    def _top_evidence_lines(reasons: list[str]) -> str:
        top = [reason.strip().rstrip(".") for reason in reasons[:2] if reason]
        return "; ".join(top)

    def build_message(
        self,
        *,
        case_id: str,
        transaction_id: str,
        trust_state: str,
        decision: str,
        fused_score: float,
        reasons: list[str],
        timestamp: datetime,
        replay_available: bool,
    ) -> str:
        summary = self._top_evidence_lines(reasons)
        replay_line = "Replay: available in Trust Replay." if replay_available else "Replay: pending."
        return "\n".join(
            [
                "Rayzaa operational alert",
                f"Case {case_id} moved to {trust_state.upper()}.",
                f"Transaction: {transaction_id}",
                f"Decision: {decision} | Fused score: {fused_score:.0f}",
                f"Evidence: {summary or 'Awaiting detailed evidence summary.'}",
                replay_line,
                f"Time: {timestamp.isoformat()}",
            ]
        )

    async def dispatch(self, message: str) -> AlertDispatchResult:
        delivered_at = datetime.utcnow().isoformat()
        if not self.is_configured():
            return AlertDispatchResult(
                ok=False,
                provider=self.provider,
                status="skipped",
                message=message,
                delivered_at=delivered_at,
                error="Telegram is not configured.",
            )

        payload: dict[str, Any] = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        if settings.telegram_message_thread_id:
            payload["message_thread_id"] = settings.telegram_message_thread_id

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        def send_request() -> dict[str, Any]:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            response_payload = await asyncio.to_thread(send_request)
        except Exception as exc:  # pragma: no cover - network failures are environment-dependent
            return AlertDispatchResult(
                ok=False,
                provider=self.provider,
                status="failed",
                message=message,
                delivered_at=delivered_at,
                error=str(exc),
            )

        if not response_payload.get("ok"):
            return AlertDispatchResult(
                ok=False,
                provider=self.provider,
                status="failed",
                message=message,
                delivered_at=delivered_at,
                error=str(response_payload),
            )

        return AlertDispatchResult(
            ok=True,
            provider=self.provider,
            status="sent",
            message=message,
            delivered_at=delivered_at,
        )
