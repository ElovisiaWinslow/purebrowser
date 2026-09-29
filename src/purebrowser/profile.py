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

    # 保留持久 cookie，让登录状态跨会话保持。
    # AllowPersistentCookies 是正常浏览器行为：
    #   - 带过期时间的 cookie 落盘，重开浏览器仍在
    #   - 会话 cookie 关窗口即失效
    #
    # 注意：不要改回 NoPersistentCookies。那会清空所有 cookie，
    # 导致每次打开 B 站都要重新登录。见 AGENTS.md 第二节。
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
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