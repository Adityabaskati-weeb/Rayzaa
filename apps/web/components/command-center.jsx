"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getRuntimeConfig } from "../lib/runtime-config";
import EvidenceLensPanel from "./command-center/evidence-lens-panel";
import { compactNumber, DEFAULT_POLICY, formatTimestamp } from "./command-center/formatters";
import QueuePanel from "./command-center/queue-panel";
import ReplayPanel from "./command-center/replay-panel";
import SignalRailPanel from "./command-center/signal-rail-panel";
import TrustStatePill from "./command-center/trust-state-pill";

const TrustGraph = dynamic(() => import("./trust-graph"), {
  ssr: false,
  loading: () => (
    <div className="graph-shell">
      <div className="graph-toolbar">
        <div>
          <p className="eyebrow">Trust Memory Graph</p>
          <h3>Loading relationship topology</h3>
        </div>
        <div className="state-pill state-healthy">Loading</div>
      </div>
      <div className="graph-canvas graph-loading" />
    </div>
  )
});

const { apiBase: API_BASE, wsUrl: WS_URL, backendConfigured } = getRuntimeConfig();
const EMPTY_GRAPH = { nodes: [], edges: [] };
const EVIDENCE_GROUP_KEYS = ["modelEvidence", "graphEvidence", "driftEvidence", "policyEvidence"];
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);
const POLL_INTERVAL_MS = 10000;
const MODEL_SCORECARD_ROWS = [
  { label: "Model", value: "XGBoost" },
  { label: "Neural sidecar", value: "Planned anomaly sidecar" },
  { label: "Artifact", value: "benchmark_v3" },
  { label: "Dataset", value: "IBM AML" },
  { label: "ROC AUC", value: "0.9445" },
  { label: "PR AUC", value: "0.8436" },
  { label: "Precision @ 0.5", value: "0.7204" },
  { label: "Recall @ 0.5", value: "0.7901" },
  { label: "F1 @ 0.5", value: "0.7536" },
];

function isBaselineCase(caseRecord) {
  return Boolean(caseRecord?.isBaselineSeed || String(caseRecord?.lastTransactionId || "").startsWith("seed_"));
}

function sourceLabel(source, item = null) {
  if (source === "live") {
    return isBaselineCase(item) ? "Baseline context" : "Live intake";
  }
  if (source === "replay") {
    return "Replay";
  }
  return source || "Pending";
}

function replayModeLabel(replayContext) {
  if (!replayContext?.hasReplay) {
    return "Timeline-only";
  }
  if (replayContext.mode === "replay-ready") {
    return "Replay ready";
  }
  if (replayContext.mode === "selected-case") {
    return "Pinned case";
  }
  if (replayContext.mode === "manual-step") {
    return "Pinned replay step";
  }
  if (replayContext.mode === "live-case-ready") {
    return "Checkpoint replay";
  }
  if (replayContext.mode === "follow-replay") {
    return "Following replay";
  }
  return "Live context";
}

function shouldUseHostedPolling() {
  if (typeof window === "undefined") {
    return false;
  }
  return !LOCAL_HOSTS.has(window.location.hostname);
}

function connectionLabel(connection) {
  if (connection === "live") {
    return "Live stream";
  }
  if (connection === "synced") {
    return "Synced";
  }
  if (connection === "degraded") {
    return "Attention";
  }
  return "Connecting";
}

