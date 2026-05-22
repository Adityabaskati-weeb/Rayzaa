"use client";

import CaseTimeline from "./case-timeline";
import { compactNumber, formatFeature, formatTimestamp } from "./formatters";
import PolicyPanel from "./policy-panel";
import QueuePanel from "./queue-panel";
import TrustStatePill from "./trust-state-pill";

const EVIDENCE_SECTIONS = [
  {
    key: "modelEvidence",
    title: "Model Evidence",
    source: "Model",
    emptyCopy: "No model-driven evidence is above the current explanation threshold."
  },
  {
    key: "graphEvidence",
    title: "Graph Evidence",
    source: "Graph",
    emptyCopy: "No relationship-driven graph pressure is active yet."
  },
  {
    key: "driftEvidence",
    title: "Drift Evidence",
    source: "Drift",
    emptyCopy: "No behavioral drift is outside the operating baseline."
  },
  {
    key: "policyEvidence",
    title: "Policy Evidence",
    source: "Policy",
    emptyCopy: "No threshold or guardrail promotion is active yet."
  }
];

function getEvidenceGroup(evidence, key) {
  const group = evidence?.[key];
  if (!group || typeof group !== "object") {
    return { items: [], shapValues: [] };
  }
  return {
    items: Array.isArray(group.items) ? group.items : [],
    shapValues: Array.isArray(group.shapValues) ? group.shapValues : []
  };
}

function formatActionLabel(action) {
  return action.replaceAll("_", " ");
}

function isBaselineCase(caseRecord) {
  return Boolean(caseRecord?.isBaselineSeed || String(caseRecord?.lastTransactionId || "").startsWith("seed_"));
}

function formatSourceLabel(source, caseRecord = null) {
  if (source === "live") {
    return isBaselineCase(caseRecord) ? "Baseline context" : "Live intake";
  }
  if (source === "replay") {
    return "Replay case";
  }
  return source || "Pending source";
}

function replayContextCopy(replayContext, focusCase) {
  if (!replayContext?.hasReplay) {
    return "Live investigation context is active.";
  }
  if (replayContext.mode === "live-case-ready") {
    return `Replay is available for ${focusCase?.caseId || "the active case"} using persisted chronology. Select a step to inspect the trust transition path.`;
  }
  if (replayContext.mode === "selected-case") {
    return `Replay is active. This view stays pinned to ${formatSourceLabel(replayContext.caseSource, focusCase).toLowerCase()} ${focusCase?.caseId || "case"} until selection changes.`;
  }
  if (replayContext.mode === "manual-step") {
    return `Pinned to replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}: ${replayContext.activeStepLabel || "selected chronology step"}.`;
  }
  return `Following replay step ${replayContext.activeStepIndex}/${replayContext.totalSteps}: ${replayContext.activeStepLabel || "latest chronology step"}.`;
}

function caseMetricItems(focusCase, evidence) {
  const scores = evidence?.scores || {};
  return [
    { key: "fraud", label: "Fraud", value: Number(scores.fraud || focusCase?.fraudScore || 0) },
    { key: "graph", label: "Graph", value: Number(scores.graph || focusCase?.graphScore || 0) },
    { key: "drift", label: "Drift", value: Number(scores.drift || focusCase?.driftScore || 0) },
    { key: "fused", label: "Fused", value: Number(scores.fused || focusCase?.fusedScore || 0) }
  ];
}

