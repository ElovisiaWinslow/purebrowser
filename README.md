<p align="center">
  <img src="docs/assets/purebrowser.png" width="128" alt="PureBrowser logo">
</p>

<h1 align="center">PureBrowser</h1>

<p align="center"><b>A Python-hackable, privacy-first browser with H.264 built in.</b></p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MPL--2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20x64-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status">
</p>

---

## What is this

PureBrowser is a Windows desktop browser built on **PyQt6 + a self-compiled QtWebEngine 6.7.3**.

It exists to solve one ecosystem-level pain point: the official Qt pip wheels ship **without H.264**, so
sites like Bilibili report "your browser does not support HTML5 playback". PureBrowser compiles
QtWebEngine from source with `-webengine-proprietary-codecs` so a Python browser can actually play video.
The whole build and every patch is documented in [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md).

The three things that set it apart:

1. **H.264 built in** — self-compiled Qt + QtWebEngine with proprietary codecs enabled. Bilibili plays.
2. **Hackable in pure Python** — every UI, privacy policy and blocking rule is a `.py` file under
   `src/purebrowser/`. Change a line, no C++ rebuild.
3. **Privacy-first and auditable** — no telemetry, no crash upload, no RLZ; HTTPS upgrades; DoH; a
   built-in ad/tracker blocklist; all site permissions denied by default; local SQLite only.

## System requirements

| Component | Version | Source |
|---|---|---|
| OS | Windows 10/11 **x64** | — |
| Python | **3.10.11** (project venv) | python.org |
| PyQt6 | 6.7.1 | **self-compiled wheel** (not PyPI) |
| PyQt6_sip | 13.8.0 | PyPI |
| PyQt6-WebEngine | 6.7.0 | **self-compiled wheel** (not PyPI) |
| Qt / QtWebEngine | 6.7.3 + H.264 | **self-compiled**, installed at `D:\develop\Qt6-custom` |

Environment variables (user level): `QT_PLUGIN_PATH` and `PATH` must point into the custom Qt install.

Pure-Python dependencies (declared in `pyproject.toml`): `httpx`, `platformdirs`.

## Quick start

### Normal users

> No public installer yet. Current status: **alpha**.

### Developers: clone and run

```bash
git clone https://github.com/<your-name>/purebrowser.git
cd purebrowser
```

**Step 1 — Python environment**

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

`pip install -e .` installs only `httpx` and `platformdirs`; it never touches Qt.

**Step 2 — install the self-compiled PyQt6**

Download from [Releases](https://github.com/<your-name>/purebrowser/releases):

- `PyQt6-6.7.1-cp38-abi3-win_amd64.whl`
- `PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl`
- `Qt6-custom.zip` (~500 MB)

```cmd
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-WebEngine PyQt6-WebEngine-Qt6 PyQt6_sip -y

pip install PyQt6-6.7.1-cp38-abi3-win_amd64.whl --no-deps
pip install PyQt6_sip==13.8.0 --no-deps
pip install PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl --no-deps
```

> **Important:** never install `PyQt6-Qt6` or `PyQt6-WebEngine-Qt6`. They overwrite the self-compiled Qt.

**Step 3 — deploy the self-compiled Qt**

Unzip `Qt6-custom.zip` to `D:\develop\Qt6-custom`, then set the user environment variables:

```powershell
$p = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "D:\develop\Qt6-custom\bin;" + $p, "User")
[Environment]::SetEnvironmentVariable("QT_PLUGIN_PATH", "D:\develop\Qt6-custom\plugins", "User")
```

Restart all terminals so the variables take effect.

**Step 4 — run**

```cmd
python -m purebrowser
```

### Kernel maintainers: build QtWebEngine from scratch

See [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md). Expect 2–5 days and many pitfalls; every one is recorded.

## Packaging (Windows)

Packaging is **PyInstaller + Inno Setup**:

| File | Role |
|---|---|
| `PureBrowser.spec` | PyInstaller recipe: bundles the custom Qt6 DLLs/plugins/resources and `QtWebEngineProcess.exe`, entry `src/purebrowser/__main__.py`. |
| `runtime_hook.py` | Sets the runtime paths (`QT_PLUGIN_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH`, `QTWEBENGINEPROCESS_PATH`, `QTWEBENGINE_RESOURCES_PATH`, `QTWEBENGINE_LOCALES_PATH`). |
| `rebuild.bat` | One-shot: kill running instances → `pyinstaller PureBrowser.spec --noconfirm` → Inno Setup `ISCC PureBrowser.iss`. |
| `PureBrowser.iss` | Inno Setup script; output `installer\Output\PureBrowserSetup.exe`. |

```cmd
rebuild.bat
```

Outputs: `dist\PureBrowser\` (portable) and `installer\Output\PureBrowserSetup.exe` (installer).

> **Portability warning:** `PureBrowser.spec`, `rebuild.bat` and `PureBrowser.iss` contain **hard-coded
> absolute paths** for this machine (`D:\PythonProject\purebrowser`, `D:\develop\Qt6-custom`, the Inno Setup
> install path). Edit them before building on another machine.

Building Qt itself from source is a separate, much larger effort — see
[`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md).

