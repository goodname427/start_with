"""界面配色、字体、DPI 缩放与通用控件。"""
import tkinter as tk
from tkinter import ttk

BG = "#eef1f7"
CARD = "#ffffff"
CARD_SOFT = "#f7f9fc"
BORDER = "#dde3ef"
TEXT = "#1e2431"
MUTED = "#6b7280"
ACCENT = "#2f6fed"
ACCENT_DARK = "#1f57c8"
ACCENT_SOFT = "#e7efff"
HEADER_BG = "#131b2c"
HEADER_MUTED = "#8fa0bb"
SUCCESS = "#0f9d58"
DANGER = "#d93025"
WARN = "#b45309"
LOG_BG = "#0c1424"
LOG_FG = "#a9bdd8"

FONT_FAMILY = "Microsoft YaHei UI"
FONT_UI = (FONT_FAMILY, 10)
FONT_UI_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SECTION = (FONT_FAMILY, 11, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 17, "bold")
FONT_DIALOG_TITLE = (FONT_FAMILY, 13, "bold")
FONT_MONO = ("Consolas", 9)

BASE_WINDOW_WIDTH = 1020
BASE_WINDOW_HEIGHT = 680

SCALE = 1.0


def init_scale(root: tk.Misc) -> None:
    """根据系统 DPI 计算缩放比例，并让 Tk 的字体按同样比例渲染。"""
    global SCALE

    try:
        dpi = float(root.winfo_fpixels("1i"))
    except tk.TclError:
        dpi = 96.0

    scale = max(1.0, dpi / 96.0)

    # 小屏幕/高缩放时限制窗口大小，避免超出屏幕
    try:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        cap = min(
            (screen_w - 60) / BASE_WINDOW_WIDTH,
            (screen_h - 120) / BASE_WINDOW_HEIGHT,
        )
        scale = min(scale, max(1.0, cap))
    except tk.TclError:
        pass

    SCALE = round(scale, 2)
    try:
        root.tk.call("tk", "scaling", SCALE * 96.0 / 72.0)
    except tk.TclError:
        pass


def sp(value):
    """把设计稿像素值换算成当前 DPI 下的像素值，支持元组/列表。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(round(value * SCALE))
    if isinstance(value, (tuple, list)):
        return type(value)(sp(item) for item in value)
    return value


def setup_theme(root: tk.Misc) -> None:
    init_scale(root)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(bg=BG)
    root.option_add("*Font", FONT_UI)
    root.option_add("*TCombobox*Listbox.font", FONT_UI)
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_SOFT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_UI)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=FONT_UI)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=FONT_SMALL)
    style.configure("Section.TLabel", background=CARD, foreground=TEXT, font=FONT_SECTION)

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        padding=(sp(14), sp(7)),
        font=FONT_UI_BOLD,
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK), ("disabled", "#a9bbdd")],
        foreground=[("disabled", "#f2f5fb")],
    )

    style.configure(
        "Ghost.TButton",
        background=CARD,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=CARD,
        darkcolor=CARD,
        padding=(sp(12), sp(6)),
        font=FONT_UI,
    )
    style.map(
        "Ghost.TButton",
        background=[("pressed", ACCENT_SOFT), ("active", ACCENT_SOFT)],
        foreground=[("active", ACCENT_DARK), ("disabled", "#a4adbd")],
    )

    style.configure(
        "Danger.TButton",
        background=CARD,
        foreground=DANGER,
        bordercolor="#f0c9c5",
        lightcolor=CARD,
        darkcolor=CARD,
        padding=(sp(12), sp(6)),
        font=FONT_UI,
    )
    style.map("Danger.TButton", background=[("active", "#fdecea"), ("pressed", "#fdecea")])

    style.configure("TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG)
    style.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, focuscolor=CARD)
    style.map("Card.TCheckbutton", background=[("active", CARD)])
    style.configure("TRadiobutton", background=BG, foreground=TEXT, focuscolor=BG)
    style.configure("Card.TRadiobutton", background=CARD, foreground=TEXT, focuscolor=CARD)
    style.map("Card.TRadiobutton", background=[("active", CARD)])

    style.configure("TEntry", padding=(sp(8), sp(5)), fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT)
    style.configure(
        "TCombobox",
        padding=(sp(6), sp(4)),
        fieldbackground=CARD,
        background=CARD,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD)],
        foreground=[("readonly", TEXT)],
        selectbackground=[("readonly", CARD), ("!readonly", ACCENT_SOFT)],
        selectforeground=[("readonly", TEXT), ("!readonly", TEXT)],
    )

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, sp(4), 0, 0))
    style.configure(
        "TNotebook.Tab",
        background="#e2e7f1",
        foreground=MUTED,
        padding=(sp(20), sp(8)),
        font=FONT_UI,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", CARD)],
        foreground=[("selected", ACCENT)],
        lightcolor=[("selected", CARD)],
        darkcolor=[("selected", CARD)],
    )

    style.configure(
        "Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        rowheight=sp(30),
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", "#dbe7ff")],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "Treeview.Heading",
        background="#f1f4fa",
        foreground=MUTED,
        relief="flat",
        font=FONT_UI_BOLD,
        padding=(sp(8), sp(7)),
        borderwidth=0,
    )
    style.map("Treeview.Heading", background=[("active", "#e8edf7")])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("TScrollbar", background="#c9d2e3", troughcolor=CARD, borderwidth=0, arrowsize=sp(12))
    style.configure("TSeparator", background=BORDER)


def make_card(parent: tk.Misc, **kwargs) -> tk.Frame:
    options = {
        "bg": CARD,
        "bd": 0,
        "takefocus": 0,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": BORDER,
    }
    options.update(kwargs)
    return tk.Frame(parent, **options)


def accent_button(parent: tk.Misc, text: str, command=None, **kwargs) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style="Accent.TButton", **kwargs)


def ghost_button(parent: tk.Misc, text: str, command=None, **kwargs) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style="Ghost.TButton", **kwargs)


def dialog_header(parent: tk.Misc, title: str, subtitle: str = "") -> tk.Frame:
    header = tk.Frame(parent, bg=HEADER_BG)
    tk.Label(header, text=title, bg=HEADER_BG, fg="#ffffff", font=FONT_DIALOG_TITLE).pack(
        anchor="w", padx=sp(20), pady=(sp(14), 0)
    )
    if subtitle:
        tk.Label(header, text=subtitle, bg=HEADER_BG, fg=HEADER_MUTED, font=FONT_SMALL).pack(
            anchor="w", padx=sp(20), pady=(sp(3), sp(13))
        )
    else:
        tk.Frame(header, bg=HEADER_BG, height=sp(12)).pack()
    return header


def center_window(
    win: tk.Toplevel,
    parent: tk.Misc | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """width/height 传入设计稿尺寸，内部会自动按 DPI 缩放。"""
    win.update_idletasks()
    width = sp(width) if width is not None else win.winfo_width()
    height = sp(height) if height is not None else win.winfo_height()

    if parent is not None and parent.winfo_exists():
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + (pw - width) // 2
        y = py + (ph - height) // 3
    else:
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 3

    x = max(0, min(x, win.winfo_screenwidth() - width))
    y = max(0, min(y, win.winfo_screenheight() - height))
    win.geometry(f"{width}x{height}+{x}+{y}")
