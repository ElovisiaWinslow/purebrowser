# Building PureBrowser from Source

This guide walks you through building PureBrowser from source on a Windows x64 machine, including the **self-compiled PyQt6 / QtWebEngine with H.264 support**.

> **Why can't I just `pip install PyQt6`?**
> Standard PyPI wheels do **not** include H.264 — video playback on sites like Bilibili will fail.
> PureBrowser requires a custom QtWebEngine build with proprietary codecs enabled. See [BUILD_NOTES.md](BUILD_NOTES.md) for how it was built.

---

## Prerequisites

- **Windows 10 or 11 (x64)**
- **Python 3.10.x** (3.10.11 recommended) — [python.org](https://www.python.org/downloads/release/python-31011/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **Visual C++ Redistributable 2015–2022 (x64)** — [download](https://aka.ms/vs/17/release/vc_redist.x64.exe)

---

## Quick Start (using prebuilt dependencies)

### 1. Download prebuilt dependencies

Go to the [latest release](https://github.com/ElovisiaWinslow/purebrowser/releases/latest) and download these three files:

| File | Purpose |
|---|---|
| `PyQt6-6.7.1-cp38-abi3-win_amd64.whl` | PyQt6 Python bindings |
| `PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl` | QtWebEngine bindings |
| `Qt6-runtime-win64.zip` | Qt6 runtime binaries (DLLs, plugins, resources) |

Put them somewhere convenient, e.g. `D:\purebrowser-deps\`.

### 2. Extract Qt6 runtime

Extract `Qt6-runtime-win64.zip` to a **permanent location without spaces in the path**, e.g.:

```text
D:\Qt6-runtime\
```

After extraction, you should have:

```text
D:\Qt6-runtime
├── bin
│   ├── Qt6Core.dll
│   ├── Qt6WebEngineCore.dll
│   ├── QtWebEngineProcess.exe
│   └── ...
├── resources
│   ├── icudtl.dat
│   ├── qtwebengine_resources.pak
│   └── ...
├── plugins
│   ├── platforms
│   ├── imageformats
│   ├── tls
│   └── ...
└── translations
    └── qtwebengine_locales\
```

### 3. Configure environment variables

PureBrowser needs to find the Qt6 runtime. Add these **system environment variables** (Windows Settings → System → About → Advanced system settings → Environment Variables):

| Variable | Value |
|---|---|
| `PATH` | Append `D:\Qt6-runtime\bin` |
| `QT_PLUGIN_PATH` | `D:\Qt6-runtime\plugins` |

Optional but recommended:

| Variable | Value |
|---|---|
| `QTWEBENGINE_RESOURCES_PATH` | `D:\Qt6-runtime\resources` |
| `QTWEBENGINE_LOCALES_PATH` | `D:\Qt6-runtime\translations\qtwebengine_locales` |

> **Note**: The paths above must match where you extracted the runtime in step 2.

**Close and reopen your terminal** (or log out / log in) for the changes to take effect.

### 4. Clone the repository

```cmd
cd /d D:\
git clone https://github.com/ElovisiaWinslow/purebrowser.git
cd purebrowser
```

### 5. Create a virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
```

### 6. Install PyQt6 from local wheels

Order matters — install the bindings first:

```cmd
pip install D:\purebrowser-deps\PyQt6-6.7.1-cp38-abi3-win_amd64.whl
pip install D:\purebrowser-deps\PyQt6_WebEngine-6.7.0-cp38-abi3-win_amd64.whl
```

This will pull in PyQt6_sip from PyPI automatically.

### 7. Install PureBrowser

```cmd
pip install -e .
```

This installs PureBrowser and its pure-Python dependencies (httpx, platformdirs). It will not reinstall or upgrade PyQt6.

### 8. Verify H.264

This is the critical step. Run:

```cmd
python tools\e2e_test.py
```

Expected output:

```text
  avc1   : probably
  ...
[OK]   H.264 可用（avc1 = probably）
```

If you see `avc1 : probably` — everything is working. If not, see Troubleshooting.

### 9. Run PureBrowser

```cmd
python -m purebrowser
```

## Building the installer

To produce PureBrowserSetup.exe:

Install Inno Setup 6

Edit PureBrowser.spec, runtime_hook.py, rebuild.bat, and PureBrowser.iss — they contain hardcoded absolute paths that point to the author's machine (e.g. D:\PythonProject\purebrowser). Replace with your own paths.

Run rebuild.bat (double-click, or from cmd).

Outputs:

dist\PureBrowser\ — portable folder

installer\Output\PureBrowserSetup.exe — installer

## Rebuilding QtWebEngine from scratch

If you want to compile PyQt6 / QtWebEngine yourself (with H.264), see:

docs/BUILD_NOTES.md — full compile log

Expect several hours of compile time and ~50 GB of disk space.

## Troubleshooting

### Failed to load Python DLL 'python310.dll' when running the exe

You copied only PureBrowser.exe somewhere. You must copy the entire PureBrowser\ folder (including _internal\).

### qt.qpa.plugin: Could not find the Qt platform plugin "windows"

QT_PLUGIN_PATH is not set, or points to the wrong directory. Verify:

```cmd
echo %QT_PLUGIN_PATH%
```

It should print your Qt6-runtime plugins folder.

### Video plays but no audio / crashes on video sites

Usually means H.264 is missing. Run python tools\e2e_test.py and check for avc1 : probably. If it shows anything else, your Qt6 runtime is not the self-compiled one.

### ImportError: DLL load failed while importing QtWebEngineCore

The Qt6 runtime DLLs are not on your PATH. Verify D:\Qt6-runtime\bin is in PATH and that you restarted your terminal after setting it.

### ModuleNotFoundError: No module named 'purebrowser'

You forgot pip install -e . in step 7, or you're running from the wrong directory.

## Project layout

See README.md.

## License

MPL-2.0