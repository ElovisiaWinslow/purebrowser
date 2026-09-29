from pathlib import Path

from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
)

FAKE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def build_profile(
    storage_dir: Path, interceptor: QWebEngineUrlRequestInterceptor
) -> QWebEngineProfile:
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "storage").mkdir(exist_ok=True)
    (storage_dir / "cache").mkdir(exist_ok=True)

    profile = QWebEngineProfile("purebrowser", None)
    profile.setPersistentStoragePath(str(storage_dir / "storage"))
    profile.setCachePath(str(storage_dir / "cache"))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    )
    profile.setHttpUserAgent(FAKE_UA)
    profile.setUrlRequestInterceptor(interceptor)

    s = profile.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

    return profile