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
pip install --force-reinstall PyQt6
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
D:\PythonProject\purebrowser\.venv\Lib\site-packages\PyQt6\   # 自编译 PyQt6
                                 # 注意：PyQt6-WebEngine 也折叠在此目录下
                                 # （QtWebEngineWidgets.pyd / QtWebEngineCore.pyd 等）
```

> 说明：`site-packages\PyQt6_WebEngine\` 目录**并不存在**——PyQt6-WebEngine 的扩展
> 都装在 `site-packages\PyQt6\` 里。不要去找/创建 `PyQt6_WebEngine\`。

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

### 3.1 总原则

**除第二节（冻结文件）与二点五节（文件系统红线）外，以下均可自由修改、优化、重构：**

- `src/purebrowser/**`（含 `ui/`、`core/`、`data/`、`pages/`）
- `resources/**`
- `tools/**`（脚本与测试）
- 新增文档（`docs/` 下新增文件；`docs/BUILD_NOTES.md` 除外）

当前主要文件（示例，非穷举）：

- UI：`ui/window.py`、`ui/tab.py`、`ui/tab_area.py`、`ui/tabbar.py`、`ui/urlbar.py`、
  `ui/theme.py`、`ui/icons.py`、`ui/hud.py`、`ui/menu_rows.py`、`ui/context_menu.py`、
  `ui/dropdown.py`、`ui/session_prompt.py`、`ui/freeze_overlay.py`
- Pages：`pages/pages.py`、`pages/newtab.py`、`pages/downloads.py`
- Data：`data/storage.py`、`data/history.py`、`data/bookmarks.py`、`data/favicons.py`、
  `data/downloads_store.py`、`data/session.py`
- Core（非冻结项）：`core/settings.py`、`core/locations.py`
- Entry（谨慎）：`app.py`

### 3.2 UI 和资源

- `resources/` 下的图标
- 新增 UI 文件
- `newtab.html` 以外的 HTML
- `resources/newtab.html`：新标签页，允许改。
  红线：保留 `/* __THEME_VARS__ */` 占位符，主题变量由 `pages/pages.py` 注入。

### 3.3 工具和文档

- `tools/` 下的脚本
- `README.md` / `README.zh-CN.md`
- 新增的文档
- 测试

### 3.4 可以改，但要保留原行为

- `src/purebrowser/__main__.py`
- `src/purebrowser/main.py`
- `pyproject.toml`（**不要改依赖版本**）

---

## 四、修改后的强制自检

每次改动后，**必须**跑相应命令并确认输出。

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

窗口应正常打开。**改动后，自己跑一次**，确认：

- 新标签页能加载
- 地址栏能输入并能打开 `example.com`
- 输入 `purebrowser://history` 能打开历史页
- 历史 / 书签 / 下载 **下拉面板**能弹出且可上下滚动（不是旧的 QMenu）
- `Ctrl+T` / `Ctrl+W` / `Ctrl+L` 快捷键有效

### 4.4 测试脚本（共 5 个）

| 脚本 | 用途 | 联网 | 何时必跑 |
|---|---|---|---|
| `tools/smoke_test.py` | 免 GUI 基础检查（版本 / 导入 / 数据目录 / 无官方 Qt6 覆盖） | 否 | **每次改动都跑** |
| `tools/e2e_test.py` | H.264 可用性检测（`avc1`） | 否 | 改 `profile.py` / `flags.py` / `tab.py` / `window.py` / `pyproject.toml` / `requirements.txt`（见 4.6） |
| `tools/regression_test.py` | GUI 回归：会话与窗口状态、右键菜单不泄漏 / 非分层、下载面板进度与角标、下拉滚动、Ctrl+F 桥接、全屏客户区 | 否 | 改 `ui/**`、`data/**`、`pages/**` 建议跑 |
| `tools/fullscreen_harness_test.py` | 离线全屏状态机（无中间态几何） | 否 | 改 `window.py` / `tab.py` 的全屏相关必跑 |
| `tools/fullscreen_test.py` | 联网全屏 e2e（真实站点，Fullscreen API 全链路） | 是 | 改全屏链路时跑；网络不可达会 SKIP（退出码 2） |

