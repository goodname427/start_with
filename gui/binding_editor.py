"""应用绑定编辑对话框：单个应用 / 文件夹批量绑定。"""
import os
import queue
import threading
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk

from common.binding_store import (
    BINDING_TYPE_APP,
    BINDING_TYPE_FOLDER,
    AppBinding,
    count_folder_executables,
)
from gui import theme

sp = theme.sp
CLOSE_NONE_LABEL = "（不应用）"


class BindingEditorDialog(tk.Toplevel):
    def __init__(self, master, binding: AppBinding | None, config_names: list[str], on_saved):
        super().__init__(master)
        self.binding = binding
        self.config_names = list(config_names)
        if binding and binding.close_config and binding.close_config not in self.config_names:
            self.config_names.append(binding.close_config)
        self.on_saved = on_saved
        self._closed = False
        self._scan_token = 0
        self._scan_queue: queue.Queue | None = None

        self.title("编辑绑定" if binding else "新增绑定")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Destroy>", self._on_destroy)

        self.type_var = tk.StringVar(master=self, value=binding.type if binding else BINDING_TYPE_APP)
        self.path_var = tk.StringVar(master=self, value=binding.target if binding else "")
        self.config_var = tk.StringVar(
            master=self,
            value=binding.config if binding else (self.config_names[0] if self.config_names else ""),
        )
        close_value = binding.close_config if binding and binding.close_config else CLOSE_NONE_LABEL
        self.close_config_var = tk.StringVar(master=self, value=close_value)
        self.ignore_content = "\n".join(binding.ignore if binding else [])
        self.recursive_var = tk.BooleanVar(master=self, value=binding.recursive if binding else True)
        self.info_var = tk.StringVar(master=self, value="")

        self._build()
        self._on_type_changed()
        theme.center_window(self, master, 660, 620)
        self.grab_set()
        self._schedule_scan()

    # ------------------------------------------------------------------ 构建界面

    def _build(self) -> None:
        theme.dialog_header(
            self,
            "应用绑定",
            "程序启动/退出时自动应用配置；动作会自动读取当前启动的 exe 信息",
        ).pack(fill="x")

        body = theme.make_card(self)
        body.pack(fill="both", expand=True, padx=sp(16), pady=sp(14))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="绑定方式", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=0, column=0, sticky="w", padx=sp((16, 10)), pady=sp((16, 6))
        )
        radios = tk.Frame(body, bg=theme.CARD)
        radios.grid(row=0, column=1, columnspan=2, sticky="w", pady=sp((16, 6)), padx=sp((0, 16)))
        ttk.Radiobutton(
            radios,
            text="单个应用",
            value=BINDING_TYPE_APP,
            variable=self.type_var,
            style="Card.TRadiobutton",
            command=self._on_type_changed,
        ).pack(side="left")
        ttk.Radiobutton(
            radios,
            text="文件夹（批量）",
            value=BINDING_TYPE_FOLDER,
            variable=self.type_var,
            style="Card.TRadiobutton",
            command=self._on_type_changed,
        ).pack(side="left", padx=sp((18, 0)))

        self.path_label = tk.Label(body, text="程序路径", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI)
        self.path_label.grid(row=1, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8))
        self.path_entry = ttk.Entry(body, textvariable=self.path_var)
        self.path_entry.grid(row=1, column=1, sticky="ew", pady=sp(8))
        self.path_entry.bind("<FocusOut>", lambda _event: self._schedule_scan())
        self.btn_browse = ttk.Button(body, text="浏览…", style="Ghost.TButton", command=self._browse)
        self.btn_browse.grid(row=1, column=2, sticky="e", padx=sp((8, 16)), pady=sp(8))

        tk.Label(body, text="启动时应用", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=2, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8)
        )
        self.config_combo = ttk.Combobox(
            body,
            textvariable=self.config_var,
            values=self.config_names,
            state="readonly" if self.config_names else "disabled",
        )
        self.config_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp(8))

        tk.Label(body, text="退出后应用", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=3, column=0, sticky="w", padx=sp((16, 10)), pady=sp(8)
        )
        self.close_config_combo = ttk.Combobox(
            body,
            textvariable=self.close_config_var,
            values=[CLOSE_NONE_LABEL, *self.config_names],
            state="readonly",
        )
        self.close_config_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp(8))
        tk.Label(
            body,
            text="可选。程序退出后应用此配置，例如退出游戏后停止加速并切回桌面配置。",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, sp(2)))

        self.ignore_label = tk.Label(
            body, text="忽略程序", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI
        )
        self.ignore_label.grid(row=5, column=0, sticky="nw", padx=sp((16, 10)), pady=sp(8))
        self.ignore_text = tk.Text(
            body,
            height=3,
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_MONO,
            relief="solid",
            bd=1,
            padx=sp(6),
            pady=sp(4),
        )
        self.ignore_text.grid(row=5, column=1, columnspan=2, sticky="ew", padx=sp((0, 16)), pady=sp(8))
        self.ignore_text.insert("1.0", self.ignore_content)
        self.ignore_hint = tk.Label(
            body,
            text="仅文件夹绑定使用。每行一个通配符，例如 UnityCrashHandler*.exe、*AntiCheat*.exe、vcredist*.exe。",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            justify="left",
        )
        self.ignore_hint.grid(row=6, column=1, columnspan=2, sticky="w", pady=(0, sp(2)))

        self.chk_recursive = ttk.Checkbutton(
            body,
            text="包含子文件夹",
            variable=self.recursive_var,
            style="Card.TCheckbutton",
            command=self._schedule_scan,
        )
        self.chk_recursive.grid(row=7, column=1, sticky="w", pady=sp((2, 6)))

        self.info_label = tk.Label(
            body,
            textvariable=self.info_var,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=sp(540),
        )
        self.info_label.grid(row=8, column=0, columnspan=3, sticky="ew", padx=sp(16), pady=sp((6, 14)))

        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(fill="x", padx=sp(16), pady=sp((0, 14)))
        theme.accent_button(footer, "保存绑定", self._save, width=10).pack(side="right")
        theme.ghost_button(footer, "取消", self._close, width=8).pack(side="right", padx=sp((0, 8)))

    # ------------------------------------------------------------------ 交互

    def _on_type_changed(self) -> None:
        is_folder = self.type_var.get() == BINDING_TYPE_FOLDER
        self.path_label.configure(text="文件夹路径" if is_folder else "程序路径")
        self.btn_browse.configure(text="选择文件夹…" if is_folder else "选择程序…")
        if is_folder:
            self.chk_recursive.grid()
            self.ignore_label.grid()
            self.ignore_text.grid()
            self.ignore_hint.grid()
        else:
            self.chk_recursive.grid_remove()
            self.ignore_label.grid_remove()
            self.ignore_text.grid_remove()
            self.ignore_hint.grid_remove()
        self._schedule_scan()

    def _browse(self) -> None:
        if self.type_var.get() == BINDING_TYPE_FOLDER:
            path = filedialog.askdirectory(parent=self, title="选择要批量绑定的文件夹")
        else:
            path = filedialog.askopenfilename(
                parent=self,
                title="选择要绑定的程序",
                filetypes=[("可执行文件", ("*.exe", "*.bat", "*.cmd")), ("所有文件", "*.*")],
            )
        if path:
            self.path_var.set(os.path.normpath(path))
            self._schedule_scan()

    def _schedule_scan(self) -> None:
        target = self.path_var.get().strip()
        self._scan_token += 1
        token = self._scan_token

        if self.type_var.get() == BINDING_TYPE_APP:
            if target and os.path.exists(target):
                self.info_var.set(
                    f"目标程序：{os.path.basename(target)}。启动时应用「启动时应用」配置，退出后应用「退出后应用」配置。"
                )
            else:
                self.info_var.set("请选择要绑定的程序；也可直接填写进程名（如 game.exe）。")
            return

        if not target:
            self.info_var.set("请选择文件夹，文件夹中的所有程序都会批量应用此配置。")
            return
        if not os.path.isdir(target):
            self.info_var.set("文件夹不存在，请重新选择。")
            return

        self.info_var.set("正在扫描该文件夹中的可执行文件…")
        scan_queue: queue.Queue = queue.Queue()
        self._scan_queue = scan_queue
        recursive = self.recursive_var.get()

        def work() -> None:
            scan_queue.put(count_folder_executables(target, recursive))

        threading.Thread(target=work, daemon=True).start()
        self.after(120, lambda: self._poll_scan(token, target, recursive))

    def _poll_scan(self, token: int, target: str, recursive: bool) -> None:
        try:
            if self._closed or not self.winfo_exists():
                return
        except tk.TclError:
            return

        if token != self._scan_token or self._scan_queue is None:
            return
        try:
            count = self._scan_queue.get_nowait()
        except queue.Empty:
            try:
                self.after(150, lambda: self._poll_scan(token, target, recursive))
            except tk.TclError:
                pass
            return

        if token != self._scan_token:
            return
        scope = "（含子文件夹）" if recursive else "（不含子文件夹）"
        if count:
            self.info_var.set(
                f"该文件夹下检测到 {count} 个可执行文件{scope}；启动任意一个时会应用启动配置，退出后应用退出配置。"
            )
        else:
            self.info_var.set(f"该文件夹下暂未检测到 .exe{scope}，仍可保存绑定。")

    # ------------------------------------------------------------------ 保存

    def _save(self) -> None:
        btype = self.type_var.get()
        target = self.path_var.get().strip()
        config = self.config_var.get().strip()
        close_config = self.close_config_var.get().strip()
        if close_config == CLOSE_NONE_LABEL:
            close_config = ""
        ignore: list[str] = []
        if btype == BINDING_TYPE_FOLDER:
            for line in self.ignore_text.get("1.0", "end").replace(",", "\n").splitlines():
                pattern = line.strip()
                if pattern and pattern not in ignore:
                    ignore.append(pattern)

        if not target:
            messagebox.showwarning("缺少路径", "请填写或选择要绑定的程序/文件夹。", parent=self)
            return
        if btype == BINDING_TYPE_FOLDER and not os.path.isdir(target):
            messagebox.showerror("路径无效", "请选择一个有效的文件夹。", parent=self)
            return
        if btype == BINDING_TYPE_APP and not os.path.exists(target):
            if not messagebox.askyesno(
                "路径不存在",
                f"路径不存在：\n{target}\n\n仍要保存这个绑定吗？",
                parent=self,
            ):
                return
        if not config:
            messagebox.showwarning("缺少配置", "请选择要应用的配置。", parent=self)
            return
        if config not in self.config_names:
            messagebox.showerror("配置不存在", f"配置 [{config}] 不在配置列表中，请重新选择。", parent=self)
            return
        if close_config and close_config not in self.config_names:
            messagebox.showerror("配置不存在", f"退出配置 [{close_config}] 不在配置列表中，请重新选择。", parent=self)
            return

        binding = AppBinding(
            id=self.binding.id if self.binding else uuid.uuid4().hex,
            type=btype,
            target=target,
            config=config,
            close_config=close_config,
            enabled=self.binding.enabled if self.binding else True,
            recursive=bool(self.recursive_var.get()),
            ignore=ignore,
        )

        callback = self.on_saved
        self._close()
        if callback:
            callback(binding)

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
