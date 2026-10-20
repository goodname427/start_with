"""操作类型元数据：供 GUI 动态生成编辑器。"""
import importlib
import inspect
import pkgutil
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    label: str
    args_label: str
    args_kind: str
    description: str
    order: int
    action_class: type


def get_action_definitions() -> list[ActionDefinition]:
    try:
        import actions as actions_pkg
        from actions.action import StartWithAction
    except Exception:
        return []

    definitions: list[ActionDefinition] = []
    prefix = actions_pkg.__name__ + "."

    for module_info in pkgutil.iter_modules(actions_pkg.__path__):
        if module_info.name in {"action", "__init__"}:
            continue
        try:
            module = importlib.import_module(prefix + module_info.name)
        except Exception:
            continue

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is StartWithAction or not issubclass(cls, StartWithAction):
                continue
            if cls.__module__ != module.__name__:
                continue

            module_name = module_info.name
            action_name = module_name[: -len("_action")] if module_name.endswith("_action") else module_name
            definitions.append(
                ActionDefinition(
                    name=action_name,
                    label=getattr(cls, "label", action_name),
                    args_label=getattr(cls, "args_label", "参数"),
                    args_kind=getattr(cls, "args_kind", "text"),
                    description=getattr(cls, "description", ""),
                    order=int(getattr(cls, "order", 100)),
                    action_class=cls,
                )
            )
            break

    definitions.sort(key=lambda d: (d.order, d.name))
    return definitions


def get_definition_map() -> dict[str, ActionDefinition]:
    return {d.name: d for d in get_action_definitions()}
