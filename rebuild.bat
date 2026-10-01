@echo off
chcp 65001 >nul
setlocal

set PROJECT=D:\PythonProject\purebrowser
set PYINSTALLER=%PROJECT%\.venv\Scripts\pyinstaller.exe
set SPEC=%PROJECT%\PureBrowser.spec
set ISCC="D:\Tools\Inno Setup 6\Inno Setup 6\ISCC.exe"
set ISS=%PROJECT%\PureBrowser.iss

cd /d "%PROJECT%"

echo ========================================
echo   PureBrowser Rebuild
echo ========================================
echo.

echo [1/4] Killing running instances...
taskkill /F /IM PureBrowser.exe >nul 2>&1
taskkill /F /IM QtWebEngineProcess.exe >nul 2>&1

echo [2/4] Running PyInstaller (this may take 2-5 minutes)...
"%PYINSTALLER%" "%SPEC%" --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See output above.
    pause
    exit /b 1
)

echo.
echo [3/4] Building installer with Inno Setup...
%ISCC% "%ISS%"
if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup compilation failed.
    echo Check that ISCC.exe exists at:
    echo   D:\Tools\Inno Setup 6\Inno Setup 6\ISCC.exe
    pause
    exit /b 1
)

echo.
echo [4/4] Done.
echo.
echo   Portable folder : %PROJECT%\dist\PureBrowser\
echo   Installer       : %PROJECT%\installer\Output\PureBrowserSetup.exe
echo.
echo To test:
echo   - Logic-only changes: run dist\PureBrowser\PureBrowser.exe
echo   - Icon changes:       xcopy to a NEW path first (Windows icon cache)
echo.

pause
endlocal