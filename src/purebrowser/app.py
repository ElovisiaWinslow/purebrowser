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

    from purebrowser.core.locations import get_data_dir
    from purebrowser.window import MainWindow

    app = QApplication(argv)
    app.setApplicationName("PureBrowser")
    app.setOrganizationName("PureBrowser")
    app.setDesktopFileName("purebrowser")

    data_dir = get_data_dir()
    win = MainWindow(data_dir)
    win.show()
    return app.exec()