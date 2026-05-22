"use client";

import { compactNumber, formatTimestamp } from "./formatters";
import TrustStatePill from "./trust-state-pill";

export default function ReplayPanel({
  scenarios,
  currentScenarioId,
  replaySteps,
  effectiveReplayIndex,
  replayContext,
  demoFlow,
  launchingScenario,
  onStartScenario,
  onFollowLive,
  onReplayIndexChange
}) {
  const replayLocked = Boolean(demoFlow?.locked && !demoFlow?.livePaymentSeen);
  const followLabel = replayContext?.source === "case"
    ? "Follow latest case step"
    : replayContext?.isRunning
      ? "Follow replay"
      : replaySteps.length
        ? "Return to live context"
        : "Follow live";
  const replayStatus = replayLocked
    ? "Demo mode is locked to the live payment proof. Seed baseline context, complete one live payment, then open Trust Replay."
    : !replayContext?.hasReplay
    ? "No replay sequence is loaded. Live transaction state remains active, and the case timeline stays available as the fallback investigation path."
    : replayContext.mode === "replay-ready"
      ? "Scenario replay is ready for inspection. Live queue, Signal Rail, and case focus remain in the operational context until you pin a replay step."
    : replayContext.mode === "live-case-ready"
      ? "Live case replay is ready from persisted chronology. Select a step to inspect graph, evidence, and trust-state history."
    : replayContext.mode === "selected-case"
      ? "Replay is active, but the investigation view remains pinned to the selected case."
      : replayContext.mode === "manual-step"
        ? `Pinned to replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}: ${replayContext.activeStepLabel || "selected chronology step"}.`
        : `Following replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}: ${replayContext.activeStepLabel || "latest chronology step"}.`;
  const activeStep = replaySteps[effectiveReplayIndex] || null;

  return (
    <section className="panel replay-panel">
      <div className="replay-header">
        <div>
          <p className="eyebrow">Trust Replay</p>
          <h2>Reconstruct trust fracture in time</h2>
          <p className="replay-context-copy">{replayStatus}</p>
        </div>
        <button
          type="button"
          className="ghost-button"
          onClick={onFollowLive}
          disabled={!replaySteps.length || replayContext?.mode === "selected-case" || replayContext?.mode === "live" || replayContext?.mode === "replay-ready"}
        >
          {followLabel}
        </button>
      </div>

      <div className="replay-status-grid">
        <div className="replay-status-card">
          <span className="ops-overview-label">Mode</span>
          <strong>
            {replayContext?.mode === "manual-step"
              ? "Pinned step"
              : replayContext?.mode === "replay-ready"
                ? "Replay ready"
              : replayContext?.mode === "selected-case"
                ? "Pinned case"
                : replayContext?.hasReplay
                  ? "Follow chronology"
                  : "Live context"}
          </strong>
          <span>{replayContext?.hasReplay ? `${replayContext.totalSteps} replay checkpoints loaded` : "Replay unlocks from live checkpoints or scenario playback."}</span>
        </div>
        <div className="replay-status-card">
          <span className="ops-overview-label">Active step</span>
          <strong>{activeStep?.label || "Awaiting replay step"}</strong>
          <span>{activeStep?.timestamp ? formatTimestamp(activeStep.timestamp) : "Timeline-only investigation remains active."}</span>
        </div>
        <div className="replay-status-card">
          <span className="ops-overview-label">Trust state</span>
          <strong>{activeStep?.trustState || "Healthy"}</strong>
          <span>{activeStep ? `${compactNumber(activeStep.fusedScore)} fused at this checkpoint` : "No replay checkpoint selected."}</span>
        </div>
      </div>

      <div className="scenario-row">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            className={`scenario-card ${currentScenarioId === scenario.id ? "active" : ""}`}
            onClick={() => onStartScenario(scenario.id)}
            disabled={replayLocked}
          >
            <div>
              <p>{scenario.title}</p>
              <span>{scenario.subtitle}</span>
            </div>
            <strong>{launchingScenario === scenario.id ? "Loading..." : `${scenario.total_steps} steps`}</strong>
          </button>
        ))}
      </div>

      <div className="timeline-shell">
        <div className="timeline-shell-header">
          <div>
            <span className="context-label">Replay scrubber</span>
            <p className="muted-copy">
              Step selection keeps graph, timeline, and Evidence Lens synchronized without creating a second scoring path.
            </p>
          </div>
          {activeStep && <TrustStatePill value={activeStep.trustState} />}
        </div>
        <input
          type="range"
          min={0}
          max={Math.max(0, replaySteps.length - 1)}
          value={Math.min(Math.max(0, effectiveReplayIndex), Math.max(0, replaySteps.length - 1))}
          onChange={(event) => onReplayIndexChange(Number(event.target.value))}
          disabled={!replaySteps.length}
        />
        <div className="timeline-points">
          {replaySteps.map((step, index) => (
            <button
              key={`${step.caseId}-${step.index}`}
              type="button"
              className={index === effectiveReplayIndex ? "active" : ""}
              onClick={() => onReplayIndexChange(index)}
            >
              <div className="timeline-point-head">
                <span>{step.label}</span>
                <TrustStatePill value={step.trustState} />
              </div>
              <strong>{compactNumber(step.fusedScore)} fused</strong>
              <span>{formatTimestamp(step.timestamp)}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
