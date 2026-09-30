# AGENTS.md — 智能体工作约束

> 本文件对所有在此仓库操作的 AI 智能体（Codex / Claude Code / Cursor / Copilot 等）生效。
> 违反本文件约束的改动，视为破坏性改动，不予合并。
> 若本文件与你收到的用户指令冲突，**以本文件为准**，并向用户澄清。

---

## 一、项目本质（先读这一段）

PureBrowser 是一个 **Windows x64 桌面浏览器**，技术栈固定：

| 组件 | 版本 | 来源 |
|---|---|---|
| Python | 3.10.11 | 项目 venv |
| PyQt6 | 6.7.1 | **自编译 wheel**，非 PyPI |
| PyQt6_sip | 13.8.0 | PyPI |
| PyQt6-WebEngine | 6.7.0 | **自编译 wheel**，非 PyPI |
| Qt | 6.7.3 | **自编译**，装在 `D:\develop\Qt6-custom` |
| QtWebEngineCore | 6.7.3 + H.264 | **自编译**，启用 `-webengine-proprietary-codecs` |

**这个组合无法用 `pip install` 复现。** 所有依赖都经过手工编译和 patch，细节在 `docs/BUILD_NOTES.md`。

一旦你尝试用 pip 的标准方式"修复依赖"，整个项目会崩。

---

## 二、绝对禁止（红线）

### 2.1 禁止执行的命令

**永远不要运行以下任何命令：**

```cmd
pip install PyQt6
pip install PyQt6-Qt6
pip install PyQt6-WebEngine
pip install PyQt6-WebEngine-Qt6
pip install --upgrade PyQt6
pip uninstall PyQt6
pip uninstall PyQt6-Qt6
pip uninstall PyQt6-WebEngine
pip uninstall PyQt6-WebEngine-Qt6
pip uninstall PyQt6_sip
pip install --upgrade PyQt6_sip
```

**原因**：这些操作会：
- 用 PyPI 官方 wheel 覆盖自编译版本
- 官方 wheel 不带 H.264
- 结果：B 站视频立刻不能播

如果用户明确要求"升级 PyQt6"，**必须先警告用户**，然后由用户自己手动操作。

### 2.2 禁止改动的文件

**以下文件在未经用户明确书面许可前，不允许任何改动：**

| 文件 | 原因 |
|---|---|
| `src/purebrowser/core/profile.py` | 内藏 H.264 兼容、UA、隐私默认策略的精细平衡 |
| `src/purebrowser/core/privacy/flags.py` | Chromium 命令行参数逐个调过，改动会导致启动异常 |
| `src/purebrowser/core/interceptor.py` | 拦截规则和 HTTPS 强制逻辑是隐私核心 |
| `docs/BUILD_NOTES.md` | 历史记录文档，不可被"润色"或重构 |

**这些文件里看似"冗余"或"不优雅"的代码，都是踩坑后的产物。** 例如：
- `profile.py` 里的 `FAKE_UA` 是为了让 B 站识别为 Chrome
- 早期版本曾有 `COMPAT_JS`，已删除。**不要加回来。**
- `flags.py` 里的 DoH 指向阿里 DNS，不是 Quad9，因为 Quad9 国内不可达

### 2.3 禁止改动的目录和文件

```
D:\develop\Qt6-custom\          # 自编译 Qt 安装目录，任何文件都不要动
D:\develop\qt6-build\            # 构建产物
D:\develop\qt6-src\              # Qt 源码
D:\develop\qt-build-archive\     # 归档，只读
D:\PythonProject\purebrowser\.venv\Lib\site-packages\PyQt6\      # 自编译 PyQt6
D:\PythonProject\purebrowser\.venv\Lib\site-packages\PyQt6_WebEngine\  # 自编译
```

### 2.4 禁止的"清理"操作

- 不要删除 `Qt6-custom\bin\zlib1__.dll`
- 不要删除 `Qt6-custom\bin\libpng16-16__.dll`
- 不要"整理"`Qt6-custom\bin` 里非 Qt6 开头的 DLL

这些是从 Strawberry Perl 借来的依赖，删了 Qt6Core.dll 就加载不了。

---

## 二点五、文件系统操作红线（最高优先级）

> 起因：曾用 `Get-ChildItem -LiteralPath <dir> -Include *.download`（无 `-Recurse`/通配符，`-Include` 被忽略）配合
> `Remove-Item -Force`，误删用户 `Downloads` 下的全部文件且无法从回收站恢复。以下为强制规则。

