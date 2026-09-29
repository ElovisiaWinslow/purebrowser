import json
from pathlib import Path

DEFAULTS = {
    "interceptor_enabled": True,
    "doh_enabled": True,
    "search_engine": "bing",
    "download_dir": "",
    "theme": "system",  # "system" | "light" | "dark"
}

SEARCH_ENGINES = {
    "bing": "https://cn.bing.com/search?q={q}",
    "baidu": "https://www.baidu.com/s?wd={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
    "google": "https://www.google.com/search?q={q}",
}

_BOOL_KEYS = ("interceptor_enabled", "doh_enabled")


class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = dict(DEFAULTS)
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value) -> None:
        if key in _BOOL_KEYS:
            value = str(value).lower() in ("true", "1", "on", "yes")
        self._data[key] = value
        self._save()

    def all(self) -> dict:
        return dict(self._data)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )