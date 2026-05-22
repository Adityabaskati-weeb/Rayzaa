from __future__ import annotations

import asyncio
import copy
from collections import deque
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .broadcast import BroadcastHub
from .config import settings
from .database import get_db, init_db, session_scope
from .models import CaseEventRecord, CaseRecord, PolicyVersionRecord, TransactionRecord
from .scenarios import load_scenarios, scenario_metadata
from .schemas import (
    CaseActionRequest,
    PolicyPayload,
    PolicyUpdate,
    RazorpayCheckoutVerificationRequest,
    RazorpayDemoOrderRequest,
    TransactionEvent,
)
from .services.alerts import TelegramAlertDispatcher
from .services.copilot import InvestigationCopilot
from .services.fraud import FraudScorer
from .services.fusion import SignalFusionEngine
from .services.graph import TrustMemoryGraph
from .services.razorpay_adapter import RazorpayAdapter
from .services.rolling_state import MemoryRollingState


class Runtime:
    def __init__(self) -> None:
        self.broadcast = BroadcastHub()
        self.rolling = MemoryRollingState()
        self.graph = TrustMemoryGraph()
        self.state_lock = asyncio.Lock()
        self._fraud: FraudScorer | None = None
        self.fusion = SignalFusionEngine()
        self.copilot = InvestigationCopilot()
        self.alerts = TelegramAlertDispatcher()
        self.razorpay = RazorpayAdapter()
        self.signal_rail: deque[dict[str, Any]] = deque(maxlen=14)
        self.scenarios = load_scenarios(settings.fixture_dir)
        self.current_scenario_id: str | None = None
        self.replay_session_id: str | None = None
        self.current_step: int = 0
        self.total_steps: int = 0
        self.is_running: bool = False
        self.replay_steps: list[dict[str, Any]] = []
        self.live_runtime_snapshot: dict[str, Any] | None = None
        self.focus_case_id: str | None = None
        self.focus_account_id: str | None = None
        self.live_focus_case_id: str | None = None
        self.live_focus_account_id: str | None = None
        self.runner: asyncio.Task | None = None
        self.latest_alert: dict[str, Any] | None = None
        self.latest_state: dict[str, Any] = {
            "booting": False,
            "signalRail": [],
            "graph": {"nodes": [], "edges": []},
            "focusCase": None,
            "queue": [],
            "replay": {"activeIndex": 0, "steps": []},
            "policy": self.fusion.current_policy(),
            "operations": {
                "integrationStatus": {
                    "razorpay": self.razorpay.integration_status(),
                    "telegram": self.alerts.integration_status(),
                },
                "latestAlert": None,
                "demoFlow": {
                    "locked": settings.demo_flow_lock,
                    "livePaymentSeen": False,
                    "requiredOrder": ["seed baseline", "live payment", "trust transition", "queue", "telegram", "replay"],
                },
            },
            "system": {
                "status": "idle",
                "scenarioId": None,
                "activeStep": 0,
                "totalSteps": 0,
                "focusAccountId": None,
            },
            "scenarios": [item.model_dump() for item in scenario_metadata(self.scenarios)],
        }

    @property
    def fraud(self) -> FraudScorer:
        if self._fraud is None:
            self._fraud = FraudScorer()
        return self._fraud

    def hydrate_policy(self) -> None:
        with session_scope() as db:
            record = db.scalar(select(PolicyVersionRecord).order_by(PolicyVersionRecord.id.desc()))
            if record:
                self.fusion.update_policy(PolicyPayload(**record.payload))
            else:
                db.add(PolicyVersionRecord(version_name="policy-v1", payload=self.fusion.current_policy()))

    def update_state(self, payload: dict[str, Any]) -> None:
        self.latest_state = payload


runtime = Runtime()
LIVE_SCENARIO_ID = "live"
SEED_TRANSACTION_PREFIX = "seed_"

