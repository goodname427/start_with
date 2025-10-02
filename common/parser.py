import importlib
import json

from actions.action import StartWithAction
from common.action_collection import ActionCollection

actions_module = importlib.import_module("actions")

class ActionParser:
    @staticmethod
    def __snake_to_pascal(s):
        # 分割字符串并处理每个单词
        words = s.split('_')
        # 每个单词首字母大写，然后拼接
        return ''.join(word.capitalize() for word in words)

    @staticmethod
    def parse(text:str) -> ActionCollection:
        collection = ActionCollection()

        try:
            json_object = json.loads(text)
        except json.decoder.JSONDecodeError:
            print("Config is not valid JSON")
            return collection

        if "actions" not in json_object:
            print("Config No actions found")
            return collection

        for action in json_object["actions"]:
            if "action" not in action:
                print(f"Action [{action}] has no action")
                continue
            if "args" not in action:
                print(f"Action [{action}] has no args")
                continue

            action_module_name = action["action"] + "_action"
            if action_module_name not in actions_module.__dict__:
                print(f"Action Module [{action_module_name}] is not defined")
                continue

            action_module = getattr(actions_module, action_module_name)
            action_class_name = ActionParser.__snake_to_pascal(action_module_name)
            if action_class_name not in action_module.__dict__:
                print(f"Action [{action_module_name}] has no action class")

            action_class = getattr(action_module, action_class_name)
            if not issubclass(action_class, StartWithAction):
                print(f"Action class [{action_module_name}] does not inherit from StartWithAction")
                continue

            collection.add_action(action_class(action["args"]))

        return collection