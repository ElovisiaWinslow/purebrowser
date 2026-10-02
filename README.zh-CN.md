<p align="center">
  <img src="docs/assets/purebrowser.png" width="128" alt="PureBrowser logo">
</p>

<h1 align="center">PureBrowser</h1>

<p align="center"><b>一个可用纯 Python 改造、隐私优先、内置 H.264 的浏览器。</b></p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>
</p>

<p align="center">
  <a href="https://github.com/ElovisiaWinslow/purebrowser/releases/latest"><img src="https://img.shields.io/github/v/release/ElovisiaWinslow/purebrowser" alt="Latest Release"></a>
  <a href="https://github.com/ElovisiaWinslow/purebrowser/releases"><img src="https://img.shields.io/github/downloads/ElovisiaWinslow/purebrowser/total" alt="Downloads"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MPL--2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20x64-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status">
</p>

---

## 这是什么

PureBrowser 是一个基于 **PyQt6 + 自行编译的 QtWebEngine 6.7.3** 构建的 Windows 桌面浏览器。

它为了解决一个生态级痛点：官方 Qt pip wheel 不带 **H.264**，所以 Bilibili 等网站会提示“你的浏览器不支持 HTML5 播放”。PureBrowser 从源码编译 QtWebEngine，并启用 `-webengine-proprietary-codecs`，让 Python 浏览器真正能播放视频。完整构建过程与所有补丁记录在 [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)。

三大特点：

1. **内置 H.264** —— 自行编译 Qt + QtWebEngine，启用专有编解码器。Bilibili 可播放。
2. **纯 Python 可改造** —— 所有 UI、隐私策略和拦截规则都是 `src/purebrowser/` 下的 `.py` 文件。改一行即可，无需重新编译 C++。
3. **隐私优先且可审计** —— 无遥测、无崩溃上传、无 RLZ；HTTPS 升级；DoH；内置广告/追踪器屏蔽列表；默认拒绝所有站点权限；仅本地 SQLite。

## 系统要求

| 组件 | 版本 | 来源 |
|---|---|---|
| 操作系统 | Windows 10/11 **x64** | — |
| Python | **3.10.11**（项目 venv） | python.org |
| PyQt6 | 6.7.1 | **自行编译的 wheel**（非 PyPI） |
| PyQt6_sip | 13.8.0 | PyPI |
| PyQt6-WebEngine | 6.7.0 | **自行编译的 wheel**（非 PyPI） |
| Qt / QtWebEngine | 6.7.3 + H.264 | **自行编译** |

环境变量（用户级别）：`QT_PLUGIN_PATH` 和 `PATH` 必须指向自定义 Qt 安装目录。

纯 Python 依赖（在 `pyproject.toml` 中声明）：`httpx`、`platformdirs`。

## 快速开始

### 普通用户

从 [Releases](https://github.com/ElovisiaWinslow/purebrowser/releases/latest) 下载安装程序：

- `PureBrowserSetup.exe` —— Windows x64 安装程序（支持自定义安装路径）

运行后，从开始菜单启动 PureBrowser。

### 开发者：克隆并运行

```bash
git clone https://github.com/ElovisiaWinslow/purebrowser.git
cd purebrowser
```

**步骤 1 —— Python 环境**

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

`pip install -e .` 只安装 `httpx` 和 `platformdirs`；不会触碰 Qt。

**步骤 2 —— 安装自行编译的 PyQt6 + Qt6 运行时**

参见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) —— 它逐步说明：