app = FastAPI(title=settings.project_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timing_checkpoint(label: str, start: float, **details: Any) -> float:
    elapsed_ms = (perf_counter() - start) * 1000
    detail_text = ""
    if details:
        detail_text = " " + " ".join(f"{key}={value}" for key, value in details.items())
    print(f"[timing] {label} elapsed_ms={elapsed_ms:.2f}{detail_text}")
    return perf_counter()


def _source_tag(scenario_id: str) -> str:
    return "live" if scenario_id == "live" else "replay"


def _integration_status() -> dict[str, Any]:
    return {
        "razorpay": runtime.razorpay.integration_status(),
        "telegram": runtime.alerts.integration_status(),
    }


def _severity_rank(trust_state: str, status: str) -> int:
    if status == "escalated" or trust_state == "Escalated":
        return 4
    if trust_state == "Fractured":
        return 3
    if status == "review" or trust_state == "Watch":
        return 2
    return 1


def _base_case_id(account_id: str) -> str:
    return f"case_{account_id.lower().replace('-', '_')}"


def _replay_case_id(replay_session_id: str, account_id: str) -> str:
    return f"replay_{replay_session_id}_{_base_case_id(account_id)}"


def _is_live_case(record: CaseRecord) -> bool:
    return record.scenario_id == LIVE_SCENARIO_ID


def _is_baseline_seed_transaction_id(transaction_id: str) -> bool:
    return transaction_id.startswith(SEED_TRANSACTION_PREFIX)


def _has_live_transactions(db: Session) -> bool:
    return db.scalar(select(TransactionRecord.id).where(TransactionRecord.scenario_id == LIVE_SCENARIO_ID).limit(1)) is not None


def _has_demo_live_payment(db: Session) -> bool:
    return (
        db.scalar(
            select(TransactionRecord.id)
            .where(
                TransactionRecord.scenario_id == LIVE_SCENARIO_ID,
                ~TransactionRecord.transaction_id.like(f"{SEED_TRANSACTION_PREFIX}%"),
            )
            .limit(1)
        )
        is not None
    )


def _evidence_row(*, evidence_id: str, label: str, detail: str, source: str) -> dict[str, str]:
    return {
        "id": evidence_id,
        "label": label,
        "detail": detail,
        "source": source,
    }


def _build_model_evidence(contributions: list[dict[str, Any]]) -> dict[str, Any]:
    feature_reasons = {
        "amount_log": (
            "Amount scale",
            "Model score increased following a payment size that departs sharply from the sender's normal scale.",
        ),
        "sender_velocity_1h": (
            "Sender velocity",
            "Model score increased following accelerated sender velocity within the last hour.",
        ),
        "receiver_velocity_1h": (
            "Receiver velocity",
            "Model score increased following an inbound velocity spike on the receiving side.",
        ),
        "pair_velocity_24h": (
            "Pair velocity",
            "Model score increased following intensified repeat activity with the same counterparty.",
        ),
        "sender_unique_counterparties_24h": (
            "Counterparty spread",
            "Model score increased as counterparty spread widened across the last 24 hours.",
        ),
        "amount_ratio_to_sender_avg": (
            "Amount vs sender average",
            "Model score increased because payment size exceeded the sender's recent average.",
        ),
        "is_cross_bank": (
            "Cross-bank movement",
            "Model score increased after funds crossed bank boundaries during the transfer path.",
        ),
        "is_cross_currency": (
            "Cross-currency movement",
            "Model score increased after currency mismatch increased transfer complexity.",
        ),
        "fmt_account_transfer": (
            "Account transfer rail",
            "Model score increased while the transaction moved over account-transfer rails with elevated benchmark pressure.",
        ),
        "fmt_cash": (
            "Cash rail",
            "Model score increased because cash rails reduce identity certainty across the transfer path.",
        ),
        "fmt_crypto": (
            "Crypto rail",
            "Model score increased while the transaction aligned with higher-risk crypto rail behavior.",
        ),
    }
    items: list[dict[str, str]] = []
    for contribution in contributions:
        if contribution["impact"] < 0.75:
            continue
        feature = contribution["feature"]
        mapping = feature_reasons.get(feature)
        if mapping is None:
            continue
        label, detail = mapping
        items.append(
            _evidence_row(
                evidence_id=f"model-{feature}",
                label=label,
                detail=detail,
                source="Model",
            )
        )
        if len(items) == 3:
            break
    return {
        "source": "Model",
        "items": items,
        "shapValues": contributions,
    }


def _build_graph_evidence(graph_pressure: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    if graph_pressure["ring_pressure"] >= 20:
        items.append(
            _evidence_row(
                evidence_id="graph-ring-pressure",
                label="Ring pressure",
                detail="Recent circular fund flow raised ring pressure in the trust graph.",
                source="Graph",
            )
        )
    if graph_pressure["shared_device_pressure"] >= 12:
        items.append(
            _evidence_row(
                evidence_id="graph-shared-device",
                label="Shared device reuse",
                detail="Shared-device pressure increased because this device links multiple recent accounts.",
                source="Graph",
            )
        )
    if graph_pressure["merchant_pressure"] >= 10:
        items.append(
            _evidence_row(
                evidence_id="graph-merchant-pressure",
                label="Merchant concentration",
                detail="Merchant concentration intensified across recent connected accounts.",
                source="Graph",
            )
        )
    if graph_pressure["neighbor_pressure"] >= 20:
        items.append(
            _evidence_row(
                evidence_id="graph-neighbor-exposure",
                label="Neighbor exposure",
                detail="Neighbor exposure rose after recent transfers to already-risky linked accounts.",
                source="Graph",
            )
        )
    return {
        "source": "Graph",
        "items": items,
    }


def _build_drift_evidence(event: dict[str, Any], drift_score: float) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    if event["dormant_days"] >= 21:
        items.append(
            _evidence_row(
                evidence_id="drift-dormant-activation",
                label="Dormant-to-active shift",
                detail="Dormant-to-active behavior broke the account's recent rhythm.",
                source="Drift",
            )
        )
    if event["geo_distance_km"] >= 250:
        items.append(
            _evidence_row(
                evidence_id="drift-geo-displacement",
                label="Geographic displacement",
                detail="Geographic movement diverged materially from the account baseline.",
                source="Drift",
            )
        )
    if drift_score >= 80:
        items.append(
            _evidence_row(
                evidence_id="drift-behavioral-band",
                label="Behavioral drift",
                detail="Behavioral drift is operating above the platform comfort band.",
                source="Drift",
            )
        )
    return {
        "source": "Drift",
        "items": items,
    }


def _build_policy_evidence(fusion: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    policy_hits = set(fusion.get("policy_hits", []))
    if "ring_fracture_guardrail" in policy_hits:
        items.append(
            _evidence_row(
                evidence_id="policy-ring-fracture-guardrail",
                label="Ring fracture guardrail",
                detail="Policy guardrail elevated the case from Watch into Fractured review.",
                source="Policy",
            )
        )
    if "repeat_cross_border_escalation" in policy_hits:
        items.append(
            _evidence_row(
                evidence_id="policy-cross-border-escalation",
                label="Cross-border escalation",
                detail="Policy guardrail escalated the case into AML review after repeated cross-border pressure.",
                source="Policy",
            )
        )

    if fusion["decision"] == "escalate_aml" and "repeat_cross_border_escalation" not in policy_hits:
        items.append(
            _evidence_row(
                evidence_id="policy-escalated-threshold",
                label="Escalated threshold",
                detail=f"Fused trust score crossed the escalated threshold of {policy['escalated_threshold']:.0f}.",
                source="Policy",
            )
        )
    elif fusion["trust_state"] == "Fractured" and "ring_fracture_guardrail" not in policy_hits:
        items.append(
            _evidence_row(
                evidence_id="policy-fractured-threshold",
                label="Fractured review threshold",
                detail=f"Fused trust score crossed the fractured review threshold of {policy['fractured_threshold']:.0f}.",
                source="Policy",
            )
        )
    elif fusion["trust_state"] == "Watch":
        items.append(
            _evidence_row(
                evidence_id="policy-watch-threshold",
                label="Watch threshold",
                detail=f"Fused trust score crossed the watch threshold of {policy['watch_threshold']:.0f}.",
                source="Policy",
            )
        )
    return {
        "source": "Policy",
        "items": items,
    }


def _flatten_evidence_groups(evidence_groups: dict[str, Any]) -> list[str]:
    flattened: list[str] = []
    for group_key in ("modelEvidence", "graphEvidence", "driftEvidence", "policyEvidence"):
        group = evidence_groups.get(group_key, {}) or {}
        for item in group.get("items", []):
            detail = item.get("detail")
            if detail and detail not in flattened:
                flattened.append(detail)
    return flattened[:6]


def _normalize_evidence_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "modelEvidence": {"source": "Model", "items": [], "shapValues": []},
            "graphEvidence": {"source": "Graph", "items": []},
            "driftEvidence": {"source": "Drift", "items": []},
            "policyEvidence": {"source": "Policy", "items": []},
        }

    if all(key in payload for key in ("modelEvidence", "graphEvidence", "driftEvidence", "policyEvidence")):
        return payload

    normalized = {
        key: value
        for key, value in payload.items()
        if key not in {"reasons", "shapValues", "modelEvidence", "graphEvidence", "driftEvidence", "policyEvidence"}
    }
    shap_values = payload.get("shapValues", []) or []
    model_group = _build_model_evidence(shap_values)
    graph_items: list[dict[str, str]] = []
    drift_items: list[dict[str, str]] = []
    policy_items: list[dict[str, str]] = []
    model_items = list(model_group["items"])

    def add_legacy_item(target: list[dict[str, str]], source: str, detail: str) -> None:
        if any(existing["detail"] == detail for existing in target):
            return
        target.append(
            _evidence_row(
                evidence_id=f"legacy-{source.lower()}-{len(target) + 1}",
                label=f"{source} signal",
                detail=detail,
                source=source,
            )
        )

    for reason in payload.get("reasons", []) or []:
        lowered = reason.lower()
        if any(keyword in lowered for keyword in ("ring pressure", "trust graph", "device reuse", "merchant concentration", "neighbor exposure")):
            add_legacy_item(graph_items, "Graph", reason)
        elif any(keyword in lowered for keyword in ("dormant-to-active", "recent rhythm", "geographic displacement", "behavioral drift")):
            add_legacy_item(drift_items, "Drift", reason)
        elif any(keyword in lowered for keyword in ("guardrail", "threshold", "aml review", "fractured review")):
            add_legacy_item(policy_items, "Policy", reason)
        else:
            add_legacy_item(model_items, "Model", reason)

    normalized["modelEvidence"] = {
        "source": "Model",
        "items": model_items,
        "shapValues": shap_values,
    }
    normalized["graphEvidence"] = {"source": "Graph", "items": graph_items}
    normalized["driftEvidence"] = {"source": "Drift", "items": drift_items}
    normalized["policyEvidence"] = {"source": "Policy", "items": policy_items}
    return normalized


def _build_evidence_groups(
    contributions: list[dict[str, Any]],
    graph_pressure: dict[str, Any],
    event: dict[str, Any],
    drift_score: float,
    fusion: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "modelEvidence": _build_model_evidence(contributions),
        "graphEvidence": _build_graph_evidence(graph_pressure),
        "driftEvidence": _build_drift_evidence(event, drift_score),
        "policyEvidence": _build_policy_evidence(fusion, policy),
    }


def _drift_score(event: dict[str, Any]) -> float:
    drift = 0.0
    drift += min(45.0, event["dormant_days"] * 1.2)
    drift += min(28.0, event["geo_distance_km"] / 24.0)
    if event["dormant_days"] >= 21:
        drift += 14.0
    if event["geo_distance_km"] >= 250:
        drift += 12.0
    return round(min(100.0, drift), 2)


def _upsert_case(db: Session, payload: dict[str, Any]) -> CaseRecord:
    record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == payload["case_id"]))
    if record is None:
        record = CaseRecord(**payload)
        db.add(record)
    else:
        for key, value in payload.items():
            setattr(record, key, value)
    db.flush()
    return record