1. **禁止对任何用户目录**（`Downloads` / `Documents` / `Desktop` / 用户主目录）**执行批量删除**。
2. 清理操作**只允许针对自己创建的文件**，且必须放在 `D:\T\opencode\` 下。
3. `Get-ChildItem -Include` **必须**配合 `-Recurse` 或路径通配符；优先用 `-Filter`。
4. 任何 `Remove-Item` 前必须：先 `-WhatIf`，或先输出将被删除的文件列表让用户确认。
5. **禁止**用 `Remove-Item -Force`（跳过回收站）删除用户可见的文件。
6. 清理测试产物时，**只删 `D:\T\opencode\` 下的文件**。

---

## 三、允许改动的范围

以下文件可以自由修改、优化、重构：

### 3.1 主逻辑

- `src/purebrowser/ui/window.py` — 主窗口、标签、菜单
- `src/purebrowser/ui/tab.py` — 标签封装
- `src/purebrowser/ui/urlbar.py` — 地址栏补全
- `src/purebrowser/pages/downloads.py` — 下载管理
- `src/purebrowser/pages/pages.py` — 本地页面
- `src/purebrowser/core/settings.py` — 配置读写
- `src/purebrowser/data/storage.py` — SQLite
- `src/purebrowser/data/history.py` — 历史
- `src/purebrowser/data/bookmarks.py` — 书签
- `src/purebrowser/core/locations.py` — 路径管理
- `src/purebrowser/app.py` — QApplication 引导（谨慎）

### 3.2 UI 和资源

- `resources/` 下的图标
- 新增 UI 文件
- `newtab.html` 以外的 HTML
- `resources/newtab.html`：新标签页，允许改。
  红线：保留 `/* __THEME_VARS__ */` 占位符，主题变量由 `pages/pages.py` 注入。

### 3.3 工具和文档

- `tools/` 下的脚本
- `README.md`
- 新增的文档
- 测试

### 3.4 可以改，但要保留原行为

- `src/purebrowser/__main__.py`
- `src/purebrowser/main.py`
- `pyproject.toml`（**不要改依赖版本**）

---

## 四、修改后的强制自检

每次改动后，**必须**跑以下命令并确认输出：

### 4.1 确认 Qt 版本没被顶掉

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe -c "from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR; print('Qt', QT_VERSION_STR); print('PyQt', PYQT_VERSION_STR)"
```

**必须**输出：

```
Qt 6.7.3
PyQt 6.7.1
```

如果输出不是这两个版本，**立刻停下来**，说明 PyQt6 被替换了。**不要试图自己修**，报告给用户。

### 4.2 确认 QtWebEngine 可加载

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

必须输出 `OK`。

### 4.3 确认 PureBrowser 能启动

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe -m purebrowser
```

窗口应正常打开。**改动后，自己跑一次，看新标签页能加载，地址栏能输入，历史菜单能弹出。**

### 4.4 如果改了 tab 或 window，额外验证

- 点 `+` 新标签
- 地址栏输入 `example.com` 能打开
- 输入 `purebrowser://history` 能打开历史页
- `Ctrl+T` / `Ctrl+W` / `Ctrl+L` 快捷键有效

### 4.5 如果改了拦截器或隐私相关，额外验证

- 打开一个包含广告的网站
- 确认广告没加载出来

### 4.6 一键冒烟测试（推荐）
```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe D:\PythonProject\purebrowser\tools\smoke_test.py
```
- 所有检查项通过（全部通过）才算改动安全。
---

## 五、环境约束

### 5.1 关键路径

| 用途 | 路径 |
|---|---|
| 项目根 | `D:\PythonProject\purebrowser` |
| venv | `D:\PythonProject\purebrowser\.venv` |
| 自编译 Qt | `D:\develop\Qt6-custom` |
| 构建档案 | `D:\develop\qt-build-archive` |
| 归档 zip | `D:\develop\qt-build-archive.zip` |

### 5.2 必需的环境变量

用户级环境变量（已配置，不要改）：

```
QT_PLUGIN_PATH = D:\develop\Qt6-custom\plugins
PATH 包含 D:\develop\Qt6-custom\bin
```

### 5.3 Python 版本

- venv 里是 Python **3.10.11**
- 系统另有 Python 3.13.2（在 `D:\python3.13.2`），**那是给 Qt 构建用的，不要动**
- 另一个 3.10 在 `D:\Environment\Python\Python310`，**那是给 sip-wheel 用的，不要动**

**不要用一个 Python 去跑另一个 Python 的脚本。**

---

## 六、常见错误的处理方式

### 6.1 如果编译或导入报 `DLL load failed`

**不要**尝试重装任何包。先报告给用户，附完整错误信息。

可能的真实原因：
- 自编译 Qt 的某个依赖 DLL 被删了
- 环境变量没生效（用户需重启终端）
- venv 被污染

### 6.2 如果用户要求"升级依赖"

**先停下**，把本文件第二节"绝对禁止"展示给用户，请用户确认后再操作。

### 6.3 如果 `pip list` 显示 `PyQt6-Qt6` 或 `PyQt6-WebEngine-Qt6`

**立即报告用户**。这两个包不该存在，存在就意味着自编译 Qt 正被官方 Qt 覆盖。

### 6.4 如果 `BUILD_NOTES.md` 被误改

从 `D:\develop\qt-build-archive\BUILD_NOTES.md` 恢复：

