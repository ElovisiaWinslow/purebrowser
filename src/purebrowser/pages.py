import json
import shutil
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrlQuery
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)
from PyQt6.QtWidgets import QFileDialog

from . import history as history_mod
from .locations import default_download_dir, set_data_dir

NEWTAB_HTML_PATH = Path(__file__).resolve().parents[2] / "resources" / "newtab.html"

REFRESH_SNIPPET = (
    b"<html><head><meta charset='utf-8'></head>"
    b"<body><script>parent.location.reload();</script></body></html>"
)

HISTORY_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>历史记录</title>
<style>
  body { font: 14px system-ui, "Microsoft YaHei", sans-serif; margin: 0;
         background: Canvas; color: CanvasText; }
  h1 { padding: 20px 24px 8px; font-size: 20px; margin: 0; }
  ul { list-style: none; margin: 0; padding: 8px 24px 32px; }
  li { padding: 10px 0; border-bottom: 1px solid rgba(128,128,128,.2); }
  a { color: inherit; text-decoration: none; display: block; }
  .title { font-weight: 600; }
  .url { opacity: .6; font-size: 12px; margin-top: 2px; }
  .empty { padding: 40px; opacity: .6; text-align: center; }
</style></head><body>
<h1>历史记录</h1>
<div id="root"></div>
<script>
const rows = __DATA__;
const root = document.getElementById('root');
if (!rows.length) {
  root.innerHTML = '<div class="empty">暂无历史记录</div>';
} else {
  const ul = document.createElement('ul');
  for (const r of rows) {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = r.url;
    const t = document.createElement('div');
    t.className = 'title';
    t.textContent = r.title || r.url;
    const u = document.createElement('div');
    u.className = 'url';
    u.textContent = r.url;
    a.appendChild(t);
    a.appendChild(u);
    li.appendChild(a);
    ul.appendChild(li);
  }
  root.appendChild(ul);
}
</script>
</body></html>
"""

SETTINGS_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>设置</title>
<style>
  body { font: 14px system-ui, "Microsoft YaHei", sans-serif; margin: 0;
         background: Canvas; color: CanvasText; }
  .container { max-width: 760px; margin: 0 auto; padding: 32px 24px; }
  h1 { font-size: 22px; font-weight: 600; margin: 0 0 24px; }
  section { margin-bottom: 24px; padding: 20px; border-radius: 12px;
            background: color-mix(in oklab, Canvas 92%, CanvasText 8%);
            border: 1px solid color-mix(in oklab, CanvasText 12%, transparent); }
  h2 { font-size: 15px; font-weight: 600; margin: 0 0 14px; }
  .row { display: flex; align-items: center; justify-content: space-between;
         padding: 12px 0; gap: 16px; }
  .row + .row { border-top: 1px solid color-mix(in oklab, CanvasText 8%, transparent); }
  label { flex: 1; min-width: 0; }
  .desc { opacity: 0.65; font-size: 12px; margin-top: 2px; }
  .path { opacity: 0.5; font-size: 12px; margin-top: 6px;
          font-family: ui-monospace, Consolas, monospace;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hint { opacity: 0.5; font-size: 12px; margin-top: 4px; }
  .btn-group { display: flex; gap: 6px; flex: 0 0 auto; }
  select, button { font: inherit; padding: 6px 12px; border-radius: 8px;
                   border: 1px solid color-mix(in oklab, CanvasText 20%, transparent);
                   background: Canvas; color: inherit; cursor: pointer;
                   white-space: nowrap; }
  button.danger { border-color: #c0392b; color: #c0392b; min-width: 64px; }
  .switch { position: relative; width: 40px; height: 22px; flex: 0 0 auto; }
  .switch input { display: none; }
  .switch span { position: absolute; inset: 0; border-radius: 11px;
                 background: color-mix(in oklab, CanvasText 20%, transparent);
                 transition: .15s; cursor: pointer; }
  .switch span::after { content: ""; position: absolute; top: 2px; left: 2px;
                        width: 18px; height: 18px; border-radius: 50%;
                        background: white; transition: .15s; }
  .switch input:checked + span { background: #2f6feb; }
  .switch input:checked + span::after { transform: translateX(18px); }
</style></head><body>
<div class="container">
  <h1>PureBrowser 设置</h1>
  <iframe id="bridge" style="display:none"></iframe>

  <section>
    <h2>隐私</h2>
    <div class="row">
      <label>
        请求拦截器
        <div class="desc">阻止广告、追踪器，去掉跨站 Cookie</div>
      </label>
      <label class="switch">
        <input type="checkbox" id="interceptor"
               onchange="save('interceptor_enabled', this.checked)">
        <span></span>
      </label>
    </div>
    <div class="row">
      <label>
        DNS over HTTPS
        <div class="desc">加密 DNS 查询</div>
        <div class="hint">修改后需要重启浏览器</div>
      </label>
      <label class="switch">
        <input type="checkbox" id="doh"
               onchange="save('doh_enabled', this.checked)">
        <span></span>
      </label>
    </div>
  </section>

  <section>
    <h2>搜索引擎</h2>
    <div class="row">
      <label>
        默认搜索引擎
        <div class="desc">地址栏输入关键词时使用</div>
      </label>
      <select id="engine" onchange="save('search_engine', this.value)">
        __ENGINES__
      </select>
    </div>
  </section>

  <section>
    <h2>存储</h2>
    <div class="row">
      <label>
        数据目录
        <div class="desc">历史、缓存、Cookie 存储位置</div>
        <div class="hint">修改后需要重启浏览器</div>
        <div class="path" title="__DATA_DIR__">__DATA_DIR__</div>
      </label>
      <div class="btn-group">
        <button onclick="pickFolder('data')">更改</button>
        <button onclick="openFolder('data')">打开</button>
      </div>
    </div>
    <div class="row">
      <label>
        下载目录
        <div class="desc">下载文件的保存位置</div>
        <div class="path" title="__DOWNLOAD_DIR__">__DOWNLOAD_DIR__</div>
      </label>
      <div class="btn-group">
        <button onclick="pickFolder('download')">更改</button>
        <button onclick="openFolder('download')">打开</button>
      </div>
    </div>
    <div class="row">
      <label>
        缓存目录
        <div class="desc">网页缓存，图片等临时文件</div>
        <div class="path" title="__CACHE_DIR__">__CACHE_DIR__</div>
      </label>
      <button class="danger" onclick="clearCache(this)">清除</button>
    </div>
  </section>

  <section>
    <h2>数据</h2>
    <div class="row">
      <label>清除浏览历史</label>
      <button class="danger" onclick="clearHistory(this)">清除</button>
    </div>
  </section>
</div>

<script>
const iframe = document.getElementById('bridge');

function save(key, value) {
  iframe.src = 'purebrowser://settings/save?key=' + encodeURIComponent(key)
             + '&value=' + encodeURIComponent(value) + '&t=' + Date.now();
}
function pickFolder(target) {
  iframe.src = 'purebrowser://settings/pick-folder?target=' + target
             + '&t=' + Date.now();
}
function openFolder(target) {
  iframe.src = 'purebrowser://settings/open-folder?target=' + target
             + '&t=' + Date.now();
}
function clearCache(btn) {
  const old = btn.textContent;
  btn.textContent = '已清除';
  iframe.src = 'purebrowser://settings/clear-cache?t=' + Date.now();
  setTimeout(() => { btn.textContent = old; }, 1500);
}
function clearHistory(btn) {
  const old = btn.textContent;
  btn.textContent = '已清除';
  iframe.src = 'purebrowser://settings/clear-history?t=' + Date.now();
  setTimeout(() => { btn.textContent = old; }, 1500);
}

document.getElementById('interceptor').checked = __INTERCEPTOR__;
document.getElementById('doh').checked = __DOH__;
</script>
</body></html>
"""


