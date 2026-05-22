from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .taxonomy import canonicalize_channel, canonicalize_payment_rail


class TransactionEvent(BaseModel):
    delay_ms: int = 0
    transaction_id: str
    timestamp: datetime
    account_id: str
    counterparty_id: str
    device_id: str
    merchant_id: str
    channel: str
    amount: float
    city: str
    country: str
    payment_format: str
    from_bank: str = ""
    to_bank: str = ""
    payment_currency: str = ""
    receiving_currency: str = ""
    geo_distance_km: float = 0.0
    dormant_days: int = 0
    scenario_note: str = ""
    custom_copilot_focus: str = ""

    @field_validator("payment_format", mode="before")
    @classmethod
    def normalize_payment_format(cls, value: str) -> str:
        return canonicalize_payment_rail(value)

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, value: str) -> str:
        return canonicalize_channel(value)


class PolicyPayload(BaseModel):
    fraud_weight: float = Field(default=0.34, ge=0.05, le=0.8)
    graph_weight: float = Field(default=0.36, ge=0.05, le=0.8)
    drift_weight: float = Field(default=0.30, ge=0.05, le=0.8)
    watch_threshold: float = Field(default=34.0, ge=15.0, le=70.0)
    fractured_threshold: float = Field(default=56.0, ge=25.0, le=85.0)
    escalated_threshold: float = Field(default=72.0, ge=40.0, le=95.0)
    graph_boost_multiplier: float = Field(default=1.15, ge=0.5, le=2.0)
    ring_fractured_threshold: float = Field(default=45.0, ge=10.0, le=95.0)
    repeat_cross_border_escalation_prior: float = Field(default=50.0, ge=10.0, le=100.0)
    repeat_cross_border_escalation_drift: float = Field(default=85.0, ge=40.0, le=100.0)
    repeat_cross_border_escalation_graph: float = Field(default=10.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_policy(self) -> "PolicyPayload":
        if not (self.watch_threshold < self.fractured_threshold < self.escalated_threshold):
            raise ValueError("Policy thresholds must increase from watch to fractured to escalated.")
        total_weight = self.fraud_weight + self.graph_weight + self.drift_weight
        if not 0.95 <= total_weight <= 1.05:
            raise ValueError("Fraud, graph, and drift weights must sum to approximately 1.0.")
        return self


class PolicyUpdate(BaseModel):
    actor: str = "operator"
    payload: PolicyPayload


class CaseActionRequest(BaseModel):
    action: Literal["approve", "review", "escalate_aml"]
    actor: str = "analyst"
    note: str = ""


class RazorpayDemoOrderRequest(BaseModel):
    amount: float = Field(default=45999.0, ge=1.0, le=500000.0)
    currency: str = "INR"
    payer_name: str = "PayEasy Test User"
    payer_email: str = "demo@payeasy.test"
    payer_contact: str = "9000090000"
    account_id: str = "ACC-PAYEASY-1024"
    counterparty_id: str = "PAYEASY_SETTLEMENT"
    device_id: str = "DEV-PAYEASY-17"
    merchant_id: str = "MER-PAYEASY"
    city: str = "Bengaluru"
    country: str = "IN"
    geo_distance_km: float = Field(default=420.0, ge=0.0, le=20000.0)
    dormant_days: int = Field(default=28, ge=0, le=3650)
    risk_preset: Literal["baseline", "dormant_device_reuse", "merchant_retry_pressure"] = "dormant_device_reuse"
    scenario_note: str = ""
    custom_copilot_focus: str = ""

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "INR").upper()


class RazorpayCheckoutVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ScenarioMetadata(BaseModel):
    id: str
    title: str
    subtitle: str
    description: str
    total_steps: int


class StateEnvelope(BaseModel):
    type: str = "state"
    payload: dict[str, Any]
