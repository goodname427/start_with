import re
from typing import override

from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class SwitchAudioDeviceAction(StartWithAction):
    label = "切换音频设备"
    args_label = "音频设备名称"
    args_kind = "audio_device"
    description = "将 Windows 默认音频播放设备切换到指定设备。"
    order = 20

    @staticmethod
    def get_all_audio_devices() -> list[dict]:
        """
        Get all audio devices.
        :return: A list of dictionaries, each dictionary contains the device information.
        """
        list_command = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-AudioDevice -List"
        )
        result = CommandUtils.execute_command(
            "powershell.exe", ["-Command", list_command], encoding="utf-8"
        )
        if result.returncode != CMD_RETURN_CODE_SUCCESS:
            print(f"Get-AudioDevice failed: {(result.stderr or result.stdout).strip()}")
            return []

        # Get-AudioDevice 返回的是由空行分隔的多个设备块，每块的字段数量可能变化
        text = (result.stdout or "").replace("\r\n", "\n")
        blocks = re.split(r"\n\s*\n", text.strip())

        pattern = r"^\s*([A-Za-z][A-Za-z ]*?)\s*:\s*(.*?)\s*$"
        devices: list[dict] = []
        for block in blocks:
            device: dict[str, str] = {}
            for line in block.splitlines():
                match_result = re.match(pattern, line)
                if match_result:
                    device[match_result.group(1).strip()] = match_result.group(2).strip()

            # 至少要有名称和 ID 才是有效设备
            if device.get("Name") and device.get("ID"):
                devices.append(device)

        return devices

    @staticmethod
    def switch_audio_device(device_name) -> bool:
        """
        Switch audio device to the specified device name.
        :param device_name: The name of the audio device to switch to.
        :return: True if the switch is successful, False otherwise.
        """
        target = str(device_name).strip()
        devices = SwitchAudioDeviceAction.get_all_audio_devices()

        matched = [d for d in devices if d.get("Name", "").strip() == target]
        if not matched:
            matched = [d for d in devices if d.get("Name", "").strip().lower() == target.lower()]

        if not matched:
            available = ", ".join(d.get("Name", "") for d in devices) or "（无）"
            print(f"Audio device [{device_name}] not found. Available: {available}")
            return False

        device_id = matched[0].get("ID", "").strip()
        if not device_id:
            print(f"Audio device [{device_name}] has no ID")
            return False

        set_command = f"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Set-AudioDevice -ID '{device_id}'"
        result = CommandUtils.execute_command(
            "powershell.exe", ["-Command", set_command], encoding="utf-8"
        )
        if result.returncode != CMD_RETURN_CODE_SUCCESS:
            print(f"Set-AudioDevice failed: {(result.stderr or result.stdout).strip()}")
            return False

        return True

    @override
    def run(self) -> bool:
        if not self._check_args_is_type(str):
            return False

        if SwitchAudioDeviceAction.switch_audio_device(self.args):
            print(f"Switch audio device to {self.args} success")
            return True
        else:
            print(f"Switch audio device to {self.args} failed")
            return False
