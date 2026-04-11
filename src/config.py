"""
本地配置文件管理
配置存储在项目根目录的 config.json，不纳入版本控制
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

DEFAULTS = {}


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULTS)


def save(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
