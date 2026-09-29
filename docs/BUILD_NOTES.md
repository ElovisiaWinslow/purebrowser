# QtWebEngine 6.7.3 自编译笔记

> 本笔记记录了在 Windows 上从源码编译 Qt 6.7.3 + QtWebEngine（启用 H.264）、
> 以及编译 PyQt6 和 PyQtWebEngine 的完整过程、所有 patch 和踩坑记录。
> 目标读者：想复现此构建、或想修改 QtWebEngine 内核行为的开发者。

---

## 一、项目背景

标准 Qt 6.7.3 的 pip wheel 中，QtWebEngine 不带 H.264 解码器
（Qt 官方编译时未开启 `-webengine-proprietary-codecs`）。
后果是 B 站、腾讯视频等使用 H.264 的网站报“当前浏览器不支持 HTML5 播放器”。

本项目从源码编译 Qt 6.7.3，显式启用 H.264，生成可用的 Qt6WebEngineCore.dll，
并通过自编译的 PyQt6 绑定在 Python 中使用。

## 二、最终产物

| 产物 | 路径 | 大小 |
|---|---|---|
| Qt 6.7.3 自编译安装 | `D:\develop\Qt6-custom\` | ~1.5 GB |
| Qt6WebEngineCore.dll | `Qt6-custom\bin\Qt6WebEngineCore.dll` | 149 MB |
| PyQt6 wheel | `D:\develop\pyqt6-src\PyQt6-6.7.1-cp38-abi3-win_amd64.whl` | 5.3 MB |
| PyQt6_WebEngine wheel | `D:\develop\pyqtwebengine-src\PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl` | 189 KB |

**验证结果**：B 站视频可正常播放，画面与声音均正常。

## 三、硬件与软件环境

### 机器规格（本次构建）
- 操作系统：Windows 10.0.26200
- 内存：16 GB
- 磁盘：需预留 100 GB 以上

### 工具链

| 工具 | 版本 | 路径 |
|---|---|---|
| VS Build Tools 2022 | v18.10.2 | `D:\develop\VSBuildTools` |
| MSVC v143（预览） | 14.51.36231 | `D:\develop\VSBuildTools\VC\Tools\MSVC\14.51.36231` |
| MSVC v142 | 14.29.30133 | `D:\develop\VSBuildTools\VC\Tools\MSVC\14.29.30133` |
| Windows SDK | 10.0.26100 | 系统安装 |
| CMake | 4.4.3 | Strawberry 附带 |
| Ninja | 1.13.2 | Strawberry 附带 |
| Strawberry Perl | 5.42.3 | `C:\Strawberry` |
| Node.js | v24.19.0 | 系统安装 |
| gperf | 3.0.1 | `D:\develop\tools\gperf\bin` |
| winflexbison | 2.5.25 | `D:\develop\tools\winflexbison` |
| Python（Qt 构建用） | 3.13.2 | `D:\python3.13.2` |
| Python（PyQt 构建用） | 3.10.11 | `D:\Environment\Python\Python310` |

### 源码位置
- Qt 源码：`D:\develop\qt6-src\qt-everywhere-src-6.7.3`
- Qt 构建目录：`D:\develop\qt6-build`
- Qt 安装目录：`D:\develop\Qt6-custom`

## 四、编译总览

| 阶段 | 耗时 | 说明 |
|---|---|---|
| 环境准备 | 2~4 小时 | 装工具链、下载源码 |
| Qt configure | 2~5 分钟 | |
| Qt 主编译 | 3~6 小时 | 至 6356/6558 |
| QtWebEngine 编译 | 2~4 天 | 首次构建几乎必然踩坑 |
| Qt install | 1~5 分钟 | |
| PyQt6 编译 | 20~40 分钟 | |
| PyQtWebEngine 编译 | 10~30 分钟 | |

**首次复现预计总时间：2~5 天**（取决于踩坑多少）

## 五、从零开始的完整流程

### 阶段 1：系统准备

#### 1.1 开启 UTF-8 系统区域
```
控制面板 → 区域 → 管理 → 更改系统区域设置
→ 勾选"Beta: 使用 Unicode UTF-8 提供全球语言支持"
→ 重启
```
**原因**：Qt 源码中含非 GBK 字符，不开 UTF-8 系统区域会报 `warning C4819`，配合 `/WX` 直接编译失败。

#### 1.2 开启长路径支持
以管理员身份运行：
```cmd
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
```
重启生效。

**原因**：Chromium 编译产生极深的目录结构，超过 260 字符会触发 `RecursionError`。

#### 1.3 TEMP 指向短路径
```cmd
mkdir D:\T
setx TEMP "D:\T"
setx TMP "D:\T"
```

### 阶段 2：工具链安装

- VS Build Tools 2022，勾选：
  - 使用 C++ 的桌面开发
  - MSVC v143 + MSVC v142
  - Windows 11 SDK (10.0.26100)
  - C++ ATL for x64/x86
  - C++ CMake 工具
- Strawberry Perl（winget install StrawberryPerl.StrawberryPerl）
- Node.js LTS（winget install OpenJS.NodeJS.LTS）
- gperf 3.0.1（从 SourceForge 下载，放到 `D:\develop\tools\gperf\bin`）
- winflexbison 2.5.25（从 GitHub releases 下载，复制 `win_bison.exe` 和 `win_flex.exe` 为 `bison.exe` 和 `flex.exe`）

### 阶段 3：获取源码

从清华镜像下载：
```
https://mirrors.ustc.edu.cn/qtproject/archive/qt/6.7/6.7.3/single/qt-everywhere-src-6.7.3.zip
```
解压到 `D:\develop\qt6-src\qt-everywhere-src-6.7.3`，确保 `configure.bat` 直接可见。

### 阶段 4：Qt configure

打开 **x64 Native Tools Command Prompt for VS 2022**（或手动 call vcvars64.bat）：

```cmd
mkdir D:\develop\qt6-build
cd /d D:\develop\qt6-build

