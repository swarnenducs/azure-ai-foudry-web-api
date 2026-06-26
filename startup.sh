#!/bin/bash
# Azure Web App (Linux) startup script

APP_ROOT="${APP_PATH:-/home/site/wwwroot}"
cd "$APP_ROOT" || exit 1

export PYTHONPATH="${APP_ROOT}:${PYTHONPATH:-}"
PORT="${WEBSITES_PORT:-${PORT:-8000}}"

# Oryx creates antenv during deployment; fall back to local venv or python3.
if [ -x "${APP_ROOT}/antenv/bin/python" ]; then
  PYTHON="${APP_ROOT}/antenv/bin/python"
elif [ -x "${APP_ROOT}/.venv/bin/python" ]; then
  PYTHON="${APP_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

echo "Starting FastAPI from ${APP_ROOT} on port ${PORT} using ${PYTHON}"

exec "${PYTHON}" -m uvicorn src.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
