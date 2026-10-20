"""单个操作的编辑对话框。"""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from common.action_meta import ActionDefinition, get_action_definitions
from common.process_monitor import list_process_names
from gui import theme

sp = theme.sp


class ActionEditorDialog(tk.Toplevel):
    def __init__(self, master, action: dict | None, config_names: list[str], on_saved):
        super().__init__(master)
        self.on_saved = on_saved
        self.config_names = list(config_names)
        self.definitions = get_action_definitions()
        self.display_map: dict[str, ActionDefinition] = {
            self._display(d): d for d in self.definitions
        }
        self.current_def: ActionDefinition | None = None
        self._closed = False
        self._load_token = 0
        self._audio_queue: queue.Queue | None = None

        self.title("编辑操作" if action else "添加操作")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Destroy>", self._on_destroy)

        self._build()
        self._init_values(action)
        theme.center_window(self, master, 560, 340)
        self.grab_set()
        self.combo_args.focus_set()

    # ------------------------------------------------------------------ 构建界面

    def _build(self) -> None:
        theme.dialog_header(self, "操作设置", "选择操作类型并填写参数").pack(fill="x")

        body = theme.make_card(self)
        body.pack(fill="both", expand=True, padx=sp(16), pady=sp(14))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="操作类型", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=0, column=0, sticky="w", padx=sp((14, 10)), pady=sp((16, 8))
        )
        self.combo_type = ttk.Combobox(body, state="readonly", values=list(self.display_map.keys()))
        self.combo_type.grid(row=0, column=1, columnspan=2, sticky="ew", padx=sp((0, 14)), pady=sp((16, 8)))
        self.combo_type.bind("<<ComboboxSelected>>", self._on_type_selected)

        self.args_label = tk.Label(body, text="参数", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI)
        self.args_label.grid(row=1, column=0, sticky="w", padx=sp((14, 10)), pady=sp(8))
        self.combo_args = ttk.Combobox(body)
        self.combo_args.grid(row=1, column=1, sticky="ew", pady=sp(8), padx=sp((0, 0)))
        self.btn_aux = ttk.Button(body, text="浏览…", style="Ghost.TButton", command=self._browse_file)
        self.btn_aux.grid(row=1, column=2, sticky="e", padx=sp((8, 14)), pady=sp(8))

        self.hint_label = tk.Label(
            body,
            text="",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=sp(470),
        )
        self.hint_label.grid(row=2, column=0, columnspan=3, sticky="ew", padx=sp(14), pady=sp((0, 6)))

        self.condition_var = tk.BooleanVar(master=self, value=False)
        self.chk_condition = ttk.Checkbutton(
            body,
            text="仅在上一个操作成功时运行",
            variable=self.condition_var,
            style="Card.TCheckbutton",
        )
        self.chk_condition.grid(row=3, column=0, columnspan=3, sticky="w", padx=sp(14), pady=sp((2, 8)))

        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(fill="x", padx=sp(16), pady=sp((0, 14)))
        theme.accent_button(footer, "确定", self._save, width=10).pack(side="right")
        theme.ghost_button(footer, "取消", self._close, width=8).pack(side="right", padx=sp((0, 8)))

    def _init_values(self, action: dict | None) -> None:
        if not self.definitions:
            self.hint_label.configure(text="未能加载操作类型，请检查 actions 目录。", fg=theme.DANGER)
            self.combo_type.configure(state="disabled")
            self.combo_args.configure(state="disabled")
            return

        if action:
            name = str(action.get("action", ""))
            target = next((d for d in self.definitions if d.name == name), None)
            if target is not None:
                self.combo_type.set(self._display(target))
            else:
                self.combo_type.current(0)
            self.combo_args.set(str(action.get("args", "")))
            self.condition_var.set(bool(action.get("run_while_prev_action_success", False)))
        else:
            self.combo_type.current(0)

        self._on_type_changed()

    @staticmethod
    def _display(definition: ActionDefinition) -> str:
        return f"{definition.label}（{definition.name}）"

    # ------------------------------------------------------------------ 交互

    def _on_type_selected(self, _event=None) -> None:
        self.combo_args.set("")
        self._on_type_changed()

    def _on_type_changed(self, _event=None) -> None:
        definition = self.display_map.get(self.combo_type.get())
        if definition is None:
            return
        self.current_def = definition
        self.args_label.configure(text=f"参数 · {definition.args_label}")
        self.hint_label.configure(text=definition.description or "", fg=theme.MUTED)
        self._configure_args_widget(definition)

    def _configure_args_widget(self, definition: ActionDefinition) -> None:
        self._load_token += 1
        token = self._load_token
        kind = definition.args_kind

        self.btn_aux.grid()
        if kind == "file":
            self.combo_args.configure(values=[])
            self.btn_aux.configure(text="浏览…", command=self._browse_file, state="normal")
        elif kind == "config":
            self.combo_args.configure(values=self.config_names)
            self.btn_aux.grid_remove()
        elif kind == "process":
            self.combo_args.configure(values=self._safe_process_names())
            self.btn_aux.configure(text="刷新", command=self._refresh_processes, state="normal")
        elif kind == "audio_device":
            self.combo_args.configure(values=[])
            self.btn_aux.configure(text="刷新", command=self._refresh_audio_devices, state="normal")
            self._load_audio_devices(token)
        else:
            self.combo_args.configure(values=[])
            self.btn_aux.grid_remove()

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="选择要运行的程序或文件",
            filetypes=[
                ("可执行文件与快捷方式", ("*.exe", "*.bat", "*.cmd", "*.lnk", "*.ps1")),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.combo_args.set(path)

    @staticmethod
    def _safe_process_names() -> list[str]:
        try:
            return list_process_names()
        except Exception:
            return []

    def _refresh_processes(self) -> None:
        self.combo_args.configure(values=self._safe_process_names())

    def _refresh_audio_devices(self) -> None:
        self._load_token += 1
        self._load_audio_devices(self._load_token)

    def _load_audio_devices(self, token: int) -> None:
        self._audio_queue = queue.Queue()
        audio_queue = self._audio_queue

        def work() -> None:
            names: list[str] = []
            try:
                from actions.switch_audio_device_action import SwitchAudioDeviceAction

                devices = SwitchAudioDeviceAction.get_all_audio_devices()
                names = sorted({str(d.get("Name")) for d in devices if d.get("Name")}, key=str.lower)
            except Exception:
                names = []
            audio_queue.put(names)

        threading.Thread(target=work, daemon=True).start()
        self.after(120, lambda: self._poll_audio(token))

    def _poll_audio(self, token: int) -> None:
        try:
            if self._closed or not self.winfo_exists():
                return
        except tk.TclError:
            return

        if token != self._load_token or self._audio_queue is None:
            return
        try:
            names = self._audio_queue.get_nowait()
        except queue.Empty:
            try:
                self.after(150, lambda: self._poll_audio(token))
            except tk.TclError:
                pass
            return

        if token != self._load_token:
            return
        self.combo_args.configure(values=names)
        if not names:
            self.hint_label.configure(
                text="未读取到音频设备，可直接手动输入设备名称（需安装 AudioDeviceCmdlets）。",
                fg=theme.WARN,
            )

    def _save(self) -> None:
        definition = self.current_def
        if definition is None:
            return

        args = self.combo_args.get().strip()
        if not args:
            messagebox.showwarning("参数不能为空", f"请填写「{definition.args_label}」。", parent=self)
            self.combo_args.focus_set()
            return

        action = {"action": definition.name, "args": args}
        if self.condition_var.get():
            action["run_while_prev_action_success"] = True

        callback = self.on_saved
        self._close()
        if callback:
            callback(action)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self._closed = True

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
