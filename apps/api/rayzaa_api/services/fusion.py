from __future__ import annotations

from typing import Any

from ..schemas import PolicyPayload


class SignalFusionEngine:
    def __init__(self, payload: PolicyPayload | None = None) -> None:
        self.policy = payload or PolicyPayload()

    def update_policy(self, payload: PolicyPayload) -> None:
        self.policy = payload

    def current_policy(self) -> dict[str, Any]:
        return self.policy.model_dump()

    def fuse(
        self,
        *,
        fraud_score: float,
        graph_score: float,
        drift_score: float,
        prior_account_score: float = 0.0,
        ring_pressure: float = 0.0,
        is_cross_currency: bool = False,
    ) -> dict[str, Any]:
        adjusted_graph = min(100.0, graph_score * self.policy.graph_boost_multiplier)
        fused = (
            fraud_score * self.policy.fraud_weight
            + adjusted_graph * self.policy.graph_weight
            + drift_score * self.policy.drift_weight
        )
        fused = round(min(100.0, fused), 2)
        policy_hits: list[str] = []

        if fused >= self.policy.escalated_threshold:
            trust_state = "Escalated"
            decision = "escalate_aml"
        elif fused >= self.policy.fractured_threshold:
            trust_state = "Fractured"
            decision = "review"
        elif fused >= self.policy.watch_threshold:
            trust_state = "Watch"
            decision = "review"
        else:
            trust_state = "Healthy"
            decision = "approve"

        if trust_state == "Watch" and ring_pressure >= self.policy.ring_fractured_threshold:
            trust_state = "Fractured"
            decision = "review"
            policy_hits.append("ring_fracture_guardrail")

        if (
            trust_state in {"Watch", "Fractured"}
            and is_cross_currency
            and prior_account_score >= self.policy.repeat_cross_border_escalation_prior
            and drift_score >= self.policy.repeat_cross_border_escalation_drift
            and graph_score >= self.policy.repeat_cross_border_escalation_graph
        ):
            trust_state = "Escalated"
            decision = "escalate_aml"
            policy_hits.append("repeat_cross_border_escalation")

        return {
            "fused_score": fused,
            "trust_state": trust_state,
            "decision": decision,
            "policy_hits": policy_hits,
        }