def _serialize_case_event(record: CaseEventRecord) -> dict[str, Any]:
    payload = record.payload or {}
    event_type = record.event_type
    label = {
        "signal_update": "Signal update",
        "transaction_ingested": "Transaction ingested",
        "trust_transition": "Trust state changed",
        "queue_transition": "Queue status updated",
        "analyst_action": "Analyst action",
        "policy_update": "Policy update",
        "alert_dispatched": "Telegram alert sent",
        "alert_skipped": "Telegram alert skipped",
        "alert_failed": "Telegram alert failed",
    }.get(event_type, event_type.replace("_", " ").title())

    detail = ""
    if event_type == "transaction_ingested":
        provider = payload.get("provider")
        detail = (
            f"{payload.get('source', 'live').title()} event {payload.get('transactionId', 'unknown')} "
            f"arrived on {payload.get('channel', 'unknown')} using {payload.get('paymentRail', 'unknown')}."
        )
        if provider:
            detail += f" Provider {provider.title()}."
    elif event_type == "trust_transition":
        detail = (
            f"{payload.get('from', 'Unknown')} -> {payload.get('to', 'Unknown')} at "
            f"{payload.get('fusedScore', 0)} fused score."
        )
    elif event_type == "queue_transition":
        detail = f"Case entered {payload.get('status', 'review')} workflow from {payload.get('source', 'unknown')} intake."
    elif event_type == "analyst_action":
        detail = f"{payload.get('action', 'updated')} by {record.actor}."
    elif event_type == "signal_update":
        detail = (
            f"Fraud {payload.get('fraudScore', 0)} | Graph {payload.get('graphScore', 0)} | "
            f"Drift {payload.get('driftScore', 0)}."
        )
    elif event_type == "policy_update":
        detail = "Policy thresholds were revised in Policy Lab."
    elif event_type == "alert_dispatched":
        detail = (
            f"Telegram alert sent for {payload.get('trustState', 'Unknown')} state on "
            f"{payload.get('transactionId', 'unknown')}."
        )
    elif event_type == "alert_skipped":
        detail = (
            f"Telegram alert skipped for {payload.get('transactionId', 'unknown')}. "
            f"{payload.get('error', 'Telegram is not configured for this environment.')}."
        )
    elif event_type == "alert_failed":
        detail = (
            f"Telegram alert failed for {payload.get('transactionId', 'unknown')}. "
            f"{payload.get('error', 'No failure reason provided')}."
        )

    return {
        "id": record.id,
        "eventType": event_type,
        "label": label,
        "actor": record.actor,
        "detail": detail,
        "payload": payload,
        "createdAt": record.created_at.isoformat() if record.created_at else None,
    }


def _case_timeline(db: Session, case_id: str) -> list[dict[str, Any]]:
    records = db.scalars(
        select(CaseEventRecord)
        .where(CaseEventRecord.case_id == case_id, CaseEventRecord.event_type != "replay_checkpoint")
        .order_by(CaseEventRecord.created_at.asc())
    ).all()
    return [_serialize_case_event(record) for record in records]


def _case_replay_steps(db: Session, case_id: str) -> list[dict[str, Any]]:
    records = db.scalars(
        select(CaseEventRecord)
        .where(CaseEventRecord.case_id == case_id, CaseEventRecord.event_type == "replay_checkpoint")
        .order_by(CaseEventRecord.created_at.asc())
    ).all()
    steps: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        payload = record.payload or {}
        steps.append(
            {
                "index": index,
                "label": payload.get("label") or f"Step {index + 1}",
                "timestamp": payload.get("timestamp") or (record.created_at.isoformat() if record.created_at else None),
                "trustState": payload.get("trustState", "Healthy"),
                "fusedScore": payload.get("fusedScore", 0.0),
                "caseId": payload.get("caseId", case_id),
                "graph": payload.get("graph") or {"nodes": [], "edges": []},
                "evidence": _normalize_evidence_payload(payload.get("evidence") or {}),
                "source": payload.get("source", "live"),
                "decision": payload.get("decision", "approve"),
            }
        )
    return steps


