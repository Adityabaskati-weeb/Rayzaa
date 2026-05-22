"use client";

import { formatTimestamp, trustClass } from "./formatters";

function timelineContextCopy(replayContext) {
  if (!replayContext?.hasReplay) {
    return "Chronology is rendering from persisted live case events.";
  }
  if (replayContext.mode === "live-case-ready") {
    return "Replay is available from persisted live checkpoints. Select a step to inspect the chronology path.";
  }
  if (replayContext.mode === "selected-case") {
    return "Replay is active, but chronology remains pinned to the selected case.";
  }
  if (replayContext.mode === "manual-step") {
    return `Pinned to replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}.`;
  }
  return `Following replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}.`;
}

function sourceLabel(item) {
  const source = item?.payload?.source;
  if (source === "live") {
    return "Live intake";
  }
  if (source === "replay") {
    return "Replay";
  }
  if (source === "analyst") {
    return "Analyst";
  }
  return null;
}

function eventTypeLabel(item) {
  if (item.eventType === "trust_transition") {
    return "Trust transition";
  }
  if (item.eventType === "queue_transition") {
    return "Queue routing";
  }
  if (item.eventType === "analyst_action") {
    return "Analyst action";
  }
  if (
    item.eventType === "alert_dispatched" ||
    item.eventType === "alert_skipped" ||
    item.eventType === "alert_failed"
  ) {
    return "Alert";
  }
  if (item.eventType === "transaction_ingested") {
    return "Live intake";
  }
  return "Case event";
}

function detailBadge(item) {
  if (item.eventType === "trust_transition") {
    const from = item.payload?.from || "Unknown";
    const to = item.payload?.to || "Unknown";
    return `${from} -> ${to}`;
  }
  if (item.eventType === "queue_transition") {
    return String(item.payload?.status || "review").replaceAll("_", " ");
  }
  if (item.eventType === "analyst_action") {
    return String(item.payload?.action || "updated").replaceAll("_", " ");
  }
  if (
    item.eventType === "alert_dispatched" ||
    item.eventType === "alert_skipped" ||
    item.eventType === "alert_failed"
  ) {
    return item.payload?.provider || "telegram";
  }
  return null;
}

function itemClassName(item) {
  const classes = ["case-timeline-item", `timeline-${item.eventType}`];
  if (item.eventType === "trust_transition") {
    classes.push(trustClass(item.payload?.to || "Healthy"));
  }
  if (item.eventType === "queue_transition" && item.payload?.status === "escalated") {
    classes.push("timeline-escalated");
  }
  return classes.join(" ");
}

export default function CaseTimeline({ timeline, replayContext }) {
  return (
    <div className="info-block case-timeline">
      <div className="info-header">
        <h4>Case timeline</h4>
        <span>{timeline.length} events</span>
      </div>
      <div className={`timeline-context ${replayContext?.mode || "live"}`}>
        <span className="context-label">Replay marker</span>
        <p>{timelineContextCopy(replayContext)}</p>
      </div>
      <ol className="case-timeline-list">
        {timeline.map((item) => (
          <li key={item.id} className={itemClassName(item)}>
            <div className="case-timeline-marker" />
            <div className="case-timeline-body">
              <div className="case-timeline-header">
                <div className="case-timeline-title">
                  <span className="case-timeline-type">{eventTypeLabel(item)}</span>
                  <strong>{item.label}</strong>
                </div>
                <time dateTime={item.createdAt || ""}>{formatTimestamp(item.createdAt)}</time>
              </div>
              <p className="case-timeline-detail">{item.detail}</p>
              <div className="case-timeline-meta">
                {sourceLabel(item) && <span className="timeline-tag">{sourceLabel(item)}</span>}
                {detailBadge(item) && <span className="timeline-tag emphasis">{detailBadge(item)}</span>}
                {item.actor && item.actor !== "system" && <span className="timeline-tag">Actor {item.actor}</span>}
              </div>
            </div>
          </li>
        ))}
        {!timeline.length && <li className="timeline-empty">No persisted case activity yet.</li>}
      </ol>
    </div>
  );
}