D:\develop\qt6-src\qt-everywhere-src-6.7.3\configure.bat ^
  -release ^
  -webengine-proprietary-codecs ^
  -nomake examples -nomake tests ^
  -prefix D:\develop\Qt6-custom ^
  -skip qtdoc -skip qttranslations -skip qt3d -skip qt5compat ^
  -skip qtcharts -skip qtcoap -skip qtconnectivity -skip qtdatavis3d ^
  -skip qtgraphs -skip qtgrpc -skip qthttpserver -skip qtimageformats ^
  -skip qtlanguageserver -skip qtlocation -skip qtlottie -skip qtmultimedia ^
  -skip qtnetworkauth -skip qtopcua -skip qtquick3d -skip qtquick3dphysics ^
  -skip qtquickeffectmaker -skip qtquicktimeline -skip qtremoteobjects ^
  -skip qtscxml -skip qtsensors -skip qtserialbus -skip qtserialport ^
  -skip qtspeech -skip qtvirtualkeyboard -skip qtwebview
```

**configure 成功的标志**：
```
Compiler: msvc 19.xx
  Build QtWebEngineCore ................ yes
  Build QtWebEngineWidgets ............. yes
  Proprietary Codecs ..................... yes
```

### 阶段 5：Qt 主编译

```cmd
cd /d D:\develop\qt6-build
cmake --build . --parallel 4 > D:\develop\build.log 2>&1
```

**注意**：16 GB 内存推荐 `--parallel 4`，32 GB 可用 `--parallel 8`。
过高并行度会导致 `cl.exe` 内存溢出被杀。

### 阶段 6：QtWebEngine 内核编译

首次编译在 `base_jumbo_45.obj` 处失败，报 ATL 头文件缺失。

内层编译必须在 `D:\develop\qt6-build\qtwebengine\src\core\Release\AMD64` 目录里单独跑，
该目录下的 `environment.x64` 和 `toolchain.ninja` 是内层 ninja 使用的环境文件。

```cmd
cd /d D:\develop\qt6-build\qtwebengine\src\core\Release\AMD64
C:\Strawberry\c\bin\ninja.exe QtWebEngineCore
```

编译到 26023 个目标。中途需要打下面所有 patch。

### 阶段 7：Qt 安装

```cmd
cd /d D:\develop\qt6-build
cmake --install . > D:\develop\install.log 2>&1
```

### 阶段 8：PyQt6 编译

```cmd
:: 装构建工具（用系统 Python 3.10，不是项目 venv）
D:\Environment\Python\Python310\python.exe -m pip install "sip==6.8.6" "PyQt-builder==1.16.4" -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 下载 PyQt6 源码（绕过 pip 的 metadata 检查）
curl -L -o PyQt6-6.7.1.tar.gz "https://pypi.tuna.tsinghua.edu.cn/packages/d1/f9/b0c2ba758b14a7219e076138ea1e738c068bf388e64eee68f3df4fc96f5a/PyQt6-6.7.1.tar.gz"
mkdir D:\develop\pyqt6-src
tar -xzf PyQt6-6.7.1.tar.gz -C D:\develop\pyqt6-src --strip-components=1