## Project structure

```
purebrowser/
├─ src/purebrowser/
│  ├─ __main__.py / main.py / app.py     # entry, Chromium flags, QApplication + scheme registration
│  ├─ core/
│  │  ├─ profile.py                      # QWebEngineProfile: UA, cookies, settings  (frozen)
│  │  ├─ interceptor.py                  # request interceptor: blocklist, HTTPS, cookie strip (frozen)
│  │  ├─ privacy/flags.py                # Chromium command-line flags               (frozen)
│  │  ├─ settings.py                     # settings.json read/write
│  │  └─ locations.py                    # data/cache/download paths
│  ├─ data/                              # storage.py history.py bookmarks.py
│  │                                     # favicons.py downloads_store.py session.py
│  ├─ pages/
│  │  ├─ pages.py                        # purebrowser:// handler + history/settings pages
│  │  ├─ newtab.py                       # new tab URL helpers
│  │  └─ downloads.py                    # DownloadManager
│  └─ ui/
│     ├─ window.py                       # main window, tabs, menus, shortcuts, fullscreen
│     ├─ tab.py / tab_area.py / tabbar.py# tab widgets + adaptive tab strip
│     ├─ urlbar.py                       # address bar + autocomplete
│     ├─ theme.py / icons.py             # theme tokens + inline SVG icons
│     ├─ hud.py                          # zoom/find HUDs, Ctrl+wheel filter
│     ├─ menu_rows.py / context_menu.py  # shared rich row + custom right-click menu
│     ├─ dropdown.py                     # scrollable history/bookmarks/downloads panels
│     ├─ session_prompt.py               # "restore session?" card
│     └─ freeze_overlay.py               # resize/move freeze frame
├─ resources/                            # newtab.html, purebrowser.ico
├─ tools/                                # smoke_test, e2e_test, regression_test,
│                                        # fullscreen_harness_test, fullscreen_test, audit/net_audit.py
├─ docs/                                 # BUILD_NOTES.md, assets/ (logo + screenshots)
├─ PureBrowser.spec / runtime_hook.py / rebuild.bat / PureBrowser.iss
├─ pyproject.toml / requirements.txt
└─ LICENSE / README.md / README.zh-CN.md / AGENTS.md
```

## Features

**Browsing & tabs**
- Tabbed browsing with an adaptive (sliding) tab strip, drag-to-reorder, per-tab close buttons, `+` button.
- Reopen the last closed tab (`Ctrl+Shift+T`).
- Back / forward / reload; `Alt+←/→`, `F5`, `Ctrl+R`.

**Window**
- Custom-drawn title bar (frameless) with native minimize/maximize/restore.
- Remembers maximized vs. windowed and the windowed size/position; on launch asks whether to restore
  the previous session.

**Find & zoom**
- `Ctrl+F` find bar with match count, next/previous, `Esc` to close. Pages that implement their own
  `Ctrl+F` take priority; the browser only steps in when the page doesn't handle it.
- Page zoom via `Ctrl`+wheel and `Ctrl` `+` / `-` / `0`, with a zoom HUD; per-site zoom is remembered.

**Bookmarks & history**
- `Ctrl+D` to toggle a bookmark; star icon in the toolbar; bookmarks dropdown panel.
- History in SQLite, autocompleted in the address bar, grouped dropdown (Today / Yesterday / Earlier),
  and a `purebrowser://history` page.

**Downloads**
- Pause / resume / cancel / retry; records persisted to SQLite (pruned to 200).
- Live speed / current size / progress bar in the downloads dropdown panel, plus a red count badge on
  the toolbar download button. Open file / reveal in folder.

**Menus**
- Custom Chinese right-click menu (link save-as / copy link, image save / copy, edit actions,
  copy/search selection, back/forward/reload).
- History / bookmarks / downloads use a scrollable, themed dropdown panel.

**Appearance**
- Light / dark / system theme, applied consistently across the toolbar, menus and built-in pages.

**Privacy**
- Built-in ad/tracker host blocklist (~22 domains, hard-coded), toggleable in settings.
- HTTP → HTTPS upgrade for requests.
- Cross-site Cookie header stripped on XHR/media requests, plus partitioned cookies
  (`PartitionedCookies`, `ThirdPartyStoragePartitioning`).
- DNS over HTTPS (AliDNS, reachable from mainland China).
- No telemetry, crash upload, RLZ or device IDs; all site permission requests denied by default;
  pages can't pop up windows or read the clipboard.
- Persistent cookies allowed (so logins survive restarts), local SQLite only — no cloud, no account.

**Local pages & tools**
- `purebrowser://newtab`, `purebrowser://history`, `purebrowser://settings`.
- Settings: theme, ad-block toggle, DoH toggle, restore-session toggle, search engine,
  data/download/cache directories, clear cache / clear history.