- 从 [Releases](https://github.com/ElovisiaWinslow/purebrowser/releases) 下载预编译的 PyQt6 wheels 和 Qt6 运行时
- 将 Qt6 运行时解压到固定路径
- 设置 `PATH` / `QT_PLUGIN_PATH` 环境变量
- 验证 H.264

**步骤 3 —— 运行**

```cmd
python -m purebrowser
```

### 从源码构建

- **使用预编译依赖**（推荐）：参见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。
- **从头重新编译 QtWebEngine**：参见 [docs/BUILD_NOTES.md](docs/BUILD_NOTES.md) —— 预计需要 2–5 天，坑很多；每个坑都有记录。

## 打包（Windows）

打包使用 **PyInstaller + Inno Setup**：

| 文件 | 作用 |
|---|---|
| `PureBrowser.spec` | PyInstaller 配方：打包自定义 Qt6 DLL/插件/资源以及 `QtWebEngineProcess.exe`，入口为 `src/purebrowser/__main__.py`。 |
| `runtime_hook.py` | 设置运行时路径（`QT_PLUGIN_PATH`、`QT_QPA_PLATFORM_PLUGIN_PATH`、`QTWEBENGINEPROCESS_PATH`、`QTWEBENGINE_RESOURCES_PATH`、`QTWEBENGINE_LOCALES_PATH`）。 |
| `rebuild.bat` | 一键：结束正在运行的实例 → `pyinstaller PureBrowser.spec --noconfirm` → Inno Setup `ISCC PureBrowser.iss`。 |
| `PureBrowser.iss` | Inno Setup 脚本；输出 `installer\Output\PureBrowserSetup.exe`。 |

```cmd
rebuild.bat
```

输出：`dist\PureBrowser\`（便携版）和 `installer\Output\PureBrowserSetup.exe`（安装程序）。

> **可移植性警告：** `PureBrowser.spec`、`rebuild.bat` 和 `PureBrowser.iss` 包含本机的 **硬编码绝对路径**（`D:\PythonProject\purebrowser`、`D:\develop\Qt6-custom`、Inno Setup 安装路径）。在另一台机器上构建前请先编辑它们。

从源码编译 Qt 本身是另一项大得多的工程 —— 参见
[`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)。

## 项目结构

```
purebrowser/
├─ src/purebrowser/
│  ├─ __main__.py / main.py / app.py     # 入口、Chromium 标志、QApplication + scheme 注册
│  ├─ core/
│  │  ├─ profile.py                      # QWebEngineProfile：UA、cookies、设置（冻结）
│  │  ├─ interceptor.py                  # 请求拦截器：屏蔽列表、HTTPS、Cookie 剥离（冻结）
│  │  ├─ privacy/flags.py                # Chromium 命令行标志（冻结）
│  │  ├─ settings.py                     # settings.json 读写
│  │  └─ locations.py                    # 数据/缓存/下载路径
│  ├─ data/                              # storage.py history.py bookmarks.py
│  │                                     # favicons.py downloads_store.py session.py
│  ├─ pages/
│  │  ├─ pages.py                        # purebrowser:// 处理器 + 历史/设置页面
│  │  ├─ newtab.py                       # 新标签页 URL 辅助函数
│  │  └─ downloads.py                    # DownloadManager
│  └─ ui/
│     ├─ window.py                       # 主窗口、标签页、菜单、快捷键、全屏
│     ├─ tab.py / tab_area.py / tabbar.py# 标签页控件 + 自适应标签条
│     ├─ urlbar.py                       # 地址栏 + 自动补全
│     ├─ theme.py / icons.py             # 主题 token + 内联 SVG 图标
│     ├─ hud.py                          # 缩放/查找 HUD，Ctrl+滚轮过滤器
│     ├─ menu_rows.py / context_menu.py  # 共享富行 + 自定义右键菜单
│     ├─ dropdown.py                     # 可滚动历史/书签/下载面板
│     ├─ session_prompt.py               # “恢复会话？”卡片
│     └─ freeze_overlay.py               # 调整大小/移动时的冻结帧
├─ resources/                            # newtab.html, purebrowser.ico
├─ tools/                                # smoke_test, e2e_test, regression_test,
│                                        # fullscreen_harness_test, fullscreen_test, audit/net_audit.py
├─ docs/                                 # BUILD_NOTES.md, DEVELOPMENT.md, assets/（logo + 截图）
├─ PureBrowser.spec / runtime_hook.py / rebuild.bat / PureBrowser.iss
├─ pyproject.toml / requirements.txt
└─ LICENSE / README.md / README.zh-CN.md / AGENTS.md
```