:: 编译（在 MSVC 环境中）
cd /d D:\develop\pyqt6-src
D:\Environment\Python\Python310\Scripts\sip-wheel.exe --qmake D:\develop\Qt6-custom\bin\qmake.exe --build-dir D:\pb
```

### 阶段 9：PyQtWebEngine 编译

```cmd
:: 下载（须开 VPN）
curl -L -o PyQt6_WebEngine-6.7.0.tar.gz "https://files.pythonhosted.org/packages/source/P/PyQt6-WebEngine/PyQt6_WebEngine-6.7.0.tar.gz"
mkdir D:\develop\pyqtwebengine-src
tar -xzf PyQt6_WebEngine-6.7.0.tar.gz -C D:\develop\pyqtwebengine-src --strip-components=1

:: 修改 pyproject.toml，加 sip-include-dirs（见 P11）

:: 编译
cd /d D:\develop\pyqtwebengine-src
D:\Environment\Python\Python310\Scripts\sip-wheel.exe --qmake D:\develop\Qt6-custom\bin\qmake.exe --build-dir D:\pbwe
```

### 阶段 10：装到项目 venv

```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe -m pip uninstall PyQt6 PyQt6-Qt6 PyQt6-WebEngine PyQt6-WebEngine-Qt6 PyQt6_sip -y

D:\PythonProject\purebrowser\.venv\Scripts\python.exe -m pip install D:\develop\pyqt6-src\PyQt6-6.7.1-cp38-abi3-win_amd64.whl --no-deps

D:\PythonProject\purebrowser\.venv\Scripts\python.exe -m pip install "PyQt6_sip==13.8.0" --no-deps

D:\PythonProject\purebrowser\.venv\Scripts\python.exe -m pip install D:\develop\pyqtwebengine-src\PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl --no-deps
```

### 阶段 11：环境变量

以**用户级环境变量**设置（管理员权限）：

```powershell
# PATH 追加
$p = [Environment]::GetEnvironmentVariable("Path", "User")
$p = "D:\develop\Qt6-custom\bin;" + $p
[Environment]::SetEnvironmentVariable("Path", $p, "User")

# 插件路径
[Environment]::SetEnvironmentVariable("QT_PLUGIN_PATH", "D:\develop\Qt6-custom\plugins", "User")
```

---

## 六、Patch 详解

### P1. 系统 UTF-8 区域
见阶段 1.1。**不开启会导致 `warning C4819` 被 `/WX` 升级为 error。**

### P2. 长路径支持
见阶段 1.2。**不开启会导致临时目录清理时 `RecursionError`。**

### P3. ATL 路径注入

**文件**：`D:\develop\qt6-build\qtwebengine\src\core\Release\AMD64\environment.x64`

**问题**：Chromium 的 `base/win/atl_throw.h` 引用 `atldef.h`，但内层 ninja 的环境文件不含 ATL 路径。

**修改**：在该文件中，
- `set INCLUDE=` 开头插入 `D:\develop\VSBuildTools\VC\Tools\MSVC\14.51.36231\atlmfc\include;`
- `set LIB=` 开头插入 `D:\develop\VSBuildTools\VC\Tools\MSVC\14.51.36231\atlmfc\lib\x64;`

**PowerShell 一行改法**：
```powershell
$f = "D:\develop\qt6-build\qtwebengine\src\core\Release\AMD64\environment.x64"
copy $f "$f.bak"
$atl_inc = "D:\develop\VSBuildTools\VC\Tools\MSVC\14.51.36231\atlmfc\include"
$atl_lib = "D:\develop\VSBuildTools\VC\Tools\MSVC\14.51.36231\atlmfc\lib\x64"
(Get-Content $f) `
  -replace '^set INCLUDE=', "set INCLUDE=$atl_inc;" `
  -replace '^set LIB=', "set LIB=$atl_lib;" `
  | Set-Content $f
```

### P4. 相对路径批量替换

**问题**：内层 ninja 的 `toolchain.ninja` 使用 `../../../../../../qt6-src/` 相对路径，
在某些场合（尤其 Python 脚本调用时）解析失败，报 `FileNotFoundError`。

**修改**：将所有 `.ninja` 和 `.rsp` 文件中的
`../../../../../../qt6-src/` 替换为 `D:/develop/qt6-src/`。