export default function CommandCenter() {
  const [state, setState] = useState(null);
  const [activeTab, setActiveTab] = useState("evidence");
  const [selectedCase, setSelectedCase] = useState(null);
  const [manualReplayIndex, setManualReplayIndex] = useState(null);
  const [policyDraft, setPolicyDraft] = useState(DEFAULT_POLICY);
  const [busyAction, setBusyAction] = useState("");
  const [launchingScenario, setLaunchingScenario] = useState("");
  const [connection, setConnection] = useState("connecting");
  const selectedCaseRef = useRef(null);
  const caseRefreshTimerRef = useRef(null);
  const keepAliveRef = useRef(null);
  const reconnectRef = useRef(null);
  const narrativeRecoveryRef = useRef("");
  const pollingOnlyRef = useRef(false);

  async function loadState(options = {}) {
    const { preserveLiveConnection = false } = options;
    const response = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
    const payload = await response.json();
    setState(payload);
    setPolicyDraft(payload.policy || DEFAULT_POLICY);
    if (!preserveLiveConnection) {
      setConnection((current) => (current === "live" ? current : "synced"));
    }
  }

  async function loadCase(caseId, options = {}) {
    const { resetReplayIndex = true, activateEvidenceTab = true } = options;
    const response = await fetch(`${API_BASE}/api/cases/${caseId}`, { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (resetReplayIndex) {
      setManualReplayIndex(null);
    }
    setSelectedCase(payload);
    if (activateEvidenceTab) {
      setActiveTab("evidence");
    }
  }

  function selectCaseFromSignal(item) {
    loadCase(item.caseId || `case_${String(item.accountId || "").toLowerCase().replaceAll("-", "_")}`);
  }

  function handlePolicyChange(key, value) {
    setPolicyDraft((current) => ({
      ...current,
      [key]: value
    }));
  }

  useEffect(() => {
    if (!backendConfigured) {
      setConnection("degraded");
      return;
    }
    pollingOnlyRef.current = shouldUseHostedPolling();
    loadState({ preserveLiveConnection: false }).catch(() => {
      setConnection("degraded");
    });
  }, []);

  useEffect(() => {
    if (!backendConfigured) {
      return undefined;
    }

    pollingOnlyRef.current = shouldUseHostedPolling();
    const poller = window.setInterval(() => {
      loadState({ preserveLiveConnection: true }).catch(() => {
        if (pollingOnlyRef.current) {
          setConnection("degraded");
        }
      });
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(poller);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const routeCaseId = new URLSearchParams(window.location.search).get("case");
    if (routeCaseId) {
      loadCase(routeCaseId).catch(() => {});
    }
  }, []);

  useEffect(() => {
    selectedCaseRef.current = selectedCase;
  }, [selectedCase]);

  useEffect(() => {
    if (!selectedCase) {
      return;
    }
    narrativeRecoveryRef.current = selectedCase.caseId || "";
  }, [selectedCase?.caseId]);

  useEffect(() => {
    return () => {
      if (caseRefreshTimerRef.current) {
        window.clearTimeout(caseRefreshTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!backendConfigured) {
      setConnection("degraded");
      return undefined;
    }
    if (shouldUseHostedPolling()) {
      setConnection("synced");
      return undefined;
    }
    let closed = false;

    function connect() {
      if (closed) {
        return;
      }

      const socket = new WebSocket(WS_URL);
      setConnection("connecting");

      socket.onopen = () => {
        setConnection("live");
        keepAliveRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("keepalive");
          }
        }, 12000);
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "state") {
            setState(message.payload);
            setPolicyDraft((current) => ({
              ...current,
              ...(message.payload.policy || {})
            }));
            const pinnedCase = selectedCaseRef.current;
            if (!pinnedCase) {
              return;
            }
            if (message.payload.focusCase?.caseId === pinnedCase.caseId) {
              setSelectedCase(message.payload.focusCase);
              return;
            }
            const shouldRefreshPinnedCase =
              pinnedCase.source === "live" &&
              (
                message.payload.signalRail?.some((item) => item.caseId === pinnedCase.caseId) ||
                message.payload.queue?.some((item) => item.caseId === pinnedCase.caseId) ||
                message.payload.operations?.latestAlert?.caseId === pinnedCase.caseId
              );
            if (shouldRefreshPinnedCase) {
              if (caseRefreshTimerRef.current) {
                window.clearTimeout(caseRefreshTimerRef.current);
              }
              caseRefreshTimerRef.current = window.setTimeout(() => {
                loadCase(pinnedCase.caseId, { resetReplayIndex: false, activateEvidenceTab: false }).catch(() => {});
              }, 140);
            }
          }
        } catch {
          setConnection("degraded");
        }
      };

      socket.onclose = () => {
        setConnection("reconnecting");
        if (keepAliveRef.current) {
          window.clearInterval(keepAliveRef.current);
        }
        reconnectRef.current = window.setTimeout(connect, 1800);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      closed = true;
      if (keepAliveRef.current) {
        window.clearInterval(keepAliveRef.current);
      }
      if (reconnectRef.current) {
        window.clearTimeout(reconnectRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!state?.focusCase || !selectedCase) {
      return;
    }
    if (state.focusCase.caseId === selectedCase.caseId) {
      setSelectedCase(state.focusCase);
    }
  }, [state?.focusCase, selectedCase?.caseId]);

  useEffect(() => {
    if (!state || selectedCase || state?.system?.status === "running") {
      return;
    }

    const livePaymentSeen = Boolean(state?.operations?.demoFlow?.livePaymentSeen);
    const stateFocusCase = state?.focusCase || null;
    if (!livePaymentSeen || (stateFocusCase && !isBaselineCase(stateFocusCase))) {
      return;
    }
    if (narrativeRecoveryRef.current === "pending" || narrativeRecoveryRef.current === "none") {
      return;
    }

    narrativeRecoveryRef.current = "pending";
    fetch(`${API_BASE}/api/cases`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : []))
      .then((payload) => {
        const cases = Array.isArray(payload) ? payload : Array.isArray(payload?.value) ? payload.value : [];
        const candidate = cases.find((item) => item?.source === "live" && !isBaselineCase(item));
        if (!candidate) {
          narrativeRecoveryRef.current = "none";
          return;
        }
        narrativeRecoveryRef.current = candidate.caseId || "";
        setSelectedCase(candidate);
        setActiveTab("evidence");
      })
      .catch(() => {
        narrativeRecoveryRef.current = "";
      });
  }, [selectedCase, state]);

  const scenarios = state?.scenarios || [];
  const scenarioReplaySteps = state?.replay?.steps || [];
  const focusCase = selectedCase || state?.focusCase || null;
  const usingSelectedCase = Boolean(selectedCase);
  const caseReplaySteps = focusCase?.replaySteps || [];
  const scenarioReplayLoaded = scenarioReplaySteps.length > 0;
  const scenarioReplayActive = scenarioReplayLoaded && state?.system?.status === "running";
  const replaySteps = scenarioReplayLoaded ? scenarioReplaySteps : caseReplaySteps;
  const liveReplayIndex = scenarioReplayLoaded
    ? state?.replay?.activeIndex || 0
    : Math.max(0, replaySteps.length - 1);
  const effectiveReplayIndex = manualReplayIndex ?? liveReplayIndex;
  const activeReplayStep = replaySteps[effectiveReplayIndex] || null;
  const hasReplay = replaySteps.length > 0;
  const replayOverlayActive = scenarioReplayLoaded
    ? scenarioReplayActive
      ? !usingSelectedCase
      : manualReplayIndex !== null
    : manualReplayIndex !== null && activeReplayStep?.caseId === focusCase?.caseId;
  const evidence = replayOverlayActive ? activeReplayStep?.evidence || focusCase?.evidence || {} : focusCase?.evidence || {};
  const graph = replayOverlayActive ? activeReplayStep?.graph || focusCase?.graph || state?.graph || EMPTY_GRAPH : focusCase?.graph || state?.graph || EMPTY_GRAPH;
  const trustState = replayOverlayActive ? activeReplayStep?.trustState || focusCase?.trustState || "Healthy" : focusCase?.trustState || "Healthy";
  const trustLabel = replayOverlayActive
    ? activeReplayStep?.label || "Replay chronology"
    : focusCase
      ? `${focusCase.source === "live" ? "Live intake" : "Replay case"} | ${focusCase.caseId || "case"}`
      : "Live relationship topology";
  const queue = state?.queue || [];
  const operations = state?.operations || {};
  const demoFlow = operations.demoFlow || {};
  const latestAlert = operations.latestAlert || null;
  const baselineSignalCount = (state?.signalRail || []).filter((item) => item.isBaselineSeed).length;
  const latestLiveSignal = (state?.signalRail || []).find((item) => item.source === "live" && !item.isBaselineSeed) || null;
  const focusCaseIsBaseline = isBaselineCase(focusCase);
  const visibleLiveCaseReady = Boolean(focusCase?.source === "live" && !focusCaseIsBaseline);
  const liveNarrativeReady = Boolean(latestLiveSignal || visibleLiveCaseReady);
  const replayAvailableForNarrative = Boolean(demoFlow.livePaymentSeen && hasReplay);
  const trustNarrativeState = liveNarrativeReady
    ? latestLiveSignal?.trustState || (!focusCaseIsBaseline ? focusCase?.trustState : null)
    : null;
  const liveNarrativeLabel = latestLiveSignal
    ? latestLiveSignal.transactionId
    : visibleLiveCaseReady
      ? `${focusCase?.caseId || "Live case"} restored from case history`
      : "Awaiting PayEasy trigger";
  const replayContext = {
    hasReplay,
    source: scenarioReplayLoaded ? "scenario" : caseReplaySteps.length ? "case" : "none",
    mode: !hasReplay
      ? "live"
      : scenarioReplayLoaded
        ? usingSelectedCase
          ? "selected-case"
          : scenarioReplayActive
            ? manualReplayIndex === null
              ? "follow-replay"
              : "manual-step"
            : manualReplayIndex === null
              ? "replay-ready"
              : "manual-step"
        : manualReplayIndex === null
          ? "live-case-ready"
          : "manual-step",
    isRunning: scenarioReplayActive,
    activeStepIndex: hasReplay ? effectiveReplayIndex + 1 : 0,
    totalSteps: replaySteps.length,
    activeStepLabel: activeReplayStep?.label || "",
    caseSource: focusCase?.source || "live",
    selectedCasePinned: usingSelectedCase
  };
  const replayModeDisplay = replayAvailableForNarrative ? replayModeLabel(replayContext) : "Locked until live payment";
  const currentScenario = scenarios.find((item) => item.id === state?.system?.scenarioId) || scenarios[0];
  const statusHeadline = state?.system?.status === "running"
    ? "Incident replay live"
    : liveNarrativeReady
      ? replayContext.mode === "replay-ready"
        ? "Live context restored"
        : "Live payment verified"
      : replayAvailableForNarrative
        ? "Replay ready"
      : "Awaiting live payment";
  const statusTitle = state?.system?.status === "running"
    ? currentScenario?.title || "Trust fracture scenario"
    : replayContext.mode === "replay-ready"
      ? "Replay checkpoints remain available while the live investigation stays primary."
      : liveNarrativeReady
        ? latestLiveSignal
          ? "Live payment monitoring"
          : "Live case history recovered from persisted intake."
        : replayAvailableForNarrative
          ? "Replay checkpoints are available, but the shell has not pinned a non-seed live case yet."
        : "Awaiting PayEasy test payment";
  const queueCounts = {
    review: queue.filter((item) => item.status === "review").length,
    escalated: queue.filter((item) => item.status === "escalated").length
  };
  const demoSequence = [
    {
      id: "baseline",
      step: "01",
      label: "Baseline seeded",
      meta: baselineSignalCount ? `${baselineSignalCount} baseline signals loaded` : "Awaiting baseline context",
      status: baselineSignalCount ? "complete" : "ready"
    },
    {
      id: "live",
      step: "02",
      label: "Live payment",
      meta: liveNarrativeLabel,
      status: liveNarrativeReady ? "complete" : baselineSignalCount ? "ready" : "pending"
    },
    {
      id: "trust",
      step: "03",
      label: "Trust transition",
      meta: trustNarrativeState ? `${trustNarrativeState} on live intake` : "No active trust shift yet",
      status: liveNarrativeReady ? "complete" : baselineSignalCount ? "ready" : "pending"
    },
    {
      id: "queue",
      step: "04",
      label: "Queue update",
      meta: queue.length ? `${queue.length} active entries` : "Queue remains clear",
      status: queue.length ? "complete" : latestLiveSignal ? "active" : "pending"
    },
    {
      id: "alert",
      step: "05",
      label: "Telegram",
      meta: latestAlert ? `${latestAlert.status} | ${latestAlert.trustState}` : "Awaiting alert threshold",
      status: latestAlert
        ? latestAlert.status === "sent"
          ? "complete"
          : latestAlert.status === "failed"
            ? "risk"
            : "active"
        : latestLiveSignal
          ? "active"
          : "pending"
    },
    {
      id: "replay",
      step: "06",
      label: "Trust Replay",
      meta: replayAvailableForNarrative ? `${replayContext.totalSteps} steps available` : "Timeline remains primary",
      status: replayAvailableForNarrative ? "complete" : liveNarrativeReady ? "ready" : "pending"
    }
  ];
  const operationsOverview = [
    {
      label: "Focus case",
      value: focusCase?.caseId || "Awaiting case",
      meta: focusCase ? `${sourceLabel(focusCase.source, focusCase)} | ${focusCase.lastTransactionId || "transaction pending"}` : "No investigation pinned"
    },
    {
      label: "Replay mode",
      value: replayModeDisplay,
      meta: replayAvailableForNarrative
        ? replayContext.mode === "replay-ready"
          ? `${replayContext.totalSteps} scenario steps ready | live investigation preserved`
          : `${replayContext.activeStepIndex || replaySteps.length}/${replayContext.totalSteps || replaySteps.length} visible`
        : "Chronology is still collecting baseline context before the live trigger."
    },
    {
      label: "Queue posture",
      value: queue.length ? `${queue.length} active` : "Queue clear",
      meta: `${queueCounts.review} review | ${queueCounts.escalated} escalated`
    },
    {
      label: "Latest alert",
      value: latestAlert?.status || "Pending",
      meta: latestAlert
        ? `${latestAlert.caseId} | ${compactNumber(latestAlert.fusedScore)} fused`
        : "Telegram fallback remains truthful when unavailable"
    }
  ];

  const scores = evidence.scores || {};
  const scoreBars = [
    { key: "fraud", label: "Fraud", value: Number(scores.fraud || focusCase?.fraudScore || 0) },
    { key: "graph", label: "Graph", value: Number(scores.graph || focusCase?.graphScore || 0) },
    { key: "drift", label: "Drift", value: Number(scores.drift || focusCase?.driftScore || 0) },
    { key: "fused", label: "Fused", value: Number(scores.fused || focusCase?.fusedScore || 0) }
  ];
  const evidenceSignalCount = EVIDENCE_GROUP_KEYS.reduce((total, key) => {
    const items = Array.isArray(evidence?.[key]?.items) ? evidence[key].items : [];
    return total + items.length;
  }, 0);
  const caseTimelineCount = Array.isArray(focusCase?.timeline) ? focusCase.timeline.length : 0;
  const liveViewActive = !replayOverlayActive && replayContext.mode !== "replay-ready";
  const replayViewActive = !liveViewActive;

  async function startScenario(scenarioId) {
    setLaunchingScenario(scenarioId);
    try {
      const response = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/start`, { method: "POST" });
      if (!response.ok) {
        return;
      }
      setManualReplayIndex(null);
      setSelectedCase(null);
    } finally {
      window.setTimeout(() => setLaunchingScenario(""), 400);
    }
  }

  async function takeAction(action) {
    if (!focusCase?.caseId) {
      return;
    }
    setBusyAction(action);
    try {
      await fetch(`${API_BASE}/api/cases/${focusCase.caseId}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, actor: "operator", note: "Command center action" })
      });
      await loadCase(focusCase.caseId);
      await loadState();
    } finally {
      setBusyAction("");
    }
  }

  async function savePolicy() {
    setBusyAction("policy");
    try {
      const response = await fetch(`${API_BASE}/api/policy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "policy_lab", payload: policyDraft })
      });
      const payload = await response.json();
      setPolicyDraft(payload);
      await loadState();
    } finally {
      setBusyAction("");
    }
  }

  function activateLiveView() {
    setManualReplayIndex(null);
  }

  function activateReplayView() {
    if (!replayAvailableForNarrative) {
      return;
    }
    setActiveTab("evidence");
    if (scenarioReplayLoaded) {
      setSelectedCase(null);
    }
    setManualReplayIndex(Math.max(0, liveReplayIndex));
  }

  return (
    <main className="app-shell">
      {!backendConfigured && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Deployment Configuration</p>
              <h2>Frontend is deployed, but the Rayzaa backend endpoint is not configured for this host.</h2>
            </div>
          </div>
          <p className="muted-copy">
            Set <code>NEXT_PUBLIC_API_BASE</code> and <code>NEXT_PUBLIC_WS_URL</code> in Vercel before using the Rayzaa command center outside local development.
          </p>
        </section>
      )}
      <header className="panel rayzaa-shell-header">
        <div className="rayzaa-shell-brand">
          <div>
            <p className="eyebrow">Rayzaa</p>
            <h1>Trust Operations Command</h1>
          </div>
          <p className="rayzaa-shell-copy">
            Analyst-facing trust investigation surface for live intake, queue triage, typed evidence, and replay chronology.
          </p>
        </div>
        <div className="rayzaa-shell-actions">
          <nav className="dashboard-switch">
            <Link href="/payeasy" className="switch-link">
              PayEasy
            </Link>
            <Link href="/rayzaa" className="switch-link active">
              Rayzaa command
            </Link>
          </nav>
          <div className="rayzaa-header-controls">
            <div className="mode-switch" aria-label="Analyst context mode">
              <button type="button" className={liveViewActive ? "active" : ""} onClick={activateLiveView}>
                Live
              </button>
              <button
                type="button"
                className={replayViewActive ? "active" : ""}
                onClick={activateReplayView}
                disabled={!replayAvailableForNarrative}
              >
                Replay
              </button>
            </div>
            <div className={`status-chip ${connection}`}>
              <span className="status-dot" />
              {connectionLabel(connection)}
            </div>
          </div>
          <div className="rayzaa-status-copy">
            <strong>{statusHeadline}</strong>
            <span>
              {statusTitle}{" "}
              {state?.system?.status === "running" && state?.system?.totalSteps ? `| ${state.system.activeStep}/${state.system.totalSteps}` : ""}
            </span>
          </div>
        </div>
      </header>

      <div className="app-shell-body">
        <section className="rayzaa-command-layout">
          <aside className="rayzaa-column rayzaa-column-left">
          <SignalRailPanel signalRail={state?.signalRail || []} onSelectCase={selectCaseFromSignal} />
          <section className="panel rayzaa-queue-surface">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Queue Posture</p>
                <h2>Review and escalation queue</h2>
              </div>
            </div>
            <div className="rayzaa-queue-metrics">
              <div className="rayzaa-queue-metric">
                <span>Review required</span>
                <strong>{queueCounts.review}</strong>
              </div>
              <div className="rayzaa-queue-metric">
                <span>Escalated</span>
                <strong>{queueCounts.escalated}</strong>
              </div>
              <div className="rayzaa-queue-metric">
                <span>Live trigger</span>
                <strong>{latestLiveSignal?.transactionId || "Pending"}</strong>
              </div>
            </div>
            <QueuePanel queue={queue} onSelectCase={loadCase} selectedCaseId={selectedCase?.caseId || ""} />
          </section>
          </aside>

          <section className="rayzaa-column rayzaa-column-center">
          <section className="panel rayzaa-case-summary">
            <div className="rayzaa-case-summary-head">
              <div>
                <p className="eyebrow">Case Studio</p>
                <h2>{focusCase?.title || "Awaiting live or replay case selection"}</h2>
                <div className="rayzaa-case-meta">
                  <span>Case {focusCase?.caseId || "pending-case"}</span>
                  <span>{focusCase ? sourceLabel(focusCase.source, focusCase) : "Live intake"}</span>
                  <span>{focusCase?.lastTransactionId || "Awaiting persisted transaction"}</span>
                </div>
              </div>
              <TrustStatePill value={trustState} />
            </div>
            <p className="rayzaa-case-summary-copy">
              {focusCase?.summary ||
                "Signal Rail selection or live ingest will pin the investigation context for evidence review, queue action, and replay analysis."}
            </p>
            <div className="rayzaa-case-stat-grid">
              <div className="rayzaa-case-stat">
                <span>Trust score</span>
                <strong>{compactNumber(Number(scores.fused || focusCase?.fusedScore || 0))}%</strong>
                <p>Fused score for the active investigation.</p>
              </div>
              <div className="rayzaa-case-stat">
                <span>Evidence count</span>
                <strong>{evidenceSignalCount}</strong>
                <p>Typed evidence signals above the current threshold.</p>
              </div>
              <div className="rayzaa-case-stat">
                <span>Timeline</span>
                <strong>{caseTimelineCount}</strong>
                <p>Persisted chronology events for this case.</p>
              </div>
            </div>
            <div className="score-band rayzaa-score-band">
              {scoreBars.map((item) => (
                <div key={item.key} className="score-card">
                  <div className="score-label-row">
                    <span>{item.label}</span>
                    <strong>{compactNumber(item.value)}%</strong>
                  </div>
                  <div className="meter-track">
                    <div className={`meter-fill meter-${item.key}`} style={{ width: `${Math.min(100, item.value)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <EvidenceLensPanel
            activeTab={activeTab}
            onTabChange={setActiveTab}
            focusCase={focusCase}
            trustState={trustState}
            evidence={evidence}
            replayContext={replayContext}
            busyAction={busyAction}
            onTakeAction={takeAction}
            queue={queue}
            onSelectCase={loadCase}
            selectedCaseId={selectedCase?.caseId || ""}
            policyDraft={policyDraft}
            onPolicyChange={handlePolicyChange}
            onSavePolicy={savePolicy}
          />
          </section>

          <aside className="rayzaa-column rayzaa-column-right">
          <TrustGraph elements={[...(graph.nodes || []), ...(graph.edges || [])]} trustState={trustState} replayLabel={trustLabel} />

          <ReplayPanel
            scenarios={scenarios}
            currentScenarioId={state?.system?.scenarioId}
            replaySteps={replaySteps}
            effectiveReplayIndex={effectiveReplayIndex}
            replayContext={replayContext}
            demoFlow={demoFlow}
            launchingScenario={launchingScenario}
            onStartScenario={startScenario}
            onFollowLive={activateLiveView}
            onReplayIndexChange={setManualReplayIndex}
          />

          <section className="panel rayzaa-ops-surface">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Operations</p>
                <h2>Live command context</h2>
              </div>
              <Link href="/payeasy" className="ghost-button portal-link-button">
                Open PayEasy
              </Link>
            </div>
            <div className="rayzaa-ops-grid">
              {operationsOverview.map((item) => (
                <div key={item.label} className="rayzaa-ops-card">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <p>{item.meta}</p>
                </div>
              ))}
            </div>
            <div className="rayzaa-demo-flow">
              <div className="rayzaa-demo-flow-head">
                <span className="context-label">Deterministic operational flow</span>
                <p>{demoFlow.locked ? "Replay stays gated behind the first non-seed live payment." : "Live flow is active."}</p>
              </div>
              <div className="rayzaa-demo-step-list">
                {demoSequence.map((step) => (
                  <div key={step.id} className={`rayzaa-demo-step rayzaa-demo-${step.status}`}>
                    <span className="rayzaa-demo-index">{step.step}</span>
                    <div>
                      <strong>{step.label}</strong>
                      <p>{step.meta}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="panel rayzaa-scorecard-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Model Validation</p>
                <h2>Model Scorecard</h2>
              </div>
            </div>
            <div className="rayzaa-scorecard-body">
              <table className="rayzaa-scorecard-table">
                <tbody>
                  {MODEL_SCORECARD_ROWS.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      <td>{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="rayzaa-scorecard-note">
                Offline benchmark validation for the locked runtime artifact. Live payments update case-level scores,
                evidence, queue state, and replay chronology, not benchmark metrics. Neural anomaly sidecar is roadmap
                only and is not part of the deployed runtime path yet.
              </p>
            </div>
          </section>
          </aside>
        </section>
      </div>
    </main>
  );
}