export default function EvidenceLensPanel({
  activeTab,
  onTabChange,
  focusCase,
  trustState,
  evidence,
  replayContext,
  busyAction,
  onTakeAction,
  queue,
  onSelectCase,
  selectedCaseId,
  policyDraft,
  onPolicyChange,
  onSavePolicy
}) {
  const caseSource = focusCase?.source || evidence.source || "live";
  const metrics = caseMetricItems(focusCase, evidence);

  return (
    <aside className="panel evidence-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Evidence Lens</p>
          <h2>Next actions</h2>
        </div>
        <div className="tab-strip">
          {["evidence", "queue", "policy"].map((tab) => (
            <button
              key={tab}
              type="button"
              className={tab === activeTab ? "active" : ""}
              onClick={() => onTabChange(tab)}
            >
              {tab === "evidence" ? "Case Studio" : tab === "queue" ? "Escalation Queue" : "Policy Lab"}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "evidence" && (
        <div className="evidence-scroll">
          <div className="case-card">
            <div className="case-header">
              <div>
                <p className="eyebrow">Investigation Summary</p>
                <h3>{focusCase?.title || "No focus case selected"}</h3>
              </div>
              <div className="case-header-meta">
                <TrustStatePill value={trustState} />
                <span className="case-source">{formatSourceLabel(caseSource, focusCase)}</span>
              </div>
            </div>
            <p className="copilot-summary">
              {focusCase?.summary ||
                "Rayzaa will surface a backend-derived case summary here once a case enters active investigation."}
            </p>
            <div className="case-metadata-grid">
              <div className="case-metadata-cell">
                <span className="context-label">Case</span>
                <strong>{focusCase?.caseId || "pending-case"}</strong>
                <span>{focusCase?.lastTransactionId || "Awaiting persisted transaction"}</span>
              </div>
              <div className="case-metadata-cell">
                <span className="context-label">Updated</span>
                <strong>{formatTimestamp(focusCase?.updatedAt)}</strong>
                <span>{formatSourceLabel(caseSource, focusCase)}</span>
              </div>
            </div>
            <div className="case-metric-grid">
              {metrics.map((item) => (
                <div key={item.key} className="case-metric-card">
                  <span>{item.label}</span>
                  <strong>{compactNumber(item.value)}%</strong>
                </div>
              ))}
            </div>
            <div className={`context-banner ${replayContext?.mode || "live"}`}>
              <span className="context-label">Context</span>
              <p>{replayContextCopy(replayContext, focusCase)}</p>
            </div>
            <div className="action-row">
              {["approve", "review", "escalate_aml"].map((action) => (
                <button
                  key={action}
                  type="button"
                  className={`action-button ${action}`}
                  onClick={() => onTakeAction(action)}
                  disabled={!focusCase?.caseId || busyAction === action || caseSource !== "live"}
                >
                  {busyAction === action ? "Working..." : formatActionLabel(action)}
                </button>
              ))}
            </div>
          </div>

          <div className="info-block">
            <div className="info-header">
              <h4>Recommended next actions</h4>
              <span>{focusCase?.caseId || "pending-case"}</span>
            </div>
            <p className="muted-copy">
              Operator actions remain backend-authoritative. Replay cases stay read-only to preserve chronology integrity.
            </p>
            <ul className="stack-list">
              {(focusCase?.recommendedActions || []).map((item) => (
                <li key={item}>{item}</li>
              ))}
              {!focusCase?.recommendedActions?.length && <li>Awaiting case creation.</li>}
            </ul>
          </div>

          {EVIDENCE_SECTIONS.map((section) => {
            const group = getEvidenceGroup(evidence, section.key);
            const hasItems = group.items.length > 0;
            const hasShapValues = section.key === "modelEvidence" && group.shapValues.length > 0;

            return (
              <div key={section.key} className="info-block evidence-section">
                <div className="info-header">
                  <h4>{section.title}</h4>
                  <span>{group.items.length}{group.items.length === 1 ? " signal" : " signals"}</span>
                </div>
                <div className="evidence-section-body">
                  {hasItems ? (
                    <div className="evidence-list">
                      {group.items.map((item) => (
                        <div key={item.id || item.detail} className="evidence-row">
                          <div className="evidence-row-head">
                            <strong>{item.label || `${section.source} signal`}</strong>
                            <span className="evidence-source-tag">{item.source || section.source}</span>
                          </div>
                          <p>{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted-copy">{section.emptyCopy}</p>
                  )}

                  {section.key === "modelEvidence" && (
                    <div className="evidence-shap-block">
                      <div className="evidence-subheader">
                        <h5>SHAP contribution view</h5>
                        <span>{group.shapValues.length} local factors</span>
                      </div>
                      <div className="factor-list">
                        {group.shapValues.map((item) => (
                          <div key={item.feature} className="factor-row">
                            <div>
                              <div className="factor-row-head">
                                <strong>{item.label || formatFeature(item.feature)}</strong>
                                <span className="evidence-source-tag">Model</span>
                              </div>
                              <span>Value {compactNumber(item.value)}</span>
                            </div>
                            <b className={item.impact >= 0 ? "positive" : "negative"}>
                              {item.impact >= 0 ? "+" : ""}
                              {compactNumber(item.impact)}
                            </b>
                          </div>
                        ))}
                        {!hasShapValues && <p className="muted-copy">No local SHAP profile is cached yet.</p>}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          <CaseTimeline timeline={focusCase?.timeline || []} replayContext={replayContext} />
        </div>
      )}

      {activeTab === "queue" && <QueuePanel queue={queue} onSelectCase={onSelectCase} selectedCaseId={selectedCaseId} />}

      {activeTab === "policy" && (
        <PolicyPanel
          policyDraft={policyDraft}
          busyAction={busyAction}
          onPolicyChange={onPolicyChange}
          onSavePolicy={onSavePolicy}
        />
      )}
    </aside>
  );
}
