"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getRuntimeConfig } from "../lib/runtime-config";
import EvidenceLensPanel from "./command-center/evidence-lens-panel";
import { compactNumber, DEFAULT_POLICY, formatTimestamp } from "./command-center/formatters";
import ReplayPanel from "./command-center/replay-panel";
import SignalRailPanel from "./command-center/signal-rail-panel";

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

  async function loadState() {
    const response = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
    const payload = await response.json();
    setState(payload);
    setPolicyDraft(payload.policy || DEFAULT_POLICY);
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
    loadState().catch(() => {});
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
    : `${focusCase?.source === "live" ? "Live intake" : "Replay case"} | ${focusCase?.caseId || "case"}`;
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
      <header className="topbar">
        <div>
          <p className="eyebrow">Rayzaa</p>
          <h1>Trust Operations Command</h1>
        </div>
        <div className="topbar-status">
          <nav className="dashboard-switch">
            <Link href="/payeasy" className="switch-link">
              PayEasy
            </Link>
            <Link href="/rayzaa" className="switch-link active">
              Rayzaa command
            </Link>
          </nav>
          <div className={`status-chip ${connection}`}>
            <span className="status-dot" />
            {connection}
          </div>
          <div className="status-copy">
            <strong>{statusHeadline}</strong>
            <span>
              {statusTitle}{" "}
              {state?.system?.status === "running" && state?.system?.totalSteps ? `| ${state.system.activeStep}/${state.system.totalSteps}` : ""}
            </span>
          </div>
        </div>
      </header>

      <section className="panel ops-banner">
        <div className="ops-sequence">
          <div className="ops-banner-header">
            <div>
              <p className="eyebrow">Demo Overlay</p>
              <h2>Deterministic operational flow</h2>
            </div>
            <span className="ops-banner-copy">
              Demo mode remains locked to the live payment path before Trust Replay opens.
            </span>
          </div>
          <div className="ops-sequence-grid">
            {demoSequence.map((step) => (
              <div key={step.id} className={`ops-step ops-${step.status}`}>
                <span className="ops-step-index">{step.step}</span>
                <div className="ops-step-copy">
                  <strong>{step.label}</strong>
                  <span>{step.meta}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="ops-overview-grid">
          {operationsOverview.map((item) => (
            <div key={item.label} className="ops-overview-card">
              <span className="ops-overview-label">{item.label}</span>
              <strong>{item.value}</strong>
              <span>{item.meta}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel handoff-brief">
        <div className="handoff-brief-copy">
          <p className="eyebrow">Customer Payment Handoff</p>
          <h2>PayEasy owns checkout. Rayzaa owns trust evaluation and investigation.</h2>
          <p>
            Customer-triggered Razorpay payments originate in the PayEasy dashboard, then enter Rayzaa through the same live ingest path used by queueing, evidence, alerts, and replay.
          </p>
        </div>
        <div className="handoff-brief-grid">
          <div className="handoff-brief-card">
            <span>Latest live trigger</span>
            <strong>{latestLiveSignal?.transactionId || "Pending"}</strong>
            <p>
              {latestLiveSignal
                ? `${latestLiveSignal.accountId} | ${compactNumber(latestLiveSignal.fusedScore)} fused | ${latestLiveSignal.trustState}`
                : "Customer checkout is still waiting on a live payment trigger."}
            </p>
          </div>
          <div className="handoff-brief-card">
            <span>Queue posture</span>
            <strong>{queue.length ? `${queue.length} active` : "Queue clear"}</strong>
            <p>{queue.length ? "Analyst triage is active." : "No live cases currently require manual action."}</p>
          </div>
          <div className="handoff-brief-card">
            <span>Replay readiness</span>
            <strong>{replayAvailableForNarrative ? "Available" : "Timeline only"}</strong>
            <p>
              {replayAvailableForNarrative
                ? `${replayContext.totalSteps} chronology steps are ready for investigation.`
                : "Replay will unlock after the live payment path produces checkpoints."}
            </p>
          </div>
          <Link href="/payeasy" className="handoff-brief-link">
            <span>Open PayEasy dashboard</span>
            <strong>Go to customer checkout surface</strong>
            <p>Use the separate customer-facing dashboard to launch the Razorpay test payment.</p>
          </Link>
        </div>
      </section>

      <section className="command-grid">
        <SignalRailPanel signalRail={state?.signalRail || []} onSelectCase={selectCaseFromSignal} />

        <section className="panel center-panel">
          <div className="center-context-bar">
            <div className="center-context-card">
              <span className="context-label">Active investigation</span>
              <strong>{focusCase?.title || "Awaiting live or replay case selection"}</strong>
              <span className="center-context-meta">
                {focusCase
                  ? `${focusCase.caseId} | ${sourceLabel(focusCase.source)} | ${focusCase.lastTransactionId || "transaction pending"}`
                  : "Signal Rail selection or live ingest will pin the investigation context."}
              </span>
            </div>
            <div className="center-context-card">
              <span className="context-label">Operational context</span>
              <strong>{replayModeDisplay}</strong>
              <span className="center-context-meta">
                {!replayAvailableForNarrative
                  ? `Replay remains locked until the first non-seed live payment arrives. Baseline signals: ${baselineSignalCount}.`
                  : replayContext.mode === "replay-ready"
                  ? `Replay ready | last live signal ${latestLiveSignal ? formatTimestamp(latestLiveSignal.timestamp) : "pending"} | queue ${queue.length || 0}`
                  : replayContext.hasReplay
                    ? `${replayContext.activeStepIndex || replaySteps.length}/${replayContext.totalSteps || replaySteps.length} steps | ${trustState} focus`
                  : `Last live signal ${latestLiveSignal ? formatTimestamp(latestLiveSignal.timestamp) : "pending"} | queue ${queue.length || 0}`}
              </span>
            </div>
          </div>
          <div className="score-band">
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
          <TrustGraph elements={[...(graph.nodes || []), ...(graph.edges || [])]} trustState={trustState} replayLabel={trustLabel} />
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

      <ReplayPanel
        scenarios={scenarios}
        currentScenarioId={state?.system?.scenarioId}
        replaySteps={replaySteps}
        effectiveReplayIndex={effectiveReplayIndex}
        replayContext={replayContext}
        demoFlow={demoFlow}
        launchingScenario={launchingScenario}
        onStartScenario={startScenario}
        onFollowLive={() => setManualReplayIndex(null)}
        onReplayIndexChange={setManualReplayIndex}
      />
    </main>
  );
}
