from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone


API_BASE = os.getenv("RAYZAA_API_BASE", "http://127.0.0.1:8000")
INGEST_URL = f"{API_BASE}/api/transactions/ingest"


def iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


BASELINE_EVENTS = [
    {
        "transaction_id": "seed_payeasy_001",
        "timestamp": iso_minutes_ago(14),
        "account_id": "ACC-PAYEASY-1024",
        "counterparty_id": "PAYEASY_SETTLEMENT",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "channel": "upi",
        "amount": 2200,
        "city": "Bengaluru",
        "country": "IN",
        "payment_format": "upi",
        "from_bank": "bank_of_india",
        "to_bank": "hdfc_bank",
        "payment_currency": "INR",
        "receiving_currency": "INR",
        "geo_distance_km": 6,
        "dormant_days": 2,
        "scenario_note": "PayEasy baseline traffic remains stable before the live judge payment.",
        "custom_copilot_focus": "Establish a clean baseline before the live checkout arrives",
    },
    {
        "transaction_id": "seed_payeasy_002",
        "timestamp": iso_minutes_ago(10),
        "account_id": "ACC-PAYEASY-3301",
        "counterparty_id": "PAYEASY_SETTLEMENT",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "channel": "upi",
        "amount": 1800,
        "city": "Bhubaneswar",
        "country": "IN",
        "payment_format": "upi",
        "from_bank": "icici_bank",
        "to_bank": "hdfc_bank",
        "payment_currency": "INR",
        "receiving_currency": "INR",
        "geo_distance_km": 20,
        "dormant_days": 2,
        "scenario_note": "Shared-device context begins to build around the PayEasy settlement path without forcing an early escalation.",
        "custom_copilot_focus": "Establish shared-device context while trust remains stable before the live payment lands",
    },
    {
        "transaction_id": "seed_payeasy_003",
        "timestamp": iso_minutes_ago(6),
        "account_id": "ACC-PAYEASY-1024",
        "counterparty_id": "PAYEASY_SETTLEMENT",
        "device_id": "DEV-PAYEASY-17",
        "merchant_id": "MER-PAYEASY",
        "channel": "upi",
        "amount": 1950,
        "city": "Bengaluru",
        "country": "IN",
        "payment_format": "upi",
        "from_bank": "bank_of_india",
        "to_bank": "hdfc_bank",
        "payment_currency": "INR",
        "receiving_currency": "INR",
        "geo_distance_km": 12,
        "dormant_days": 1,
        "scenario_note": "Recent sender activity builds enough context for a live dormant reactivation payment to stand out.",
        "custom_copilot_focus": "Prepare the live account history so the next payment shows a meaningful trust shift",
    },
]


def post_event(event: dict) -> tuple[bool, str]:
    request = urllib.request.Request(
        INGEST_URL,
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return True, payload.get("transactionId", event["transaction_id"])
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            return False, f"duplicate:{event['transaction_id']}"
        raise


def main() -> None:
    seeded = 0
    skipped = 0
    for event in BASELINE_EVENTS:
        ok, detail = post_event(event)
        if ok:
            seeded += 1
            print(f"seeded {detail}")
        else:
            skipped += 1
            print(f"skipped {detail}")
    print(json.dumps({"seeded": seeded, "skipped": skipped, "apiBase": API_BASE}, indent=2))


if __name__ == "__main__":
    main()
