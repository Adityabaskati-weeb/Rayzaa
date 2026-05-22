"use client";

const policyControls = [
  ["watch_threshold", "Watch threshold", 25, 60, 1],
  ["fractured_threshold", "Fractured threshold", 45, 80, 1],
  ["escalated_threshold", "Escalated threshold", 60, 95, 1],
  ["graph_boost_multiplier", "Graph multiplier", 0.8, 1.6, 0.05]
];

export default function PolicyPanel({ policyDraft, busyAction, onPolicyChange, onSavePolicy }) {
  return (
    <div className="policy-panel">
      {policyControls.map(([key, label, min, max, step]) => (
        <label key={key} className="policy-control">
          <div className="policy-label-row">
            <span>{label}</span>
            <strong>{policyDraft[key]}</strong>
          </div>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={policyDraft[key]}
            onChange={(event) => onPolicyChange(key, Number(event.target.value))}
          />
        </label>
      ))}
      <button type="button" className="save-policy" onClick={onSavePolicy} disabled={busyAction === "policy"}>
        {busyAction === "policy" ? "Saving policy..." : "Commit policy version"}
      </button>
    </div>
  );
}
