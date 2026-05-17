#!/bin/sh
# Tailscale sidecar for celery-booking-browser — optional exit node (residential IP).
set -eu

TAILSCALED_SOCK="${TAILSCALED_SOCK:-/var/run/tailscale/tailscaled.sock}"
TS_HOSTNAME="${TS_HOSTNAME:-tailscale-booking-browser}"
TS_LOGIN_SERVER="${TS_LOGIN_SERVER:-}"
TS_AUTHKEY="${TS_AUTHKEY:-}"
TAILSCALE_EXIT_NODE="${TAILSCALE_EXIT_NODE:-}"

if [ -z "${TS_AUTHKEY}" ]; then
  echo "tailscale-booking: TS_AUTHKEY_BOOKING_BROWSER nije postavljen — čekam (dodajte u .env)"
  exec sleep infinity
fi

mkdir -p /var/run/tailscale /var/lib/tailscale

tailscaled --state=/var/lib/tailscale/tailscaled.state --socket="${TAILSCALED_SOCK}" &
TS_PID=$!

for _ in $(seq 1 60); do
  if tailscale --socket="${TAILSCALED_SOCK}" version >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

UP_ARGS="--hostname=${TS_HOSTNAME} --accept-dns=false --accept-routes=true"
if [ -n "${TS_LOGIN_SERVER}" ]; then
  UP_ARGS="${UP_ARGS} --login-server=${TS_LOGIN_SERVER}"
fi
if [ -n "${TS_AUTHKEY}" ]; then
  UP_ARGS="${UP_ARGS} --authkey=${TS_AUTHKEY}"
fi

# shellcheck disable=SC2086
tailscale --socket="${TAILSCALED_SOCK}" up ${UP_ARGS}

if [ -n "${TAILSCALE_EXIT_NODE}" ]; then
  echo "tailscale-booking: setting exit node to ${TAILSCALE_EXIT_NODE}"
  tailscale --socket="${TAILSCALED_SOCK}" set \
    --exit-node="${TAILSCALE_EXIT_NODE}" \
    --exit-node-allow-lan-access=true
  sleep 2
  tailscale --socket="${TAILSCALED_SOCK}" status || true
fi

wait "${TS_PID}"