## 界面截图

| 主界面（亮色） | 主界面（暗色） |
|---|---|
| ![主界面亮色](docs/assets/screenshots/main-light.png) | ![主界面暗色](docs/assets/screenshots/main-dark.png) |

| 历史面板 | 下载面板 |
|---|---|
| ![历史面板](docs/assets/screenshots/dropdown-history.png) | ![下载面板](docs/assets/screenshots/dropdown-downloads.png) |

| 右键菜单 | 设置页 |
|---|---|
| ![右键菜单](docs/assets/screenshots/context-menu.png) | ![设置页](docs/assets/screenshots/settings.png) |

## 功能

**浏览与标签页**
- 标签式浏览，自适应（滑动）标签条，可拖拽排序，每个标签有独立关闭按钮，`+` 按钮。
- 重新打开最近关闭的标签页（`Ctrl+Shift+T`）。
- 后退 / 前进 / 刷新；`Alt+←/→`、`F5`、`Ctrl+R`。

**窗口**
- 自绘标题栏（无边框），支持原生最小化/最大化/还原。
- 记住最大化与窗口化状态，以及窗口化时的大小/位置；启动时询问是否恢复上次会话。

**查找与缩放**
- `Ctrl+F` 查找栏，显示匹配数量、下一个/上一个、`Esc` 关闭。实现了自身 `Ctrl+F` 的页面优先；页面不处理时浏览器才介入。
- 通过 `Ctrl`+滚轮和 `Ctrl` `+` / `-` / `0` 缩放页面，带缩放 HUD；按站点记住缩放。

**书签与历史**
- `Ctrl+D` 切换书签；工具栏星标图标；书签下拉面板。
- 历史记录存入 SQLite，在地址栏自动补全，分组下拉（今天 / 昨天 / 更早），以及 `purebrowser://history` 页面。

**下载**
- 暂停 / 继续 / 取消 / 重试；记录持久化到 SQLite（裁剪到 200 条）。
- 下载下拉面板中显示实时速度 / 当前大小 / 进度条，工具栏下载按钮上有红色计数徽章。打开文件 / 在文件夹中显示。

**菜单**
- 自定义中文右键菜单（链接另存为 / 复制链接，图片保存 / 复制，编辑操作，复制/搜索选中内容，后退/前进/刷新）。
- 历史 / 书签 / 下载使用可滚动、主题化下拉面板。

**外观**
- 浅色 / 深色 / 跟随系统主题，一致应用于工具栏、菜单和内置页面。

**隐私**
- 内置广告/追踪器主机屏蔽列表（约 22 个域名，硬编码），可在设置中开关。
- 请求 HTTP → HTTPS 升级。
- XHR/媒体请求中剥离跨站 Cookie 头，并使用分区 Cookie（`PartitionedCookies`、`ThirdPartyStoragePartitioning`）。
- DNS over HTTPS（AliDNS，中国大陆可访问）。
- 无遥测、崩溃上传、RLZ 或设备 ID；默认拒绝所有站点权限请求；页面不能弹出窗口或读取剪贴板。
- 允许持久 Cookie（登录可在重启后保留），仅本地 SQLite —— 无云、无账户。

**本地页面与工具**
- `purebrowser://newtab`、`purebrowser://history`、`purebrowser://settings`。
- 设置：主题、广告拦截开关、DoH 开关、恢复会话开关、搜索引擎、数据/下载/缓存目录、清除缓存 / 清除历史。
- 可配置数据目录（`location.txt`）。
- 网络审计：将 `PUREBROWSER_NETLOG` 设为路径，然后运行 `tools/audit/net_audit.py`。

**编解码器**
- 通过自行编译的 QtWebEngine 支持 H.264（核心亮点）。

## 与主流浏览器对比

