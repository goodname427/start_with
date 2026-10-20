import importlib
import json
import re

from actions.action import StartWithAction
from common.command_utils import CommandUtils

actions_module = importlib.import_module("actions")

ACTION_MODULE_NAME_SUBFIX = "_action"
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_.-]+)\}")


def substitute_variables(value, variables: dict[str, str] | None):
    """把字符串中的 {key} 替换为绑定提供的参数，未提供的占位符保持原样。"""
    if not variables or not isinstance(value, str):
        return value

    def replace(match):
        key = match.group(1)
        return variables.get(key, match.group(0))

    return PLACEHOLDER_PATTERN.sub(replace, value)


class StartWithActionCollection:
    @staticmethod
    def __snake_to_pascal(s):
        # 分割字符串并处理每个单词
        words = s.split('_')
        # 每个单词首字母大写，然后拼接
        return ''.join(word.capitalize() for word in words)

    @staticmethod
    def parse(text: str, variables: dict[str, str] | None = None):
        collection = StartWithActionCollection()
        collection.variables = dict(variables or {})

        try:
            json_object = json.loads(text)
        except json.decoder.JSONDecodeError:
            print("Config is not valid JSON")
            return collection

        if "actions" not in json_object:
            print("Config No actions found")
            return collection

        for action_desc in json_object["actions"]:
            if "action" not in action_desc:
                print(f"Action [{action_desc}] has no action")
                continue
            if "args" not in action_desc:
                print(f"Action [{action_desc}] has no args")
                continue

            action_module_name = action_desc["action"] + ACTION_MODULE_NAME_SUBFIX
            if action_module_name not in actions_module.__dict__:
                print(f"Action Module [{action_module_name}] is not defined")
                continue

            action_module = getattr(actions_module, action_module_name)
            action_class_name = StartWithActionCollection.__snake_to_pascal(action_module_name)
            if action_class_name not in action_module.__dict__:
                print(f"Action [{action_module_name}] has no action class")
                continue

            action_class = getattr(action_module, action_class_name)
            if not issubclass(action_class, StartWithAction):
                print(f"Action class [{action_module_name}] does not inherit from StartWithAction")
                continue

            action_args = substitute_variables(action_desc["args"], variables)
            if isinstance(action_args, str) and PLACEHOLDER_PATTERN.search(action_args):
                print(f"Warning: 参数 [{action_args}] 含未提供的占位符，请通过 --var 或绑定参数传入")
            action = action_class(action_args)
            action.variables = dict(variables or {})

            if "run_while_prev_action_success" in action_desc:
                action.run_while_prev_action_success = action_desc["run_while_prev_action_success"]

            collection.add_action(action)

        return collection

    def __init__(self):
        self.actions = []
        self.should_run_as_admin = False

    def add_action(self, action):
        self.actions.append(action)
        self.should_run_as_admin = self.should_run_as_admin or action.should_run_as_admin()

    def run(self) -> bool:
        if self.should_run_as_admin:
            CommandUtils.require_admin()

        prev_action_success = True
        success = True
        for action in self.actions:
            if action.run_while_prev_action_success and not prev_action_success:
                prev_action_success = False
                continue

            prev_action_success = bool(action.run())
            if not prev_action_success:
                success = False

        return success