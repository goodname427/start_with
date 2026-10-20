"""版本管理页：上传配置、拉取、历史查看与回退。"""
import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from common import git_service
from gui import theme

sp = theme.sp
logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "M": "修改",
    "A": "新增",
    "D": "删除",
    "R": "重命名",
    "C": "复制",
    "??": "未跟踪",
    "MM": "修改",
    "AM": "新增",
    "AD": "新增后删除",
    "MD": "修改后删除",
}


class VersionPanel(tk.Frame):
    def __init__(self, master, on_log, on_status, on_configs_changed):
        super().__init__(master, bg=theme.BG)
        self.on_log = on_log
        self.on_status = on_status
        self.on_configs_changed = on_configs_changed

        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._commits: dict[str, git_service.GitCommit] = {}
        self._last_status: git_service.ConfigStatus | None = None

        self._build()
        self._poll()
        self.refresh()

    # ------------------------------------------------------------------ 界面

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_status_card()
        self._build_upload_card()
        self._build_history_card()

    def _build_status_card(self) -> None:
        card = theme.make_card(self)
        card.grid(row=0, column=0, sticky="ew", padx=sp(12), pady=(sp(12), sp(10)))
        card.columnconfigure(0, weight=1)

        head = tk.Frame(card, bg=theme.CARD)
        head.grid(row=0, column=0, sticky="ew", padx=sp(14), pady=(sp(11), sp(4)))
        tk.Label(head, text="仓库状态", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(side="left")
        self.branch_label = tk.Label(head, text="", bg=theme.CARD, fg=theme.ACCENT, font=theme.FONT_UI_BOLD)
        self.branch_label.pack(side="left", padx=sp(10))
        self.activity_label = tk.Label(head, text="", bg=theme.CARD, fg=theme.MUTED, font=theme.FONT_SMALL)
        self.activity_label.pack(side="right")

        self.status_label = tk.Label(
            card,
            text="正在读取仓库状态…",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_UI,
            anchor="w",
            justify="left",
            wraplength=sp(820),
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=sp(14), pady=(0, sp(2)))

        self.files_label = tk.Label(
            card,
            text="",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_MONO,
            anchor="w",
            justify="left",
            wraplength=sp(820),
        )
        self.files_label.grid(row=2, column=0, sticky="ew", padx=sp(14), pady=(sp(2), sp(4)))

        actions = tk.Frame(card, bg=theme.CARD)
        actions.grid(row=3, column=0, sticky="w", padx=sp(14), pady=(sp(4), sp(12)))
        self.btn_refresh = theme.ghost_button(actions, "刷新状态", self.refresh)
        self.btn_refresh.pack(side="left")
        self.btn_pull = theme.ghost_button(actions, "拉取最新", self._on_pull)
        self.btn_pull.pack(side="left", padx=sp((8, 0)))
        self.btn_discard = theme.ghost_button(actions, "撤销未提交修改", self._on_discard)
        self.btn_discard.pack(side="left", padx=sp((8, 0)))

    def _build_upload_card(self) -> None:
        card = theme.make_card(self)
        card.grid(row=1, column=0, sticky="ew", padx=sp(12), pady=(0, sp(10)))
        card.columnconfigure(1, weight=1)

        head = tk.Frame(card, bg=theme.CARD)
        head.grid(row=0, column=0, columnspan=3, sticky="ew", padx=sp(14), pady=(sp(11), sp(2)))
        tk.Label(head, text="上传配置", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(side="left")
        tk.Label(
            head,
            text="仅提交 config 目录，提交后自动推送到远程",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left", padx=sp(10))

        tk.Label(card, text="提交说明", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_UI).grid(
            row=1, column=0, sticky="w", padx=sp((14, 10)), pady=sp(6)
        )
        self.message_var = tk.StringVar(master=self, value=self._default_message())
        self.message_entry = ttk.Entry(card, textvariable=self.message_var)
        self.message_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=sp((0, 14)), pady=sp(6))

        actions = tk.Frame(card, bg=theme.CARD)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", padx=sp(14), pady=(sp(2), sp(12)))
        self.btn_upload = theme.accent_button(actions, "上传配置（提交并推送）", self._on_upload)
        self.btn_upload.pack(side="left")
        tk.Label(
            actions,
            text="回退前建议先上传当前配置，误操作也能从历史中找回",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="left", padx=sp(12))

    def _build_history_card(self) -> None:
        card = theme.make_card(self)
        card.grid(row=2, column=0, sticky="nsew", padx=sp(12), pady=(0, sp(12)))
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)

        head = tk.Frame(card, bg=theme.CARD)
        head.grid(row=0, column=0, sticky="ew", padx=sp(14), pady=(sp(11), sp(6)))
        tk.Label(head, text="配置历史", bg=theme.CARD, fg=theme.TEXT, font=theme.FONT_SECTION).pack(side="left")
        self.history_count_label = tk.Label(head, text="", bg=theme.CARD, fg=theme.MUTED, font=theme.FONT_SMALL)
        self.history_count_label.pack(side="left", padx=sp(10))
        tk.Label(
            head,
            text="历史只包含修改过 config 目录的提交",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).pack(side="right")

        tree_wrap = tk.Frame(card, bg=theme.CARD)
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=sp(14), pady=(0, sp(6)))
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.history_tree = ttk.Treeview(
            tree_wrap,
            columns=("hash", "date", "author", "message"),
            show="headings",
            selectmode="browse",
        )
        columns = (
            ("hash", "版本", sp(90), "w", False, sp(70)),
            ("date", "时间", sp(160), "w", False, sp(120)),
            ("author", "作者", sp(120), "w", False, sp(80)),
            ("message", "说明", sp(520), "w", True, sp(200)),
        )
        for key, title, width, anchor, stretch, minwidth in columns:
            self.history_tree.heading(key, text=title)
            self.history_tree.column(key, width=width, minwidth=minwidth, anchor=anchor, stretch=stretch)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.history_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.history_tree.configure(yscrollcommand=scroll.set)
        self.history_tree.bind("<<TreeviewSelect>>", self._on_history_selected)
        self.history_tree.bind("<Double-1>", lambda _event: self._on_rollback())

        footer = tk.Frame(card, bg=theme.CARD)
        footer.grid(row=2, column=0, sticky="ew", padx=sp(14), pady=(0, sp(12)))
        self.history_hint = tk.Label(
            footer,
            text="选中一条记录后可回退到该版本。",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
        )
        self.history_hint.pack(side="left")
        self.btn_rollback = theme.ghost_button(footer, "回退到选中版本", self._on_rollback)
        self.btn_rollback.pack(side="right")
        self.btn_rollback.configure(state="disabled")

    @staticmethod
    def _default_message() -> str:
        return f"更新配置 {datetime.now():%Y-%m-%d %H:%M}"

    # ------------------------------------------------------------------ 异步调度

    def _poll(self) -> None:
        try:
            while True:
                try:
                    kind, payload = self._queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._handle_event(kind, payload)
                except Exception:
                    logger.exception("处理版本管理事件失败: %s", kind)
        finally:
            try:
                self.after(150, self._poll)
            except tk.TclError:
                pass

    def _handle_event(self, kind: str, payload) -> None:
        if kind == "refresh_ok":
            self._apply_refresh(payload)
            self._set_busy(False)
            return
        if kind == "refresh_error":
            self._last_status = None
            self._commits = {}
            self.history_tree.delete(*self.history_tree.get_children())
            self.history_count_label.configure(text="")
            self._set_busy(False)
            message = self._friendly_error(str(payload))
            self.branch_label.configure(text="")
            self.status_label.configure(text="无法读取仓库状态", fg=theme.DANGER)
            self.files_label.configure(text=message, fg=theme.DANGER)
            self.history_hint.configure(text="Git 不可用或当前目录不是仓库。")
            self.on_log(f"版本管理不可用：{message}", "error")
            return

        if kind.endswith("_ok"):
            self._set_busy(False)
            message = str(payload)
            action = kind[:-3]
            self.on_log(message, "success")
            self.on_status(message)
            self._info("操作完成", message)
            self._after_mutation(action)
            return

        if kind.endswith("_error"):
            self._set_busy(False)
            message = self._friendly_error(str(payload))
            self.on_log(f"版本管理操作失败：{message}", "error")
            self.on_status("版本管理操作失败")
            self._error("操作失败", message)
            self._after_mutation(kind[:-6])
            return

    def _after_mutation(self, action: str) -> None:
        if action == "upload":
            self.message_var.set(self._default_message())
        try:
            self.on_configs_changed()
        except Exception:
            pass
        self.refresh()

    def _info(self, title: str, message: str) -> None:
        try:
            messagebox.showinfo(title, message, parent=self.winfo_toplevel())
        except tk.TclError:
            pass

    def _error(self, title: str, message: str) -> None:
        if len(message) > 1000:
            message = message[:1000] + "…"
        try:
            messagebox.showerror(title, message, parent=self.winfo_toplevel())
        except tk.TclError:
            pass

    @staticmethod
    def _friendly_error(message: str) -> str:
        lower = message.lower()
        if "not a git repository" in lower:
            return "当前目录不是 Git 仓库，无法使用版本管理。"
        return message or "未知错误"

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        self.activity_label.configure(text=text if busy else "")
        if busy:
            for button in (self.btn_refresh, self.btn_pull, self.btn_discard, self.btn_upload, self.btn_rollback):
                button.configure(state="disabled")
        else:
            self.btn_refresh.configure(state="normal")
            self._apply_button_states()

    def _apply_button_states(self) -> None:
        if self._busy:
            return
        status = self._last_status
        has_changes = bool(status and status.changes)
        self.btn_upload.configure(state="normal" if has_changes else "disabled")
        self.btn_discard.configure(state="normal" if has_changes else "disabled")
        self.btn_pull.configure(state="normal" if (status and status.has_upstream) else "disabled")
        self.btn_rollback.configure(
            state="normal" if (status is not None and self.history_tree.selection() and not self._busy) else "disabled"
        )

    # ------------------------------------------------------------------ 刷新

    def refresh(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "正在读取仓库状态…")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            result = {
                "status": git_service.status(),
                "commits": git_service.log_config(),
            }
            self._queue.put(("refresh_ok", result))
        except Exception as exc:
            self._queue.put(("refresh_error", str(exc)))

    def _apply_refresh(self, payload: dict) -> None:
        status: git_service.ConfigStatus = payload["status"]
        commits: list[git_service.GitCommit] = payload["commits"]
        self._last_status = status

        self.branch_label.configure(text=f"分支 {status.branch}" if status.branch else "")
        parts = [f"待上传 {len(status.changes)} 个配置文件" if status.changes else "工作区干净"]
        if status.has_upstream:
            parts.append(f"领先 {status.ahead} / 落后 {status.behind}")
        else:
            parts.append("未设置远程跟踪分支")
        if status.remote:
            parts.append(status.remote)
        self.status_label.configure(text=" · ".join(parts), fg=theme.MUTED)

        if status.changes:
            names = []
            for line in status.changes[:8]:
                code = line[:2].strip()
                path = line[3:].strip() if len(line) > 3 else line.strip()
                names.append(f"{path}（{STATUS_LABELS.get(code, code or '变更')}）")
            if len(status.changes) > 8:
                names.append(f"… 另有 {len(status.changes) - 8} 个文件")
            self.files_label.configure(text="\n".join(names), fg=theme.WARN)
        else:
            self.files_label.configure(text="config 目录没有未提交的改动。", fg=theme.MUTED)

        self._populate_history(commits)

    def _populate_history(self, commits: list[git_service.GitCommit]) -> None:
        self.history_tree.delete(*self.history_tree.get_children())
        self._commits = {commit.full_hash: commit for commit in commits}
        for commit in commits:
            self.history_tree.insert(
                "",
                "end",
                iid=commit.full_hash,
                values=(commit.short_hash, commit.date, commit.author, commit.subject),
            )
        self.history_count_label.configure(text=f"{len(commits)} 条记录")
        self.history_hint.configure(
            text="选中一条记录后可回退到该版本。" if commits else "暂无配置提交记录。"
        )
        self._apply_button_states()

    def _on_history_selected(self, _event=None) -> None:
        self._apply_button_states()

    # ------------------------------------------------------------------ 操作

    def _on_upload(self) -> None:
        if self._busy:
            return
        message = self.message_var.get().strip()
        if not message:
            messagebox.showwarning("缺少提交说明", "请先填写提交说明。", parent=self.winfo_toplevel())
            return

        self._set_busy(True, "正在提交并推送…")
        threading.Thread(target=self._upload_worker, args=(message,), daemon=True).start()

    def _upload_worker(self, message: str) -> None:
        try:
            self._queue.put(("upload_ok", git_service.commit_and_push(message)))
        except Exception as exc:
            self._queue.put(("upload_error", str(exc)))

    def _on_rollback(self) -> None:
        if self._busy:
            return
        selection = self.history_tree.selection()
        if not selection:
            return
        commit = self._commits.get(selection[0])
        if commit is None:
            return

        confirmed = messagebox.askyesno(
            "回退配置",
            "将把 config 目录恢复为该版本的内容：\n\n"
            f"{commit.short_hash}  {commit.date}\n{commit.subject}\n\n"
            "之后新增的已提交配置会被删除，未提交的新文件会保留。\n"
            "回退完成后会自动提交并推送。是否继续？",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._set_busy(True, f"正在回退到 {commit.short_hash}…")
        threading.Thread(target=self._rollback_worker, args=(commit.full_hash,), daemon=True).start()

    def _rollback_worker(self, commit_hash: str) -> None:
        try:
            self._queue.put(("rollback_ok", git_service.rollback_to(commit_hash)))
        except Exception as exc:
            self._queue.put(("rollback_error", str(exc)))

    def _on_pull(self) -> None:
        if self._busy:
            return
        confirmed = messagebox.askyesno(
            "拉取最新内容",
            "将拉取远程仓库的最新内容（可能同时更新代码与配置），是否继续？",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._set_busy(True, "正在拉取最新内容…")
        threading.Thread(target=self._pull_worker, daemon=True).start()

    def _pull_worker(self) -> None:
        try:
            self._queue.put(("pull_ok", git_service.pull_latest()))
        except Exception as exc:
            self._queue.put(("pull_error", str(exc)))

    def _on_discard(self) -> None:
        if self._busy:
            return
        confirmed = messagebox.askyesno(
            "撤销未提交修改",
            "将丢弃 config 目录中所有未提交的修改，是否继续？\n\n未跟踪的新文件不会被删除。",
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        self._set_busy(True, "正在撤销修改…")
        threading.Thread(target=self._discard_worker, daemon=True).start()

    def _discard_worker(self) -> None:
        try:
            self._queue.put(("discard_ok", git_service.discard_changes()))
        except Exception as exc:
            self._queue.put(("discard_error", str(exc)))
