import argparse
import sys
from pathlib import Path

from common.action_collection import StartWithActionCollection

ROOT = Path(__file__).resolve().parent


def apply_config(config_path: Path) -> bool:
    with open(config_path, "r", encoding="utf-8-sig") as f:
        text = f.read()

    collection = StartWithActionCollection.parse(text)
    return collection.run()


def main() -> int:
    parser = argparse.ArgumentParser(description='StartWith应用程序')
    parser.add_argument('--config', '-c', default='desktop', help='配置文件名（不包含.json扩展名）')
    args = parser.parse_args()

    config_path = ROOT / "config" / f"{args.config}.json"
    if not config_path.exists():
        print(f"配置不存在: {config_path}")
        return 1

    if apply_config(config_path):
        print(f"配置 [{args.config}] 应用完成")
        return 0

    print(f"配置 [{args.config}] 应用失败")
    return 1


if __name__ == '__main__':
    sys.exit(main())
