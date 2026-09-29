# PureBrowser

> A Python-hackable, privacy-first browser with **H.264 built in**.
> 一个用 Python 就能改的、自带 H.264 的隐私浏览器。

[![License](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-lightgrey.svg)]()
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## 这是什么

PureBrowser 是一个基于 **PyQt6 + 自编译 QtWebEngine** 的桌面浏览器。它解决了一个生态级的痛点：

> **Qt 官方 pip wheel 不带 H.264 解码器，导致 B 站、腾讯视频等网站报"当前浏览器不支持 HTML5 播放器"。**

本项目从源码编译 QtWebEngine 6.7.3，启用 `-webengine-proprietary-codecs`，让 Python 也能拥有一个能播视频的浏览器。整个编译过程和所有 patch 记录在 [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)。

## 三个核心差异点

### 1. 自带 H.264（这最难）

- 自编译 Qt 6.7.3 + QtWebEngine，显式开启 proprietary codecs
- 手改 `environment.x64`、`toolchain.ninja`、`build.ninja`，切换 v142/v143 编译器，绕过 MSVC 回归 bug
- 完整可复现步骤在 `docs/BUILD_NOTES.md`
- 结果：B 站视频直接播，画面声音正常

### 2. 纯 Python 可开发

- 技术栈：Python 3.10 + PyQt6 6.7.1 + QtWebEngine 6.7.3
- 所有 UI、隐私策略、拦截规则都在 `src/purebrowser/` 下的 Python 文件里
- 改一行 py 文件就有效果，不需要重编 C++
- 对比 ungoogled-chromium / LibreWolf：那些是 C++ 项目

### 3. 隐私优先 + 可审计

- 无遥测、无崩溃上传、无 RLZ、无设备 ID
- 默认 HTTPS-only
- 默认 DoH（阿里 DNS，国内可达）
- 默认阻止第三方 Cookie
- 内置广告/追踪拦截（EasyList / EasyPrivacy）
- 所有站点权限默认拒绝（地理位置、通知、摄像头、剪贴板）
- 新标签页纯本地：无新闻、无推荐、无广告
- 数据本地 SQLite，无云端同步，无账号系统

**实测证据**：静默 60 秒 + 访问 2 个站点，共 4 个网络请求，3 个远端域名，遥测命中 0。可用 `tools/audit/net_audit.py` 复现。

---

## 快速开始

### 普通用户

> 安装包尚未发布。当前状态为 Alpha。

### 开发者：克隆即跑

```bash
git clone https://github.com/<your-name>/purebrowser.git
cd purebrowser
```

**第 1 步：Python 环境**

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

**第 2 步：装自编译的 PyQt6（不用自己编）**

