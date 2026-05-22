#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PYTHONUNBUFFERED=1
export PYTHONPATH="${ROOT_DIR}/apps/api:${ROOT_DIR}:${PYTHONPATH:-}"

export RAYZAA_RUNTIME_DIR="${RAYZAA_RUNTIME_DIR:-/var/data/rayzaa/runtime}"
export RAYZAA_ARTIFACT_DIR="${RAYZAA_ARTIFACT_DIR:-/var/data/rayzaa/artifacts}"
export RAYZAA_REPLAY_DIR="${RAYZAA_REPLAY_DIR:-/var/data/rayzaa/replay}"
export RAYZAA_LOG_DIR="${RAYZAA_LOG_DIR:-/var/data/rayzaa/logs}"
export RAYZAA_BENCHMARK_DIR="${RAYZAA_BENCHMARK_DIR:-/var/data/rayzaa/benchmark}"
export RAYZAA_TMP_DIR="${RAYZAA_TMP_DIR:-/var/data/rayzaa/tmp}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////var/data/rayzaa/runtime/rayzaa.db}"
export RAYZAA_ARTIFACT_MANIFEST="${RAYZAA_ARTIFACT_MANIFEST:-${ROOT_DIR}/docs/approved_model_artifact.json}"
export RAYZAA_APPROVED_ARTIFACT_SOURCE="${RAYZAA_APPROVED_ARTIFACT_SOURCE:-${ROOT_DIR}/deploy/artifacts/fraud_model/benchmark_v3}"

mkdir -p \
  "${RAYZAA_RUNTIME_DIR}" \
  "${RAYZAA_ARTIFACT_DIR}" \
  "${RAYZAA_REPLAY_DIR}" \
  "${RAYZAA_LOG_DIR}" \
  "${RAYZAA_BENCHMARK_DIR}" \
  "${RAYZAA_TMP_DIR}"

if [[ -n "${RENDER_EXTERNAL_URL:-}" && -z "${RAYZAA_PUBLIC_API_URL:-}" ]]; then
  export RAYZAA_PUBLIC_API_URL="${RENDER_EXTERNAL_URL}"
fi

python "${ROOT_DIR}/scripts/prewarm_model_artifact.py"

cd "${ROOT_DIR}/apps/api"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-10000}"
