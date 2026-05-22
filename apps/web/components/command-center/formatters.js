export const DEFAULT_POLICY = {
  fraud_weight: 0.34,
  graph_weight: 0.36,
  drift_weight: 0.3,
  watch_threshold: 34,
  fractured_threshold: 56,
  escalated_threshold: 72,
  graph_boost_multiplier: 1.15
};

export function currency(amount) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(Number(amount || 0));
}

export function compactNumber(value) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export function formatTimestamp(value) {
  if (!value) {
    return "Pending";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Pending";
  }
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "short"
  }).format(date);
}

export function trustClass(value) {
  return `state-${String(value || "Healthy").toLowerCase()}`;
}

export function formatFeature(name) {
  const map = {
    amount_log: "Amount scale",
    sender_velocity_1h: "Sender velocity",
    receiver_velocity_1h: "Receiver velocity",
    pair_velocity_24h: "Pair velocity",
    sender_unique_counterparties_24h: "Counterparty spread",
    amount_ratio_to_sender_avg: "Amount vs sender average",
    hour_of_day: "Hour of day",
    is_cross_bank: "Cross-bank movement",
    is_self_transfer: "Self-transfer pattern",
    is_cross_currency: "Cross-currency movement",
    fmt_account_transfer: "Account transfer rail",
    fmt_internal_transfer: "Internal transfer rail",
    fmt_cheque: "Cheque rail",
    fmt_card: "Card rail",
    fmt_cash: "Cash rail",
    fmt_crypto: "Crypto rail"
  };
  return map[name] || name;
}
