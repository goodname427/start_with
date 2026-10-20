import sys
from pathlib import Path
from typing import override

from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS

APPLY_SCRIPT = Path(__file__).resolve().parent.parent / "apply_config.py"


class ApplyConfigAction(StartWithAction):
    label = "应用配置"
    args_label = "配置名称"
    args_kind = "config"
    description = "依次应用另一个配置中的操作（支持嵌套）。"
    order = 40

    @override
    def run(self):
        if not self._check_args_is_type(str):
            return False

        config_file = APPLY_SCRIPT.parent / "config" / f"{self.args}.json"
        if not config_file.exists():
            print(f"配置不存在: {config_file}")
            return False

        result = CommandUtils.execute_command(sys.executable, [str(APPLY_SCRIPT), "--config", self.args])
        if result.returncode != CMD_RETURN_CODE_SUCCESS:
            output = (result.stdout or "") + (result.stderr or "")
            if output.strip():
                print(output.strip())

        if result.returncode == CMD_RETURN_CODE_SUCCESS:
            print(f"Apply config [{self.args}] success")
            return True
        else:
            print(f"Apply config [{self.args}] failed")
            return False
