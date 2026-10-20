"""项目路径常量。所有路径均基于项目根目录，避免受工作目录影响。"""
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_ROOT / "config"
DATA_DIR = APP_ROOT / "data"
GUI_ASSETS_DIR = APP_ROOT / "gui" / "assets"

SETTINGS_FILE = DATA_DIR / "settings.json"
BINDINGS_FILE = DATA_DIR / "bindings.json"
LOG_FILE = DATA_DIR / "app.log"
ACC_LOG_FILE = DATA_DIR / "accelerator.log"
APPLY_SCRIPT = APP_ROOT / "apply_config.py"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