def _serialize_case(
    record: CaseRecord | None,
    timeline: list[dict[str, Any]] | None = None,
    replay_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if record is None:
        return None
    evidence_payload = _normalize_evidence_payload(record.evidence_payload or {})
    return {
        "caseId": record.case_id,
        "title": record.title,
        "accountId": record.account_id,
        "source": _source_tag(record.scenario_id),
        "scenarioId": record.scenario_id,
        "trustState": record.trust_state,
        "status": record.status,
        "fraudScore": record.fraud_score,
        "graphScore": record.graph_score,
        "driftScore": record.drift_score,
        "fusedScore": record.fused_score,
        "summary": record.summary,
        "topReasons": record.top_reasons or [],
        "recommendedActions": record.recommended_actions or [],
        "graph": record.graph_snapshot or {"nodes": [], "edges": []},
        "evidence": evidence_payload,
        "replaySteps": replay_steps or [],
        "lastTransactionId": record.last_transaction_id,
        "isBaselineSeed": _is_baseline_seed_transaction_id(record.last_transaction_id or ""),
        "timeline": timeline or [],
        "updatedAt": record.updated_at.isoformat() if record.updated_at else None,
    }


def _queue_snapshot(db: Session, include_replay_session: str | None = None) -> list[dict[str, Any]]:
    rows = db.scalars(select(CaseRecord).order_by(CaseRecord.updated_at.desc())).all()
    queue_events = db.scalars(
        select(CaseEventRecord).where(CaseEventRecord.event_type == "queue_transition").order_by(CaseEventRecord.created_at.desc())
    ).all()
    latest_queue_event: dict[str, CaseEventRecord] = {}
    for event in queue_events:
        latest_queue_event.setdefault(event.case_id, event)

    replay_prefix = f"replay_{include_replay_session}_" if include_replay_session else ""
    queued_rows = []
    for row in rows:
        if row.status not in {"review", "escalated"}:
            continue
        if _is_live_case(row):
            queued_rows.append(row)
            continue
        if include_replay_session and row.case_id.startswith(replay_prefix):
            queued_rows.append(row)
    queued_rows.sort(
        key=lambda row: (
            -_severity_rank(row.trust_state, row.status),
            -(latest_queue_event[row.case_id].created_at.timestamp() if row.case_id in latest_queue_event and latest_queue_event[row.case_id].created_at else row.updated_at.timestamp() if row.updated_at else 0.0),
            -row.fused_score,
        )
    )

    snapshot: list[dict[str, Any]] = []
    for row in queued_rows:
        queue_event = latest_queue_event.get(row.case_id)
        snapshot.append(
            {
                "caseId": row.case_id,
                "title": row.title,
                "trustState": row.trust_state,
                "status": row.status,
                "fusedScore": row.fused_score,
                "summary": row.summary,
                "severity": _severity_rank(row.trust_state, row.status),
                "source": _source_tag(row.scenario_id),
                "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
                "queueEnteredAt": queue_event.created_at.isoformat() if queue_event and queue_event.created_at else None,
            }
        )
    return snapshot


def _build_state(db: Session, focus_case_id: str | None = None) -> dict[str, Any]:
    if focus_case_id is None:
        focus_case_id = runtime.focus_case_id
    focus = db.scalar(select(CaseRecord).where(CaseRecord.case_id == focus_case_id)) if focus_case_id else None
    focus_timeline = _case_timeline(db, focus_case_id) if focus_case_id and focus else []
    focus_replay_steps = _case_replay_steps(db, focus_case_id) if focus_case_id and focus else []
    live_payment_seen = _has_demo_live_payment(db) if settings.demo_flow_lock else _has_live_transactions(db)
    payload = {
        "generatedAt": _now_iso(),
        "scenarioId": runtime.current_scenario_id,
        "signalRail": list(runtime.signal_rail),
        "graph": focus.graph_snapshot if focus else {"nodes": [], "edges": []},
        "focusCase": _serialize_case(focus, focus_timeline, focus_replay_steps),
        "queue": _queue_snapshot(db, include_replay_session=runtime.replay_session_id if runtime.is_running else None),
        "replay": {
            "activeIndex": runtime.current_step,
            "steps": runtime.replay_steps,
        },
        "policy": runtime.fusion.current_policy(),
        "operations": {
            "integrationStatus": _integration_status(),
            "latestAlert": runtime.latest_alert,
            "demoFlow": {
                "locked": settings.demo_flow_lock,
                "livePaymentSeen": live_payment_seen,
                "requiredOrder": ["seed baseline", "live payment", "trust transition", "queue", "telegram", "replay"],
            },
        },
        "system": {
            "status": "running" if runtime.is_running else "idle",
            "scenarioId": runtime.current_scenario_id,
            "activeStep": runtime.current_step + 1 if runtime.total_steps else 0,
            "totalSteps": runtime.total_steps,
            "focusAccountId": runtime.focus_account_id,
        },
        "scenarios": [item.model_dump() for item in scenario_metadata(runtime.scenarios)],
    }
    runtime.update_state(payload)
    return payload


async def _publish_state(db: Session, focus_case_id: str | None = None) -> None:
    payload = _build_state(db, focus_case_id)
    await runtime.broadcast.publish(payload)


def _reset_runtime_view() -> None:
    runtime.replay_session_id = None
    runtime.current_step = 0
    runtime.total_steps = 0
    runtime.is_running = False
    runtime.replay_steps = []
    runtime.live_runtime_snapshot = None
    runtime.signal_rail.clear()
    runtime.focus_case_id = None
    runtime.focus_account_id = None
    runtime.live_focus_case_id = None
    runtime.live_focus_account_id = None
    runtime.rolling = MemoryRollingState()
    runtime.graph = TrustMemoryGraph()


def _capture_live_runtime_snapshot() -> dict[str, Any]:
    return {
        "signal_rail": deque(copy.deepcopy(list(runtime.signal_rail)), maxlen=runtime.signal_rail.maxlen),
        "focus_case_id": runtime.live_focus_case_id or runtime.focus_case_id,
        "focus_account_id": runtime.live_focus_account_id or runtime.focus_account_id,
        "rolling": copy.deepcopy(runtime.rolling),
        "graph": copy.deepcopy(runtime.graph),
    }


def _restore_live_runtime_snapshot(snapshot: dict[str, Any] | None) -> None:
    if snapshot is None:
        return
    runtime.signal_rail = snapshot["signal_rail"]
    runtime.focus_case_id = snapshot["focus_case_id"]
    runtime.focus_account_id = snapshot["focus_account_id"]
    runtime.live_focus_case_id = snapshot["focus_case_id"]
    runtime.live_focus_account_id = snapshot["focus_account_id"]
    runtime.rolling = snapshot["rolling"]
    runtime.graph = snapshot["graph"]


def _rehydrate_runtime_from_db(db: Session) -> None:
    start = perf_counter()
    _reset_runtime_view()
    runtime.current_scenario_id = None
    tx_rows = db.scalars(
        select(TransactionRecord).where(TransactionRecord.scenario_id == LIVE_SCENARIO_ID).order_by(TransactionRecord.id.asc())
    ).all()
    case_rows = db.scalars(
        select(CaseRecord).where(CaseRecord.scenario_id == LIVE_SCENARIO_ID).order_by(CaseRecord.updated_at.asc())
    ).all()
    checkpoint = _timing_checkpoint("startup.rehydrate.load_rows", start, transactions=len(tx_rows), cases=len(case_rows))

    for tx in tx_rows:
        payload = dict(tx.raw_payload or {})
        timestamp = payload.get("timestamp")
        if not timestamp:
            continue
        try:
            payload["timestamp"] = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        runtime.rolling.record(
            account_id=payload["account_id"],
            counterparty_id=payload["counterparty_id"],
            amount=payload["amount"],
            payment_format=payload["payment_format"],
            timestamp=payload["timestamp"],
            from_bank=payload.get("from_bank", ""),
            to_bank=payload.get("to_bank", ""),
        )
        runtime.graph.ingest(payload)
    checkpoint = _timing_checkpoint("startup.rehydrate.graph", checkpoint, graph_nodes=runtime.graph.graph.number_of_nodes())

    for case in case_rows:
        runtime.graph.mark_account(case.account_id, case.fused_score)

    latest_case_by_account = {case.account_id: case for case in case_rows}
    for tx in reversed(tx_rows[-14:]):
        raw_payload = tx.raw_payload or {}
        matching_case = latest_case_by_account.get(tx.account_id)
        runtime.signal_rail.append(
            {
                "caseId": matching_case.case_id if matching_case else f"case_{tx.account_id.lower().replace('-', '_')}",
                "source": _source_tag(tx.scenario_id),
                "transactionId": tx.transaction_id,
                "timestamp": raw_payload.get("timestamp", tx.created_at.isoformat() if tx.created_at else _now_iso()),
                "accountId": tx.account_id,
                "counterpartyId": tx.counterparty_id,
                "amount": tx.amount,
                "channel": tx.channel,
                "paymentRail": tx.payment_format,
                "merchantId": tx.merchant_id,
                "trustState": matching_case.trust_state if matching_case else "Healthy",
                "fusedScore": matching_case.fused_score if matching_case else 0.0,
                "scenarioNote": raw_payload.get("scenario_note", ""),
                "isBaselineSeed": _is_baseline_seed_transaction_id(tx.transaction_id),
            }
        )

    latest_case = case_rows[-1] if case_rows else None
    if latest_case:
        runtime.focus_case_id = latest_case.case_id
        runtime.focus_account_id = latest_case.account_id
        runtime.live_focus_case_id = latest_case.case_id
        runtime.live_focus_account_id = latest_case.account_id
    _timing_checkpoint("startup.rehydrate.signal_rail", checkpoint, rail_count=len(runtime.signal_rail))


async def _process_event(
    db: Session,
    scenario_id: str,
    event: dict[str, Any],
    step_index: int,
    total_steps: int,
    *,
    source: str,
    append_replay_step: bool,
) -> dict[str, Any]:
    step_start = perf_counter()
    event.setdefault("from_bank", "")
    event.setdefault("to_bank", "")
    event.setdefault("payment_currency", "")
    event.setdefault("receiving_currency", "")
    persisted_transaction_id = event["transaction_id"]
    if source == "replay":
        replay_session = runtime.replay_session_id or "session"
        persisted_transaction_id = f"{event['transaction_id']}::{replay_session}::{step_index}"
    existing_tx = db.scalar(select(TransactionRecord).where(TransactionRecord.transaction_id == persisted_transaction_id))
    if source == "live" and existing_tx is not None:
        raise HTTPException(status_code=409, detail=f"Transaction {event['transaction_id']} already exists.")
    serializable_event = {
        **event,
        "timestamp": event["timestamp"].isoformat(),
        "source": source,
    }
    tx = TransactionRecord(
        transaction_id=persisted_transaction_id,
        scenario_id=scenario_id,
        account_id=event["account_id"],
        counterparty_id=event["counterparty_id"],
        device_id=event["device_id"],
        merchant_id=event["merchant_id"],
        channel=event["channel"],
        amount=event["amount"],
        city=event["city"],
        country=event["country"],
        payment_format=event["payment_format"],
        geo_distance_km=event["geo_distance_km"],
        dormant_days=event["dormant_days"],
        raw_payload=serializable_event,
    )
    db.add(tx)
    db.flush()
    checkpoint = _timing_checkpoint("event.persisted", step_start, source=source, transaction_id=event["transaction_id"])

    rolling = runtime.rolling.record(
        account_id=event["account_id"],
        counterparty_id=event["counterparty_id"],
        amount=event["amount"],
        payment_format=event["payment_format"],
        timestamp=event["timestamp"],
        from_bank=event["from_bank"],
        to_bank=event["to_bank"],
    )
    checkpoint = _timing_checkpoint("event.rolling_features", checkpoint, source=source, sender_velocity=rolling.sender_velocity_1h)
    vector = runtime.fraud.make_vector(event, rolling)
    fraud_score, contributions = runtime.fraud.score(vector)
    checkpoint = _timing_checkpoint("event.model_scored", checkpoint, source=source, fraud_score=fraud_score)
    graph_pressure = runtime.graph.ingest(event)
    checkpoint = _timing_checkpoint("event.graph_updated", checkpoint, source=source, graph_score=round(graph_pressure.score, 2))
    drift_score = _drift_score(event)
    policy = runtime.fusion.current_policy()
    prior_account_score = runtime.graph.account_risk.get(event["account_id"], 0.0)
    fusion = runtime.fusion.fuse(
        fraud_score=fraud_score,
        graph_score=graph_pressure.score,
        drift_score=drift_score,
        prior_account_score=prior_account_score,
        ring_pressure=graph_pressure.ring_pressure,
        is_cross_currency=bool(
            event.get("payment_currency")
            and event.get("receiving_currency")
            and event["payment_currency"] != event["receiving_currency"]
        ),
    )
    runtime.graph.mark_account(event["account_id"], fusion["fused_score"])
    checkpoint = _timing_checkpoint(
        "event.fusion_applied",
        checkpoint,
        source=source,
        trust_state=fusion["trust_state"],
        decision=fusion["decision"],
    )

    evidence_groups = _build_evidence_groups(
        contributions,
        {
            "ring_pressure": graph_pressure.ring_pressure,
            "shared_device_pressure": graph_pressure.shared_device_pressure,
            "merchant_pressure": graph_pressure.merchant_pressure,
            "neighbor_pressure": graph_pressure.neighbor_pressure,
        },
        event,
        drift_score,
        fusion,
        policy,
    )
    reasons = _flatten_evidence_groups(evidence_groups)
    summary, actions = runtime.copilot.summarize(
        account_id=event["account_id"],
        trust_state=fusion["trust_state"],
        fraud_score=fraud_score,
        graph_score=graph_pressure.score,
        drift_score=drift_score,
        reasons=reasons,
        focus=event.get("custom_copilot_focus", ""),
    )
    graph_snapshot = runtime.graph.snapshot(event["account_id"])

    evidence_payload = {
        "scores": {
            "fraud": fraud_score,
            "graph": round(graph_pressure.score, 2),
            "drift": drift_score,
            "fused": fusion["fused_score"],
        },
        "trustState": fusion["trust_state"],
        "decision": fusion["decision"],
        "channel": event["channel"],
        "paymentRail": event["payment_format"],
        "source": source,
        "pressures": {
            "ring": graph_pressure.ring_pressure,
            "sharedDevice": graph_pressure.shared_device_pressure,
            "merchantBurst": graph_pressure.merchant_pressure,
            "neighborExposure": graph_pressure.neighbor_pressure,
        },
        "policy": {
            "watchThreshold": policy["watch_threshold"],
            "fracturedThreshold": policy["fractured_threshold"],
            "escalatedThreshold": policy["escalated_threshold"],
        },
        "policyHits": fusion.get("policy_hits", []),
        "note": event.get("scenario_note", ""),
        **evidence_groups,
    }

    case_id = _base_case_id(event["account_id"])
    if source == "replay":
        case_id = _replay_case_id(runtime.replay_session_id or "session", event["account_id"])
    previous_case = db.scalar(select(CaseRecord).where(CaseRecord.case_id == case_id))
    previous_status = previous_case.status if previous_case else None
    previous_trust_state = previous_case.trust_state if previous_case else None
    status = "approved"
    if fusion["decision"] == "review":
        status = "review"
    elif fusion["decision"] == "escalate_aml":
        status = "escalated"
    case_payload = {
        "case_id": case_id,
        "scenario_id": scenario_id,
        "title": f"Trust investigation on {event['account_id']}",
        "account_id": event["account_id"],
        "trust_state": fusion["trust_state"],
        "status": status,
        "fraud_score": fraud_score,
        "graph_score": round(graph_pressure.score, 2),
        "drift_score": drift_score,
        "fused_score": fusion["fused_score"],
        "summary": summary,
        "top_reasons": reasons,
        "recommended_actions": actions,
        "graph_snapshot": graph_snapshot,
        "evidence_payload": evidence_payload,
        "last_transaction_id": event["transaction_id"],
    }
    _upsert_case(db, case_payload)
    db.add(
        CaseEventRecord(
            case_id=case_id,
            event_type="transaction_ingested",
            payload={
                "transactionId": event["transaction_id"],
                "amount": event["amount"],
                "channel": event["channel"],
                "paymentRail": event["payment_format"],
                "source": source,
                "provider": ((event.get("integration") or {}).get("provider") or ""),
            },
        )
    )
    db.add(
        CaseEventRecord(
            case_id=case_id,
            event_type="signal_update",
            payload={
                "transactionId": event["transaction_id"],
                "trustState": fusion["trust_state"],
                "fusedScore": fusion["fused_score"],
                "fraudScore": fraud_score,
                "graphScore": round(graph_pressure.score, 2),
                "driftScore": drift_score,
                "decision": fusion["decision"],
                "source": source,
                "policy": policy,
                "policyHits": fusion.get("policy_hits", []),
            },
        )
    )
    if previous_trust_state != fusion["trust_state"]:
        db.add(
            CaseEventRecord(
                case_id=case_id,
                event_type="trust_transition",
                payload={
                    "from": previous_trust_state or "None",
                    "to": fusion["trust_state"],
                    "fusedScore": fusion["fused_score"],
                    "source": source,
                    "policyHits": fusion.get("policy_hits", []),
                },
            )
        )
    if status in {"review", "escalated"} and previous_status != status:
        db.add(
            CaseEventRecord(
                case_id=case_id,
                event_type="queue_transition",
                payload={
                    "status": status,
                    "trustState": fusion["trust_state"],
                    "source": source,
                    "severity": _severity_rank(fusion["trust_state"], status),
                    "policyHits": fusion.get("policy_hits", []),
                },
            )
        )
    db.add(
        CaseEventRecord(
            case_id=case_id,
            event_type="replay_checkpoint",
            payload={
                "label": event["scenario_note"] or (f"Live payment {event['transaction_id']}" if source == "live" else f"Step {step_index + 1}"),
                "timestamp": event["timestamp"].isoformat(),
                "trustState": fusion["trust_state"],
                "fusedScore": fusion["fused_score"],
                "caseId": case_id,
                "graph": graph_snapshot,
                "evidence": evidence_payload,
                "source": source,
                "decision": fusion["decision"],
            },
        )
    )
    checkpoint = _timing_checkpoint("event.timeline_persisted", checkpoint, source=source)
    db.flush()

    if source == "live":
        runtime.live_focus_case_id = case_id
        runtime.live_focus_account_id = event["account_id"]
    if source == "replay" or not runtime.is_running:
        runtime.focus_case_id = case_id
        runtime.focus_account_id = event["account_id"]
    if source == "live":
        runtime.signal_rail.appendleft(
            {
                "caseId": case_id,
                "source": source,
                "transactionId": event["transaction_id"],
                "timestamp": event["timestamp"].isoformat(),
                "accountId": event["account_id"],
                "counterpartyId": event["counterparty_id"],
                "amount": event["amount"],
                "channel": event["channel"],
                "paymentRail": event["payment_format"],
                "merchantId": event["merchant_id"],
                "trustState": fusion["trust_state"],
                "fusedScore": fusion["fused_score"],
                "scenarioNote": event["scenario_note"],
                "isBaselineSeed": _is_baseline_seed_transaction_id(event["transaction_id"]),
            }
        )
    if append_replay_step:
        runtime.current_step = step_index
        runtime.replay_steps.append(
            {
                "index": step_index,
                "label": event["scenario_note"] or f"Step {step_index + 1}",
                "timestamp": event["timestamp"].isoformat(),
                "trustState": fusion["trust_state"],
                "fusedScore": fusion["fused_score"],
                "caseId": case_id,
                "graph": graph_snapshot,
                "evidence": evidence_payload,
            }
        )
        checkpoint = _timing_checkpoint("event.replay_step_recorded", checkpoint, step=step_index + 1, total=total_steps)
    await _publish_state(db, case_id)
    _timing_checkpoint("event.broadcast_complete", checkpoint, source=source, queue_size=len(_queue_snapshot(db)))
    return {
        "caseId": case_id,
        "transactionId": event["transaction_id"],
        "trustState": fusion["trust_state"],
        "decision": fusion["decision"],
        "fusedScore": fusion["fused_score"],
        "reasons": reasons,
        "timestamp": event["timestamp"].isoformat(),
        "source": source,
    }


async def _dispatch_case_alert(result: dict[str, Any]) -> None:
    if result.get("source") != "live":
        return
    if not runtime.alerts.should_alert(result.get("trustState", "Healthy")):
        return

    timestamp = datetime.fromisoformat(result["timestamp"])
    message = runtime.alerts.build_message(
        case_id=result["caseId"],
        transaction_id=result["transactionId"],
        trust_state=result["trustState"],
        decision=result["decision"],
        fused_score=float(result.get("fusedScore", 0.0)),
        reasons=list(result.get("reasons", [])),
        timestamp=timestamp,
        replay_available=True,
    )
    dispatch_result = await runtime.alerts.dispatch(message)
    runtime.latest_alert = {
        "provider": dispatch_result.provider,
        "status": dispatch_result.status,
        "caseId": result["caseId"],
        "transactionId": result["transactionId"],
        "trustState": result["trustState"],
        "decision": result["decision"],
        "fusedScore": float(result.get("fusedScore", 0.0)),
        "message": dispatch_result.message,
        "deliveredAt": dispatch_result.delivered_at,
        "replayAvailable": True,
        "error": dispatch_result.error,
    }

    if dispatch_result.status == "skipped":
        alert_event_type = "alert_skipped"
    elif dispatch_result.ok:
        alert_event_type = "alert_dispatched"
    else:
        alert_event_type = "alert_failed"

    with session_scope() as db:
        db.add(
            CaseEventRecord(
                case_id=result["caseId"],
                event_type=alert_event_type,
                payload={
                    "provider": dispatch_result.provider,
                    "status": dispatch_result.status,
                    "transactionId": result["transactionId"],
                    "trustState": result["trustState"],
                    "decision": result["decision"],
                    "fusedScore": float(result.get("fusedScore", 0.0)),
                    "replayAvailable": True,
                    "error": dispatch_result.error,
                },
            )
        )
        db.flush()
        await _publish_state(db, result["caseId"])


async def _run_scenario(scenario_id: str) -> None:
    scenario = runtime.scenarios.get(scenario_id)
    if scenario is None:
        return

    async with runtime.state_lock:
        runtime.live_runtime_snapshot = _capture_live_runtime_snapshot()
        runtime.current_scenario_id = scenario_id
        runtime.replay_session_id = uuid4().hex[:8]
        runtime.current_step = 0
        runtime.total_steps = len(scenario["events"])
        runtime.is_running = True
        runtime.replay_steps = []
        runtime.focus_case_id = None
        runtime.focus_account_id = None
        runtime.rolling = MemoryRollingState()
        runtime.graph = TrustMemoryGraph()

        with session_scope() as db:
            await _publish_state(db)

    try:
        for idx, raw_event in enumerate(scenario["events"]):
            delay_ms = raw_event.get("delay_ms", 0)
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
            event = TransactionEvent.model_validate(raw_event).model_dump()
            async with runtime.state_lock:
                with session_scope() as db:
                    await _process_event(
                        db,
                        scenario_id,
                        event,
                        idx,
                        runtime.total_steps,
                        source="replay",
                        append_replay_step=True,
                    )
    finally:
        async with runtime.state_lock:
            runtime.is_running = False
            _restore_live_runtime_snapshot(runtime.live_runtime_snapshot)
            runtime.live_runtime_snapshot = None
            with session_scope() as db:
                await _publish_state(db, runtime.focus_case_id)


@app.on_event("startup")
async def on_startup() -> None:
    startup_start = perf_counter()
    init_db()
    checkpoint = _timing_checkpoint("startup.init_db", startup_start)
    runtime.hydrate_policy()
    checkpoint = _timing_checkpoint("startup.hydrate_policy", checkpoint)
    runtime.fraud.warmup()
    checkpoint = _timing_checkpoint("startup.model_warmup", checkpoint, bundle=runtime.fraud.bundle_id)
    with session_scope() as db:
        _rehydrate_runtime_from_db(db)
        checkpoint = _timing_checkpoint("startup.rehydrate_runtime", checkpoint)
        await _publish_state(db)
        _timing_checkpoint("startup.publish_state", checkpoint)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "rayzaa-api"}


