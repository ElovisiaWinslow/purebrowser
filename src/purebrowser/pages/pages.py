import base64
import json
import shutil
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrlQuery
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)
from PyQt6.QtWidgets import QFileDialog

from purebrowser.data import favicons
from purebrowser.data import history as history_mod
from purebrowser.core.locations import default_download_dir, resource_path, set_data_dir

NEWTAB_HTML_PATH = resource_path("newtab.html")

REFRESH_SNIPPET = (
    b"<html><head><meta charset='utf-8'></head>"
    b"<body><script>parent.location.reload();</script></body></html>"
)


def _theme_root(theme) -> str:
    """把 Theme 的语义色转成 CSS 变量块（theme 为 None 时退回系统色）。"""
    if theme is None:
        return ":root{color-scheme:light dark;}"
    return (
        ":root{"
        f"--bg:{theme.window};"
        f"--panel:{theme.chrome};"
        f"--text:{theme.text};"
        f"--subtext:{theme.subtext};"
        f"--accent:{theme.accent};"
        f"--border:{theme.border};"
        f"--hover:{theme.hover};"
        f"--danger:{theme.danger};"
        f"--on-accent:{theme.on_accent};"
        f"--shadow:{theme.shadow};"
        f"--radius:{theme.radius}px;"
        f"--panel-radius:{theme.panel}px;"
        "}"
    )