命令：

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\smoke_test.py
D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\regression_test.py
D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\e2e_test.py
D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\fullscreen_harness_test.py
```

退出码约定：`0` 通过、`1` 失败、`2` 跳过（如网络不可达）。

### 4.5 如果改了拦截器或隐私相关，额外验证

- 打开一个包含广告的网站
- 确认广告没加载出来

### 4.6 H.264 守护：端到端必须 `avc1 : probably`

以下改动**必须**额外跑 `tools/e2e_test.py`：

- `src/purebrowser/core/profile.py`
- `src/purebrowser/core/privacy/flags.py`
- `src/purebrowser/ui/tab.py`
- `src/purebrowser/ui/window.py`
- `pyproject.toml` / `requirements.txt` 里的依赖相关部分

命令：

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe tools\e2e_test.py
```

必须输出：

```
avc1   : probably
[OK]   H.264 可用（avc1 = probably）
```

若输出 `(不支持)` 或 `[FAIL]`，**立即停止改动**，报告用户。
这意味着自编译 QtWebEngine 被污染，或某个依赖 DLL 缺失。

### 4.7 如果改了打包相关（spec / runtime_hook / rebuild.bat / iss）

必须先 `rebuild.bat` 重新打包，再在 `dist\PureBrowser\PureBrowser.exe` 上实际验证（见第十节）。

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
| 临时工作区 | `D:\T\opencode`（仅在此建临时文件） |

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
- 改完立刻跑第四节中该改动涉及的测试（见 4.4 表格）
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
2. 第四节相关的自检输出（原样贴）
3. 有没有不确定的地方 / 未做/妥协项

### 7.4 不要做的事

- 不要加新的依赖（除非用户明确同意）
- 不要改 `pyproject.toml` 的依赖版本
- 不要加 CI/CD 配置（这是 Alpha 阶段，暂不需要）
- 不要"美化"代码风格（除非用户明确要求）
- 不要加 emoji 到代码里

### 7.5 提交规范（commit）

- **未经用户明确许可，不要 `commit` / `push`。** 默认只改工作区并报告。
- 一次提交只做一件事；文档改动单独成 commit。
- **不要 `amend` 已有 commit**（尤其是可能已推送的）。改错了就再补一个新 commit。
- commit message 前缀：`feat` / `fix` / `docs` / `build` / `chore` / `test` / `refactor`，示例：
  - `fix: fullscreen client area covers taskbar`
  - `docs: rewrite README (bilingual) + AGENTS`
- **不要提交**：`dist/`、`build/`、`installer/`、`*.db`、`settings.json`、`location.txt`、任何密钥/令牌/本机绝对路径产物（这些已在 `.gitignore`）。
- 提交前先 `git status` / `git diff` 自查，只 stage 本次改动涉及的文件。

### 7.6 测试脚本加固模板

新增/修改 `tools/` 下的 GUI 测试时，遵循现有脚本的模式：

- **硬超时**：`QTimer.singleShot(HARD_TIMEOUT_MS, ...)` 兜底，避免挂死。
- **销毁检测**：用 `sip.isdeleted(obj)`、`destroyed` 信号、或
  `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` 确认对象真的释放。
- **退出前先关窗**：先 `win.close()` 再 `app.exit(code)`，规避 QtWebEngine 退出时的偶发
  access violation（0xC0000005）。
