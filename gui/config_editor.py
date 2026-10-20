"""配置文件编辑器：新增 / 修改配置。"""
import tkinter as tk
from tkinter import messagebox, ttk

from common import config_store
from common.config_store import ConfigInfo
from gui import theme
from gui.action_editor import ActionEditorDialog

sp = theme.sp


class ConfigEditorDialog(tk.Toplevel):
    def __init__(self, master, info: ConfigInfo | None, config_names: list[str], on_saved=None):
        super().__init__(master)
        self.info = info
        self.config_names = list(config_names)
        self.on_saved = on_saved
        self.actions: list[dict] = [dict(a) for a in info.actions] if info else []
        self._closed = False

        self.title("编辑配置" if info else "新建配置")
        self.configure(bg=theme.BG)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())

        self._build()
        self._refresh_tree(0 if self.actions else None)
        theme.center_window(self, master, 840, 600)
        self.minsize(sp(720), sp(480))
        self.grab_set()

    # ------------------------------------------------------------------ 构建界面

    def _build(self) -> None:
        theme.dialog_header(
            self,
            "编辑配置" if self.info else "新建配置",
            "配置文件会保存到 config 目录，应用时按顺序执行下列操作",
        ).pack(fill="x")

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=sp(16), pady=sp(12))

        name_row = tk.Frame(body, bg=theme.BG)
        name_row.pack(fill="x")
        tk.Label(name_row, text="配置名称", bg=theme.BG, fg=theme.TEXT, font=theme.FONT_UI_BOLD).pack(side="left")
        self.name_var = tk.StringVar(master=self, value=self.info.name if self.info else "")
        self.name_entry = ttk.Entry(name_row, textvariable=self.name_var, width=28)
        self.name_entry.pack(side="left", padx=sp((10, 10)))
        if self.info:
            self.name_entry.configure(state="readonly")
            tk.Label(
                name_row,
                text="名称创建后不可修改",
                bg=theme.BG,
                fg=theme.MUTED,
                font=theme.FONT_SMALL,
            ).pack(side="left")
        else:
            tk.Label(
                name_row,
                text="保存为 config/<名称>.json",
                bg=theme.BG,
                fg=theme.MUTED,
                font=theme.FONT_SMALL,
            ).pack(side="left")

        card = theme.make_card(body)
        card.pack(fill="both", expand=True, pady=sp((12, 0)))

        head = tk.Frame(card, bg=theme.CARD)
        head.pack(fill="x", padx=sp(14), pady=sp((12, 6)))
        tk.Label(head, text="操作列表", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(side="left")
        tk.Label(
            head,
            text="勾选「仅在上一步成功时」可控制失败后的跳过行为",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left", padx=sp((10, 0)))

        tree_wrap = tk.Frame(card, bg=theme.CARD)
        tree_wrap.pack(fill="both", expand=True, padx=sp(14), pady=sp((0, 4)))
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("idx", "action", "args", "cond"),
            show="headings",
            selectmode="browse",
        )
        columns = (
            ("idx", "序号", sp(50), "center", False, sp(40)),
            ("action", "操作", sp(130), "w", False, sp(90)),
            ("args", "参数", sp(320), "w", True, sp(140)),
            ("cond", "执行条件", sp(110), "center", False, sp(86)),
        )
        for key, title, width, anchor, stretch, minwidth in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=minwidth, anchor=anchor, stretch=stretch)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._update_buttons)
        self.tree.bind("<Double-1>", lambda _event: self._edit_action())
        self.tree.bind("<Delete>", lambda _event: self._delete_action())

        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        side = tk.Frame(tree_wrap, bg=theme.CARD)
        side.grid(row=0, column=2, sticky="n", padx=sp((10, 0)))
        theme.accent_button(side, "添加操作", self._add_action).pack(fill="x", pady=sp((0, 6)))
        self.btn_edit = theme.ghost_button(side, "编辑", self._edit_action)
        self.btn_edit.pack(fill="x", pady=sp(2))
        self.btn_delete = theme.ghost_button(side, "删除", self._delete_action)
        self.btn_delete.pack(fill="x", pady=sp(2))
        self.btn_up = theme.ghost_button(side, "上移", lambda: self._move(-1))
        self.btn_up.pack(fill="x", pady=sp((10, 2)))
        self.btn_down = theme.ghost_button(side, "下移", lambda: self._move(1))
        self.btn_down.pack(fill="x", pady=sp(2))

        footer = tk.Frame(body, bg=theme.BG)
        footer.pack(fill="x", pady=sp((12, 0)))
        tk.Label(
            footer,
            text="提示：应用配置时会按从上到下的顺序执行这些操作。",
            bg=theme.BG,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left")
        theme.accent_button(footer, "保存配置", self._save, width=10).pack(side="right")
        theme.ghost_button(footer, "取消", self._close, width=8).pack(side="right", padx=sp((0, 8)))

    # ------------------------------------------------------------------ 列表操作

    def _refresh_tree(self, select: int | None = None) -> None:
        selected = self._selected_index() if select is None else select
        self.tree.delete(*self.tree.get_children())
        definitions = {d.name: d for d in self._action_definitions()}
        for index, action in enumerate(self.actions):
            definition = definitions.get(str(action.get("action", "")))
            label = definition.label if definition else str(action.get("action", ""))
            condition = "仅上一步成功时" if action.get("run_while_prev_action_success") else ""
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(index + 1, label, action.get("args", ""), condition),
            )
        if selected is not None and 0 <= selected < len(self.actions):
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))
        self._update_buttons()

    @staticmethod
    def _action_definitions():
        from common.action_meta import get_action_definitions

        return get_action_definitions()

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _update_buttons(self, _event=None) -> None:
        has_selection = self._selected_index() is not None
        state = "normal" if has_selection else "disabled"
        for button in (self.btn_edit, self.btn_delete, self.btn_up, self.btn_down):
            button.configure(state=state)

        index = self._selected_index()
        if index is not None:
            self.btn_up.configure(state="normal" if index > 0 else "disabled")
            self.btn_down.configure(state="normal" if index < len(self.actions) - 1 else "disabled")

    def _add_action(self) -> None:
        result = self._open_action_editor(None)
        if result is not None:
            self.actions.append(result)
            self._refresh_tree(len(self.actions) - 1)

    def _edit_action(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        result = self._open_action_editor(self.actions[index])
        if result is not None:
            self.actions[index] = result
            self._refresh_tree(index)

    def _open_action_editor(self, action: dict | None) -> dict | None:
        holder: dict[str, dict] = {}
        dialog = ActionEditorDialog(self, action, self.config_names, lambda result: holder.setdefault("action", result))
        self.wait_window(dialog)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        return holder.get("action")

    def _delete_action(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        name = self.actions[index].get("action", "")
        if not messagebox.askyesno("删除操作", f"确定删除该操作（{name}）吗？", parent=self):
            return
        del self.actions[index]
        self._refresh_tree(min(index, len(self.actions) - 1) if self.actions else None)

    def _move(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        target = index + delta
        if 0 <= target < len(self.actions):
            self.actions[index], self.actions[target] = self.actions[target], self.actions[index]
            self._refresh_tree(target)

    # ------------------------------------------------------------------ 保存

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not config_store.is_valid_name(name):
            messagebox.showerror(
                "名称不合法",
                '配置名称不能为空，且不能包含 \\ / : * ? " < > | 等字符。',
                parent=self,
            )
            return
        if name.lower() == "action_list":
            messagebox.showerror("名称被占用", "action_list 是保留名称，请换一个。", parent=self)
            return

        if self.info is None and config_store.config_path(name).exists():
            messagebox.showerror("配置已存在", f"已存在同名配置 [{name}]，请换一个名称。", parent=self)
            return

        for index, action in enumerate(self.actions, 1):
            if not str(action.get("args", "")).strip():
                if not messagebox.askyesno(
                    "参数为空",
                    f"第 {index} 个操作没有填写参数，应用时可能失败。仍要保存吗？",
                    parent=self,
                ):
                    return
                break

        try:
            config_store.save_config(name, self.actions)
        except Exception as exc:
            messagebox.showerror("保存失败", f"无法保存配置：{exc}", parent=self)
            return

        callback = self.on_saved
        self._close()
        if callback:
            callback(name)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
