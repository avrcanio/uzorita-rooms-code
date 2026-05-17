#!/bin/sh
# Healthcheck for tailscale-booking-browser sidecar.
set -eu

TAILSCALED_SOCK="${TAILSCALED_SOCK:-/var/run/tailscale/tailscaled.sock}"

TS_AUTHKEY="${TS_AUTHKEY:-}"
if [ -z "${TS_AUTHKEY}" ]; then
  exit 0
fi

if ! tailscale --socket="${TAILSCALED_SOCK}" status >/dev/null 2>&1; then
  exit 1
fi
if tailscale --socket="${TAILSCALED_SOCK}" status 2>&1 | grep -qi "Tailscale is starting"; then
  exit 1
fi

TAILSCALE_EXIT_NODE="${TAILSCALE_EXIT_NODE:-}"
if [ -z "${TAILSCALE_EXIT_NODE}" ]; then
  exit 0
fi

# Exit node name appears in `tailscale status` when routing is active.
if tailscale --socket="${TAILSCALED_SOCK}" status 2>/dev/null | grep -qi "exit node"; then
  exit 0
fi

# Fallback: peer listed as exit node in JSON
if tailscale --socket="${TAILSCALED_SOCK}" status --json 2>/dev/null | grep -q "${TAILSCALE_EXIT_NODE}"; then
  exit 0
fi

exit 1
