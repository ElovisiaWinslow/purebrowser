"""Chromium flags injected before QtWebEngine boots.

Must be applied before any Qt import that pulls QtWebEngineCore.
"""
import os

FLAGS = [
    # --- kill Google/telemetry surface ---
    "--disable-background-networking",
    "--disable-breakpad",
    "--disable-crash-reporter",
    "--disable-client-side-phishing-detection",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-sync",
    "--no-pings",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-search-engine-collection",
    # --- disable features we don't want ---
    "--disable-features="
    "Translate,"
    "OptimizationHints,"
    "OptimizationGuideModelDownloading,"
    "MediaRouter,"
    "InterestFeedContentSuggestions,"
    "AutofillServerCommunication,"
    "PrivacySandboxSettings4,"
    "CalculateNativeWinOcclusion",
    # --- privacy-preserving defaults ---
    "--enable-features="
    "DnsOverHttps,"
    "HttpsUpgrades,"
    "PartitionedCookies,"
    "ThirdPartyStoragePartitioning",
    "--dns-over-https-templates=https://dns.alidns.com/dns-query",
]


def apply() -> None:
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    merged = (existing + " " + " ".join(FLAGS)).strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = merged