- Configurable data directory (`location.txt`).
- Network audit: set `PUREBROWSER_NETLOG` to a path, then run `tools/audit/net_audit.py`.

**Codecs**
- H.264 via the self-compiled QtWebEngine (the headline feature).

## Comparison with mainstream

| | **PureBrowser** | ungoogled-chromium | qutebrowser | LibreWolf |
|---|---|---|---|---|
| Language | **Python** | C++ | Python | C++ |
| H.264 included | **Yes** | DIY | No | Yes |
| Self-compiled engine | Yes | Yes | No | Yes |
| No telemetry | Yes | Yes | Yes | Yes |
| "Edit and run" | edit `.py` | rebuild hours | edit `.py` | edit C++ |
| Target | learn / customize / research | hardcore users | keyboard users | privacy users |

## Screenshots

> Placeholder paths — drop the PNGs into `docs/assets/screenshots/` and they appear here.

| Main (light) | Main (dark) |
|---|---|
| ![main light](docs/assets/screenshots/main-light.png) | ![main dark](docs/assets/screenshots/main-dark.png) |

| History panel | Downloads panel |
|---|---|
| ![history](docs/assets/screenshots/dropdown-history.png) | ![downloads](docs/assets/screenshots/dropdown-downloads.png) |

| Right-click menu | Settings |
|---|---|
| ![context menu](docs/assets/screenshots/context-menu.png) | ![settings](docs/assets/screenshots/settings.png) |

## Roadmap

**Done**
- [x] Compile QtWebEngine 6.7.3 + H.264 from source
- [x] Base UI + interceptor + privacy defaults
- [x] History, bookmarks, downloads, settings page
- [x] Find bar, page zoom, favicons
- [x] Custom Chinese menus + scrollable dropdown panels
- [x] Session-restore prompt + window-state memory
- [x] Windows packaging (PyInstaller + Inno Setup)

**Planned**
- [ ] Auto-update (self-hosted, signed)
- [ ] Linux / macOS
- [ ] Extensions (optional)
- [ ] E2EE sync (optional, off by default)
- [ ] Full EasyList rules, bookmarks manager page, private window, per-site permissions

## Known limitations

- **Windows x64 only.**
- Ad-blocking is a **small built-in host blocklist (~22 domains)**, not EasyList/EasyPrivacy.
- No per-site permission grants — every permission request is denied.
- No extensions, no sync, no accounts, no auto-update, no multi-profile, no private/incognito window.
- Built-in pages are limited to new tab / history / settings (no standalone bookmarks manager page).
- **Download resume** only works within the same session; on restart, in-progress downloads are marked
  interrupted and must be retried (started fresh).
- Session restore remembers URLs, not full form/scroll state.

## FAQ

**Q: Why a self-compiled PyQt6 instead of the pip one?**
A: The pip Qt wheels are built without H.264. Only the self-compiled build has it. They can coexist, but
don't mix them inside one venv.

**Q: Why only Windows?**
A: Only Windows x64 is validated. The build scripts, patches and dependency DLLs are all Windows-specific;
Linux/macOS need a fresh pass through `BUILD_NOTES.md`.

**Q: Can I use PySide6?**
A: No. PySide6's official wheel also lacks H.264, and its QtWebEngine version doesn't line up with PyQt6.
This project pins PyQt6 6.7.1 + self-compiled Qt 6.7.3.

**Q: Why isn't Qt6-custom in the repo?**
A: It's too large for GitHub file limits (>2 GB unpacked; ~500 MB zipped). It ships as a Releases asset.

**Q: How is this different from ungoogled-chromium?**
A: ungoogled-chromium is C++; one change means a rebuild. PureBrowser is Python; one `.py` edit takes effect.

**Q: Why PyInstaller and not Nuitka (older docs mentioned Nuitka)?**
A: The current, working pipeline is PyInstaller (`PureBrowser.spec` + `runtime_hook.py`) wrapped by Inno
Setup (`PureBrowser.iss`), driven by `rebuild.bat`. Older notes mentioning Nuitka are obsolete.

**Q: Why is the ad-blocker so small?**
A: It's a deliberate, dependency-free host blocklist. Pull requests with larger, maintained rule sets are
welcome — see the Roadmap.

## Contributing

- Open an issue for bugs or feature requests.
- Send a PR with code changes.
- Reproduce `BUILD_NOTES.md` and report new pitfalls.
- Translate the docs.

## License

Project code (`src/`, `tools/`, etc.) is licensed under **MPL-2.0** — see [LICENSE](LICENSE).

Distributed binaries also link **PyQt6 (GPL edition)**, so a binary distribution is GPL-3.0 overall.
For closed-source commercial use, buy a commercial PyQt6 license from Riverbank and comply with Qt's
commercial terms.

*Last updated: 2026-10-01*
