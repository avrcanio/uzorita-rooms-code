#!/usr/bin/env python3
"""
Minimal Cloudflare DNS record upsert (create or update).

Auth (pick one):
- API token: env CLOUDFLARE_API_TOKEN (recommended)
- Global API key: env CLOUDFLARE_GLOBAL_API_KEY + env CLOUDFLARE_EMAIL

Zone:
- env CLOUDFLARE_ZONE_ID

Example:
  python3 code/ops/cloudflare_dns.py --env-file /opt/stacks/uzorita/rooms/.env \
    --type CNAME --name booking.uzorita.hr --content rooms.uzorita.hr --proxied true
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def load_env_file(path: str) -> None:
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].lstrip()
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if not k:
                    continue
                # Strip simple wrapping quotes; do not interpret escapes.
                if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                    v = v[1:-1]
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        raise SystemExit(f"env file not found: {path}")


def cf_headers() -> dict[str, str]:
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if token:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    key = os.getenv("CLOUDFLARE_GLOBAL_API_KEY", "").strip()
    email = os.getenv("CLOUDFLARE_EMAIL", "").strip()
    if key and email:
        return {
            "X-Auth-Key": key,
            "X-Auth-Email": email,
            "Content-Type": "application/json",
        }

    raise SystemExit(
        "Missing Cloudflare auth. Set CLOUDFLARE_API_TOKEN (recommended) or CLOUDFLARE_GLOBAL_API_KEY + CLOUDFLARE_EMAIL."
    )


def cf_request(method: str, url: str, body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=cf_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Cloudflare API error {e.code} {e.reason}: {msg}")
    except Exception as e:
        raise SystemExit(f"Cloudflare API request failed: {e}")

    try:
        return json.loads(payload)
    except Exception:
        raise SystemExit(f"Cloudflare API returned non-JSON: {payload[:200]}")


def ensure_ok(res: dict) -> None:
    if res.get("success") is True:
        return
    errs = res.get("errors") or []
    raise SystemExit(f"Cloudflare API responded with success=false errors={errs!r}")


def upsert_dns_record(*, zone_id: str, rtype: str, name: str, content: str, ttl: int, proxied: bool) -> None:
    base = "https://api.cloudflare.com/client/v4"
    q = urllib.parse.urlencode({"type": rtype, "name": name})
    list_url = f"{base}/zones/{zone_id}/dns_records?{q}"
    listed = cf_request("GET", list_url)
    ensure_ok(listed)
    records = listed.get("result") or []

    payload = {
        "type": rtype,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }

    if len(records) == 0:
        create_url = f"{base}/zones/{zone_id}/dns_records"
        created = cf_request("POST", create_url, payload)
        ensure_ok(created)
        rid = (created.get("result") or {}).get("id")
        print(f"created {rtype} {name} -> {content} (proxied={proxied}) id={rid}")
        return

    if len(records) == 1:
        rid = records[0].get("id")
        update_url = f"{base}/zones/{zone_id}/dns_records/{rid}"
        updated = cf_request("PUT", update_url, payload)
        ensure_ok(updated)
        print(f"updated {rtype} {name} -> {content} (proxied={proxied}) id={rid}")
        return

    ids = [r.get("id") for r in records]
    raise SystemExit(f"Multiple DNS records found for type={rtype} name={name}. ids={ids}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", default="", help="Optional .env file to load (no shell evaluation).")
    ap.add_argument("--zone-id", default="", help="Cloudflare zone id (or env CLOUDFLARE_ZONE_ID).")
    ap.add_argument("--type", default="CNAME", help="DNS record type (A, CNAME, etc).")
    ap.add_argument("--name", required=True, help="Record name, e.g. booking.uzorita.hr")
    ap.add_argument("--content", required=True, help="Record content, e.g. rooms.uzorita.hr or origin IP")
    ap.add_argument("--ttl", type=int, default=1, help="TTL seconds; 1 means auto on Cloudflare.")
    ap.add_argument("--proxied", default="true", choices=["true", "false"], help="Whether to proxy through Cloudflare.")
    args = ap.parse_args(argv)

    if args.env_file:
        load_env_file(args.env_file)

    zone_id = (args.zone_id or os.getenv("CLOUDFLARE_ZONE_ID") or "").strip()
    if not zone_id:
        raise SystemExit("Missing zone id. Pass --zone-id or set CLOUDFLARE_ZONE_ID.")

    upsert_dns_record(
        zone_id=zone_id,
        rtype=args.type.strip().upper(),
        name=args.name.strip(),
        content=args.content.strip(),
        ttl=int(args.ttl),
        proxied=args.proxied == "true",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