**批量脚本 `fix_paths.ps1`**：
```powershell
$root = "D:\develop\qt6-build"
$old  = "../../../../../../qt6-src/"
$new  = "D:/develop/qt6-src/"

Get-ChildItem -Path $root -Recurse -Include *.ninja,*.rsp | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -like "*$old*") {
        $content = $content -replace [regex]::Escape($old), $new
        Set-Content -Path $_.FullName -Value $content -NoNewline
        Write-Host "patched: $($_.FullName)"
    }
}
```

### P5. GN 规则空操作

**问题**：每次 ninja 认为 `build.ninja` 过期，就调用 GN 重新生成，把 P4 的绝对路径又写回相对路径。

**文件**：`D:\develop\qt6-build\qtwebengine\src\core\Release\AMD64\build.ninja`（内层）

**修改**：将第 3 行开始的 `rule gn` 段中的 `command` 替换为空操作：

    rule gn
      command = cmd /c exit 0
      pool = console
      description = Regenerating ninja files

**原因**：`cmd /c exit 0` 返回成功但不做任何事，ninja 认为 GN 已运行完毕，不会报错，也不会真正调用 GN 去覆盖已 patch 的 .ninja 文件。

**注意**：
- 这是权宜之计。若要重新 configure，必须先备份此修改，或从 `qt-build-archive\build.ninja` 恢复。
- 外层 `D:\develop\qt6-build\build.ninja` 由 CMake 生成，本身没有 GN 规则，不需要修改。

### P6. TypeScript 编译配置

**文件**：`D:\develop\qt6-src\qt-everywhere-src-6.7.3\qtwebengine\src\3rdparty\chromium\tools\typescript\ts_library.py`

**问题**：devtools-frontend 前端编译时，`tsconfig.json` 里 `rootDir` 太窄，
TS 报 `TS6059` / `TS6305` / `TS6307`。

**修改**：在 `generate_tsconfig()` 中将 `rootDir` 扩展到 `front_end` 目录，
添加 `include` 字段，设置 `allowJs=True`, `checkJs=False`。

### P7. Rollup 插件路径

**文件**：`D:\develop\qt6-src\qt-everywhere-src-6.7.3\qtwebengine\src\3rdparty\chromium\third_party\devtools-frontend\scripts\build\build_inspector_overlay.py`

**问题**：Rollup 把 `D:/...loadCSS.rollup.js` 当作 `key:value` 解析，报 `Invalid --plugin argument format`。

**修改**：将传递给 `--plugin` 的路径改为相对于当前工作目录的相对路径。

### P8. Mojo 生成器路径

**文件**：`...\chromium\mojo\public\tools\bindings\mojom_bindings_generator.py`

**问题**：Windows 盘符 `D:` 被当成路径分隔符。

**修改**：在路径处理逻辑中显式识别 `X:` 形式的盘符前缀，正确拼接。

**同时**：所有 `.rsp` 文件里的相对路径也要改成绝对路径（P4 已覆盖）。

### P9. 编译器切换 v143 → v142

**问题**：MSVC 14.51.36231 在编译 `per_target.obj`（涉及 `x86_128-inl.h` 的 V8 代码）
时触发 `C1001: 内部编译器错误`。这是该版本的回归 bug。

**修改**：
1. 在 VS Installer 中安装 MSVC v142（14.29.30133）
2. 编辑 `toolchain.ninja` 和 `environment.x64`，
   将所有 `14.51.36231` 替换为 `14.29.30133`
3. v142 未装 ATL，借用 v143 的 ATL 路径（见 P3）

**验证**：`toolchain.ninja` 中应无 `14.51.36231`。

### P10. sipbuild GBK 编码

**文件**：`D:\Environment\Python\Python310\Lib\site-packages\sipbuild\project.py`

**问题**：中文版 MSVC 输出 GBK 编码，sip 用 `sys.stdout.encoding`（UTF-8）解码，
报 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb3`。

**修改**：约第 572 行，
```python
# 修改前
yield str(line, encoding=sys.stdout.encoding)

