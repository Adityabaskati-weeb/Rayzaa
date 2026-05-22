"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { getRuntimeConfig } from "../lib/runtime-config";
import { compactNumber, currency, formatTimestamp } from "./command-center/formatters";
import LivePaymentPanel from "./command-center/live-payment-panel";
import TrustStatePill from "./command-center/trust-state-pill";

const { apiBase: API_BASE, wsUrl: WS_URL, backendConfigured } = getRuntimeConfig();
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);
const POLL_INTERVAL_MS = 10000;

function liveSignalLabel(item) {
  if (!item) {
    return "Awaiting trigger";
  }
  return item.isBaselineSeed ? "Baseline seed" : "Live payment";
}

function isBaselineCase(item) {
  return Boolean(item?.isBaselineSeed || String(item?.lastTransactionId || "").startsWith("seed_"));
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

export default function PayEasyDashboard() {
  const shellRef = useRef(null);
  const headerRef = useRef(null);
  const [state, setState] = useState(null);
  const [connection, setConnection] = useState("connecting");
  const keepAliveRef = useRef(null);
  const reconnectRef = useRef(null);
  const pollingOnlyRef = useRef(false);

  async function loadState(options = {}) {
    const { preserveLiveConnection = false } = options;
    const response = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
    const payload = await response.json();
    setState(payload);
    if (!preserveLiveConnection) {
      setConnection((current) => (current === "live" ? current : "synced"));
    }
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
    if (!shellRef.current || !headerRef.current) {
      return undefined;
    }

    const updateHeaderOffset = () => {
      const height = headerRef.current?.offsetHeight || 0;
      shellRef.current?.style.setProperty("--shell-header-offset", `${height + 32}px`);
    };

    updateHeaderOffset();
    window.addEventListener("resize", updateHeaderOffset);

    return () => window.removeEventListener("resize", updateHeaderOffset);
  }, [connection]);

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

  const operations = state?.operations || {};
  const queue = state?.queue || [];
  const signalRail = state?.signalRail || [];
  const latestAlert = operations.latestAlert || null;
  const integrationStatus = operations.integrationStatus || {};
  const demoFlow = operations.demoFlow || {};
  const baselineSignals = signalRail.filter((item) => item.isBaselineSeed);
  const liveSignals = signalRail.filter((item) => item.source === "live" && !item.isBaselineSeed);
  const latestLiveSignal = liveSignals[0] || null;
  const focusLiveCase = state?.focusCase?.source === "live" && !isBaselineCase(state?.focusCase) ? state.focusCase : null;
  const trustShiftCase = demoFlow.livePaymentSeen ? focusLiveCase || latestLiveSignal : null;
  const paymentActivity = useMemo(() => [...liveSignals, ...baselineSignals].slice(0, 6), [liveSignals, baselineSignals]);

  function openRayzaaCase(caseId) {
    if (!caseId) {
      window.location.assign("/rayzaa");
      return;
    }
    window.location.assign(`/rayzaa?case=${encodeURIComponent(caseId)}`);
  }

  return (
    <main ref={shellRef} className="portal-shell">
      {!backendConfigured && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Deployment Configuration</p>
              <h2>Frontend is deployed, but the Rayzaa backend endpoint is not configured for this host.</h2>
            </div>
          </div>
          <p className="muted-copy">
            Set <code>NEXT_PUBLIC_API_BASE</code> and <code>NEXT_PUBLIC_WS_URL</code> in Vercel before using the PayEasy live checkout surface outside local development.
          </p>
        </section>
      )}
      <header ref={headerRef} className="portal-header panel">
        <div className="portal-brand">
          <p className="eyebrow">PayEasy</p>
          <h1>Live Checkout Surface</h1>
          <p className="portal-copy">
            Customer-facing checkout proves the real payment trigger. Rayzaa remains the operational intelligence layer behind the handoff.
          </p>
        </div>
        <div className="portal-actions">
          <div className={`status-chip ${connection}`}>
            <span className="status-dot" />
            {connectionLabel(connection)}
          </div>
          <nav className="dashboard-switch">
            <Link href="/" className="switch-link active">
              PayEasy
            </Link>
            <Link href="/rayzaa" className="switch-link">
              Rayzaa command
            </Link>
          </nav>
        </div>
      </header>

      <div className="portal-body">
        <section className="panel payeasy-hero">
          <div className="payeasy-hero-copy">
            <p className="eyebrow">Customer Dashboard</p>
            <h2>Accept a real Razorpay test payment, then hand the case to Rayzaa.</h2>
            <p>
              Baseline traffic stays visible for context, but only a true live payment unlocks Trust Replay and the analyst investigation workflow.
            </p>
          </div>
          <div className="payeasy-kpi-grid">
            <div className="payeasy-kpi-card">
              <span>Baseline context</span>
              <strong>{baselineSignals.length}</strong>
              <p>{baselineSignals.length ? "Seeded signals are ready." : "Awaiting seed context."}</p>
            </div>
            <div className="payeasy-kpi-card">
              <span>Live payment proof</span>
              <strong>{latestLiveSignal ? latestLiveSignal.transactionId : "Pending"}</strong>
              <p>{latestLiveSignal ? "Webhook reached Rayzaa." : "No live checkout has cleared yet."}</p>
            </div>
            <div className="payeasy-kpi-card">
              <span>Trust handoff</span>
              <strong>{trustShiftCase?.trustState || "Healthy"}</strong>
              <p>{trustShiftCase ? `${compactNumber(trustShiftCase.fusedScore || 0)} fused into Rayzaa.` : "Awaiting operational handoff."}</p>
            </div>
            <div className="payeasy-kpi-card">
              <span>Replay unlock</span>
              <strong>{demoFlow.livePaymentSeen ? "Ready" : "Locked"}</strong>
              <p>{demoFlow.livePaymentSeen ? "Analyst replay is now available." : "Seed baseline first, then complete one live payment."}</p>
            </div>
          </div>
        </section>

        <section className="payeasy-main-grid">
          <LivePaymentPanel
            apiBase={API_BASE}
            operations={operations}
            latestLiveSignal={latestLiveSignal}
            onOpenCase={openRayzaaCase}
          />

          <aside className="panel payeasy-activity-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Checkout Activity</p>
                <h2>Customer-side proof trail</h2>
              </div>
              <Link href="/rayzaa" className="ghost-button portal-link-button">
                Open analyst view
              </Link>
            </div>
            <div className="payeasy-activity-list">
              {paymentActivity.map((item) => (
                <button
                  key={item.transactionId}
                  type="button"
                  className="payeasy-activity-card"
                  onClick={() => openRayzaaCase(item.caseId)}
                >
                  <div className="payeasy-activity-head">
                    <span className="timeline-tag">{liveSignalLabel(item)}</span>
                    <time dateTime={item.timestamp || ""}>{formatTimestamp(item.timestamp)}</time>
                  </div>
                  <div className="payeasy-activity-identity">
                    <strong>{item.accountId}</strong>
                    <strong>{currency(item.amount)}</strong>
                  </div>
                  <p>{item.scenarioNote || "Payment entered the shared operational rail."}</p>
                  <div className="payeasy-activity-foot">
                    <span>{item.transactionId}</span>
                    <TrustStatePill value={item.trustState} />
                  </div>
                </button>
              ))}
              {!paymentActivity.length && (
                <div className="empty-state">
                  <p>No checkout activity yet.</p>
                  <span>Seed baseline context or complete one Razorpay test payment to populate the customer activity rail.</span>
                </div>
              )}
            </div>
          </aside>
        </section>

        <section className="panel payeasy-handoff-panel">
          <div className="payeasy-handoff-header">
            <div>
              <p className="eyebrow">Operational Handoff</p>
              <h2>Rayzaa receives the checkout, scores trust, and exposes the investigation path.</h2>
            </div>
            <div className="payeasy-handoff-actions">
              <Link href="/rayzaa" className="ghost-button portal-link-button">
                Open Rayzaa command center
              </Link>
              {trustShiftCase?.caseId && (
                <button type="button" className="action-button review" onClick={() => openRayzaaCase(trustShiftCase.caseId)}>
                  Open latest live case
                </button>
              )}
            </div>
          </div>

          <div className="payeasy-handoff-grid">
            <div className="payeasy-handoff-card">
              <span>Latest trust outcome</span>
              <strong>{trustShiftCase?.trustState || "Healthy"}</strong>
              <p>
                {trustShiftCase
                  ? `${trustShiftCase.caseId || trustShiftCase.accountId} | ${compactNumber(trustShiftCase.fusedScore || 0)} fused`
                  : "Awaiting live trust evaluation from Rayzaa."}
              </p>
            </div>
            <div className="payeasy-handoff-card">
              <span>Queue impact</span>
              <strong>{queue.length ? `${queue.length} active` : "Queue clear"}</strong>
              <p>{queue.length ? "Live payment has entered analyst triage." : "No queue pressure from the current checkout session."}</p>
            </div>
            <div className="payeasy-handoff-card">
              <span>Telegram status</span>
              <strong>{latestAlert?.status || "Pending"}</strong>
              <p>{latestAlert ? latestAlert.message : "Alerting remains threshold-driven and may stay quiet for low-pressure checkouts."}</p>
            </div>
            <div className="payeasy-handoff-card">
              <span>Integration posture</span>
              <strong>{integrationStatus.razorpay?.configured ? "Ready" : "Config missing"}</strong>
              <p>
                {integrationStatus.razorpay?.configured
                  ? integrationStatus.razorpay?.testMode
                    ? "Razorpay Test Mode is active."
                    : "Live Razorpay credentials are present."
                  : "Add Razorpay credentials before using the customer checkout on stage."}
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
