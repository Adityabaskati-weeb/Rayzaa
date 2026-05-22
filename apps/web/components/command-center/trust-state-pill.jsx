"use client";

import { trustClass } from "./formatters";

export default function TrustStatePill({ value, className = "" }) {
  const safeValue = value || "Healthy";
  const classes = ["state-pill", trustClass(safeValue), className].filter(Boolean).join(" ");

  return <span className={classes}>{safeValue}</span>;
}
