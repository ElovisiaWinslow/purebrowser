import os
import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

from purebrowser.core.locations import default_download_dir
from purebrowser.data import downloads_store

_State = QWebEngineDownloadRequest.DownloadState


def _state_text(state) -> str:
    if state == _State.DownloadCompleted:
        return "completed"
    if state == _State.DownloadCancelled:
        return "cancelled"
    if state == _State.DownloadInterrupted:
        return "interrupted"
    return "inprogress"


class DownloadManager(QObject):
    changed = pyqtSignal()

    def __init__(self, profile, settings, conn, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.conn = conn
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
            "state": req.state(),
            "interrupt_reason": "",
            "is_paused": req.isPaused(),
            "finished": False,
            "canceled": False,
            "url": req.url().toString(),
            "mime": req.mimeType(),
            "created_at": int(time.time()),
            "finished_at": None,
            "state_text": "inprogress",
            "db_id": None,
        }
        self.records.append(rec)
        rec["db_id"] = downloads_store.save(self.conn, rec)

        req.receivedBytesChanged.connect(lambda r=req: self._on_progress(r))
        req.totalBytesChanged.connect(lambda r=req: self._on_progress(r))
        req.stateChanged.connect(lambda r=req: self._on_state(r))
        req.isPausedChanged.connect(lambda r=req: self._on_state(r))
        req.interruptReasonChanged.connect(lambda r=req: self._on_state(r))
        req.isFinishedChanged.connect(lambda r=req: self._on_state(r))
        req.accept()
        self.changed.emit()

    def _rec(self, req: QWebEngineDownloadRequest):
        for rec in self.records:
            if rec["req"] is req:
                return rec
        return None

    def _on_progress(self, req: QWebEngineDownloadRequest) -> None:
        rec = self._rec(req)
        if rec is None:
            return
        rec["received"] = req.receivedBytes()
        rec["total"] = req.totalBytes() or rec["total"]
        self.changed.emit()

    def _on_state(self, req: QWebEngineDownloadRequest) -> None:
        rec = self._rec(req)
        if rec is None:
            return
        rec["state"] = req.state()
        rec["state_text"] = _state_text(req.state())
        rec["is_paused"] = req.isPaused()
        if req.state() == _State.DownloadInterrupted:
            rec["interrupt_reason"] = req.interruptReasonString() or ""
        rec["received"] = req.receivedBytes()
        rec["total"] = req.totalBytes() or rec["total"]
        if req.isFinished():
            rec["finished"] = True
            rec["canceled"] = req.state() != _State.DownloadCompleted
            rec["finished_at"] = int(time.time())
            rec["req"] = None
        self._persist(rec)
        self.changed.emit()

    def _persist(self, rec: dict) -> None:
        db_id = rec.get("db_id")
        if db_id is None:
            return
        downloads_store.update(
            self.conn,
            db_id,
            rec.get("state_text", "inprogress"),
            rec.get("received", 0),
            rec.get("total", 0),
            rec.get("interrupt_reason", ""),
            rec.get("finished_at"),
        )

    # ---------- controls (only meaningful while InProgress) ----------
    def toggle_pause(self, rec: dict) -> None:
        if rec.get("is_paused"):
            self.resume(rec)
        else:
            self.pause(rec)

    def pause(self, rec: dict) -> None:
        req = rec.get("req")
        if req is None or req.state() != _State.DownloadInProgress or req.isPaused():
            return
        req.pause()
        rec["is_paused"] = True
        self._persist(rec)
        self.changed.emit()

    def resume(self, rec: dict) -> None:
        req = rec.get("req")
        if req is None or req.state() != _State.DownloadInProgress or not req.isPaused():
            return
        req.resume()
        rec["is_paused"] = False
        self._persist(rec)
        self.changed.emit()

    def cancel(self, rec: dict) -> None:
        req = rec.get("req")
        if req is None or req.state() != _State.DownloadInProgress:
            return
        req.cancel()
        self._persist(rec)
        self.changed.emit()

    # ---------- helpers ----------
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

    @staticmethod
    def open_file(path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            os.startfile(str(p))  # noqa: S606
            return True
        except OSError:
            return False

    @staticmethod
    def reveal_in_explorer(path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            subprocess.Popen(
                ["explorer", "/select," + str(p)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except OSError:
            return False

    def remove(self, rec: dict) -> None:
        """从列表移除一条记录，并同步删除库中的对应行（不删文件）。"""
        db_id = rec.get("db_id")
        try:
            self.records.remove(rec)
        except ValueError:
            return
        if db_id is not None:
            downloads_store.remove(self.conn, db_id)
        self.changed.emit()