def _history_html(conn) -> str:
    rows = [
        {"url": r["url"], "title": r["title"]}
        for r in history_mod.recent(conn, limit=500)
    ]
    return HISTORY_TEMPLATE.replace("__DATA__", json.dumps(rows, ensure_ascii=False))


def _settings_html(settings, data_dir: Path) -> str:
    d = settings.all()
    engines = [
        ("bing", "Bing (国内)"),
        ("baidu", "百度"),
        ("duckduckgo", "DuckDuckGo"),
        ("google", "Google"),
    ]
    engine_options = "".join(
        '<option value="{k}"{sel}>{label}</option>'.format(
            k=k, label=label,
            sel=" selected" if k == d["search_engine"] else "",
        )
        for k, label in engines
    )
    custom = (d.get("download_dir") or "").strip()
    download_dir = custom if custom else f"{default_download_dir()}  (默认)"
    cache_dir = str(data_dir / "cache")

    return (
        SETTINGS_TEMPLATE
        .replace("__ENGINES__", engine_options)
        .replace("__INTERCEPTOR__", "true" if d["interceptor_enabled"] else "false")
        .replace("__DOH__", "true" if d["doh_enabled"] else "false")
        .replace("__DATA_DIR__", str(data_dir))
        .replace("__DOWNLOAD_DIR__", download_dir)
        .replace("__CACHE_DIR__", cache_dir)
    )


class PureBrowserSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, settings, conn, data_dir: Path, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._conn = conn
        self._data_dir = Path(data_dir)
        self._buffers: list[QBuffer] = []

    def requestStarted(self, job) -> None:
        url = job.requestUrl()
        host = url.host()
        path = url.path()

        if host == "newtab":
            self._serve_file(job, NEWTAB_HTML_PATH, b"text/html")
            return

        if host == "history":
            self._serve_bytes(
                job, _history_html(self._conn).encode("utf-8"), b"text/html"
            )
            return

        if host == "settings":
            if path == "/save":
                q = QUrlQuery(url.query())
                key = q.queryItemValue("key")
                value = q.queryItemValue("value")
                if key:
                    self._settings.set(key, value)
                self._serve_bytes(job, b"", b"text/plain")
                return

            if path == "/clear-history":
                history_mod.clear(self._conn)
                self._serve_bytes(job, b"", b"text/plain")
                return

            if path == "/clear-cache":
                self._clear_cache()
                self._serve_bytes(job, REFRESH_SNIPPET, b"text/html")
                return

            if path == "/pick-folder":
                q = QUrlQuery(url.query())
                target = q.queryItemValue("target")
                self._pick_folder(target)
                self._serve_bytes(job, REFRESH_SNIPPET, b"text/html")
                return

            if path == "/open-folder":
                q = QUrlQuery(url.query())
                target = q.queryItemValue("target")
                self._open_folder(target)
                self._serve_bytes(job, b"", b"text/plain")
                return

            self._serve_bytes(
                job,
                _settings_html(self._settings, self._data_dir).encode("utf-8"),
                b"text/html",
            )
            return

        job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)

    def _pick_folder(self, target: str) -> None:
        if target == "data":
            start = str(self._data_dir)
        else:
            custom = (self._settings.get("download_dir", "") or "").strip()
            start = custom if custom else str(default_download_dir())

        chosen = QFileDialog.getExistingDirectory(None, "选择文件夹", start)
        if not chosen:
            return
        if target == "data":
            set_data_dir(Path(chosen))
        elif target == "download":
            self._settings.set("download_dir", chosen)

    def _open_folder(self, target: str) -> None:
        import os

        if target == "data":
            p = self._data_dir
        else:
            custom = (self._settings.get("download_dir", "") or "").strip()
            p = Path(custom) if custom else default_download_dir()
        if p.exists():
            os.startfile(str(p))  # noqa: S606

    def _clear_cache(self) -> None:
        cache_dir = self._data_dir / "cache"
        if not cache_dir.exists():
            return
        for child in cache_dir.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                pass

    def _serve_file(self, job, path: Path, mime: bytes) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        self._serve_bytes(job, data, mime)

    def _serve_bytes(self, job, data: bytes, mime: bytes) -> None:
        buf = QBuffer(job)
        buf.setData(QByteArray(data))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(mime, buf)
        self._buffers.append(buf)