from __future__ import annotations

from typing import Any


class InvestigationCopilot:
    def summarize(
        self,
        *,
        account_id: str,
        trust_state: str,
        fraud_score: float,
        graph_score: float,
        drift_score: float,
        reasons: list[str],
        focus: str = "",
    ) -> tuple[str, list[str]]:
        opening = (
            f"Account {account_id} is currently in {trust_state.lower()} trust state. "
            f"Fraud pressure is led by a transaction score of {fraud_score:.0f}, graph pressure of {graph_score:.0f}, "
            f"and behavioral drift of {drift_score:.0f}."
        )
        if focus:
            opening += f" Operator focus: {focus}."

        reason_line = " Key evidence: " + "; ".join(reasons[:3]) + "." if reasons else ""
        summary = opening + reason_line

        actions = [
            "Open Trust Replay to identify the first trust fracture transition.",
            "Expand 2-hop graph context around the active account and inspect shared device pressure.",
            "Escalate to the Trust Escalation Queue if the same device or counterparty appears across multiple accounts.",
        ]
        if graph_score >= 65:
            actions[1] = "Inspect the ring path in the Trust Memory Graph and confirm whether funds loop back to the origin."
        if drift_score >= 55:
            actions[2] = "Flag the case for manual verification because behavioral drift now exceeds the policy comfort band."
        return summary, actions
