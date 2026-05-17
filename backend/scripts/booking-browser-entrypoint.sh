#!/bin/bash
set -euo pipefail

# Playwright sync API + Django ORM in the same Celery task (solo pool).
export DJANGO_ALLOW_ASYNC_UNSAFE=true

DISPLAY_NUM="${BOOKING_EXTRANET_VNC_DISPLAY:-:99}"
export DISPLAY="${DISPLAY_NUM}"

XVFB_W="${BOOKING_EXTRANET_VNC_WIDTH:-1280}"
XVFB_H="${BOOKING_EXTRANET_VNC_HEIGHT:-900}"
WEBSOCKIFY_PORT="${BOOKING_EXTRANET_VNC_PORT:-6080}"

Xvfb "${DISPLAY}" -screen 0 "${XVFB_W}x${XVFB_H}x24" &
XVFB_PID=$!
sleep 1

x11vnc -display "${DISPLAY}" -localhost -nopw -forever -shared &
X11VNC_PID=$!

websockify --web=/usr/share/novnc "${WEBSOCKIFY_PORT}" localhost:5900 &
WEBSOCKIFY_PID=$!

cleanup() {
  kill "${WEBSOCKIFY_PID}" "${X11VNC_PID}" "${XVFB_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python manage.py migrate --noinput
exec celery -A config worker -l info -Q booking_browser --pool=solo --concurrency=1