| | **PureBrowser** | ungoogled-chromium | qutebrowser | LibreWolf |
|---|---|---|---|---|
| 语言 | **Python** | C++ | Python | C++ |
| 内置 H.264 | **是** | 需自行处理 | 否 | 是 |
| 自行编译引擎 | 是 | 是 | 否 | 是 |
| 无遥测 | 是 | 是 | 是 | 是 |
| “改完即跑” | 编辑 `.py` | 重新编译数小时 | 编辑 `.py` | 编辑 C++ |
| 目标 | 学习 / 定制 / 研究 | 硬核用户 | 键盘用户 | 隐私用户 |

## 路线图

**已完成**
- [x] 从源码编译 QtWebEngine 6.7.3 + H.264
- [x] 基础 UI + 拦截器 + 隐私默认值
- [x] 历史、书签、下载、设置页面
- [x] 查找栏、页面缩放、favicon
- [x] 自定义中文菜单 + 可滚动下拉面板
- [x] 会话恢复提示 + 窗口状态记忆
- [x] Windows 打包（PyInstaller + Inno Setup）

**计划中**
- [ ] 自动更新（自托管、签名）
- [ ] Linux / macOS
- [ ] 扩展（可选）
- [ ] 端到端加密同步（可选，默认关闭）
- [ ] 完整 EasyList 规则、书签管理器页面、隐私窗口、按站点权限

## 已知限制

- **仅 Windows x64。**
- 广告拦截是 **小型内置主机屏蔽列表（约 22 个域名）**，不是 EasyList/EasyPrivacy。
- 没有按站点权限授予 —— 所有权限请求都会被拒绝。
- 无扩展、无同步、无账户、无自动更新、无多配置文件、无隐私/无痕窗口。
- 内置页面仅限于新标签页 / 历史 / 设置（没有独立书签管理器页面）。
- **下载续传** 仅在同一会话内有效；重启后，进行中的下载会标记为中断，必须重试（重新开始）。
- 会话恢复只记住 URL，不记住完整表单/滚动状态。

## 常见问题

**问：为什么使用自行编译的 PyQt6，而不是 pip 版本？**
答：pip 的 Qt wheel 编译时没有 H.264。只有自行编译的版本才有。它们可以共存，但不要在同一 venv 中混用。

**问：为什么只有 Windows？**
答：目前只验证了 Windows x64。构建脚本、补丁和依赖 DLL 都是 Windows 专用的；Linux/macOS 需要按 `BUILD_NOTES.md` 重新走一遍。

**问：可以使用 PySide6 吗？**
答：不能。PySide6 的官方 wheel 也缺少 H.264，而且其 QtWebEngine 版本与 PyQt6 不一致。本项目固定使用 PyQt6 6.7.1 + 自行编译的 Qt 6.7.3。

**问：为什么仓库里没有 Qt6 运行时？**
答：它太大，超出 GitHub 文件限制。它作为 Releases 资产发布（`Qt6-runtime-win64.zip`，约 125 MB）。

**问：这与 ungoogled-chromium 有何不同？**
答：ungoogled-chromium 是 C++；改一处就要重新编译。PureBrowser 是 Python；改一个 `.py` 就生效。

**问：为什么用 PyInstaller 而不是 Nuitka（旧文档提到过 Nuitka）？**
答：当前可用的流水线是 PyInstaller（`PureBrowser.spec` + `runtime_hook.py`），由 Inno Setup（`PureBrowser.iss`）封装，并通过 `rebuild.bat` 驱动。提到 Nuitka 的旧说明已过时。

**问：为什么广告拦截器这么小？**
答：这是有意为之、无依赖的主机屏蔽列表。欢迎提交更大、持续维护的规则集 PR —— 参见路线图。

## 贡献

- 对 bug 或功能请求开 issue。
- 提交包含代码改动的 PR。
- 复现 `BUILD_NOTES.md` 并报告新坑。
- 翻译文档。

## 许可证

项目代码（`src/`、`tools/` 等）采用 **MPL-2.0** 许可 —— 参见 [LICENSE](LICENSE)。

分发的二进制文件还会链接 **PyQt6（GPL 版本）**，因此二进制分发整体为 GPL-3.0。
如需闭源商业使用，请从 Riverbank 购买商业 PyQt6 许可证，并遵守 Qt 的商业条款。

*最后更新：2026-10-02*