```cmd
copy /Y D:\develop\qt-build-archive\BUILD_NOTES.md D:\PythonProject\purebrowser\docs\
```

---

## 七、工作流要求

### 7.1 小步提交

- 每次改动只做一件事
- 改完立刻跑第四节的自检
- 自检通过再继续

### 7.2 不确定时先问

以下情况必须先问用户，**不要自作主张**：

- 想改第二节列出的任何文件
- 想跑 `pip install` / `pip uninstall`
- 想删除任何 `Qt6-custom` 下的文件
- 想"优化"看起来奇怪但不知用途的代码
- 遇到自己不理解的错误

### 7.3 报告格式

改动后报告给用户时，包含：

1. 改了什么文件，为什么
2. 第四节的自检输出（原样贴）
3. 有没有不确定的地方

### 7.4 不要做的事

- 不要加新的依赖（除非用户明确同意）
- 不要改 `pyproject.toml` 的依赖版本
- 不要加 CI/CD 配置（这是 Alpha 阶段，暂不需要）
- 不要"美化"代码风格（除非用户明确要求）
- 不要加 emoji 到代码里

---

## 八、项目定位提醒

PureBrowser 的目标用户是：

1. **开发者**：想用 Python 改一个浏览器，不想碰 C++
2. **隐私用户**：要一个能播视频、无遥测的浏览器
3. **研究者**：想读懂一个浏览器怎么运作

**不是**：
- 不是要和 Chrome 抢市场
- 不是要做"功能最全"的浏览器
- 不是要覆盖所有平台

修改时的判断标准：

> **这个改动是否让上面三类目标用户更容易达成他们的目标？**
> 是 → 欢迎。否 → 慎重。

---

## 九、相关文档

- `README.md` — 项目对外介绍
- `docs/BUILD_NOTES.md` — 自编译 QtWebEngine 的完整记录
- `docs/BUILD_NOTES.md` 第六节 — 所有 patch 详解（P1~P12）

遇到构建问题，先查 `BUILD_NOTES.md`，再问用户。

---

*本文件最后更新：2026-09-29*
*修改本文件需用户明确许可。*
### 4.6 端到端测试：H.264 可用性

以下改动**必须**额外跑 `tools/e2e_test.py`：

- `src/purebrowser/core/profile.py`
- `src/purebrowser/core/privacy/flags.py`
- `src/purebrowser/ui/tab.py`
- `src/purebrowser/ui/window.py`
- `pyproject.toml` / `requirements.txt` 里的依赖相关部分

命令：

    D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\e2e_test.py

必须输出：

    avc1   : probably
    [OK]   H.264 可用（avc1 = probably）

若输出 `(不支持)` 或 `[FAIL]`，**立即停止改动**，报告用户。
这意味着自编译 QtWebEngine 被污染，或某个依赖 DLL 缺失。

---

## 附录 B：用户明确许可的改动（2026-09-29）

以下改动经用户明确许可，与主体约束不冲突：

1. **`profile.py` 的 cookie 策略**：从 `NoPersistentCookies` 改为 `AllowPersistentCookies`。
   原因：修复"每次打开 B 站都要重新登录"。
   红线：**不要改回 `NoPersistentCookies`。**

2. **`tab.py` 的全屏支持**：新增 `PurePage._handle_fullscreen`，接受全屏请求。
   原因：修复 B 站视频只有"网页全屏"没有真全屏。
   红线：**不要删除 `fullScreenRequested.connect(...)` 这一行。**

3. **`window.py` 的全屏实现**：Windows 平台使用原生 Win32 API（`SetWindowLongPtrW` + `SetWindowPlacement` + `SetWindowPos`）实现全屏，**不要改回 Qt 的 `showFullScreen()` / `showNormal()` / `showMaximized()` / `setWindowState()`**。

   原因：Qt 在 Windows 上把「全屏 → 最大化」拆成两段，产生 31~78ms 的窗口化中间态。9 个 Qt 层方案均无效。只有完全绕过 Qt、用 `SetWindowPlacement` 原子恢复才能消除。

   红线：
   - 不要删除 `_native_enter_fullscreen` / `_native_exit_fullscreen`
   - 不要改回 Qt 的窗口状态 API
   - 用 `self._is_fullscreen` 替代 `isFullScreen()`（Qt 不知道我们改了窗口状态）
   - `PUREBROWSER_FS_DEBUG=1` 探针保留，用于诊断
   - 保留 Qt 层的非 Windows fallback 分支

4. **`profile.py` 的 `FullScreenSupportEnabled`**：不要删除。
   不开这一项，`document.fullscreenEnabled` 返回 false，B 站等站点不渲染全屏按钮，原生全屏方案无从触发。

5. **`newtab.html` 解冻**：从冻结清单移除。
   原因：B-1.1 主题系统落地后，暗色模式下新标签页正文仍是白底，视觉不一致。
   红线：保留 `/* __THEME_VARS__ */` 占位符；不要用 `Canvas`/`CanvasText` 系统色；所有颜色用 CSS 变量。
