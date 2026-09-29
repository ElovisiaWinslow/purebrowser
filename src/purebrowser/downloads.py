import os
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

from purebrowser.locations import default_download_dir


class DownloadManager(QObject):
    changed = pyqtSignal()

    def __init__(self, profile, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.records: list[dict] = []
        profile.downloadRequested.connect(self._on_requested)

    def current_dir(self) -> Path:
        custom = (self.settings.get("download_dir", "") or "").strip()
        d = Path(custom) if custom else default_download_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _on_requested(self, req: QWebEngineDownloadRequest) -> None:
        target_dir = self.current_dir()
        req.setDownloadDirectory(str(target_dir))
        req.setDownloadFileName(self._unique_name(target_dir, req.downloadFileName()))

        rec = {
            "req": req,
            "filename": req.downloadFileName(),
            "path": str(target_dir / req.downloadFileName()),
            "total": req.totalBytes(),
            "received": 0,
            "finished": False,
            "canceled": False,
        }
        self.records.append(rec)

        req.receivedBytesChanged.connect(lambda r=req: self._on_progress(r))
        req.isFinishedChanged.connect(lambda r=req: self._on_finished(r))
        req.accept()
        self.changed.emit()

    def _on_progress(self, req: QWebEngineDownloadRequest) -> None:
        for rec in self.records:
            if rec["req"] is req:
                rec["received"] = req.receivedBytes()
                rec["total"] = req.totalBytes()
                break
        self.changed.emit()

    def _on_finished(self, req: QWebEngineDownloadRequest) -> None:
        for rec in self.records:
            if rec["req"] is req:
                rec["finished"] = True
                rec["canceled"] = (
                    req.state()
                    != QWebEngineDownloadRequest.DownloadState.DownloadCompleted
                )
                break
        self.changed.emit()

    def _unique_name(self, target_dir: Path, filename: str) -> str:
        if not (target_dir / filename).exists():
            return filename
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        n = 1
        while True:
            new_name = f"{stem} ({n}){suffix}"
            if not (target_dir / new_name).exists():
                return new_name
            n += 1

    def active_count(self) -> int:
        return sum(1 for r in self.records if not r["finished"])

    def has_any(self) -> bool:
        return bool(self.records)

    def open_folder(self) -> None:
        os.startfile(str(self.current_dir()))  # noqa: S606