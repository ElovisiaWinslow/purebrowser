from pathlib import Path

from platformdirs import user_data_dir, user_downloads_dir

APP_NAME = "PureBrowser"
APP_AUTHOR = "PureBrowser"


def config_dir() -> Path:
    d = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def pointer_file() -> Path:
    return config_dir() / "location.txt"


def settings_file() -> Path:
    return config_dir() / "settings.json"


def default_data_dir() -> Path:
    d = config_dir() / "profile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_data_dir() -> Path:
    p = pointer_file()
    if p.exists():
        try:
            line = p.read_text(encoding="utf-8").strip()
            if line:
                d = Path(line)
                d.mkdir(parents=True, exist_ok=True)
                return d
        except OSError:
            pass
    return default_data_dir()


def set_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pointer_file().write_text(str(path), encoding="utf-8")


def default_download_dir() -> Path:
    d = Path(user_downloads_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d