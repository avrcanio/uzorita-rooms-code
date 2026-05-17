#!/bin/bash
set -euo pipefail

# Playwright sync API + Django ORM in the same Celery task (solo pool).
export DJANGO_ALLOW_ASYNC_UNSAFE=true

# Shared network namespace with tailscale-booking-browser (exit node egress).
wait_for_tailscale_egress() {
  if [ -z "${TAILSCALE_EXIT_NODE:-}" ]; then
    return 0
  fi
  echo "booking-browser: waiting for Tailscale exit node (${TAILSCALE_EXIT_NODE})..."
  for _ in $(seq 1 30); do
    if curl -4 -sf --max-time 5 https://ifconfig.me >/tmp/booking_egress_ip 2>/dev/null; then
      echo "booking-browser: outbound IPv4=$(cat /tmp/booking_egress_ip)"
      rm -f /tmp/booking_egress_ip
      return 0
    fi
    # Exit node peer reachable (routing up) even if laptop does not forward public web yet
    if curl -4 -sf --max-time 3 "http://${TAILSCALE_EXIT_NODE}/" >/dev/null 2>&1 \
      || ping -c1 -W2 "${TAILSCALE_EXIT_NODE}" >/dev/null 2>&1; then
      echo "booking-browser: exit node ${TAILSCALE_EXIT_NODE} reachable on tailnet"
      return 0
    fi
    sleep 2
  done
  echo "WARN: exit node ${TAILSCALE_EXIT_NODE} — javni internet još ne prolazi (provjerite Windows exit node / firewall na dellxps17)" >&2
}

wait_for_tailscale_egress

DISPLAY_NUM="${BOOKING_EXTRANET_VNC_DISPLAY:-:99}"
export DISPLAY="${DISPLAY_NUM}"
DISPLAY_ID="${DISPLAY_NUM#:}"
X_SOCKET="/tmp/.X11-unix/X${DISPLAY_ID}"
X_LOCK="/tmp/.X${DISPLAY_ID}-lock"

XVFB_W="${BOOKING_EXTRANET_VNC_WIDTH:-1280}"
XVFB_H="${BOOKING_EXTRANET_VNC_HEIGHT:-900}"
WEBSOCKIFY_PORT="${BOOKING_EXTRANET_VNC_PORT:-6080}"

cleanup() {
  kill "${WEBSOCKIFY_PID:-}" "${X11VNC_PID:-}" "${XVFB_PID:-}" 2>/dev/null || true
  rm -f "$X_SOCKET" "$X_LOCK"
}
trap cleanup EXIT INT TERM

# Stale socket/lock from a crashed Xvfb prevents the next start (crash-loop → Traefik 502).
pkill -f "Xvfb ${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "x11vnc -display ${DISPLAY_NUM}" 2>/dev/null || true
rm -f "$X_SOCKET" "$X_LOCK"
mkdir -p /tmp/.X11-unix

Xvfb "${DISPLAY_NUM}" -screen 0 "${XVFB_W}x${XVFB_H}x24" &
XVFB_PID=$!

xvfb_ready=0
for _ in $(seq 1 40); do
  if [ -S "$X_SOCKET" ] && kill -0 "$XVFB_PID" 2>/dev/null; then
    xvfb_ready=1
    break
  fi
  sleep 0.25
done
if [ "$xvfb_ready" -ne 1 ]; then
  echo "ERROR: Xvfb failed to start on ${DISPLAY_NUM}" >&2
  exit 1
fi

x11vnc -display "${DISPLAY_NUM}" -localhost -nopw -forever -shared &
X11VNC_PID=$!

websockify --web=/usr/share/novnc "${WEBSOCKIFY_PORT}" localhost:5900 &
WEBSOCKIFY_PID=$!

python manage.py migrate --noinput
exec celery -A config worker -l info -Q booking_browser --pool=solo --concurrency=1
