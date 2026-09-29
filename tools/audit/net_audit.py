"""Analyze PureBrowser netlog (JSONL) and report remote hosts.

Usage:
    python tools/audit/net_audit.py path/to/netlog.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Hosts that should NEVER appear if we are truly telemetry-free.
TELEMETRY_HOSTS = [
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "clients1.google.com",
    "clients2.google.com",
    "clients3.google.com",
    "clients4.google.com",
    "update.googleapis.com",
    "safebrowsing.googleapis.com",
    "accounts.google.com",
    "ssl.gstatic.com",
    "www.google.com",
    "crashpad",
    "metrics",
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python tools/audit/net_audit.py <netlog.jsonl>")
        return 2

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"netlog not found: {log_path}")
        return 1

    host_counter: Counter[str] = Counter()
    blocked_counter: Counter[str] = Counter()
    first_party_counter: Counter[str] = Counter()
    total = 0
    blocked_total = 0

    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            host = rec.get("host") or "<none>"
            fp = rec.get("first_party") or "<none>"
            host_counter[host] += 1
            first_party_counter[fp] += 1
            if rec.get("blocked"):
                blocked_total += 1
                blocked_counter[host] += 1

    print("=" * 60)
    print(f"netlog: {log_path}")
    print(f"total requests : {total}")
    print(f"unique hosts   : {len(host_counter)}")
    print(f"blocked        : {blocked_total}")
    print("=" * 60)

    print("\nTop 25 hosts by request count:")
    for host, n in host_counter.most_common(25):
        print(f"  {n:5d}  {host}")

    print("\nFirst-party origins:")
    for host, n in first_party_counter.most_common(15):
        print(f"  {n:5d}  {host}")

    if blocked_counter:
        print("\nBlocked hosts:")
        for host, n in blocked_counter.most_common(20):
            print(f"  {n:5d}  {host}")

    print("\nTelemetry check:")
    hits = [h for h in host_counter if any(t in h for t in TELEMETRY_HOSTS)]
    if hits:
        print("  !! FOUND suspicious hosts:")
        for h in hits:
            print(f"     {h}")
    else:
        print("  OK - no known telemetry hosts observed.")

    print("\nAll observed hosts (sorted):")
    for host in sorted(host_counter):
        print(f"  {host}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())