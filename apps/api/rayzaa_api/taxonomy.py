from __future__ import annotations

from typing import Final

CANONICAL_PAYMENT_RAILS: Final[tuple[str, ...]] = (
    "account_transfer",
    "internal_transfer",
    "cheque",
    "card",
    "cash",
    "crypto",
)

PAYMENT_RAIL_LABELS: Final[dict[str, str]] = {
    "account_transfer": "Account transfer rail",
    "internal_transfer": "Internal transfer rail",
    "cheque": "Cheque rail",
    "card": "Card rail",
    "cash": "Cash rail",
    "crypto": "Crypto rail",
}

PAYMENT_RAIL_ALIASES: Final[dict[str, str]] = {
    "ach": "account_transfer",
    "bank_transfer": "account_transfer",
    "bank transfer": "account_transfer",
    "transfer": "account_transfer",
    "upi": "account_transfer",
    "wire": "account_transfer",
    "reinvestment": "internal_transfer",
    "internal_transfer": "internal_transfer",
    "internal transfer": "internal_transfer",
    "cheque": "cheque",
    "check": "cheque",
    "credit_card": "card",
    "credit card": "card",
    "debit_card": "card",
    "debit card": "card",
    "card": "card",
    "cash": "cash",
    "bitcoin": "crypto",
    "crypto": "crypto",
}

CHANNEL_ALIASES: Final[dict[str, str]] = {
    "upi": "upi",
    "bank_transfer": "bank_transfer",
    "bank transfer": "bank_transfer",
    "wire": "bank_transfer",
    "ach": "bank_transfer",
    "credit_card": "card",
    "credit card": "card",
    "card": "card",
    "cash": "cash",
    "bitcoin": "crypto",
    "crypto": "crypto",
}


def canonicalize_payment_rail(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    normalized = normalized.replace("__", "_")
    return PAYMENT_RAIL_ALIASES.get(normalized, normalized)


def canonicalize_channel(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    normalized = normalized.replace("__", "_")
    return CHANNEL_ALIASES.get(normalized, normalized)


def payment_rail_label(value: str) -> str:
    canonical = canonicalize_payment_rail(value)
    return PAYMENT_RAIL_LABELS.get(canonical, canonical.replace("_", " ").title())
