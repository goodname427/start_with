from common.parser import ActionParser

if __name__ == '__main__':
    with open("config/test.json", "r") as f:
        text = f.read()

    collection = ActionParser.parse(text)
    collection.run()