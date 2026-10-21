"""游戏启动项编辑对话框：先应用配置，再启动程序。"""
import os
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk

from common.launch_store import LaunchItem
from gui import theme

sp = theme.sp
CLOSE_NONE_LABEL = "（不应用）"


class LaunchEditorDialog(tk.Toplevel):
    def __init__(self, master, launch: LaunchItem | None, config_names: list[str], on_saved):
        super().__init__(master)
        self.launch = launch
        self.config_names = list(config_names)
        for name in (launch.config if launch else "", launch.close_config if launch else ""):
            if name and name not in self.config_names:
                self.config_names.append(name)
        self.on_saved = on_saved
        self._closed = False

        self.title("编辑启动项" if launch else "新增启动项")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Destroy>", self._on_destroy)

        self.name_var = tk.StringVar(master=self, value=launch.name if launch else "")
        self.path_var = tk.StringVar(master=self, value=launch.target if launch else "")
        self.config_var = tk.StringVar(
            master=self,
            value=launch.config if launch else (self.config_names[0] if self.config_names else ""),
        )
        self.close_config_var = tk.StringVar(
            master=self,
            value=launch.close_config if launch and launch.close_config else CLOSE_NONE_LABEL,
        )

        self._build()
        theme.center_window(self, master, 640, 470)
        self.grab_set()

    def _build(self) -> None:
        theme.dialog_header(
            self,
            "游戏启动",
            "先应用启动配置，再启动程序；程序退出后应用退出配置",
        ).pack(fill="x")

        body = theme.make_card(self)
        body.pack(fill="both", expand=True, padx=sp(16), pady=sp(14))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="名称", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=0, column=0, sticky="w", padx=sp((16, 10)), pady=sp((16, 8))
        )
        ttk.Entry(body, textvariable=self.name_var).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp((16, 8))
        )

        tk.Label(body, text="程序路径", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=1, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8)
        )
        ttk.Entry(body, textvariable=self.path_var).grid(row=1, column=1, sticky="ew", pady=sp(8))
        ttk.Button(body, text="浏览…", style="Ghost.TButton", command=self._browse).grid(
            row=1, column=2, sticky="e", padx=sp((8, 16)), pady=sp(8)
        )

        tk.Label(body, text="启动前配置", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=2, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8)
        )
        ttk.Combobox(
            body,
            textvariable=self.config_var,
            values=self.config_names,
            state="readonly" if self.config_names else "disabled",
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp(8))

        tk.Label(body, text="退出后应用", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=3, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8)
        )
        ttk.Combobox(
            body,
            textvariable=self.close_config_var,
            values=[CLOSE_NONE_LABEL, *self.config_names],
            state="readonly",
        ).grid(row=3, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp(8))

        tk.Label(
            body,
            text="例如启动前应用 game_acc，退出后应用 desktop_acc；动作会自动读取启动程序的 exe 信息。",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            justify="left",
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, sp(10)))

        self.info_var = tk.StringVar(master=self, value="")
        tk.Label(
            body,
            textvariable=self.info_var,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=sp(520),
        ).grid(row=5, column=0, columnspan=3, sticky="ew", padx=sp(16), pady=sp((4, 14)))

        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(fill="x", padx=sp(16), pady=sp((0, 14)))
        theme.accent_button(footer, "保存启动项", self._save, width=11).pack(side="right")
        theme.ghost_button(footer, "取消", self._close, width=8).pack(side="right", padx=sp((0, 8)))

        self.path_var.trace_add("write", lambda *_args: self._update_info())
        self._update_info()

    def _update_info(self) -> None:
        target = self.path_var.get().strip()
        if target and os.path.exists(target):
            self.info_var.set(f"启动程序：{os.path.basename(target)}")
        elif target:
            self.info_var.set("路径不存在，仍可保存，但启动会失败。")
        else:
            self.info_var.set("请选择要启动的游戏程序。")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="选择游戏程序",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )
        if path:
            self.path_var.set(os.path.normpath(path))
            if not self.name_var.get().strip():
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])

    def _save(self) -> None:
        target = self.path_var.get().strip()
        config = self.config_var.get().strip()
        close_config = self.close_config_var.get().strip()
        if close_config == CLOSE_NONE_LABEL:
            close_config = ""

        if not target:
            messagebox.showwarning("缺少路径", "请选择要启动的程序。", parent=self)
            return
        if not target.lower().endswith(".exe"):
            messagebox.showwarning(
                "不支持的程序类型",
                "游戏启动项目前只支持 .exe；批处理或启动器请改为对应的主程序 exe。",
                parent=self,
            )
            return
        if not os.path.exists(target):
            if not messagebox.askyesno(
                "路径不存在",
                f"路径不存在：\n{target}\n\n仍要保存这个启动项吗？",
                parent=self,
            ):
                return
        if not config:
            messagebox.showwarning("缺少配置", "请选择启动前要应用的配置。", parent=self)
            return
        if config not in self.config_names:
            messagebox.showerror("配置不存在", f"启动配置 [{config}] 不在配置列表中。", parent=self)
            return
        if close_config and close_config not in self.config_names:
            messagebox.showerror("配置不存在", f"退出配置 [{close_config}] 不在配置列表中。", parent=self)
            return

        name = self.name_var.get().strip() or os.path.splitext(os.path.basename(target))[0]
        launch = LaunchItem(
            id=self.launch.id if self.launch else uuid.uuid4().hex,
            name=name,
            target=target,
            config=config,
            close_config=close_config,
            enabled=self.launch.enabled if self.launch else True,
        )

        callback = self.on_saved
        self._close()
        if callback:
            callback(launch)

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
