"""StartWith 控制面板主界面。"""
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from common import autostart, binding_store, config_store, settings_store
from common.action_meta import get_definition_map
from common.binding_store import AppBinding
from common.binding_watcher import BindingWatcher
from common.paths import ACC_LOG_FILE, APP_ROOT, APPLY_SCRIPT, CONFIG_DIR
from common.process_meta import build_context
from gui import theme
from gui.binding_editor import BindingEditorDialog
from gui.config_editor import ConfigEditorDialog
from gui.version_panel import VersionPanel

sp = theme.sp

logger = logging.getLogger(__name__)


class StartWithApp:
    def __init__(self, root: tk.Tk, silent: bool = False):
        self.root = root
        self.silent = silent
        self.settings = settings_store.load_settings()
        self.configs: list[config_store.ConfigInfo] = []
        self.bindings: list[AppBinding] = []
        self.definition_map = get_definition_map()

        self._queue: queue.Queue = queue.Queue()
        self._watcher: BindingWatcher | None = None
        self._tray = None
        self._hidden = False
        self._closing = False
        self._tray_tip_shown = False

        theme.setup_theme(root)
        self._configure_window()
        self._build_header()
        self._build_status_bar()
        self._build_body()

        self._refresh_configs()
        self._refresh_bindings()
        self._setup_tray()
        self._update_monitor_ui()
        self._poll_queue()

        self._log("控制台已启动。", "info")
        if silent:
            self.root.after(250, lambda: self.hide_to_tray(show_tip=False))

    # ------------------------------------------------------------------ 窗口

    def _configure_window(self) -> None:
        self.root.title("StartWith 控制台")
        self.root.geometry(f"{sp(theme.BASE_WINDOW_WIDTH)}x{sp(theme.BASE_WINDOW_HEIGHT)}")
        self.root.minsize(sp(920), sp(600))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.report_callback_exception = self._report_callback_exception
        try:
            from gui.tray import ensure_tray_icon

            icon = ensure_tray_icon()
            if icon:
                self.root.iconbitmap(icon)
        except Exception:
            pass

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=theme.HEADER_BG, height=sp(76))
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=theme.HEADER_BG)
        left.pack(side="left", padx=sp(24), pady=sp(13))
        tk.Label(
            left,
            text="StartWith",
            bg=theme.HEADER_BG,
            fg="#ffffff",
            font=theme.FONT_TITLE,
        ).pack(anchor="w")
        tk.Label(
            left,
            text="配置管理 · 应用绑定 · 托盘快捷操作",
            bg=theme.HEADER_BG,
            fg=theme.HEADER_MUTED,
            font=theme.FONT_SMALL,
        ).pack(anchor="w")

        self.monitor_pill = tk.Label(
            header,
            text="",
            bg="#1e293b",
            fg="#34d399",
            font=theme.FONT_SMALL,
            padx=sp(12),
            pady=sp(6),
            cursor="hand2",
        )
        self.monitor_pill.pack(side="right", padx=sp(24))
        self.monitor_pill.bind("<Button-1>", lambda _event: self._toggle_monitor())

        tk.Frame(self.root, bg=theme.ACCENT, height=sp(2)).pack(fill="x")

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self.root, bg=theme.CARD)
        bar.pack(side="bottom", fill="x")
        inner = tk.Frame(bar, bg=theme.CARD)
        inner.pack(fill="x", padx=sp(16), pady=sp(6))
        self.status_label = tk.Label(inner, text="就绪", bg=theme.CARD, fg=theme.MUTED, font=theme.FONT_SMALL)
        self.status_label.pack(side="left")
        self.monitor_label = tk.Label(inner, text="", bg=theme.CARD, fg=theme.MUTED, font=theme.FONT_SMALL)
        self.monitor_label.pack(side="right")
        tk.Frame(self.root, bg=theme.BORDER, height=1).pack(side="bottom", fill="x")

    def _build_body(self) -> None:
        self._build_log_panel()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=sp(14), pady=sp((12, 8)))

        self.configs_page = tk.Frame(self.notebook, bg=theme.BG)
        self.bindings_page = tk.Frame(self.notebook, bg=theme.BG)
        self.notebook.add(self.configs_page, text="  配置文件  ")
        self.notebook.add(self.bindings_page, text="  应用绑定  ")

        self._build_configs_page()
        self._build_bindings_page()

        self.version_panel = VersionPanel(
            self.notebook,
            on_log=self._log,
            on_status=self._set_status,
            on_configs_changed=self._on_git_configs_changed,
        )
        self.notebook.add(self.version_panel, text="  版本管理  ")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_log_panel(self) -> None:
        card = theme.make_card(self.root)
        card.pack(side="bottom", fill="x", padx=sp(14), pady=sp((0, 8)))

        head = tk.Frame(card, bg=theme.CARD)
        head.pack(fill="x", padx=sp(14), pady=(sp(8), sp(4)))
        tk.Label(head, text="运行日志", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(
            side="left"
        )
        tk.Label(
            head,
            text="配置应用、绑定触发与版本管理的执行输出",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left", padx=sp(10))
        theme.ghost_button(head, "清空", self._clear_log).pack(side="right")
        self.btn_toggle_log = theme.ghost_button(head, "收起", self._toggle_log)
        self.btn_toggle_log.pack(side="right", padx=sp((0, 8)))

        self.log_body = tk.Frame(card, bg=theme.CARD)
        self.log_body.pack(fill="both", expand=True, padx=sp(14), pady=(0, sp(10)))
        self.log_body.rowconfigure(0, weight=1)
        self.log_body.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            self.log_body,
            height=6,
            bg=theme.LOG_BG,
            fg=theme.LOG_FG,
            insertbackground=theme.LOG_FG,
            font=theme.FONT_MONO,
            relief="flat",
            bd=0,
            padx=sp(10),
            pady=sp(8),
            wrap="word",
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(self.log_body, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.tag_configure("info", foreground=theme.LOG_FG)
        self.log_text.tag_configure("success", foreground="#6ee7a8")
        self.log_text.tag_configure("error", foreground="#ff9b93")

    def _toggle_log(self) -> None:
        if self.log_body.winfo_manager():
            self.log_body.pack_forget()
            self.btn_toggle_log.configure(text="展开")
        else:
            self.log_body.pack(fill="both", expand=True, padx=sp(14), pady=(0, sp(10)))
            self.btn_toggle_log.configure(text="收起")
            self.log_text.see("end")

    def _on_tab_changed(self, _event=None) -> None:
        try:
            current = self.notebook.select()
        except tk.TclError:
            return
        if current == str(self.configs_page):
            self._refresh_configs()
        elif current == str(self.bindings_page):
            self._refresh_bindings()
        elif current == str(self.version_panel):
            self.version_panel.refresh()

    def _on_git_configs_changed(self) -> None:
        self._refresh_configs()
        self._refresh_bindings()

    # ------------------------------------------------------------------ 配置文件页

    def _build_configs_page(self) -> None:
        page = self.configs_page
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)

        toolbar = tk.Frame(page, bg=theme.BG)
        toolbar.grid(row=0, column=0, sticky="ew", padx=sp(12), pady=sp((12, 8)))

        theme.accent_button(toolbar, "＋ 新建配置", self._new_config).pack(side="left")
        self.btn_edit_config = theme.ghost_button(toolbar, "编辑", self._edit_config)
        self.btn_edit_config.pack(side="left", padx=sp((8, 0)))
        self.btn_delete_config = theme.ghost_button(toolbar, "删除", self._delete_config)
        self.btn_delete_config.pack(side="left", padx=sp((8, 0)))
        self.btn_apply_config = theme.accent_button(toolbar, "▶ 应用配置", self._apply_selected_config)
        self.btn_apply_config.pack(side="left", padx=sp((16, 0)))

        theme.ghost_button(toolbar, "刷新", lambda: self._refresh_configs()).pack(side="right")
        theme.ghost_button(toolbar, "打开配置目录", self._open_config_dir).pack(side="right", padx=sp((0, 8)))

        content = tk.Frame(page, bg=theme.BG)
        content.grid(row=1, column=0, sticky="nsew", padx=sp(12), pady=sp((0, 12)))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=0, minsize=sp(280))
        content.columnconfigure(1, weight=1)

        left = theme.make_card(content)
        left.grid(row=0, column=0, sticky="nsew", padx=sp((0, 10)))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        left_head = tk.Frame(left, bg=theme.CARD)
        left_head.grid(row=0, column=0, sticky="ew", padx=sp(12), pady=sp((11, 6)))
        self.config_count_label = tk.Label(
            left_head, text="配置文件", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION
        )
        self.config_count_label.pack(side="left")

        config_tree_wrap = tk.Frame(left, bg=theme.CARD)
        config_tree_wrap.grid(row=1, column=0, sticky="nsew", padx=sp(10), pady=sp((0, 10)))
        config_tree_wrap.rowconfigure(0, weight=1)
        config_tree_wrap.columnconfigure(0, weight=1)

        self.config_tree = ttk.Treeview(
            config_tree_wrap, columns=("name", "count"), show="headings", selectmode="browse"
        )
        self.config_tree.heading("name", text="配置名称")
        self.config_tree.column("name", width=sp(180), minwidth=sp(100), anchor="w", stretch=True)
        self.config_tree.heading("count", text="操作")
        self.config_tree.column("count", width=sp(56), minwidth=sp(46), anchor="center", stretch=False)
        self.config_tree.grid(row=0, column=0, sticky="nsew")
        config_scroll = ttk.Scrollbar(config_tree_wrap, orient="vertical", command=self.config_tree.yview)
        config_scroll.grid(row=0, column=1, sticky="ns")
        self.config_tree.configure(yscrollcommand=config_scroll.set)
        self.config_tree.bind("<<TreeviewSelect>>", self._on_config_selected)
        self.config_tree.bind("<Double-1>", lambda _event: self._edit_config())

        right = theme.make_card(content)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        right_head = tk.Frame(right, bg=theme.CARD)
        right_head.grid(row=0, column=0, sticky="ew", padx=sp(14), pady=sp((12, 6)))
        tk.Label(right_head, text="配置详情", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(
            side="left"
        )
        self.detail_name = tk.Label(right_head, text="", bg=theme.CARD, fg=theme.ACCENT, font=theme.FONT_UI_BOLD)
        self.detail_name.pack(side="left", padx=sp((10, 0)))
        self.detail_path = tk.Label(right_head, text="", bg=theme.CARD, fg=theme.MUTED, font=theme.FONT_SMALL)
        self.detail_path.pack(side="right")

        preview_wrap = tk.Frame(right, bg=theme.CARD)
        preview_wrap.grid(row=1, column=0, sticky="nsew", padx=sp(14))
        preview_wrap.rowconfigure(0, weight=1)
        preview_wrap.columnconfigure(0, weight=1)

        self.preview_tree = ttk.Treeview(
            preview_wrap, columns=("idx", "action", "args", "cond"), show="headings", selectmode="none"
        )
        preview_columns = (
            ("idx", "序号", sp(46), "center", False, sp(40)),
            ("action", "操作", sp(120), "w", False, sp(90)),
            ("args", "参数", sp(320), "w", True, sp(140)),
            ("cond", "执行条件", sp(110), "center", False, sp(86)),
        )
        for key, title, width, anchor, stretch, minwidth in preview_columns:
            self.preview_tree.heading(key, text=title)
            self.preview_tree.column(key, width=width, minwidth=minwidth, anchor=anchor, stretch=stretch)
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_wrap, orient="vertical", command=self.preview_tree.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)
        self.preview_tree.tag_configure("unknown", foreground=theme.DANGER)

        self.preview_hint = tk.Label(
            right,
            text="",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=sp(560),
        )
        self.preview_hint.grid(row=2, column=0, sticky="ew", padx=sp(14), pady=sp((6, 12)))

    def _refresh_configs(self, select: str | None = None) -> None:
        current = select
        if current is None:
            selected = self._selected_config()
            current = selected.name if selected else None

        self.configs = config_store.list_configs()
        self.config_tree.delete(*self.config_tree.get_children())
        for info in self.configs:
            count = "—" if info.error else str(info.action_count)
            self.config_tree.insert("", "end", iid=info.name, values=(info.name, count))

        self.config_count_label.configure(text=f"配置文件 · {len(self.configs)}")
        names = [c.name for c in self.configs]
        if current in names:
            self.config_tree.selection_set(current)
            self.config_tree.see(current)
        elif names:
            self.config_tree.selection_set(names[0])
            self.config_tree.see(names[0])

        self._on_config_selected()

    def _selected_config(self) -> config_store.ConfigInfo | None:
        selection = self.config_tree.selection()
        if not selection:
            return None
        name = selection[0]
        return next((c for c in self.configs if c.name == name), None)

    def _on_config_selected(self, _event=None) -> None:
        info = self._selected_config()
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.detail_name.configure(text=info.name if info else "")
        self.detail_path.configure(text="")

        if info is None:
            self.preview_hint.configure(text="选择左侧的配置文件查看操作列表，或点击「新建配置」开始。")
            self._set_config_buttons(False, False, False)
            return

        try:
            self.detail_path.configure(text=str(info.path.relative_to(APP_ROOT)))
        except ValueError:
            self.detail_path.configure(text=str(info.path))

        valid = info.error is None
        self._set_config_buttons(True, valid, valid)

        if info.error:
            self.preview_hint.configure(text=f"⚠ {info.error}。可用「打开配置目录」手动修复该文件。")
            return

        if not info.actions:
            self.preview_hint.configure(text="该配置暂无操作。点击「编辑」添加操作。")
            return

        for index, action in enumerate(info.actions, 1):
            name = str(action.get("action", ""))
            definition = self.definition_map.get(name)
            label = definition.label if definition else name
            condition = "仅上一步成功时" if action.get("run_while_prev_action_success") else ""
            tags = () if definition else ("unknown",)
            self.preview_tree.insert(
                "",
                "end",
                values=(index, label, action.get("args", ""), condition),
                tags=tags,
            )

        self.preview_hint.configure(text=f"共 {len(info.actions)} 个操作，应用时按顺序执行。")

    def _set_config_buttons(self, has_selection: bool, can_edit: bool, can_apply: bool) -> None:
        self.btn_edit_config.configure(state="normal" if has_selection and can_edit else "disabled")
        self.btn_apply_config.configure(state="normal" if has_selection and can_apply else "disabled")
        self.btn_delete_config.configure(state="normal" if has_selection else "disabled")

    def _new_config(self) -> None:
        self._open_config_editor(None)

    def _edit_config(self) -> None:
        info = self._selected_config()
        if info is None:
            return
        if info.error:
            if messagebox.askyesno(
                "无法在编辑器中打开",
                f"该配置文件无法解析：\n{info.error}\n\n是否用系统默认程序打开并手动修复？",
                parent=self.root,
            ):
                self._open_path(info.path)
            return
        self._open_config_editor(info)

    def _open_config_editor(self, info: config_store.ConfigInfo | None) -> None:
        holder: dict[str, str] = {}
        dialog = ConfigEditorDialog(
            self.root,
            info,
            self._available_config_names(),
            lambda name: holder.setdefault("name", name),
        )
        self.root.wait_window(dialog)
        name = holder.get("name")
        if name:
            self._refresh_configs(select=name)
            self._set_status(f"配置 [{name}] 已保存")
            self._log(f"配置 [{name}] 已保存。", "success")

    def _delete_config(self) -> None:
        info = self._selected_config()
        if info is None:
            return
        if not messagebox.askyesno(
            "删除配置",
            f"确定要删除配置 [{info.name}] 吗？该操作不可撤销。",
            parent=self.root,
        ):
            return
        try:
            config_store.delete_config(info.name)
        except Exception as exc:
            messagebox.showerror("删除失败", f"无法删除配置：{exc}", parent=self.root)
            return

        self._refresh_configs()
        self._set_status(f"配置 [{info.name}] 已删除")
        self._log(f"配置 [{info.name}] 已删除。", "info")

    def _apply_selected_config(self) -> None:
        info = self._selected_config()
        if info is None or info.error:
            return
        self.apply_config(info.name, source="manual")

    def _open_config_dir(self) -> None:
        self._open_path(CONFIG_DIR)

    def _open_path(self, path) -> None:
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法打开：{path}\n{exc}", parent=self.root)

    def _available_config_names(self) -> list[str]:
        return [c.name for c in self.configs if not c.error]

    # ------------------------------------------------------------------ 绑定页

    def _build_bindings_page(self) -> None:
        page = self.bindings_page
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)

        toolbar = tk.Frame(page, bg=theme.BG)
        toolbar.grid(row=0, column=0, sticky="ew", padx=sp(12), pady=sp((12, 8)))

        theme.accent_button(toolbar, "＋ 新增绑定", self._new_binding).pack(side="left")
        self.btn_edit_binding = theme.ghost_button(toolbar, "编辑", self._edit_binding)
        self.btn_edit_binding.pack(side="left", padx=sp((8, 0)))
        self.btn_delete_binding = theme.ghost_button(toolbar, "删除", self._delete_binding)
        self.btn_delete_binding.pack(side="left", padx=sp((8, 0)))
        self.btn_toggle_binding = theme.ghost_button(toolbar, "启用 / 停用", self._toggle_binding)
        self.btn_toggle_binding.pack(side="left", padx=sp((8, 0)))

        self.autostart_var = tk.BooleanVar(master=self.root, value=autostart.is_enabled())
        ttk.Checkbutton(
            toolbar,
            text="开机自启",
            variable=self.autostart_var,
            command=self._on_autostart_changed,
        ).pack(side="right")
        self.monitor_var = tk.BooleanVar(master=self.root, value=self.settings.get("monitor_enabled", True))
        ttk.Checkbutton(
            toolbar,
            text="后台监听",
            variable=self.monitor_var,
            command=self._on_monitor_checkbox,
        ).pack(side="right", padx=sp((0, 16)))

        tree_card = theme.make_card(page)
        tree_card.grid(row=1, column=0, sticky="nsew", padx=sp(12), pady=sp((0, 12)))
        tree_card.rowconfigure(1, weight=1)
        tree_card.columnconfigure(0, weight=1)

        head = tk.Frame(tree_card, bg=theme.CARD)
        head.grid(row=0, column=0, sticky="ew", padx=sp(14), pady=sp((11, 6)))
        self.binding_count_label = tk.Label(
            head, text="应用绑定", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION
        )
        self.binding_count_label.pack(side="left")
        tk.Label(
            head,
            text="启动/退出时自动应用配置；动作会自动读取当前启动的 exe 信息",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left", padx=sp((10, 0)))

        binding_wrap = tk.Frame(tree_card, bg=theme.CARD)
        binding_wrap.grid(row=1, column=0, sticky="nsew", padx=sp(14), pady=sp((0, 12)))
        binding_wrap.rowconfigure(0, weight=1)
        binding_wrap.columnconfigure(0, weight=1)

        self.binding_tree = ttk.Treeview(
            binding_wrap,
            columns=("state", "type", "target", "config", "close"),
            show="headings",
            selectmode="browse",
        )
        binding_columns = (
            ("state", "状态", sp(66), "center", False, sp(56)),
            ("type", "类型", sp(84), "center", False, sp(64)),
            ("target", "目标", sp(420), "w", True, sp(180)),
            ("config", "启动时", sp(128), "w", False, sp(96)),
            ("close", "退出后", sp(128), "w", False, sp(96)),
        )
        for key, title, width, anchor, stretch, minwidth in binding_columns:
            self.binding_tree.heading(key, text=title)
            self.binding_tree.column(key, width=width, minwidth=minwidth, anchor=anchor, stretch=stretch)
        self.binding_tree.grid(row=0, column=0, sticky="nsew")
        binding_scroll = ttk.Scrollbar(binding_wrap, orient="vertical", command=self.binding_tree.yview)
        binding_scroll.grid(row=0, column=1, sticky="ns")
        self.binding_tree.configure(yscrollcommand=binding_scroll.set)
        self.binding_tree.tag_configure("disabled", foreground=theme.MUTED)
        self.binding_tree.tag_configure("missing", foreground=theme.DANGER)
        self.binding_tree.bind("<<TreeviewSelect>>", self._on_binding_selected)
        self.binding_tree.bind("<Double-1>", lambda _event: self._edit_binding())
        self.binding_tree.bind("<Delete>", lambda _event: self._delete_binding())

    def _refresh_bindings(self, select: str | None = None) -> None:
        current = select
        if current is None:
            selected = self._selected_binding()
            current = selected.id if selected else None

        self.bindings = binding_store.load_bindings()
        self.binding_tree.delete(*self.binding_tree.get_children())
        for binding in self.bindings:
            missing = not config_store.config_path(binding.config).exists()
            missing_close = bool(binding.close_config) and not config_store.config_path(binding.close_config).exists()
            state = "启用" if binding.enabled else "已停用"
            config_text = binding.config + ("  ⚠" if missing else "")
            close_text = (binding.close_config + ("  ⚠" if missing_close else "")) if binding.close_config else "—"
            tags = []
            if not binding.enabled:
                tags.append("disabled")
            if missing or missing_close:
                tags.append("missing")
            self.binding_tree.insert(
                "",
                "end",
                iid=binding.id,
                values=(state, binding.display_type(), binding.display_target(), config_text, close_text),
                tags=tuple(tags),
            )

        self.binding_count_label.configure(text=f"应用绑定 · {len(self.bindings)}")
        ids = [b.id for b in self.bindings]
        if current in ids:
            self.binding_tree.selection_set(current)
            self.binding_tree.see(current)
        elif ids:
            self.binding_tree.selection_set(ids[0])
            self.binding_tree.see(ids[0])

        self._sync_watcher()
        self._update_monitor_ui()
        self._on_binding_selected()

    def _selected_binding(self) -> AppBinding | None:
        selection = self.binding_tree.selection()
        if not selection:
            return None
        return next((b for b in self.bindings if b.id == selection[0]), None)

    def _on_binding_selected(self, _event=None) -> None:
        has_selection = self._selected_binding() is not None
        state = "normal" if has_selection else "disabled"
        for button in (self.btn_edit_binding, self.btn_delete_binding, self.btn_toggle_binding):
            button.configure(state=state)

    def _new_binding(self) -> None:
        config_names = self._available_config_names()
        if not config_names:
            messagebox.showinfo(
                "暂无配置",
                "请先在「配置文件」页创建至少一个配置（例如 game_acc）。",
                parent=self.root,
            )
            return

        holder: dict[str, AppBinding] = {}
        dialog = BindingEditorDialog(
            self.root,
            None,
            config_names,
            lambda binding: holder.setdefault("binding", binding),
        )
        self.root.wait_window(dialog)
        binding = holder.get("binding")
        if binding is None:
            return

        self.bindings.append(binding)
        self._persist_bindings(select=binding.id)
        self._log(f"已新增绑定：{binding.display_target()} → {binding.display_configs()}", "success")

    def _edit_binding(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        config_names = self._available_config_names()
        for name in (binding.config, binding.close_config):
            if name and name not in config_names:
                config_names.append(name)

        holder: dict[str, AppBinding] = {}
        dialog = BindingEditorDialog(
            self.root,
            binding,
            config_names,
            lambda result: holder.setdefault("binding", result),
        )
        self.root.wait_window(dialog)
        result = holder.get("binding")
        if result is None:
            return

        for index, existing in enumerate(self.bindings):
            if existing.id == result.id:
                self.bindings[index] = result
                break
        self._persist_bindings(select=result.id)
        self._log(f"已更新绑定：{result.display_target()} → {result.display_configs()}", "info")

    def _delete_binding(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        if not messagebox.askyesno(
            "删除绑定",
            f"确定要删除这条绑定吗？\n{binding.display_target()} → {binding.display_configs()}",
            parent=self.root,
        ):
            return

        self.bindings = [b for b in self.bindings if b.id != binding.id]
        self._persist_bindings()
        self._log(f"已删除绑定：{binding.display_target()}", "info")

    def _toggle_binding(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        binding.enabled = not binding.enabled
        self._persist_bindings(select=binding.id)
        self._log(f"绑定已{'启用' if binding.enabled else '停用'}：{binding.display_target()}", "info")

    def _persist_bindings(self, select: str | None = None) -> None:
        try:
            binding_store.save_bindings(self.bindings)
        except Exception as exc:
            messagebox.showerror("保存失败", f"无法保存绑定：{exc}", parent=self.root)
            return
        self._refresh_bindings(select=select)
        self._set_status(f"应用绑定已更新（{len(self.bindings)} 条）")

    # ------------------------------------------------------------------ 监听

    def _sync_watcher(self) -> None:
        enabled = [
            b
            for b in self.bindings
            if b.enabled
            and (
                (b.config and config_store.config_path(b.config).exists())
                or (b.close_config and config_store.config_path(b.close_config).exists())
            )
        ]
        if not self.settings.get("monitor_enabled", True) or not enabled:
            self._stop_watcher()
            self._update_monitor_ui()
            return

        interval = float(self.settings.get("poll_interval", 2.0))
        if self._watcher is None:
            self._watcher = BindingWatcher(
                self._on_process_started,
                self._on_process_stopped,
                interval=interval,
            )
            self._watcher.start()
        else:
            self._watcher.set_interval(interval)
        self._watcher.update_bindings(enabled)
        self._update_monitor_ui()

    def _stop_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def _on_process_started(self, binding: AppBinding, process) -> None:
        self._queue.put(("trigger", {"binding": binding, "process": process}))

    def _on_process_stopped(self, binding: AppBinding, process) -> None:
        self._queue.put(("trigger_close", {"binding": binding, "process": process}))

    def _handle_trigger(self, payload: dict) -> None:
        if not self.settings.get("monitor_enabled", True):
            return

        binding: AppBinding = payload["binding"]
        process = payload["process"]
        current = next((b for b in self.bindings if b.id == binding.id), None)
        if current is None or not current.enabled or not current.config:
            return
        if not config_store.config_path(current.config).exists():
            self._log(f"绑定命中，但配置 [{current.config}] 不存在。", "error")
            return

        self._log(f"检测到 {process.name} 启动 → 应用配置 [{current.config}]", "success")
        self.apply_config(
            current.config,
            source="binding",
            detail=process.name,
            variables=build_context(current, process),
        )

    def _handle_close_trigger(self, payload: dict) -> None:
        if not self.settings.get("monitor_enabled", True):
            return

        binding: AppBinding = payload["binding"]
        process = payload["process"]
        current = next((b for b in self.bindings if b.id == binding.id), None)
        if current is None or not current.enabled or not current.close_config:
            return
        if not config_store.config_path(current.close_config).exists():
            self._log(f"绑定命中，但退出配置 [{current.close_config}] 不存在。", "error")
            return

        self._log(f"检测到 {process.name} 退出 → 应用配置 [{current.close_config}]", "success")
        self.apply_config(
            current.close_config,
            source="binding",
            detail=f"{process.name} 已退出",
            variables=build_context(current, process),
        )

    def apply_config(
        self,
        name: str,
        source: str = "manual",
        detail: str | None = None,
        variables: dict[str, str] | None = None,
    ) -> None:
        if not config_store.config_path(name).exists():
            self._log(f"配置 [{name}] 不存在，无法应用。", "error")
            self._set_status(f"配置 [{name}] 不存在")
            return

        self._set_status(f"正在应用配置 [{name}]…")
        self._log(f"开始应用配置 [{name}]" + (f"（触发进程：{detail}）" if detail else ""), "info")
        threading.Thread(
            target=self._run_apply,
            args=(name, source, detail, variables),
            daemon=True,
        ).start()

    @staticmethod
    def _apply_config_sync(name: str, variables: dict[str, str] | None = None) -> tuple[bool, str]:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        command = [sys.executable, str(APPLY_SCRIPT), "--config", name]
        for key, value in (variables or {}).items():
            command.extend(["--var", f"{key}={value}"])
        try:
            result = subprocess.run(
                command,
                cwd=str(APP_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                # 配置里可能包含「等待」操作，超时时间需要覆盖较长的加速等待
                timeout=900,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            return result.returncode == 0, output
        except Exception as exc:
            logger.exception("应用配置失败")
            return False, str(exc)

    def _run_apply(
        self,
        name: str,
        source: str,
        detail: str | None,
        variables: dict[str, str] | None = None,
    ) -> None:
        ok, output = self._apply_config_sync(name, variables)
        payload = {
            "name": name,
            "ok": ok,
            "output": output,
            "source": source,
            "detail": detail,
        }
        self._queue.put(("apply_done", payload))

    def _handle_apply_done(self, payload: dict) -> None:
        name = payload["name"]
        ok = bool(payload["ok"])
        output = str(payload.get("output") or "")
        source = payload.get("source", "manual")
        detail = payload.get("detail")

        label = "配置"
        self._log_accelerator_output()

        if ok:
            headline = f"{label} [{name}] 应用完成"
            self._log_output(output, "info", skip_text=headline)
            self._log(headline, "success")
            self._set_status(headline)
            if self._hidden and self._tray and self.settings.get("notify_on_trigger", True):
                if source == "binding":
                    self._tray.notify("配置已应用", f"{detail or '进程'} → {name}")
                else:
                    self._tray.notify("配置已应用", f"已应用配置 [{name}]")
            return

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        last_line = lines[-1] if lines else ""
        error_detail = "\n".join(lines[-6:])
        logger.error("配置 [%s] 应用失败:\n%s", name, output)

        headline = f"{label} [{name}] 应用失败"
        self._log(headline, "error")
        self._log_output(output, "error", skip_text=headline)
        self._set_status(headline)

        # 优先展示“配置不存在”这类根因，便于定位问题
        short_error = last_line or "未知错误"
        for line in reversed(lines):
            if "配置不存在" in line or "not found" in line.lower():
                short_error = line
                break

        if self._hidden and self._tray:
            self._tray.notify("应用失败", f"{name}：{short_error}")
        elif source != "binding":
            messagebox.showerror(
                "应用失败",
                f"配置 [{name}] 应用失败。\n\n{error_detail or '未知错误'}",
                parent=self.root,
            )

    # ------------------------------------------------------------------ 监听开关 / 自启

    def _on_monitor_checkbox(self) -> None:
        self._set_monitor(self.monitor_var.get())

    def _toggle_monitor(self) -> None:
        self._set_monitor(not self.settings.get("monitor_enabled", True))

    def _set_monitor(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.settings.get("monitor_enabled", True):
            self._update_monitor_ui()
            return

        self.settings["monitor_enabled"] = enabled
        try:
            self.settings = settings_store.save_settings(self.settings)
        except Exception:
            logger.exception("保存设置失败")

        self._sync_watcher()
        self._update_monitor_ui()
        self._log(f"后台监听已{'启用' if enabled else '暂停'}。", "info")
        self._set_status(f"后台监听已{'启用' if enabled else '暂停'}")

    def _update_monitor_ui(self) -> None:
        enabled = self.settings.get("monitor_enabled", True)
        active = sum(1 for b in self.bindings if b.enabled and config_store.config_path(b.config).exists())

        if enabled:
            self.monitor_pill.configure(text="● 后台监听中", fg="#34d399", bg="#1b2c46")
            self.monitor_label.configure(text=f"● 后台监听中 · 生效绑定 {active} 项", fg=theme.SUCCESS)
        else:
            self.monitor_pill.configure(text="● 监听已暂停", fg="#cbd5e1", bg="#1e293b")
            self.monitor_label.configure(text="● 后台监听已暂停", fg=theme.MUTED)

        if hasattr(self, "monitor_var") and self.monitor_var.get() != enabled:
            self.monitor_var.set(enabled)

        if self._tray is not None:
            self._tray.set_tooltip(self._tooltip_text())

    def _tooltip_text(self) -> str:
        state = "后台监听中" if self.settings.get("monitor_enabled", True) else "监听已暂停"
        return f"StartWith · {state}（右键可快速应用配置）"

    def _on_autostart_changed(self) -> None:
        enabled = self.autostart_var.get()
        try:
            autostart.set_enabled(enabled)
        except Exception as exc:
            self.autostart_var.set(not enabled)
            messagebox.showerror("设置失败", f"无法修改开机自启设置：{exc}", parent=self.root)
            return

        self._log(f"已{'开启' if enabled else '关闭'}开机自动启动。", "info")
        self._set_status("开机自启已开启" if enabled else "开机自启已关闭")

    # ------------------------------------------------------------------ 托盘

    def _setup_tray(self) -> None:
        try:
            from gui.tray import TrayIcon

            self._tray = TrayIcon(
                tooltip=self._tooltip_text(),
                menu_provider=self._build_tray_menu,
                on_command=lambda key: self._queue.put(("tray", key)),
            )
            self._tray.start()
        except Exception:
            logger.exception("初始化系统托盘失败")
            self._tray = None
            self._log("系统托盘不可用（请确认已安装 pywin32），关闭窗口将直接退出。", "error")

    def _build_tray_menu(self) -> list[dict]:
        try:
            configs = [c for c in config_store.list_configs() if not c.error]
        except Exception:
            configs = []
        settings = settings_store.load_settings()

        config_items = [{"label": c.name, "key": f"apply:{c.name}"} for c in configs]
        if not config_items:
            config_items = [{"label": "（暂无配置）", "enabled": False}]
        edit_items = [{"label": c.name, "key": f"edit:{c.name}"} for c in configs]
        if not edit_items:
            edit_items = [{"label": "（暂无配置）", "enabled": False}]

        return [
            {"label": "打开控制面板", "key": "open"},
            {"label": "新建配置…", "key": "new_config"},
            {"separator": True},
            {"label": "应用配置", "children": config_items},
            {"label": "编辑配置", "children": edit_items},
            {"separator": True},
            {
                "label": "后台监听",
                "key": "toggle_monitor",
                "checked": bool(settings.get("monitor_enabled", True)),
            },
            {"label": "绑定设置…", "key": "open_bindings"},
            {"label": "版本管理…", "key": "open_versions"},
            {"separator": True},
            {"label": "退出", "key": "quit"},
        ]

    def _handle_tray_key(self, key: str) -> None:
        if key == "open":
            self.show_window()
        elif key == "new_config":
            self.show_window()
            self.notebook.select(self.configs_page)
            self._new_config()
        elif key.startswith("apply:"):
            self.apply_config(key.split(":", 1)[1], source="tray")
        elif key.startswith("edit:"):
            self.show_window()
            self._open_config_editor_by_name(key.split(":", 1)[1])
        elif key == "toggle_monitor":
            self._toggle_monitor()
        elif key == "open_bindings":
            self.show_window()
            self.notebook.select(self.bindings_page)
        elif key == "open_versions":
            self.show_window()
            self.notebook.select(self.version_panel)
        elif key == "quit":
            self.quit_app()

    def _open_config_editor_by_name(self, name: str) -> None:
        self.notebook.select(self.configs_page)
        self._refresh_configs(select=name)
        info = self._selected_config()
        if info is None:
            return
        if info.error:
            if messagebox.askyesno(
                "无法在编辑器中打开",
                f"该配置文件无法解析：\n{info.error}\n\n是否用系统默认程序打开并手动修复？",
                parent=self.root,
            ):
                self._open_path(info.path)
            return
        self._open_config_editor(info)

    def hide_to_tray(self, show_tip: bool = True) -> None:
        if self._closing:
            return
        if self._tray is None:
            self.quit_app()
            return

        self._hidden = True
        try:
            self.root.withdraw()
        except tk.TclError:
            return

        if show_tip and not self._tray_tip_shown:
            self._tray_tip_shown = True
            self._tray.notify("StartWith 已转入后台", "双击托盘图标打开面板，右键可快速应用配置。")

    def show_window(self) -> None:
        if self._closing:
            return
        self._hidden = False
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        if self._tray is not None and self.settings.get("minimize_to_tray", True):
            self.hide_to_tray(show_tip=True)
        else:
            self.quit_app()

    def _on_unmap(self, event) -> None:
        if event.widget is not self.root:
            return
        self.root.after(40, self._maybe_hide_minimized)

    def _maybe_hide_minimized(self) -> None:
        if self._closing or self._hidden:
            return
        if self._tray is None or not self.settings.get("minimize_to_tray", True):
            return
        try:
            if self.root.state() == "iconic":
                self.hide_to_tray(show_tip=True)
        except tk.TclError:
            pass

    def quit_app(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._stop_watcher()
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 事件循环 / 日志

    def _poll_queue(self) -> None:
        try:
            while True:
                try:
                    kind, payload = self._queue.get_nowait()
                except queue.Empty:
                    break

                try:
                    if kind == "trigger":
                        self._handle_trigger(payload)
                    elif kind == "trigger_close":
                        self._handle_close_trigger(payload)
                    elif kind == "apply_done":
                        self._handle_apply_done(payload)
                    elif kind == "tray":
                        self._handle_tray_key(str(payload))
                except Exception:
                    logger.exception("处理界面事件失败: %s", kind)
        finally:
            if not self._closing:
                try:
                    self.root.after(120, self._poll_queue)
                except tk.TclError:
                    pass

    def _log(self, text: str, level: str = "info") -> None:
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] {text}\n", level)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass

    def _log_output(self, output: str, level: str = "info", limit: int = 40, skip_text: str | None = None) -> None:
        """把子进程输出写入日志面板，避免成功时只显示一行结果。"""
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if skip_text and lines and lines[-1] == skip_text:
            lines.pop()
        for line in lines[:limit]:
            self._log(f"  {line}", level)
        if len(lines) > limit:
            self._log(f"  … 另有 {len(lines) - limit} 行输出", "info")

    def _log_accelerator_output(self, limit: int = 15) -> None:
        try:
            if time.time() - ACC_LOG_FILE.stat().st_mtime > 120:
                return
            lines = ACC_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        for line in lines[-limit:]:
            level = "error" if ("失败" in line or "ERROR" in line) else "info"
            self._log(f"  {line}", level)

    def _clear_log(self) -> None:
        try:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass

    def _set_status(self, text: str) -> None:
        try:
            self.status_label.configure(text=text)
        except tk.TclError:
            pass

    def _report_callback_exception(self, exc, value, tb) -> None:
        logger.exception("界面操作异常", exc_info=(exc, value, tb))
        self._log(f"操作失败：{value}", "error")
        try:
            messagebox.showerror(
                "操作失败",
                f"{value}\n\n详细信息已写入 data/app.log。",
                parent=self.root,
            )
        except tk.TclError:
            pass