# 修改后
yield str(line, encoding='gbk')
```

### P11. PyQtWebEngine 的 sip-include-dirs

**文件**：`D:\develop\pyqtwebengine-src\pyproject.toml`

**问题**：PyQtWebEngine 的 `QtWebEngineCoremod.sip` 引用 `QtCore/QtCoremod.sip`，
但 sip 不知道 PyQt6 的 bindings 在哪，报 `could not be found`。

**修改**：在 `[tool.sip.project]` 段下加一行：
```toml
sip-include-dirs = ["D:/PythonProject/purebrowser/.venv/Lib/site-packages/PyQt6/bindings"]
```

### P12. 补齐依赖 DLL

**问题**：自编译的 Qt6Core.dll / Qt6Gui.dll 依赖 `zlib1__.dll` 和 `libpng16-16__.dll`，
但二者不在 `Qt6-custom\bin`，Python 加载时 `ImportError: DLL load failed`。

**修改**：从 Strawberry Perl 拷贝 x64 版本到 `Qt6-custom\bin`：
```cmd
dumpbin /headers C:\Strawberry\c\bin\zlib1__.dll | findstr machine
:: 确认显示 machine (x64) 后
copy C:\Strawberry\c\bin\zlib1__.dll D:\develop\Qt6-custom\bin\
copy C:\Strawberry\c\bin\libpng16-16__.dll D:\develop\Qt6-custom\bin\
```

---

## 七、验证清单

### Qt 层
```cmd
D:\develop\Qt6-custom\bin\qmake.exe --version
:: 应显示 QMake version 3.1 / Using Qt version 6.7.3

dir D:\develop\Qt6-custom\bin\Qt6WebEngineCore.dll
:: 应存在，约 149 MB
```

### Python 层
```cmd
D:\PythonProject\purebrowser\.venv\Scripts\python.exe -c "from PyQt6.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)"
:: 应打印 6.7.3

D:\PythonProject\purebrowser\.venv\Scripts\python.exe -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; print('OK')"
:: 应打印 OK
```

### 端到端
```python
# test_webengine.py
import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView


class Page(QWebEnginePage):
    def createWindow(self, _type):
        return self


app = QApplication(sys.argv)
view = QWebEngineView()
view.setPage(Page(view))
view.load(QUrl("https://www.bilibili.com/"))
view.resize(1200, 800)
view.show()
sys.exit(app.exec())
```
运行后点击任意视频，画面与声音应正常。

---

## 八、已知问题与限制

1. **仅支持 Windows x64**。Linux/macOS 需重新调整。
2. **QtWebEngine 内核锁定在 v142 编译器**。如果重装 VS 时未勾选 v142，需补装。
3. **C1001 是 v143 的回归 bug**，微软已在后续版本修复，但本构建所用的 14.51.36231 仍受影响。
4. **GN 规则被改为空操作**。若需重新 configure，必须从备份恢复 build.ninja。
5. **首次编译需要 60~100 GB 磁盘**（源码 + 中间产物）。
6. **编译 PyQt6 时必须用 v143 编译器**（外层），内层 QtWebEngine 用 v142，
   两者 ABI 兼容（同一 MSVC 主版本）。
7. **`PyQt6_sip` 必须匹配 PyQt6 版本**。PyQt6 6.7.1 用 `PyQt6_sip==13.8.0`。
8. **不能装 `PyQt6-Qt6` 和 `PyQt6-WebEngine-Qt6`**。这两个 pip 包会覆盖自编译 Qt。

---

## 九、复现时间估算

| 阶段 | 最少 | 一般 | 首次踩坑 |
|---|---|---|---|
| 环境准备 | 2 h | 4 h | 1 天 |
| Qt configure | 2 min | 5 min | 数小时 |
| Qt 主编译 | 3 h | 5 h | — |
| QtWebEngine | 1 天 | 2 天 | **2~4 天** |
| install | 2 min | 5 min | — |
| PyQt6 | 20 min | 40 min | 数小时 |
| PyQtWebEngine | 10 min | 30 min | 数小时 |
| **总计** | 2 天 | 3 天 | **5~7 天** |

---

## 十、文件清单

本归档包含以下关键文件：

```
qt-build-archive/
├─ BUILD_NOTES.md              # 本文档
├─ environment.x64             # 内层构建环境（含 ATL 路径 patch）
├─ toolchain.ninja             # 内层工具链（含 v142 切换 + 路径 patch）
├─ build.ninja                 # 外层规则（GN 空操作 patch）
├─ patches/
│  ├─ sipbuild_project.py      # sipbuild GBK 编码 patch
│  ├─ pyqt6-pyproject.toml     # PyQt6 构建配置
│  └─ pyqtwebengine-pyproject.toml  # PyQtWebEngine 构建配置（含 sip-include-dirs）
├─ scripts/
│  ├─ fix_paths.ps1            # 路径批量修复
│  └─ build_qtwebengine.bat    # 一键构建脚本
└─ logs/
   ├─ build6.log               # Qt 主编译日志
   ├─ pyqt6.log                # PyQt6 编译日志
   └─ pyqtwe.log               # PyQtWebEngine 编译日志
```

---

*文档版本：1.0  |  最后更新：2026-09-29*
