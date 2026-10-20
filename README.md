# StartWith

按配置依次执行一组操作（切换音频设备、启动程序、结束进程……），并支持在特定应用启动或退出时自动应用配置。

## 安装依赖

```commandline
pip install -r requirements.txt
```

`pywin32` 用于系统托盘与进程监听，`pillow` 用于生成托盘图标；两者在 Windows 上使用。
Tkinter 随 Python 自带，无需安装。

### 安装音频设备切换模块（可选）

如需切换音频设备，需安装此模块。在 PowerShell 中执行：

```commandline
Install-Module -Name AudioDeviceCmdlets
```

## 启动控制面板

双击 `gui.bat`，或执行：

```commandline
python start_with_gui.py
```

窗口关闭 / 最小化后会隐藏到右下角系统托盘，监听不会中断：

- **双击托盘图标**：重新打开控制面板
- **右键托盘图标**：快速应用配置、编辑配置、新建配置、暂停/恢复后台监听、绑定设置、版本管理、退出
- **底部运行日志**：显示配置应用、绑定触发和版本管理的执行输出，切换标签页不会消失，也可以点「收起」节省空间

## 配置文件

配置文件位于 `config/<名称>.json`，格式示例：

```json
{
    "actions": [
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

在「配置文件」页可以：

- **新建配置**：填写名称后，用图形界面添加操作（运行程序、切换音频设备、结束进程、应用其他配置、等待、雷神加速）
- **修改配置**：双击配置或点击「编辑」，可调整操作参数与执行顺序
- **应用配置**：选中后点击「▶ 应用配置」，等同于执行 `python apply_config.py -c <名称>`

每个操作都可以勾选「仅在上一个操作成功时运行」，用于控制失败后的跳过行为。

原有的命令行用法保持不变：

```commandline
python apply_config.py -c game
```

### 先启动加速器，再启动游戏

如果某个游戏需要先打开加速器完成加速、再启动游戏，把步骤按顺序写进同一个配置即可：

```json
{
    "actions": [
        {
            "action": "apply_config",
            "args": "game"
        },
        {
            "action": "run_app",
            "args": "D:\\Program Files (x86)\\Netease\\UU\\uu_launcher.exe"
        },
        {
            "action": "wait_process",
            "args": "uu.exe|120"
        },
        {
            "action": "wait",
            "args": "15"
        },
        {
            "action": "run_app",
            "args": "E:\\SteamLibrary\\steamapps\\common\\...\\game.exe"
        }
    ]
}
```

- `wait_process`：等待加速器进程出现，参数可写 `进程名|超时秒数`（默认 120 秒），进程名以实际为准，可在操作编辑器中刷新选择
- `wait`：再等待固定秒数，给加速器留出真正完成加速的时间；如果加速器需要手动点「加速」，就填够点击所需的秒数
- 最后一个 `run_app`：加速完成后再启动游戏

通过托盘「应用配置」或 `python apply_config.py -c <名称>` 应用这个配置即可。注意应用绑定是在程序启动**之后**才触发，无法提前打开加速器。

## 应用绑定

在「应用绑定」页新增绑定，支持两种方式：

- **单个应用**：选择某个 exe（或直接填写进程名，如 `game.exe`）
- **文件夹（批量）**：选择一个文件夹（可包含子文件夹），文件夹内任意 exe 都适用

每条绑定可以分别设置：

- **启动时应用**：程序启动时应用该配置（必填）
- **退出后应用**：程序退出后应用该配置（可选，例如退出游戏后切回 `desktop`）

规则说明：

- 监听间隔默认 2 秒，只对绑定生效之后**新启动**的进程生效
- 退出配置会在匹配进程全部退出后等待约 3 秒再应用，给游戏重启/启动器拉起主程序留出时间
- 优先级类似 `.gitignore` 的覆盖关系：**单个应用 > 子文件夹 > 上级文件夹**；同级时后添加的规则生效
- 单个应用规则只对该 exe 生效；如果需要覆盖整个游戏目录（包括其子进程），建议绑定游戏自己的子文件夹
- 同一条绑定的启动配置在 10 秒内只触发一次，避免同一程序启动多个子进程时重复应用
- 绑定可随时启用/停用、编辑或删除；配置缺失时会在列表中标记 ⚠ 并跳过
- 后台监听可整体暂停，暂停后不再触发任何绑定

绑定数据保存在 `data/bindings.json`，设置保存在 `data/settings.json`。

### 先加速再启动（参数化配置）

加速器只是一个普通操作（`leigod_acc`），放在配置的动作列表里；不同应用只需要在绑定里提供不同的参数，不用复制配置。

示例配置 `config/game_launch.json`：

```json
{
    "actions": [
        { "action": "apply_config", "args": "game" },
        { "action": "leigod_acc", "args": "{acc_game}" },
        { "action": "run_app", "args": "{launch_path}" }
    ]
}
```

在「应用绑定」页编辑绑定：

- **启动配置**：选择 `game_launch`
- **启动参数**：每行一个 `key=value`
  ```text
  acc_game=Big Walk
  launch_path=steam://rungameid/123456
  ```
- 点击「▶ 启动」或托盘菜单「启动绑定」，会按配置顺序执行：
  1. 应用 `game` 配置（切换耳机等）
  2. `leigod_acc` 启动雷神、打开「我的加速」中的 `Big Walk` 并等待出现「加速中」
  3. `run_app` 启动 `launch_path`

说明：

- 配置里用 `{key}` 引用绑定参数；`apply_config` 嵌套调用会把参数继续传给子配置
- `leigod_acc` 的参数就是游戏名称，可写成 `{acc_game}`，也支持 `名称|超时秒数`（默认 120 秒）
- 游戏需要先加入雷神的「我的加速」列表（在雷神中打开一次即可）
- `leigod_acc` 需要管理员权限，应用配置时会弹出 UAC 授权；以管理员身份运行 `gui.bat` 可避免重复提示
- 雷神界面改版后自动化可能失效，届时只需调整 `common/leigod_driver.py` 中的控件名称

## 配置版本管理（Git）

「版本管理」页提供常用的 Git 配置管理功能，使用前请确保已安装 Git 并加入 PATH，
且仓库已配置好远程地址与推送凭据。

- **上传配置**：填写提交说明后，将 `config/` 目录的改动提交并推送到远程分支
- **配置历史**：查看所有修改过 `config/` 的提交（版本、时间、作者、说明）
- **回退到选中版本**：把 `config/` 恢复为该提交的内容；之后新增的**已提交**配置会被删除，
  未提交的新文件会保留；回退结果会自动提交并推送
- **拉取最新**：`git pull --ff-only`，同步远程内容（会同时更新代码与配置）
- **撤销未提交修改**：丢弃 `config/` 下已跟踪文件的本地修改

绑定、设置与日志保存在 `data/` 目录，属于本机运行数据，不参与 Git 上传。
回退前建议先上传当前配置，这样误操作之后仍可从历史中找回。

## 开机自启

在「应用绑定」页勾选「开机自启」，会写入当前用户的注册表启动项
（`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`），开机后以静默模式常驻托盘。

## 关于管理员权限

包含 `kill_task`、`run_app` 等操作的配置需要管理员权限。应用配置时会弹出 UAC 授权提示；
如果希望避免重复提示，可以右键 `gui.bat` 选择「以管理员身份运行」。

应用配置时，命令行子进程（PowerShell、taskkill、cmd 等）都会在隐藏窗口中运行，
不会弹出 cmd 控制台；只有确实需要提权时才会出现 UAC 授权窗口。

## 目录说明

```
config/     配置文件（<名称>.json）
data/       绑定、设置与运行日志
gui/        控制面板界面
actions/    可用的操作实现
common/     配置/绑定/进程监听等基础模块
start_with_gui.py   GUI 启动入口
apply_config.py     命令行应用配置入口
```
