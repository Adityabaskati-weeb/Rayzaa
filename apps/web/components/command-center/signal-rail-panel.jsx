"use client";

import { compactNumber, currency, formatTimestamp, trustClass } from "./formatters";
import TrustStatePill from "./trust-state-pill";

function signalSourceLabel(item) {
  if (item?.source === "live") {
    return item?.isBaselineSeed ? "Baseline seed" : "Live intake";
  }
  if (item?.source === "replay") {
    return "Replay";
  }
  return "Pending";
}

export default function SignalRailPanel({ signalRail, onSelectCase }) {
  return (
    <aside className="panel signal-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Signal Rail</p>
          <h2>What just happened</h2>
        </div>
      </div>
      <div className="signal-list">
        {signalRail.map((item) => (
          <button
            key={item.transactionId}
            className={`signal-card ${trustClass(item.trustState)}`}
            type="button"
            onClick={() => onSelectCase(item)}
          >
            <div className="signal-kicker">
              <span className="timeline-tag">{signalSourceLabel(item)}</span>
              <time dateTime={item.timestamp || ""}>{formatTimestamp(item.timestamp)}</time>
            </div>
            <div className="signal-topline">
              <strong>{item.accountId}</strong>
              <strong>{currency(item.amount)}</strong>
            </div>
            <div className="signal-meta">
              <span>{item.channel.toUpperCase()}</span>
              <span>{String(item.paymentRail || "").replaceAll("_", " ")}</span>
              <span>{item.merchantId}</span>
              <span>{item.counterpartyId}</span>
            </div>
            <p className="signal-note">{item.scenarioNote || "No operator note attached to this event."}</p>
            <div className="signal-bottomline">
              <div className="signal-identity">
                <span>{item.transactionId}</span>
                <span>Fused {compactNumber(item.fusedScore)}%</span>
              </div>
              <TrustStatePill value={item.trustState} />
            </div>
          </button>
        ))}
        {!signalRail.length && (
          <div className="empty-state">
            <p>No live signals yet.</p>
            <span>Seed the baseline or complete one PayEasy payment to populate the operational rail.</span>
          </div>
        )}
      </div>
    </aside>
  );
}