- **能离线就别联网**：网络用例用 `loadFinished=False` / 超时判为 SKIP。
- **产物只写 `D:\T\opencode\`**（见二点五节）。
- **退出码**：`0` 通过、`1` 失败、`2` 跳过。

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

- `README.md` / `README.zh-CN.md` — 项目对外介绍（英文精炼 / 中文完整）
- `docs/BUILD_NOTES.md` — 自编译 QtWebEngine 的完整记录
- `docs/BUILD_NOTES.md` 第六节 — 所有 patch 详解（P1~P12）

遇到构建问题，先查 `BUILD_NOTES.md`，再问用户。

---

## 十、打包约束

打包链：**PyInstaller + Inno Setup**（由 `rebuild.bat` 驱动）。

| 文件 | 职责 |
|---|---|
| `PureBrowser.spec` | PyInstaller 配方：收集自编译 Qt6 的 DLL/插件/资源与 `QtWebEngineProcess.exe`；入口 `src/purebrowser/__main__.py`；`runtime_hooks=[runtime_hook.py]`。 |
| `runtime_hook.py` | 打包后运行时设置 5 个环境变量（见下）。 |
| `rebuild.bat` | 一键：杀旧进程 → `pyinstaller PureBrowser.spec --noconfirm` → Inno Setup `ISCC PureBrowser.iss`。 |
| `PureBrowser.iss` | Inno Setup 脚本；产物 `installer\Output\PureBrowserSetup.exe`。 |

约束：

1. **绝对路径写死**：`PureBrowser.spec`（`PROJECT` / `SRC` / `QT6_DIR` / `RESOURCES`）、
   `rebuild.bat`（`PROJECT` / `PYINSTALLER` / `SPEC` / `ISCC` / `ISS`）、`PureBrowser.iss`
   （`OutputDir` / `SetupIconFile`）都写死了本机路径。**改这些文件时不要"顺手"改成相对路径**，
   除非用户明确要求；换机器由用户自行修改。
2. **`runtime_hook.py` 的 5 个环境变量不要破坏**：
   `QT_PLUGIN_PATH`、`QT_QPA_PLATFORM_PLUGIN_PATH`、`QTWEBENGINEPROCESS_PATH`、
   `QTWEBENGINE_RESOURCES_PATH`、`QTWEBENGINE_LOCALES_PATH`。删任意一个都会让打包版起不来。
3. **不要提交打包产物**：`dist/`、`build/`、`installer/` 已在 `.gitignore`，不要 `-f` 强制加入。
4. 改打包相关后，**必须先 `rebuild.bat` 重新打包，再在 `dist\PureBrowser\PureBrowser.exe` 上验证**
   （源码跑通不代表打包版跑通）。
5. `README` 不进安装包（只影响仓库），但打包产物路径/行为变化时，同步更新
   `README.md` / `README.zh-CN.md` 的 Packaging 小节。

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

6. **最大化按钮改为自维护状态机**：`window.py` 用 `self._maximized` 作为唯一状态，`_toggle_maximize`
   只翻转该布尔并调用原生 `ShowWindow`；max 键在 `_native_hit_test` 里返回 `HTCLIENT`（不再返回
   `HTMAXBUTTON`，即放弃 Win11 贴靠 Snap）。原因是 `isMaximized()` 与原生状态失配 + HTMAXBUTTON
   点击被系统接管，导致"图标对、动作不对"。
   红线：不要改回"每次点击都查 `isMaximized()`/`IsZoomed()`"或用信号 `state` 直接刷图标。

7. **下拉菜单为自绘面板**：历史/书签/下载用 `ui/dropdown.py` 的 `DropdownPanel`（非 QMenu、不透明、
   可滚动、实时刷新）；右键菜单用 `ui/context_menu.py`。工具栏不再挂 `QGraphicsDropShadowEffect`
   （阴影会让每次重绘离屏渲染 + 高斯模糊，拖累视频）。
   红线：不要改用回 `QMenu` 富行 + 阴影；不要在工具栏重新加 `QGraphicsDropShadowEffect`。

---

*本文件最后更新：2026-10-01*
*修改本文件需用户明确许可。*
