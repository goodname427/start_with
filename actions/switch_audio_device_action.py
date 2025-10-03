import re
from typing import override

from actions.action import StartWithAction


class SwitchAudioDeviceAction(StartWithAction):
    @staticmethod
    def __get_all_audio_devices() -> list[dict]:
        """
        Get all audio devices.
        :return: A list of dictionaries, each dictionary contains the device information.
        """
        result = StartWithAction._execute_cmd("powershell.exe", ["-Command", f"Get-AudioDevice -List"])
        if not result["success"] or result["output"] is None:
            return []

        lines = result["output"].splitlines()
        device_descriptions = []

        # 筛选出包含音频设备信息的行
        for i in range(len(lines)):
            line = lines[i]
            if i % 8 == 0:
                device_descriptions.append([])

            device_descriptions[-1].append(line)

        # 解析设备描述信息
        pattern = r'^\s*(\w+(?:\s+\w+)*)\s*:\s*(.+)$'
        devices = []
        for desc in device_descriptions:
            device = {}
            for line in desc:
                match_result = re.fullmatch(pattern, line, re.MULTILINE)
                if match_result:
                    device[match_result.group(1)] = match_result.group(2)

            devices.append(device)

        return devices

    @staticmethod
    def switch_audio_device(device_name) -> bool:
        """
        Switch audio device to the specified device name.
        :param device_name: The name of the audio device to switch to.
        :return: True if the switch is successful, False otherwise.
        """
        devices = SwitchAudioDeviceAction.__get_all_audio_devices()

        for device in devices:
            if device["Name"] == device_name:
                StartWithAction._execute_cmd("powershell.exe", ["-Command", f"Set-AudioDevice -ID '{device['ID']}'"])
                print(f"Switch audio device to {device_name} successfully.")
                return True

        print(f"Audio device {device_name} not found.")
        return False

    @override
    def run(self) -> bool:
        if not self._check_args_is_type(str):
            return False

        return SwitchAudioDeviceAction.switch_audio_device(self.args)
