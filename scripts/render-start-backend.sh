#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_RENDER_BASE="/var/data/rayzaa"
FALLBACK_RENDER_BASE="/tmp/rayzaa"

if [[ ! -d "/var/data" || ! -w "/var/data" ]]; then
  DEFAULT_RENDER_BASE="${FALLBACK_RENDER_BASE}"
fi

export PYTHONUNBUFFERED=1
export PYTHONPATH="${ROOT_DIR}/apps/api:${ROOT_DIR}:${PYTHONPATH:-}"

export RAYZAA_RUNTIME_DIR="${RAYZAA_RUNTIME_DIR:-${DEFAULT_RENDER_BASE}/runtime}"
export RAYZAA_ARTIFACT_DIR="${RAYZAA_ARTIFACT_DIR:-${DEFAULT_RENDER_BASE}/artifacts}"
export RAYZAA_REPLAY_DIR="${RAYZAA_REPLAY_DIR:-${DEFAULT_RENDER_BASE}/replay}"
export RAYZAA_LOG_DIR="${RAYZAA_LOG_DIR:-${DEFAULT_RENDER_BASE}/logs}"
export RAYZAA_BENCHMARK_DIR="${RAYZAA_BENCHMARK_DIR:-${DEFAULT_RENDER_BASE}/benchmark}"
export RAYZAA_TMP_DIR="${RAYZAA_TMP_DIR:-${DEFAULT_RENDER_BASE}/tmp}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${RAYZAA_RUNTIME_DIR}/rayzaa.db}"
export RAYZAA_ARTIFACT_MANIFEST="${RAYZAA_ARTIFACT_MANIFEST:-${ROOT_DIR}/docs/approved_model_artifact.json}"
export RAYZAA_APPROVED_ARTIFACT_SOURCE="${RAYZAA_APPROVED_ARTIFACT_SOURCE:-${ROOT_DIR}/deploy/artifacts/fraud_model/benchmark_v3}"
export RAYZAA_LOCKED_MODEL_BUNDLE="${RAYZAA_LOCKED_MODEL_BUNDLE:-benchmark_v3}"

mkdir -p \
  "${RAYZAA_RUNTIME_DIR}" \
  "${RAYZAA_ARTIFACT_DIR}" \
  "${RAYZAA_REPLAY_DIR}" \
  "${RAYZAA_LOG_DIR}" \
  "${RAYZAA_BENCHMARK_DIR}" \
  "${RAYZAA_TMP_DIR}"

RUNTIME_BUNDLE_DIR="${RAYZAA_ARTIFACT_DIR}/fraud_model/${RAYZAA_LOCKED_MODEL_BUNDLE}"
SOURCE_BUNDLE_DIR="${RAYZAA_APPROVED_ARTIFACT_SOURCE}"

if [[ -d "${SOURCE_BUNDLE_DIR}" ]]; then
  mkdir -p "${RUNTIME_BUNDLE_DIR}"
  cp -f "${SOURCE_BUNDLE_DIR}"/* "${RUNTIME_BUNDLE_DIR}/"
fi

if [[ -n "${RENDER_EXTERNAL_URL:-}" && -z "${RAYZAA_PUBLIC_API_URL:-}" ]]; then
  export RAYZAA_PUBLIC_API_URL="${RENDER_EXTERNAL_URL}"
fi

python "${ROOT_DIR}/scripts/prewarm_model_artifact.py"

cd "${ROOT_DIR}/apps/api"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-10000}"
