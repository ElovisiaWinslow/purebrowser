"""会话快照读写：data_dir/session.json（原子写，容错解析）。"""
import json
import os
from pathlib import Path


def session_path(data_dir) -> Path:
    return Path(data_dir) / "session.json"


def load(data_dir) -> dict:
    p = session_path(data_dir)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"tabs": [], "active": -1}


def save(data_dir, data: dict) -> None:
    p = session_path(data_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