从 [Releases](https://github.com/<your-name>/purebrowser/releases) 下载三个文件：

- `PyQt6-6.7.1-cp38-abi3-win_amd64.whl`
- `PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl`
- `Qt6-custom.zip`（约 500 MB）

```cmd
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-WebEngine PyQt6-WebEngine-Qt6 PyQt6_sip -y

pip install PyQt6-6.7.1-cp38-abi3-win_amd64.whl --no-deps
pip install PyQt6_sip==13.8.0 --no-deps
pip install PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl --no-deps
```

> **关键**：不要装 `PyQt6-Qt6` 和 `PyQt6-WebEngine-Qt6`，那两个 pip 包会覆盖自编译 Qt。

**第 3 步：部署自编译 Qt**

把 `Qt6-custom.zip` 解压到 `D:\develop\Qt6-custom`，然后设置用户级环境变量：

```powershell
$p = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "D:\develop\Qt6-custom\bin;" + $p, "User")
[Environment]::SetEnvironmentVariable("QT_PLUGIN_PATH", "D:\develop\Qt6-custom\plugins", "User")
```

**关掉所有终端重开**，让环境变量生效。

**第 4 步：运行**

```cmd
python -m purebrowser
```

### 内核维护者：从零自编译

见 [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)。预计 2~5 天，会踩很多坑，但文档记录了每一个。

---

## 架构

```
purebrowser/
├─ src/purebrowser/          # 全部 Python 代码
│  ├─ main.py                # 入口，注入 Chromium flags
│  ├─ app.py                 # QApplication，scheme 注册
│  ├─ __main__.py            # python -m purebrowser 入口
│  ├─ ui/                    # UI 层
│  │  ├─ window.py           # 主窗口、标签、菜单、快捷键
│  │  ├─ tab.py              # 单标签封装（含 createWindow）
│  │  └─ urlbar.py           # 地址栏 + 补全
│  ├─ core/                  # 核心层
│  │  ├─ profile.py          # 隐私 profile
│  │  ├─ interceptor.py      # 请求拦截器
│  │  ├─ settings.py         # 配置
│  │  ├─ locations.py        # 数据/缓存路径
│  │  └─ privacy/flags.py    # Chromium 命令行参数
│  ├─ data/                  # 数据层
│  │  ├─ storage.py          # SQLite 连接
│  │  ├─ history.py          # 历史
│  │  └─ bookmarks.py        # 书签
│  └─ pages/                 # 页面层
│     ├─ pages.py            # purebrowser:// 本地页处理
│     ├─ downloads.py        # 下载管理
│     └─ newtab.py           # 新标签页
├─ tools/
│  ├─ audit/net_audit.py     # 网络审计
│  └─ rules/                 # EasyList 编译
├─ resources/                # 图标、newtab.html
├─ docs/
│  └─ BUILD_NOTES.md         # 自编译 QtWebEngine 完整记录
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

## 与主流方案对比

| 特性 | **PureBrowser** | ungoogled-chromium | qutebrowser | LibreWolf |
|---|---|---|---|---|
| 开发语言 | **Python** | C++ | Python | C++ |
| 自带 H.264 | **是** | 需自行处理 | 否 | 是 |
| 自编译内核 | 是 | 是 | 否 | 是 |
| 无遥测 | 是 | 是 | 是 | 是 |
| 改一改就跑 | 改 py | 重编几小时 | 改 py | 改 C++ |
| 项目定位 | 学习 / 定制 / 研究 | 硬核用户 | 键盘党 | 隐私用户 |

## 已实现的功能

- 标签页、地址栏、前进后退
- 历史记录（SQLite，地址栏自动补全）
- 书签（工具栏下拉）
- 下载管理（进度条、自动去重命名）
- 快捷键：`Ctrl+T/W/L/R/D/H/B/J`、`Alt+←/→`
- 内置广告/追踪拦截
- HTTPS-only
- DoH（阿里 DNS）
- 第三方 Cookie 阻止
- 站点权限默认全拒
- `purebrowser://history` / `purebrowser://settings` 本地页
- 可配置数据目录、下载目录、缓存目录
- 网络审计日志（`PUREBROWSER_NETLOG` 环境变量开启）

## Roadmap

- [x] 从源码编译 QtWebEngine 6.7.3 + H.264
- [x] 基础 UI + 拦截器 + 隐私默认策略
- [x] 历史、书签、下载、设置页
- [ ] **打包为 Windows 安装包**（Nuitka + Inno Setup）
- [ ] 自动更新（自建更新服务 + 签名）
- [ ] Linux / macOS 支持
- [ ] 扩展系统（可选）
- [ ] E2EE 同步（可选，默认关闭）

## 常见问题

**Q: 为什么下载 PyQt6 要用自编译的，不用 pip 上的？**

A: pip 上的 PyQt6 带的 Qt 是官方编译的，**不含 H.264**。自编译的版本才带。两者可以共存，但不要混用同一个 venv。

**Q: 为什么只支持 Windows？**

A: 当前版本只在 Windows x64 上验证过。QtWebEngine 的构建脚本、patch、依赖 DLL 都针对 Windows 调过。Linux 版需要重新走一遍 BUILD_NOTES 里的流程。

**Q: 能不能直接用 PySide6？**

A: 不行。PySide6 官方 wheel 同样不带 H.264，而且它的 QtWebEngine 版本与 PyQt6 不完全对应。项目使用 PyQt6 6.7.1 + 自编译 Qt 6.7.3。

**Q: 为什么仓库里不直接附带 Qt6-custom？**

A: 太大会超过 GitHub 单文件限制（>2 GB）。Qt6-custom 打包后约 500 MB，放在 Releases 附件里。

**Q: 和 ungoogled-chromium 有什么区别？**

A: ungoogled-chromium 是 C++ 项目，改一行要重编。PureBrowser 是 Python 项目，改一行 py 文件就有效果。定位不同。

## 贡献

欢迎任何形式的贡献：

- 提 Issue 报告 bug 或功能建议
- 提交 PR 修改代码
- 复现 `BUILD_NOTES.md` 并在 Issue 里报告新坑
- 翻译文档

## 许可

本项目采用多层许可：

| 层 | 许可 | 说明 |
|---|---|---|
| 自有代码（`src/`、`tools/` 等） | **MPL-2.0** | 见 [LICENSE](LICENSE) |
| PyQt6（GPL 版） | **GPL-3.0** | 从 Riverbank 获取，非商业使用走 GPL |
| Qt 6.7.3 / QtWebEngine | **LGPL-3.0** with Qt exception | 从 Qt 官方源码编译 |
| 分发的二进制包 | **受 GPL-3.0 约束** | 因链接 GPL 版 PyQt6 |

**如果你计划闭源商用**：

1. 向 Riverbank 购买 PyQt6 商业许可
2. 遵守 Qt 商业条款
3. 联系作者

**如果开源**：

- 整个分发物视为 GPL-3.0
- 你的改动需同样以 GPL-3.0 兼容许可发布

## 致谢

Qt 6.7.3 编译过程中踩过的所有坑、所有 patch、所有环境配置，都记录在 [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)。这份文档本身也是本项目的产物之一，供后来者参考。

---

*最后更新：2026-09-29*