from typing import override

from actions.action import StartWithAction


class SwitchAudioDeviceAction(StartWithAction):
    @override
    def run(self)->bool:
        if not self.args:
            return False

        print(f"Switching audio device to: {self.args}")

        return True