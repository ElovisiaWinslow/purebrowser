import json
import time
from pathlib import Path

from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)


class Blocker(QWebEngineUrlRequestInterceptor):
    BUILTIN_BLOCK = {
        "doubleclick.net",
        "googlesyndication.com",
        "googleadservices.com",
        "google-analytics.com",
        "googletagmanager.com",
        "googletagservices.com",
        "adservice.google.com",
        "facebook.net",
        "connect.facebook.net",
        "scorecardresearch.com",
        "criteo.com",
        "criteo.net",
        "outbrain.com",
        "taboola.com",
        "quantserve.com",
        "hotjar.com",
        "mixpanel.com",
        "segment.io",
        "amplitude.com",
        "branch.io",
        "adjust.com",
        "appsflyer.com",
    }

    def __init__(self, settings, extra_block=None, netlog_path: Path | None = None):
        super().__init__()
        self._settings = settings
        self.block = set(self.BUILTIN_BLOCK)
        if extra_block:
            self.block |= {h.lower() for h in extra_block}
        self.stats = {"blocked": 0, "https_upgrades": 0, "cookie_stripped": 0}
        self._log = None
        if netlog_path is not None:
            netlog_path = Path(netlog_path)
            netlog_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = netlog_path.open("a", encoding="utf-8")

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url = info.requestUrl()
        host = (url.host() or "").lower()
        first_party = (info.firstPartyUrl().host() or "").lower()
        enabled = bool(self._settings.get("interceptor_enabled", True))

        blocked = False

        if enabled:
            if host and self._is_blocked(host):
                info.block(True)
                self.stats["blocked"] += 1
                blocked = True
            else:
                if host and first_party and host != first_party:
                    rtype = info.resourceType()
                    if rtype in (
                        QWebEngineUrlRequestInfo.ResourceType.ResourceTypeXhr,
                        QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMedia,
                    ):
                        info.setHttpHeader(b"Cookie", b"")
                        self.stats["cookie_stripped"] += 1

                if url.scheme() == "http":
                    https = url
                    https.setScheme("https")
                    info.redirect(https)
                    self.stats["https_upgrades"] += 1

        self._write_log(url.toString(), host, first_party, blocked)

    def _is_blocked(self, host: str) -> bool:
        for bad in self.block:
            if host == bad or host.endswith("." + bad):
                return True
        return False

    def _write_log(self, url: str, host: str, first_party: str, blocked: bool) -> None:
        if self._log is None:
            return
        record = {
            "ts": time.time(),
            "url": url,
            "host": host,
            "first_party": first_party,
            "blocked": blocked,
        }
        self._log.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._log.flush()

    def close(self) -> None:
        if self._log is not None:
            self._log.close()
            self._log = None