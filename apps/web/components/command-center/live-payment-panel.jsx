"use client";

import { useEffect, useState } from "react";
import { compactNumber } from "./formatters";
import TrustStatePill from "./trust-state-pill";

const DEMO_PROFILES = [
  {
    id: "dormant_device_reuse",
    label: "Dormant device reuse",
    description: "Pre-seeded account context reactivates on a shared device and should drive review."
  },
  {
    id: "baseline",
    label: "Baseline checkout",
    description: "Controlled low-pressure payment for proving the same live ingest path without escalation."
  },
  {
    id: "merchant_retry_pressure",
    label: "Merchant retry pressure",
    description: "Payment lands during elevated merchant burst context and is useful for queue triage demos."
  }
];

const TRUST_STATE_ORDER = {
  Healthy: 0,
  Watch: 1,
  Fractured: 2,
  Escalated: 3
};

function statusLabel(status, positiveLabel, negativeLabel) {
  return status ? positiveLabel : negativeLabel;
}

function ensureRazorpayScript() {
  if (typeof window !== "undefined" && window.Razorpay) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-razorpay-checkout="true"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Razorpay checkout script failed to load.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.dataset.razorpayCheckout = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Razorpay checkout script failed to load."));
    document.body.appendChild(script);
  });
}

export default function LivePaymentPanel({ apiBase, operations, latestLiveSignal, onOpenCase }) {
  const [amount, setAmount] = useState("45999");
  const [riskPreset, setRiskPreset] = useState("dormant_device_reuse");
  const [phase, setPhase] = useState("idle");
  const [statusMessage, setStatusMessage] = useState("Use Razorpay Test Mode. Webhook ingest remains the source of truth for Rayzaa.");
  const [checkoutRef, setCheckoutRef] = useState("");

  const integrationStatus = operations?.integrationStatus || {};
  const razorpay = integrationStatus.razorpay || {};
  const telegram = integrationStatus.telegram || {};
  const latestAlert = operations?.latestAlert || null;
  const alertThreshold = telegram.minimumTrustState || "Fractured";
  const proofSequence = [
    {
      id: "order",
      label: "Order",
      status: ["creating-order", "checkout-open", "verifying", "awaiting-webhook", "webhook-delayed", "ingested"].includes(phase)
        ? "complete"
        : phase === "idle"
          ? "ready"
          : "pending"
    },
    {
      id: "verify",
      label: "Verified",
      status: ["awaiting-webhook", "webhook-delayed", "ingested"].includes(phase) ? "complete" : phase === "verifying" ? "active" : "pending"
    },
    {
      id: "webhook",
      label: "Webhook",
      status: latestLiveSignal ? "complete" : phase === "webhook-delayed" ? "risk" : phase === "awaiting-webhook" ? "active" : "pending"
    },
    {
      id: "alert",
      label: "Alert",
      status: latestAlert ? (latestAlert.status === "sent" ? "complete" : latestAlert.status === "failed" ? "risk" : "active") : latestLiveSignal ? "active" : "pending"
    },
    {
      id: "replay",
      label: "Replay",
      status: latestLiveSignal ? "complete" : "pending"
    }
  ];

  useEffect(() => {
    if (phase !== "awaiting-webhook" && phase !== "webhook-delayed") {
      return;
    }
    if (!latestLiveSignal) {
      return;
    }

    setPhase("ingested");
    setStatusMessage("Razorpay webhook received. Rayzaa updated the live trust state, evidence, queue, and replay chronology.");
  }, [latestLiveSignal, phase]);

  useEffect(() => {
    if (phase !== "ingested" || !latestAlert) {
      return;
    }
    if (latestAlert.status === "sent") {
      setStatusMessage("Live ingest completed and the Telegram operational alert was delivered. Open the case to inspect queue, evidence, and replay.");
      return;
    }
    if (latestAlert.status === "skipped") {
      setStatusMessage("Live ingest completed. Telegram is unavailable in this environment, so queue, timeline, and replay remain the operational source of truth.");
      return;
    }
    if (latestAlert.status === "failed") {
      setStatusMessage("Live ingest completed, but Telegram delivery failed. Continue the investigation from the queue, timeline, and replay surfaces.");
    }
  }, [latestAlert, phase]);

  useEffect(() => {
    if (phase !== "awaiting-webhook") {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setPhase("webhook-delayed");
      setStatusMessage(
        "Checkout was verified, but the Razorpay webhook has not arrived yet. Rayzaa will not simulate ingest. If the delay persists, continue with deterministic Trust Replay or a seeded case."
      );
    }, 20000);

    return () => window.clearTimeout(timer);
  }, [phase]);

  async function launchCheckout() {
    if (!razorpay.configured) {
      setPhase("error");
      setStatusMessage("Razorpay is not configured. Add test credentials before launching PayEasy checkout.");
      return;
    }

    setPhase("creating-order");
    setStatusMessage("Creating Razorpay test order through the PayEasy adapter.");

    try {
      const orderResponse = await fetch(`${apiBase}/api/integrations/razorpay/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: Number(amount),
          risk_preset: riskPreset
        })
      });
      const orderPayload = await orderResponse.json();
      if (!orderResponse.ok) {
        throw new Error(orderPayload.detail || "Unable to create Razorpay test order.");
      }

      await ensureRazorpayScript();
      setPhase("checkout-open");
      setCheckoutRef(orderPayload.order?.id || "");
      setStatusMessage("Razorpay checkout opened in test mode. Complete the payment to trigger the webhook.");

      const instance = new window.Razorpay({
        key: orderPayload.keyId,
        amount: orderPayload.order.amount,
        currency: orderPayload.order.currency,
        name: orderPayload.checkout.name,
        description: orderPayload.checkout.description,
        order_id: orderPayload.order.id,
        prefill: orderPayload.checkout.prefill,
        notes: orderPayload.checkout.notes,
        theme: { color: "#1a1a1a" },
        modal: {
          ondismiss: () => {
            setPhase("dismissed");
            setStatusMessage("Checkout was dismissed. No webhook ingest will occur until the test payment succeeds.");
          }
        },
        handler: async (response) => {
          setPhase("verifying");
          setStatusMessage("Checkout succeeded. Verifying client callback and waiting for the webhook to enter Rayzaa.");
          try {
            const verifyResponse = await fetch(`${apiBase}/api/integrations/razorpay/checkout/verify`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(response)
            });
            const verifyPayload = await verifyResponse.json();
            if (!verifyResponse.ok) {
              throw new Error(verifyPayload.detail || "Razorpay callback verification failed.");
            }
            setPhase("awaiting-webhook");
            setStatusMessage(verifyPayload.message || "Checkout verified. Waiting for Razorpay webhook ingest.");
          } catch (error) {
            setPhase("error");
            setStatusMessage(error.message || "Razorpay callback verification failed.");
          }
        }
      });

      instance.open();
    } catch (error) {
      setPhase("error");
      setStatusMessage(error.message || "Unable to launch Razorpay test checkout.");
    }
  }

  return (
    <section className="panel live-payment-panel">
      <div className="payment-proof-header">
        <div>
          <p className="eyebrow">Live Payment Proof</p>
          <h2>PayEasy test checkout into Rayzaa</h2>
          <p className="payment-proof-copy">{statusMessage}</p>
        </div>
        <div className="payment-status-cluster">
          <span className={`status-chip ${razorpay.configured ? "live" : "degraded"}`}>
            Razorpay {statusLabel(razorpay.configured, razorpay.testMode ? "test mode" : "ready", "missing")}
          </span>
          <span className={`status-chip ${telegram.configured ? "live" : "connecting"}`}>
            Telegram {statusLabel(telegram.configured, "ready", "missing")}
          </span>
        </div>
      </div>

      <div className="payment-proof-sequence">
        {proofSequence.map((step, index) => (
          <div key={step.id} className={`payment-sequence-step payment-${step.status}`}>
            <span className="payment-sequence-index">{index + 1}</span>
            <strong>{step.label}</strong>
          </div>
        ))}
      </div>

      <div className="payment-proof-grid">
        <div className="payment-form">
          <label className="payment-field">
            <span>Demo profile</span>
            <select value={riskPreset} onChange={(event) => setRiskPreset(event.target.value)}>
              {DEMO_PROFILES.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.label}
                </option>
              ))}
            </select>
          </label>

          <label className="payment-field">
            <span>Amount (INR)</span>
            <input
              type="number"
              min="1"
              step="1"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>

          <button
            type="button"
            className="action-button review payment-launch-button"
            onClick={launchCheckout}
            disabled={
              phase === "creating-order" ||
              phase === "checkout-open" ||
              phase === "verifying" ||
              phase === "awaiting-webhook"
            }
          >
            {phase === "creating-order" ? "Creating order..." : "Launch Razorpay test checkout"}
          </button>

          <div className="payment-proof-note">
            <strong>{DEMO_PROFILES.find((profile) => profile.id === riskPreset)?.label}</strong>
            <p>{DEMO_PROFILES.find((profile) => profile.id === riskPreset)?.description}</p>
          </div>
        </div>

        <div className="payment-proof-sidebar">
          <div className="payment-proof-card">
            <div className="info-header">
              <h4>Checkout status</h4>
              <span>{phase.replaceAll("-", " ")}</span>
            </div>
            <p className="muted-copy">
              Webhook ingest remains authoritative. Checkout verification does not bypass the Rayzaa transaction pipeline.
            </p>
            {checkoutRef && <p className="muted-copy">Order {checkoutRef}</p>}
          </div>

          <div className="payment-proof-card">
            <div className="info-header">
              <h4>Latest live trigger</h4>
              {latestLiveSignal ? <TrustStatePill value={latestLiveSignal.trustState} /> : <span>pending</span>}
            </div>
            {latestLiveSignal ? (
              <>
                <p className="muted-copy">
                  {latestLiveSignal.transactionId} | {compactNumber(latestLiveSignal.fusedScore)} fused
                </p>
                <button type="button" className="ghost-button" onClick={() => onOpenCase(latestLiveSignal.caseId)}>
                  Open live case
                </button>
              </>
            ) : (
              <p className="muted-copy">No live webhook-triggered payment has entered Rayzaa in this session.</p>
            )}
          </div>

          <div className="payment-proof-card">
            <div className="info-header">
              <h4>Latest Telegram alert</h4>
              <span>{latestAlert?.status || "pending"}</span>
            </div>
            {latestAlert ? (
              <>
                <p className="muted-copy">
                  {latestAlert.caseId} | {latestAlert.trustState} | {compactNumber(latestAlert.fusedScore)} fused
                </p>
                <p className="muted-copy">{latestAlert.message}</p>
                <button type="button" className="ghost-button" onClick={() => onOpenCase(latestAlert.caseId)}>
                  Open alerted case
                </button>
              </>
            ) : !telegram.configured ? (
              <p className="muted-copy">Telegram is not configured here. Queue, case timeline, and replay remain the operational fallback during the demo.</p>
            ) : latestLiveSignal && TRUST_STATE_ORDER[latestLiveSignal.trustState] < TRUST_STATE_ORDER[alertThreshold] ? (
              <p className="muted-copy">
                The latest live case is {latestLiveSignal.trustState}. Telegram is configured for {alertThreshold} and above, so no alert is expected yet.
              </p>
            ) : (
              <p className="muted-copy">Telegram alerts will appear here after a live case reaches the configured trust-state threshold.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
