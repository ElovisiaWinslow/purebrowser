import ctypes
import os
import sys
from pathlib import Path


def run(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv

    from PyQt6.QtWebEngineCore import QWebEngineUrlScheme

    scheme = QWebEngineUrlScheme(b"purebrowser")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)

    from PyQt6.QtWidgets import QApplication

    from purebrowser.core.locations import get_data_dir, resource_path, settings_file
    from purebrowser.core.settings import Settings
    from purebrowser.ui import theme as theme_mod
    from purebrowser.ui.window import MainWindow

    app = QApplication(argv)
    app.setApplicationName("PureBrowser")
    app.setOrganizationName("PureBrowser")
    app.setDesktopFileName("purebrowser")

    from PyQt6.QtGui import QFont, QIcon

    font = QFont("Segoe UI Variable", 9)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # 应用图标（跨平台）
    app.setWindowIcon(QIcon(str(resource_path("purebrowser.ico"))))

    # Windows 任务栏分组与图标归属（AUMID 终身不变）
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PureBrowser.Browser"
            )
        except Exception:
            pass

    settings = Settings(settings_file())
    theme_mod.apply(app, theme_mod.resolve_theme(settings.get("theme", "system")))

    data_dir = get_data_dir()
    win = MainWindow(data_dir)
    win.show()
    return app.exec()