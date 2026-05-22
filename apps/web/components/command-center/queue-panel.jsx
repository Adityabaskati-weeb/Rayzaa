"use client";

import { compactNumber, formatTimestamp } from "./formatters";
import TrustStatePill from "./trust-state-pill";

function statusLabel(status) {
  if (status === "escalated") {
    return "Escalated";
  }
  if (status === "review") {
    return "Manual review";
  }
  return status || "Pending";
}

function sourceLabel(source) {
  if (source === "live") {
    return "Live intake";
  }
  if (source === "replay") {
    return "Replay";
  }
  return source || "Pending";
}

export default function QueuePanel({ queue, onSelectCase, selectedCaseId }) {
  return (
    <div className="queue-list">
      {queue.map((item) => (
        <button
          key={item.caseId}
          type="button"
          className={[
            "queue-card",
            item.caseId === selectedCaseId ? "is-selected" : "",
            item.status === "escalated" ? "is-escalated" : "is-review"
          ]
            .filter(Boolean)
            .join(" ")}
          onClick={() => onSelectCase(item.caseId)}
        >
          <div className="queue-head">
            <div className="queue-title-stack">
              <span className="queue-priority-chip">Priority {item.severity || 0}</span>
              <h4>{item.title}</h4>
              <span className="queue-status-line">
                {statusLabel(item.status)} | {sourceLabel(item.source)}
              </span>
            </div>
            <TrustStatePill value={item.trustState} />
          </div>
          <p className="queue-summary">{item.summary}</p>
          <div className="queue-meta-grid">
            <div className="queue-meta-cell">
              <span>Entered</span>
              <strong>{formatTimestamp(item.queueEnteredAt || item.updatedAt)}</strong>
            </div>
            <div className="queue-meta-cell">
              <span>Fused</span>
              <strong>{compactNumber(item.fusedScore)}%</strong>
            </div>
          </div>
          <div className="queue-foot">
            <span>Updated {formatTimestamp(item.updatedAt)}</span>
            <strong>{item.status === "escalated" ? "Escalation ready" : "Review ready"}</strong>
          </div>
        </button>
      ))}
      {!queue.length && (
        <div className="empty-state">
          <p>No active queue entries.</p>
          <span>Review and escalated cases will collect here as trust pressure rises.</span>
        </div>
      )}
    </div>
  );
}
