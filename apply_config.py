import argparse
import sys
from pathlib import Path

from common.action_collection import StartWithActionCollection

ROOT = Path(__file__).resolve().parent


def apply_config(config_path: Path, variables: dict[str, str] | None = None) -> bool:
    with open(config_path, "r", encoding="utf-8-sig") as f:
        text = f.read()

    collection = StartWithActionCollection.parse(text, variables)
    return collection.run()


def main() -> int:
    parser = argparse.ArgumentParser(description='StartWith应用程序')
    parser.add_argument('--config', '-c', default='desktop', help='配置文件名（不包含.json扩展名）')
    parser.add_argument(
        '--var',
        action='append',
        default=[],
        metavar='KEY=VALUE',
        help='为配置中的 {key} 占位符提供值，可重复指定',
    )
    args = parser.parse_args()

    variables: dict[str, str] = {}
    for item in args.var:
        key, separator, value = item.partition('=')
        key = key.strip()
        if not separator or not key:
            print(f"无效的 --var 参数: {item}（格式应为 KEY=VALUE）")
            return 1
        variables[key] = value

    config_path = ROOT / "config" / f"{args.config}.json"
    if not config_path.exists():
        print(f"配置不存在: {config_path}")
        return 1

    if apply_config(config_path, variables):
        print(f"配置 [{args.config}] 应用完成")
        return 0

    print(f"配置 [{args.config}] 应用失败")
    return 1


if __name__ == '__main__':
    sys.exit(main())