@app.get(f"{settings.api_prefix}/scenarios")
def get_scenarios() -> list[dict[str, Any]]:
    return [item.model_dump() for item in scenario_metadata(runtime.scenarios)]


@app.get(f"{settings.api_prefix}/state")
def get_state(db: Session = Depends(get_db)) -> dict[str, Any]:
    return _build_state(db)


@app.get(f"{settings.api_prefix}/replay/{{scenario_id}}")
def get_replay(scenario_id: str) -> dict[str, Any]:
    if runtime.current_scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Replay not available for this scenario yet.")
    return {"scenarioId": scenario_id, "steps": runtime.replay_steps}


@app.get(f"{settings.api_prefix}/cases")
def get_cases(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    records = db.scalars(
        select(CaseRecord).where(CaseRecord.scenario_id == LIVE_SCENARIO_ID).order_by(CaseRecord.updated_at.desc())
    ).all()
    return [
        _serialize_case(record, _case_timeline(db, record.case_id), _case_replay_steps(db, record.case_id))
        for record in records
        if record
    ]


@app.get(f"{settings.api_prefix}/cases/{{case_id}}")
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == case_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return _serialize_case(record, _case_timeline(db, case_id), _case_replay_steps(db, case_id))


@app.get(f"{settings.api_prefix}/cases/{{case_id}}/events")
def get_case_events(case_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == case_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {"caseId": case_id, "events": _case_timeline(db, case_id)}


@app.get(f"{settings.api_prefix}/integrations/status")
def get_integration_status() -> dict[str, Any]:
    return {
        "integrationStatus": _integration_status(),
        "latestAlert": runtime.latest_alert,
        "demoFlow": {
            "locked": settings.demo_flow_lock,
            "livePaymentSeen": False,
            "requiredOrder": ["seed baseline", "live payment", "trust transition", "queue", "telegram", "replay"],
        },
    }


@app.post(f"{settings.api_prefix}/integrations/razorpay/orders")
async def create_razorpay_order(request: RazorpayDemoOrderRequest) -> dict[str, Any]:
    if not runtime.razorpay.is_configured():
        raise HTTPException(status_code=503, detail="Razorpay integration is not configured.")
    try:
        return await runtime.razorpay.create_order(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to create Razorpay test order: {exc}") from exc


@app.post(f"{settings.api_prefix}/integrations/razorpay/checkout/verify")
def verify_razorpay_checkout(request: RazorpayCheckoutVerificationRequest) -> dict[str, Any]:
    if not runtime.razorpay.verify_checkout_signature(
        order_id=request.razorpay_order_id,
        payment_id=request.razorpay_payment_id,
        signature=request.razorpay_signature,
    ):
        raise HTTPException(status_code=400, detail="Invalid Razorpay checkout signature.")
    return {
        "ok": True,
        "status": "verified",
        "paymentId": request.razorpay_payment_id,
        "orderId": request.razorpay_order_id,
        "message": "Checkout signature verified. Waiting for Razorpay webhook ingest.",
    }


@app.post(f"{settings.api_prefix}/integrations/razorpay/webhook")
async def ingest_razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not runtime.razorpay.is_webhook_configured():
        raise HTTPException(status_code=503, detail="Razorpay webhook secret is not configured.")

    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    event_id = request.headers.get("x-razorpay-event-id", uuid4().hex)
    if not runtime.razorpay.verify_webhook_signature(raw_body=raw_body, signature=signature):
        raise HTTPException(status_code=401, detail="Invalid Razorpay webhook signature.")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Razorpay webhook payload: {exc}") from exc

    event_name = payload.get("event", "")
    if event_name != settings.razorpay_webhook_event:
        return {"ok": True, "status": "ignored", "event": event_name}

    try:
        normalized_event = runtime.razorpay.normalize_webhook(payload, event_id=event_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to normalize Razorpay webhook payload: {exc}") from exc

    async with runtime.state_lock:
        try:
            result = await _process_event(
                db,
                "live",
                normalized_event,
                step_index=len(runtime.replay_steps),
                total_steps=runtime.total_steps,
                source="live",
                append_replay_step=False,
            )
            db.commit()
        except HTTPException as exc:
            if exc.status_code == 409:
                db.rollback()
                return {
                    "ok": True,
                    "status": "duplicate",
                    "event": event_name,
                    "transactionId": normalized_event["transaction_id"],
                }
            raise

        asyncio.create_task(_dispatch_case_alert(result))
        case_record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == result["caseId"]))
        return {
            "ok": True,
            "status": "ingested",
            "event": event_name,
            "transactionId": result["transactionId"],
            "case": _serialize_case(case_record, _case_timeline(db, result["caseId"]), _case_replay_steps(db, result["caseId"])),
        }


@app.post(f"{settings.api_prefix}/transactions/ingest")
async def ingest_transaction(event: TransactionEvent, db: Session = Depends(get_db)) -> dict[str, Any]:
    request_start = perf_counter()
    _timing_checkpoint("ingest.request_received", request_start, transaction_id=event.transaction_id)
    async with runtime.state_lock:
        result = await _process_event(
            db,
            "live",
            event.model_dump(),
            step_index=len(runtime.replay_steps),
            total_steps=runtime.total_steps,
            source="live",
            append_replay_step=False,
        )
        db.commit()
        _timing_checkpoint("ingest.request_complete", request_start, transaction_id=event.transaction_id)
        case_record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == result["caseId"]))
        asyncio.create_task(_dispatch_case_alert(result))
        return {
            "ok": True,
            "transactionId": result["transactionId"],
            "case": _serialize_case(case_record, _case_timeline(db, result["caseId"]), _case_replay_steps(db, result["caseId"])),
        }


