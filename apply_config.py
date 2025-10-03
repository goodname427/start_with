import argparse

from common.action_collection import StartWithActionCollection

def apply_config(config_path:str):
    with open(config_path, "r", encoding="utf-8") as f:
        text = f.read()

    collection = StartWithActionCollection.parse(text)
    collection.run()

def main():
    parser = argparse.ArgumentParser(description='StartWith应用程序')
    parser.add_argument('--config', '-c', default='desktop', help='配置文件名（不包含.json扩展名）')
    args = parser.parse_args()

    # 使用解析出的配置文件名
    config_path = f"config/{args.config}.json"

    apply_config(config_path)

if __name__ == '__main__':
    main()