HISTORY_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>历史记录</title>
<style>
  __THEME_ROOT__
  * { box-sizing: border-box; }
  body { font: 13px system-ui, "Microsoft YaHei", sans-serif; margin: 0;
         background: var(--bg); color: var(--text); }
  .wrap { max-width: 820px; margin: 0 auto; padding: 24px 24px 48px; }
  .head { display: flex; align-items: baseline; justify-content: space-between;
          margin-bottom: 12px; }
  h1 { font-size: 20px; font-weight: 650; margin: 0; letter-spacing: -0.01em; }
  .count { color: var(--subtext); font-size: 12px; }
  .search { position: sticky; top: 0; z-index: 2; padding: 6px 0 12px;
            background: var(--bg); }
  .search input { width: 100%; padding: 10px 14px; font-size: 13px;
                  color: var(--text); background: var(--panel);
                  border: 1px solid var(--border); border-radius: var(--radius);
                  outline: none; }
  .search input:focus { border-color: var(--accent); }
  .list { list-style: none; margin: 0; padding: 0; }
  .item { display: flex; gap: 12px; align-items: center;
          padding: 9px 12px; margin-bottom: 6px;
          background: var(--panel); border: 1px solid var(--border);
          border-radius: var(--radius); }
  .item:hover { border-color: var(--accent); }
  .fav { width: 20px; height: 20px; flex: 0 0 20px; border-radius: 5px;
         object-fit: contain; }
  .fav.ph { display: inline-flex; align-items: center; justify-content: center;
            background: var(--border); color: var(--subtext); }
  .fav.ph svg { width: 14px; height: 14px; }
  .meta { min-width: 0; flex: 1; }
  .title { font-weight: 600; white-space: nowrap; overflow: hidden;
           text-overflow: ellipsis; }
  .url { opacity: .6; font-size: 12px; margin-top: 2px; color: var(--subtext);
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  a { color: inherit; text-decoration: none; display: block; }
  .empty { text-align: center; padding: 80px 20px; color: var(--subtext); }
  .empty svg { width: 52px; height: 52px; opacity: .45; }
  .empty .t { font-size: 15px; font-weight: 600; color: var(--text); margin-top: 12px; }
  .empty .h { font-size: 12px; margin-top: 6px; }
  .hidden { display: none; }
</style></head><body>
<div class="wrap">
  <div class="head"><h1>历史记录</h1><span class="count" id="count"></span></div>
  <div class="search"><input id="q" placeholder="搜索历史记录" autocomplete="off"></div>
  <div id="empty" class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
         stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
    <div class="t" id="emptyTitle">暂无历史记录</div>
    <div class="h" id="emptyHint">浏览过的网页会出现在这里</div>
  </div>
  <ul class="list" id="list"></ul>
</div>
<script>
const rows = __DATA__;
const list = document.getElementById('list');
const empty = document.getElementById('empty');
const countEl = document.getElementById('count');

function globeSvg() {
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
         'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
         '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>' +
         '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 ' +
         '15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>';
}

function render(filter) {
  filter = (filter || '').trim().toLowerCase();
  const shown = filter
    ? rows.filter(r => (r.title || '').toLowerCase().includes(filter) ||
                       (r.url || '').toLowerCase().includes(filter))
    : rows;
  list.innerHTML = '';
  for (const r of shown) {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.className = 'item';
    a.href = r.url;
    if (r.icon) {
      const img = document.createElement('img');
      img.className = 'fav'; img.src = r.icon; img.alt = '';
      a.appendChild(img);
    } else {
      const d = document.createElement('span');
      d.className = 'fav ph'; d.innerHTML = globeSvg();
      a.appendChild(d);
    }
    const meta = document.createElement('div');
    meta.className = 'meta';
    const t = document.createElement('div');
    t.className = 'title'; t.textContent = r.title || r.url;
    const u = document.createElement('div');
    u.className = 'url'; u.textContent = r.url;
    meta.appendChild(t); meta.appendChild(u);
    a.appendChild(meta);
    li.appendChild(a);
    list.appendChild(li);
  }
  const hasRows = rows.length > 0;
  const hasShown = shown.length > 0;
  empty.classList.toggle('hidden', hasShown);
  list.classList.toggle('hidden', !hasShown);
  if (!hasRows) {
    document.getElementById('emptyTitle').textContent = '暂无历史记录';
    document.getElementById('emptyHint').textContent = '浏览过的网页会出现在这里';
  } else if (!hasShown) {
    document.getElementById('emptyTitle').textContent = '无匹配结果';
    document.getElementById('emptyHint').textContent = '换个关键词试试';
  }
  countEl.textContent = hasRows ? (shown.length + ' / ' + rows.length) : '';
}

document.getElementById('q').addEventListener('input', e => render(e.target.value));
render('');
</script>
<script>
// Ctrl+F 网页优先：未处理时打印暗号，交给 PurePage → MainWindow 打开查找条。
(function () {
  if (window.__pbFindHooked) return;
  window.__pbFindHooked = true;
  window.addEventListener('keydown', function (e) {
    if (!e.ctrlKey || e.shiftKey || e.altKey || e.metaKey) return;
    if (e.key !== 'f' && e.key !== 'F') return;
    var ev = e;
    setTimeout(function () {
      if (!ev.defaultPrevented) {
        try { console.log('__PB_FIND__'); } catch (err) {}
      }
    }, 0);
  }, true);
})();
</script>
</body></html>
"""

SETTINGS_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>设置</title>
<style>
  __THEME_ROOT__
  * { box-sizing: border-box; }
  body { font: 13px system-ui, "Microsoft YaHei", sans-serif; margin: 0;
         background: var(--bg); color: var(--text); }
  .container { max-width: 760px; margin: 0 auto; padding: 28px 24px 48px; }
  h1 { font-size: 20px; font-weight: 650; margin: 0 0 20px; letter-spacing: -0.01em; }
  section { margin-bottom: 18px; padding: 16px 18px; border-radius: var(--panel-radius);
            background: var(--panel);
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px var(--shadow); }
  h2 { display: flex; align-items: center; gap: 8px;
       font-size: 15px; font-weight: 600; margin: 0 0 14px; }
  h2::before { content: ""; width: 8px; height: 8px; border-radius: 3px;
               background: var(--accent); flex: 0 0 auto; }
  .row { display: flex; align-items: center; justify-content: space-between;
         padding: 10px 0; gap: 16px; }
  .row + .row { border-top: 1px solid var(--border); }
  label { flex: 1; min-width: 0; }
  .desc { opacity: 0.65; font-size: 12px; margin-top: 2px; }
  .path { opacity: 0.5; font-size: 12px; margin-top: 6px;
          font-family: ui-monospace, Consolas, monospace;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hint { opacity: 0.5; font-size: 12px; margin-top: 4px; }
  .btn-group { display: flex; gap: 6px; flex: 0 0 auto; }
  select, button { font: inherit; padding: 6px 12px; border-radius: var(--radius);
                   border: 1px solid var(--border);
                   background: var(--bg); color: var(--text); cursor: pointer;
                   white-space: nowrap; }
  select:hover, button:hover { background: var(--hover); }
  select:focus, button:focus { outline: none; border-color: var(--accent); }
  button:active { background: var(--border); }
  button.danger { border-color: var(--danger); color: var(--danger); min-width: 64px; }
  .switch { position: relative; width: 40px; height: 22px; flex: 0 0 auto; }
  .switch input { display: none; }
  .switch span { position: absolute; inset: 0; border-radius: 11px;
                 background: var(--border);
                 transition: .15s; cursor: pointer; }
  .switch span::after { content: ""; position: absolute; top: 2px; left: 2px;
                        width: 18px; height: 18px; border-radius: 50%;
                        background: var(--on-accent); transition: .15s; }
  .switch input:checked + span { background: var(--accent); }
  .switch input:checked + span::after { transform: translateX(18px); }
</style></head><body>
<div class="container">
  <h1>PureBrowser 设置</h1>
  <iframe id="bridge" style="display:none"></iframe>

  <section>
    <h2>外观</h2>
    <div class="row">
      <label>
        主题
        <div class="desc">跟随系统、亮色或暗色</div>
        <div class="hint">修改后需要重启浏览器</div>
      </label>
      <select id="theme" onchange="save('theme', this.value)">
        <option value="system">跟随系统</option>
        <option value="light">亮色</option>
        <option value="dark">暗色</option>
      </select>
    </div>
  </section>

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
    <h2>启动</h2>
    <div class="row">
      <label>
        启动时询问是否恢复会话
        <div class="desc">启动时弹出提示，询问是否恢复上次关闭的标签页</div>
      </label>
      <label class="switch">
        <input type="checkbox" id="restore"
               onchange="save('restore_session', this.checked)">
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
document.getElementById('restore').checked = __RESTORE__;
document.getElementById('theme').value = "__THEME__";
</script>
<script>
// Ctrl+F 网页优先：未处理时打印暗号，交给 PurePage → MainWindow 打开查找条。
(function () {
  if (window.__pbFindHooked) return;
  window.__pbFindHooked = true;
  window.addEventListener('keydown', function (e) {
    if (!e.ctrlKey || e.shiftKey || e.altKey || e.metaKey) return;
    if (e.key !== 'f' && e.key !== 'F') return;
    var ev = e;
    setTimeout(function () {
      if (!ev.defaultPrevented) {
        try { console.log('__PB_FIND__'); } catch (err) {}
      }
    }, 0);
  }, true);
})();
</script>
</body></html>
"""


def _favicon_data_uri(conn, host: str) -> str:
    """把某 host 的缓存 favicon 转成 data URI；无缓存返回空串。"""
    if not host:
        return ""
    pixmap = favicons.get(conn, host)
    if pixmap is None or pixmap.isNull():
        return ""
    data = QByteArray()
    buf = QBuffer(data)
    if not buf.open(QIODevice.OpenModeFlag.WriteOnly):
        return ""
    try:
        pixmap.save(buf, "PNG")
    finally:
        buf.close()
    raw = bytes(data)
    if not raw:
        return ""
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _history_html(conn, theme=None) -> str:
    rows = [
        {
            "url": r["url"],
            "title": r["title"],
            "icon": _favicon_data_uri(conn, r["host"] or ""),
        }
        for r in history_mod.recent(conn, limit=500)
    ]
    return (
        HISTORY_TEMPLATE
        .replace("__THEME_ROOT__", _theme_root(theme))
        .replace("__DATA__", json.dumps(rows, ensure_ascii=False))
    )


def _settings_html(settings, data_dir: Path, theme=None) -> str:
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
        .replace("__THEME_ROOT__", _theme_root(theme))
        .replace("__ENGINES__", engine_options)
        .replace("__INTERCEPTOR__", "true" if d["interceptor_enabled"] else "false")
        .replace("__DOH__", "true" if d["doh_enabled"] else "false")
        .replace("__RESTORE__", "true" if d.get("restore_session", True) else "false")
        .replace("__THEME__", str(d.get("theme", "system")))
        .replace("__DATA_DIR__", str(data_dir))
        .replace("__DOWNLOAD_DIR__", download_dir)
        .replace("__CACHE_DIR__", cache_dir)
    )


class PureBrowserSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, settings, conn, data_dir: Path, parent=None, theme=None):
        super().__init__(parent)
        self._settings = settings
        self._conn = conn
        self._data_dir = Path(data_dir)
        self._theme = theme
        self._buffers: list[QBuffer] = []

    def requestStarted(self, job) -> None:
        url = job.requestUrl()
        host = url.host()
        path = url.path()

        if host == "newtab":
            self._serve_newtab(job)
            return

        if host == "history":
            self._serve_bytes(
                job, _history_html(self._conn, self._theme).encode("utf-8"), b"text/html"
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
                _settings_html(self._settings, self._data_dir, self._theme).encode(
                    "utf-8"
                ),
                b"text/html",
            )
            return

        job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)

    def _serve_newtab(self, job) -> None:
        """读取 newtab.html 并注入当前主题的 CSS 变量（anchor: /* __THEME_VARS__ */）。"""
        try:
            html = NEWTAB_HTML_PATH.read_text(encoding="utf-8")
        except OSError:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        t = self._theme
        if t is None:
            html = html.replace("/* __THEME_VARS__ */", "")
        else:
            css_vars = (
                ":root {\n"
                f"    --bg: {t.window};\n"
                f"    --panel: {t.chrome};\n"
                f"    --text: {t.text};\n"
                f"    --subtext: {t.subtext};\n"
                f"    --accent: {t.accent};\n"
                f"    --border: {t.border};\n"
                f"    --on-accent: {t.on_accent};\n"
                f"    --radius: {t.radius}px;\n"
                f"    --panel-radius: {t.panel}px;\n"
                "}"
            )
            html = html.replace("/* __THEME_VARS__ */", css_vars)
        self._serve_bytes(job, html.encode("utf-8"), b"text/html")

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