@app.post(f"{settings.api_prefix}/cases/{{case_id}}/actions")
async def take_case_action(case_id: str, request: CaseActionRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with runtime.state_lock:
        record = db.scalar(select(CaseRecord).where(CaseRecord.case_id == case_id))
        if record is None:
            raise HTTPException(status_code=404, detail="Case not found.")
        if record.scenario_id != LIVE_SCENARIO_ID:
            raise HTTPException(status_code=400, detail="Replay cases are read-only. Return to the live case queue for analyst actions.")

        previous_status = record.status
        previous_trust_state = record.trust_state
        status_map = {
            "approve": "approved",
            "review": "review",
            "escalate_aml": "escalated",
        }
        record.status = status_map.get(request.action, request.action)
        db.add(
            CaseEventRecord(
                case_id=case_id,
                event_type="analyst_action",
                actor=request.actor,
                payload={"action": request.action, "note": request.note},
            )
        )
        if previous_trust_state != record.trust_state:
            db.add(
                CaseEventRecord(
                    case_id=case_id,
                    event_type="trust_transition",
                    actor=request.actor,
                    payload={
                        "from": previous_trust_state,
                        "to": record.trust_state,
                        "fusedScore": record.fused_score,
                        "source": "analyst",
                    },
                )
            )
        if previous_status != record.status and record.status in {"review", "escalated"}:
            db.add(
                CaseEventRecord(
                    case_id=case_id,
                    event_type="queue_transition",
                    actor=request.actor,
                    payload={
                        "status": record.status,
                        "trustState": record.trust_state,
                        "source": "analyst",
                        "severity": _severity_rank(record.trust_state, record.status),
                    },
                )
            )
        db.flush()
        db.commit()
        await _publish_state(db, case_id)
        return {"ok": True, "caseId": case_id, "status": record.status}


@app.get(f"{settings.api_prefix}/policy")
def get_policy() -> dict[str, Any]:
    return runtime.fusion.current_policy()


@app.post(f"{settings.api_prefix}/policy")
async def update_policy(request: PolicyUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    async with runtime.state_lock:
        runtime.fusion.update_policy(request.payload)
        db.add(
            PolicyVersionRecord(
                version_name=f"policy-{uuid4().hex[:8]}",
                payload=runtime.fusion.current_policy(),
            )
        )
        db.add(
            CaseEventRecord(
                case_id="policy_lab",
                event_type="policy_update",
                actor=request.actor,
                payload=runtime.fusion.current_policy(),
            )
        )
        db.flush()
        db.commit()
        await _publish_state(db)
        return runtime.fusion.current_policy()


@app.post(f"{settings.api_prefix}/scenarios/{{scenario_id}}/start")
async def start_scenario(scenario_id: str) -> dict[str, Any]:
    if scenario_id not in runtime.scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    if settings.demo_flow_lock:
        with session_scope() as db:
            if not _has_demo_live_payment(db):
                raise HTTPException(
                    status_code=409,
                    detail="Demo mode is locked to the live payment flow. Seed the baseline and complete one live payment before opening Trust Replay.",
                )
    if runtime.runner and not runtime.runner.done():
        runtime.runner.cancel()
    runtime.runner = asyncio.create_task(_run_scenario(scenario_id))
    return {"ok": True, "scenarioId": scenario_id}


@app.websocket("/ws/live")
async def live_ws(websocket: WebSocket) -> None:
    await runtime.broadcast.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime.broadcast.disconnect(websocket)
    except Exception:
        await runtime.broadcast.disconnect(websocket)
