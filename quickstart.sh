#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo "============================================================"
echo "      MEDGUARD AI SYSTEM - 1-CLICK QUICKSTART"
echo "============================================================"
echo

PYTHON_BIN="$(command -v python3 || command -v python || echo "python")"

# 1. Setup local environment & API keys (auto-embedded default key)
if [[ ! -f "${ROOT_DIR}/.env" ]] || [[ ! -f "${ROOT_DIR}/infrastructure/litellm/.env" ]]; then
    echo "[1/4] Chưa tìm thấy file cấu hình cục bộ. Đang tự động thiết lập..."
    chmod +x "${ROOT_DIR}/scripts/configure_gemini_free.sh"
    "${ROOT_DIR}/scripts/configure_gemini_free.sh" --default
    echo "  ✅ Đã khởi tạo .env và infrastructure/litellm/.env thành công."
else
    echo "[1/4] File cấu hình .env đã sẵn sàng."
fi
echo

# 2. Check & start LiteLLM Gateway via Docker
echo "[2/4] Kiểm tra và khởi động LiteLLM Gateway..."
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    (cd "${ROOT_DIR}/infrastructure/litellm" && docker compose up -d)
    echo "  ⏳ Đang chờ LiteLLM Gateway sẵn sàng trên port 4000..."
    for i in {1..30}; do
        if curl -s -f http://127.0.0.1:4000/health/liveliness >/dev/null 2>&1; then
            echo "  ✅ LiteLLM Gateway đã hoạt động trên http://127.0.0.1:4000"
            break
        fi
        sleep 1
    done
else
    echo "  ⚠️ Docker chưa chạy hoặc không tìm thấy Docker. Nếu bạn chạy gateway ở máy khác, vui lòng kiểm tra URL trong .env."
fi
echo

# 3. Check Python Virtual Environment
echo "[3/4] Kiểm tra môi trường Python..."
if [[ -f "${ROOT_DIR}/.venv/bin/python" ]]; then
    VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
    echo "  ✅ Sử dụng môi trường ảo: .venv"
else
    echo "  ⚠️ Chưa có .venv. Đang tạo .venv và cài đặt dependencies tối thiểu..."
    "${PYTHON_BIN}" -m venv "${ROOT_DIR}/.venv"
    VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
    "${VENV_PYTHON}" -m pip install --upgrade pip
    if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
        "${VENV_PYTHON}" -m pip install -r "${ROOT_DIR}/requirements.txt"
    fi
    echo "  ✅ Đã cài đặt xong môi trường ảo."
fi
echo

# 4. Instructions / Execution
echo "[4/4] Hệ thống đã sẵn sàng!"
echo "============================================================"
echo "CÁC LỆNH KHỞI CHẠY TIẾP THEO:"
echo "------------------------------------------------------------"
echo "1. Chạy Backend MedGuard Server:"
echo "   ${ROOT_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
echo
echo "2. Chạy Frontend (Giao diện bác sĩ / bệnh nhân):"
echo "   cd frontend && npm install && npm run dev"
echo
echo "3. Kiểm tra kết nối Model Gemini:"
echo "   ${ROOT_DIR}/.venv/bin/python scripts/smoke_test_gemini_runtime.py --all"
echo "============================================================"

if [[ "${1:-}" == "--run" ]]; then
    echo
    echo "🚀 Đang tự động khởi chạy Backend MedGuard trên http://127.0.0.1:8000..."
    exec "${VENV_PYTHON}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
fi
