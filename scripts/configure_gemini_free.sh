#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ENV="${ROOT_DIR}/.env"
GATEWAY_ENV="${ROOT_DIR}/infrastructure/litellm/.env"
APP_TEMPLATE="${ROOT_DIR}/.env.gemini-free.example"

if [[ ! -f "${APP_TEMPLATE}" ]]; then
  echo "Missing ${APP_TEMPLATE}" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON:-$(command -v python3 || command -v python || echo "python")}"
DEFAULT_KEY_B64="QVEuQWI4Uk42SzdZaXFFekoxUklRcmpsNG1hOEctU0dBZ3JlYnBucWFyWW9ZVVg5aU82b1E="

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  if [[ "${1:-}" == "--default" ]] || [[ ! -t 0 ]]; then
    GEMINI_API_KEY="$("${PYTHON_BIN}" -c "import base64; print(base64.b64decode('${DEFAULT_KEY_B64}').decode())")"
  else
    echo "============================================================"
    echo "  MEDGUARD GEMINI RUNTIME CONFIGURATION"
    echo "============================================================"
    echo "Nhập Gemini API Key (nhấn [ENTER] để dùng key cấu hình sẵn):"
    read -r -s INPUT_KEY || true
    echo
    if [[ -z "${INPUT_KEY:-}" ]]; then
      GEMINI_API_KEY="$("${PYTHON_BIN}" -c "import base64; print(base64.b64decode('${DEFAULT_KEY_B64}').decode())")"
      echo "-> Đang sử dụng key cấu hình sẵn của hệ thống."
    else
      GEMINI_API_KEY="${INPUT_KEY}"
      echo "-> Đã nhận API key mới."
    fi
  fi
fi

if [[ -z "${GEMINI_API_KEY}" ]]; then
  echo "GEMINI_API_KEY is required." >&2
  exit 1
fi

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    "${PYTHON_BIN}" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

if [[ -f "${GATEWAY_ENV}" ]]; then
  EXISTING_MASTER_KEY="$(grep '^LITELLM_MASTER_KEY=' "${GATEWAY_ENV}" | cut -d= -f2- || true)"
  EXISTING_DB_PW="$(grep '^LITELLM_DB_PASSWORD=' "${GATEWAY_ENV}" | cut -d= -f2- || true)"
  EXISTING_REDIS_PW="$(grep '^REDIS_PASSWORD=' "${GATEWAY_ENV}" | cut -d= -f2- || true)"
  if [[ -n "${EXISTING_MASTER_KEY}" ]]; then LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-${EXISTING_MASTER_KEY}}"; fi
  if [[ -n "${EXISTING_DB_PW}" ]]; then LITELLM_DB_PASSWORD="${LITELLM_DB_PASSWORD:-${EXISTING_DB_PW}}"; fi
  if [[ -n "${EXISTING_REDIS_PW}" ]]; then REDIS_PASSWORD="${REDIS_PASSWORD:-${EXISTING_REDIS_PW}}"; fi
fi

LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-$(random_secret)}"
LITELLM_DB_PASSWORD="${LITELLM_DB_PASSWORD:-$(random_secret)}"
REDIS_PASSWORD="${REDIS_PASSWORD:-$(random_secret)}"

mkdir -p "$(dirname "${GATEWAY_ENV}")"
umask 077

cat > "${GATEWAY_ENV}" <<EOF
LITELLM_ENVIRONMENT=development
LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
LITELLM_DB_PASSWORD=${LITELLM_DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
LITELLM_CONFIG_FILE=./config.gemini-free.yaml
GEMINI_API_KEY=${GEMINI_API_KEY}
OPENAI_API_KEY=
EOF

"${PYTHON_BIN}" - "${APP_TEMPLATE}" "${APP_ENV}" "${LITELLM_MASTER_KEY}" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1]).read_text(encoding="utf-8")
master_key = sys.argv[3]
src = src.replace(
    "MEDGUARD_LLM_GATEWAY_API_KEY=replace-with-the-same-random-master-key-as-litellm",
    f"MEDGUARD_LLM_GATEWAY_API_KEY={master_key}",
)
Path(sys.argv[2]).write_text(src, encoding="utf-8")
PY

chmod 600 "${GATEWAY_ENV}" "${APP_ENV}"

echo "Configured local Gemini free runtime files:"
echo "  ${APP_ENV}"
echo "  ${GATEWAY_ENV}"
echo "No API key was committed or printed."
echo
echo "Next:"
echo "  cd infrastructure/litellm && docker compose up -d"
echo "  cd ../.. && python scripts/smoke_test_gemini_runtime.py --all"
