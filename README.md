# Requirements Installation
## 安装必要的Python依赖库
通过pip安装依赖库。在终端执行该命令：
```commandline
pip install -r requirements.txt
```

## 安装音频设备切换模块（可选）
如需切换音频设备，需安装此模块。

通过PowerShellGet安装此模块。在PowerShell中执行如下命令：
```commandline
Install-Module -Name AudioDeviceCmdlets
```

# Quick Start
1. 创建配置，在configs目录下创建一个新的配置文件，例如：
```json
{
    "actions":
    [
        {
            "action": "run_app",
            "args": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
        },
        {
            "action": "switch_audio_device",
            "args": "CABLE Input (VB-Audio Virtual Cable)"
        }
    ]
}
```