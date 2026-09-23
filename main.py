import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import uuid


# ============================================================
# DeskPlan Editor
# v3 - 课表编辑 + 备忘任务系统
#
# 备忘支持：
# - 点击完成 / 取消完成
# - 完成任务排在最上方
# - 完成 24 小时后自动删除
# - 可选日期 / 时间
# - 即将到期（1小时内）显示红色
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "deskplan.json"

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]

PERIODS = [
    ("第1节", "08:00", "08:45"),
    ("第2节", "08:50", "09:35"),
    ("第3节", "10:00", "10:45"),
    ("第4节", "10:50", "11:35"),
    ("第5节", "11:40", "12:25"),
    ("第6节", "13:25", "14:10"),
    ("第7节", "14:15", "15:00"),
    ("第8节", "15:05", "15:50"),
    ("第9节", "16:15", "17:00"),
    ("第10节", "17:05", "17:50"),
    ("第11节", "18:50", "19:35"),
    ("第12节", "19:40", "20:25"),
    ("第13节", "20:30", "21:15"),
]

URGENT_MINUTES = 60
COMPLETED_KEEP_HOURS = 24

# UI
BG = "#F4F5F7"
CARD = "#FFFFFF"
TEXT = "#202124"
SUBTEXT = "#6B7280"
LINE = "#E5E7EB"
ACCENT = "#3B82F6"
ACCENT_DARK = "#2563EB"
DANGER = "#DC2626"
SUCCESS = "#6B7280"
CELL_BG = "#F9FAFB"
CELL_HOVER = "#EEF4FF"
CELL_FILLED = "#EFF6FF"
CELL_FILLED_HOVER = "#DBEAFE"
URGENT_BG = "#FFF1F2"


# ============================================================
# 数据
# ============================================================

def create_default_data():
    return {
        "schedule": {
            day: [{"course": "", "location": ""} for _ in PERIODS]
            for day in WEEKDAYS
        },
        "memos": [],
    }


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def normalize_memo(item):
    """兼容旧版字符串备忘录，并统一成任务对象。"""
    changed = False

    if isinstance(item, str):
        return {
            "id": uuid.uuid4().hex,
            "text": item,
            "due_at": "",
            "completed": False,
            "completed_at": "",
            "created_at": now_iso(),
        }, True

    if not isinstance(item, dict):
        return None, True

    memo = dict(item)

    if not memo.get("id"):
        memo["id"] = uuid.uuid4().hex
        changed = True

    memo["text"] = str(memo.get("text", memo.get("memo", ""))).strip()

    if "due_at" not in memo:
        memo["due_at"] = ""
        changed = True

    if "completed" not in memo:
        memo["completed"] = False
        changed = True

    memo["completed"] = bool(memo["completed"])

    if "completed_at" not in memo:
        memo["completed_at"] = ""
        changed = True

    if "created_at" not in memo or not memo["created_at"]:
        memo["created_at"] = now_iso()
        changed = True

    if memo["completed"] and not memo["completed_at"]:
        memo["completed_at"] = now_iso()
        changed = True

    return memo, changed


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def clean_completed_memos(memos):
    """完成 24 小时后的任务自动消失。"""
    cutoff = datetime.now() - timedelta(hours=COMPLETED_KEEP_HOURS)
    cleaned = []
    changed = False

    for memo in memos:
        if memo.get("completed"):
            completed_at = parse_iso(memo.get("completed_at"))
            if completed_at and completed_at <= cutoff:
                changed = True
                continue
        cleaned.append(memo)

    return cleaned, changed


def normalize_data(raw):
    default = create_default_data()
    changed = False

    if not isinstance(raw, dict):
        return default, True

    schedule = raw.get("schedule")
    if not isinstance(schedule, dict):
        schedule = {}
        changed = True

    for day in WEEKDAYS:
        day_data = schedule.get(day, [])
        if not isinstance(day_data, list):
            day_data = []
            changed = True

        normalized = []
        for index in range(len(PERIODS)):
            info = day_data[index] if index < len(day_data) else {}
            if not isinstance(info, dict):
                info = {}
                changed = True
            normalized.append(
                {
                    "course": str(info.get("course", "")),
                    "location": str(info.get("location", "")),
                }
            )
        default["schedule"][day] = normalized

    raw_memos = raw.get("memos", [])
    if not isinstance(raw_memos, list):
        raw_memos = []
        changed = True

    memos = []
    for item in raw_memos:
        memo, item_changed = normalize_memo(item)
        changed = changed or item_changed
        if memo and memo["text"]:
            memos.append(memo)

    memos, cleaned_changed = clean_completed_memos(memos)
    changed = changed or cleaned_changed

    default["memos"] = memos
    return default, changed


def load_data():
    if not DATA_FILE.exists():
        return create_default_data()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return create_default_data()

    normalized, changed = normalize_data(raw)

    if changed:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with DATA_FILE.open("w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=4)
        except OSError:
            pass

    return normalized


def save_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


data = load_data()


# ============================================================
# 工具函数：备忘
# ============================================================

def memo_due_datetime(memo):
    return parse_iso(memo.get("due_at"))


def memo_is_urgent(memo):
    if memo.get("completed"):
        return False

    due = memo_due_datetime(memo)
    if not due:
        return False

    remaining = due - datetime.now()
    return remaining <= timedelta(minutes=URGENT_MINUTES)


def memo_sort_key(memo):
    """
    用户要求：
    1. 已完成放上边
    2. 未完成放下边

    已完成：最近完成的在最上方
    未完成：有截止时间的按时间排序，无时间的最后
    """
    if memo.get("completed"):
        completed_at = parse_iso(memo.get("completed_at")) or datetime.min
        return (0, -completed_at.timestamp() if completed_at != datetime.min else 0)

    due = memo_due_datetime(memo)
    if due:
        return (1, due.timestamp())

    created = parse_iso(memo.get("created_at")) or datetime.max
    return (2, created.timestamp())


def sorted_memos():
    return sorted(data["memos"], key=memo_sort_key)


def format_due(memo):
    due = memo_due_datetime(memo)
    if not due:
        return "无截止时间"

    now = datetime.now()

    if due.date() == now.date():
        prefix = "今天"
    elif due.date() == (now + timedelta(days=1)).date():
        prefix = "明天"
    else:
        prefix = due.strftime("%m-%d")

    if due < now and not memo.get("completed"):
        return f"已到期 · {prefix} {due.strftime('%H:%M')}"

    return f"{prefix} {due.strftime('%H:%M')}"


def build_due_at(date_text, time_text):
    date_text = date_text.strip()
    time_text = time_text.strip()

    if not date_text and not time_text:
        return ""

    if not date_text:
        date_text = datetime.now().strftime("%Y-%m-%d")

    if not time_text:
        time_text = "23:59"

    try:
        due = datetime.strptime(
            f"{date_text} {time_text}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        raise ValueError("日期请使用 YYYY-MM-DD，时间请使用 HH:MM。")

    return due.isoformat(timespec="minutes")


# ============================================================
# 主窗口
# ============================================================

root = tk.Tk()
root.title("DeskPlan · 课表编辑器")
root.geometry("1360x870")
root.minsize(1160, 760)
root.configure(bg=BG)

style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass

style.configure(
    "Desk.TButton",
    font=("Microsoft YaHei UI", 9),
    padding=(12, 7),
)
style.configure(
    "Accent.TButton",
    font=("Microsoft YaHei UI", 9, "bold"),
    padding=(14, 8),
    foreground="white",
    background=ACCENT,
    borderwidth=0,
)
style.map(
    "Accent.TButton",
    background=[("active", ACCENT_DARK)],
)
style.configure("Desk.TEntry", padding=6)
style.configure("Desk.TCombobox", padding=5)


# ============================================================
# 顶部
# ============================================================

header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=28, pady=(22, 12))

title_block = tk.Frame(header, bg=BG)
title_block.pack(side="left")

tk.Label(
    title_block,
    text="DeskPlan",
    font=("Microsoft YaHei UI", 24, "bold"),
    fg=TEXT,
    bg=BG,
).pack(anchor="w")

tk.Label(
    title_block,
    text="课表与备忘任务编辑器",
    font=("Microsoft YaHei UI", 10),
    fg=SUBTEXT,
    bg=BG,
).pack(anchor="w", pady=(2, 0))

save_state = tk.Label(
    header,
    text="数据已加载",
    font=("Microsoft YaHei UI", 9),
    fg=SUBTEXT,
    bg=BG,
)
save_state.pack(side="right", pady=(10, 0))


def flash_saved(text="已自动保存"):
    save_state.config(text=text, fg=ACCENT)
    root.after(
        1600,
        lambda: save_state.config(text="数据已同步", fg=SUBTEXT)
    )


# ============================================================
# 主内容
# ============================================================

content = tk.Frame(root, bg=BG)
content.pack(fill="both", expand=True, padx=28, pady=(0, 24))
content.grid_columnconfigure(0, weight=4)
content.grid_columnconfigure(1, weight=2)
content.grid_rowconfigure(0, weight=1)


# ============================================================
# 左侧课表
# ============================================================

schedule_card = tk.Frame(
    content,
    bg=CARD,
    highlightbackground=LINE,
    highlightthickness=1,
)
schedule_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

schedule_header = tk.Frame(schedule_card, bg=CARD)
schedule_header.pack(fill="x", padx=20, pady=(18, 12))

tk.Label(
    schedule_header,
    text="本周课表",
    font=("Microsoft YaHei UI", 14, "bold"),
    fg=TEXT,
    bg=CARD,
).pack(side="left")

tk.Label(
    schedule_header,
    text="双击课程格编辑 · 支持一次填写连续多节",
    font=("Microsoft YaHei UI", 9),
    fg=SUBTEXT,
    bg=CARD,
).pack(side="right")

grid_frame = tk.Frame(schedule_card, bg=CARD)
grid_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

grid_frame.grid_columnconfigure(0, minsize=112, weight=0)
for col in range(1, 6):
    grid_frame.grid_columnconfigure(col, weight=1, uniform="day")

for row in range(len(PERIODS) + 1):
    grid_frame.grid_rowconfigure(row, weight=1, uniform="period")

tk.Label(
    grid_frame,
    text="节次 / 时间",
    font=("Microsoft YaHei UI", 9, "bold"),
    fg=SUBTEXT,
    bg=CARD,
).grid(row=0, column=0, sticky="nsew", padx=3, pady=3)

for column, day in enumerate(WEEKDAYS, start=1):
    tk.Label(
        grid_frame,
        text=day,
        font=("Microsoft YaHei UI", 10, "bold"),
        fg=TEXT,
        bg=CARD,
    ).grid(row=0, column=column, sticky="nsew", padx=3, pady=3)


course_cells = {}


def cell_text(day, period_index):
    info = data["schedule"][day][period_index]
    course = info["course"].strip()
    location = info["location"].strip()

    if not course:
        return ""

    return course + (f"\n{location}" if location else "")


def refresh_cell(day, period_index):
    cell = course_cells[(day, period_index)]
    text = cell_text(day, period_index)
    cell.config(
        text=text,
        bg=CELL_FILLED if text else CELL_BG,
        fg=TEXT if text else SUBTEXT,
    )


def refresh_schedule():
    for day in WEEKDAYS:
        for index in range(len(PERIODS)):
            refresh_cell(day, index)


def period_gap_minutes(index_a, index_b):
    end_text = PERIODS[index_a][2]
    start_text = PERIODS[index_b][1]

    eh, em = map(int, end_text.split(":"))
    sh, sm = map(int, start_text.split(":"))

    return sh * 60 + sm - (eh * 60 + em)


def detect_continuous_range(day, period_index):
    info = data["schedule"][day][period_index]
    course = info["course"].strip()
    location = info["location"].strip()

    if not course:
        return period_index, period_index

    start = period_index
    end = period_index

    while start > 0:
        prev = data["schedule"][day][start - 1]
        if (
            prev["course"].strip() == course
            and prev["location"].strip() == location
            and period_gap_minutes(start - 1, start) == 5
        ):
            start -= 1
        else:
            break

    while end < len(PERIODS) - 1:
        nxt = data["schedule"][day][end + 1]
        if (
            nxt["course"].strip() == course
            and nxt["location"].strip() == location
            and period_gap_minutes(end, end + 1) == 5
        ):
            end += 1
        else:
            break

    return start, end


def edit_course(day, period_index):
    info = data["schedule"][day][period_index]
    detected_start, detected_end = detect_continuous_range(day, period_index)

    win = tk.Toplevel(root)
    win.title(f"编辑课程 · {day}")
    win.geometry("500x440")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    card = tk.Frame(
        win,
        bg=CARD,
        highlightbackground=LINE,
        highlightthickness=1,
    )
    card.pack(fill="both", expand=True, padx=18, pady=18)

    tk.Label(
        card,
        text="编辑课程",
        font=("Microsoft YaHei UI", 17, "bold"),
        fg=TEXT,
        bg=CARD,
    ).pack(anchor="w", padx=22, pady=(20, 2))

    tk.Label(
        card,
        text=f"{day} · 可一次填写多节连续课程",
        font=("Microsoft YaHei UI", 9),
        fg=SUBTEXT,
        bg=CARD,
    ).pack(anchor="w", padx=22, pady=(0, 18))

    form = tk.Frame(card, bg=CARD)
    form.pack(fill="x", padx=22)
    form.grid_columnconfigure(1, weight=1)

    def form_label(row, text):
        tk.Label(
            form,
            text=text,
            font=("Microsoft YaHei UI", 9),
            fg=SUBTEXT,
            bg=CARD,
            anchor="e",
        ).grid(row=row, column=0, sticky="e", padx=(0, 12), pady=9)

    form_label(0, "课程名称")
    course_entry = ttk.Entry(form, style="Desk.TEntry")
    course_entry.grid(row=0, column=1, sticky="ew", pady=9)
    course_entry.insert(0, info["course"])

    form_label(1, "教室")
    location_entry = ttk.Entry(form, style="Desk.TEntry")
    location_entry.grid(row=1, column=1, sticky="ew", pady=9)
    location_entry.insert(0, info["location"])

    period_names = [
        f"{name}  {start}-{end}"
        for name, start, end in PERIODS
    ]

    form_label(2, "开始节次")
    start_combo = ttk.Combobox(
        form,
        values=period_names,
        state="readonly",
        style="Desk.TCombobox",
    )
    start_combo.grid(row=2, column=1, sticky="ew", pady=9)
    start_combo.current(detected_start)

    form_label(3, "结束节次")
    end_combo = ttk.Combobox(
        form,
        values=period_names,
        state="readonly",
        style="Desk.TCombobox",
    )
    end_combo.grid(row=3, column=1, sticky="ew", pady=9)
    end_combo.current(detected_end)

    tk.Label(
        card,
        text="提示：同一课程跨多节时，只需选择开始和结束节次。",
        font=("Microsoft YaHei UI", 8),
        fg=SUBTEXT,
        bg=CARD,
        anchor="w",
    ).pack(fill="x", padx=22, pady=(12, 0))

    buttons = tk.Frame(card, bg=CARD)
    buttons.pack(fill="x", padx=22, pady=(20, 18))

    def save_course():
        start_index = start_combo.current()
        end_index = end_combo.current()

        if end_index < start_index:
            messagebox.showwarning(
                "节次范围错误",
                "结束节次不能早于开始节次。",
                parent=win
            )
            return

        course = course_entry.get().strip()
        location = location_entry.get().strip()

        for index in range(start_index, end_index + 1):
            data["schedule"][day][index]["course"] = course
            data["schedule"][day][index]["location"] = location

        save_data()
        refresh_schedule()
        flash_saved("课程已保存")
        win.destroy()

    def clear_course():
        start_index = start_combo.current()
        end_index = end_combo.current()

        if end_index < start_index:
            start_index, end_index = end_index, start_index

        for index in range(start_index, end_index + 1):
            data["schedule"][day][index]["course"] = ""
            data["schedule"][day][index]["location"] = ""

        save_data()
        refresh_schedule()
        flash_saved("课程已清空")
        win.destroy()

    ttk.Button(
        buttons,
        text="保存课程",
        style="Accent.TButton",
        command=save_course,
    ).pack(side="left")

    ttk.Button(
        buttons,
        text="清空所选节次",
        style="Desk.TButton",
        command=clear_course,
    ).pack(side="left", padx=8)

    ttk.Button(
        buttons,
        text="取消",
        style="Desk.TButton",
        command=win.destroy,
    ).pack(side="right")

    course_entry.focus_set()
    win.bind("<Return>", lambda event: save_course())
    win.bind("<Escape>", lambda event: win.destroy())


for index, (period_name, start_time, end_time) in enumerate(PERIODS):
    row = index + 1

    time_box = tk.Frame(grid_frame, bg=CARD)
    time_box.grid(row=row, column=0, sticky="nsew", padx=3, pady=3)

    tk.Label(
        time_box,
        text=f"{index + 1:02d}",
        font=("Microsoft YaHei UI", 10, "bold"),
        fg=TEXT,
        bg=CARD,
    ).pack(anchor="w", padx=8, pady=(5, 0))

    tk.Label(
        time_box,
        text=f"{start_time}–{end_time}",
        font=("Microsoft YaHei UI", 8),
        fg=SUBTEXT,
        bg=CARD,
    ).pack(anchor="w", padx=8, pady=(0, 5))

    for day_column, day in enumerate(WEEKDAYS, start=1):
        cell = tk.Label(
            grid_frame,
            text="",
            font=("Microsoft YaHei UI", 9),
            fg=TEXT,
            bg=CELL_BG,
            justify="center",
            anchor="center",
            cursor="hand2",
            relief="flat",
            bd=0,
        )

        cell.grid(
            row=row,
            column=day_column,
            sticky="nsew",
            padx=3,
            pady=3,
            ipadx=5,
            ipady=5,
        )

        course_cells[(day, index)] = cell

        def on_enter(event, d=day, i=index):
            event.widget.config(
                bg=CELL_FILLED_HOVER if cell_text(d, i) else CELL_HOVER
            )

        def on_leave(event, d=day, i=index):
            event.widget.config(
                bg=CELL_FILLED if cell_text(d, i) else CELL_BG
            )

        cell.bind("<Enter>", on_enter)
        cell.bind("<Leave>", on_leave)
        cell.bind(
            "<Double-Button-1>",
            lambda event, d=day, i=index: edit_course(d, i),
        )

refresh_schedule()


# ============================================================
# 右侧：备忘任务
# ============================================================

memo_card = tk.Frame(
    content,
    bg=CARD,
    highlightbackground=LINE,
    highlightthickness=1,
)
memo_card.grid(row=0, column=1, sticky="nsew")
memo_card.grid_columnconfigure(0, weight=1)
memo_card.grid_rowconfigure(3, weight=1)

memo_header = tk.Frame(memo_card, bg=CARD)
memo_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

tk.Label(
    memo_header,
    text="备忘任务",
    font=("Microsoft YaHei UI", 14, "bold"),
    fg=TEXT,
    bg=CARD,
).pack(anchor="w")

tk.Label(
    memo_header,
    text="点击圆圈切换完成 · 完成后保留 24 小时",
    font=("Microsoft YaHei UI", 8),
    fg=SUBTEXT,
    bg=CARD,
).pack(anchor="w", pady=(2, 0))


# 输入
memo_input = tk.Frame(memo_card, bg=CARD)
memo_input.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
memo_input.grid_columnconfigure(0, weight=1)

memo_entry = ttk.Entry(memo_input, style="Desk.TEntry")
memo_entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))

date_entry = ttk.Entry(memo_input, style="Desk.TEntry", width=13)
date_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
date_entry.insert(0, "")

time_entry = ttk.Entry(memo_input, style="Desk.TEntry", width=8)
time_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6))

add_button = ttk.Button(
    memo_input,
    text="添加",
    style="Accent.TButton",
)
add_button.grid(row=1, column=2, sticky="e")

hint_frame = tk.Frame(memo_card, bg=CARD)
hint_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))

tk.Label(
    hint_frame,
    text="日期 YYYY-MM-DD（可选）",
    font=("Microsoft YaHei UI", 7),
    fg=SUBTEXT,
    bg=CARD,
).pack(side="left")

tk.Label(
    hint_frame,
    text="时间 HH:MM（可选）",
    font=("Microsoft YaHei UI", 7),
    fg=SUBTEXT,
    bg=CARD,
).pack(side="right")


# 可滚动任务列表
memo_canvas_holder = tk.Frame(memo_card, bg=CARD)
memo_canvas_holder.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 8))
memo_canvas_holder.grid_columnconfigure(0, weight=1)
memo_canvas_holder.grid_rowconfigure(0, weight=1)

memo_canvas = tk.Canvas(
    memo_canvas_holder,
    bg=CARD,
    highlightthickness=0,
)
memo_canvas.grid(row=0, column=0, sticky="nsew")

memo_scrollbar = ttk.Scrollbar(
    memo_canvas_holder,
    orient="vertical",
    command=memo_canvas.yview
)
memo_scrollbar.grid(row=0, column=1, sticky="ns")

memo_canvas.configure(yscrollcommand=memo_scrollbar.set)

memo_list_frame = tk.Frame(memo_canvas, bg=CARD)
memo_window_id = memo_canvas.create_window(
    (0, 0),
    window=memo_list_frame,
    anchor="nw"
)


def sync_memo_canvas(event=None):
    memo_canvas.configure(scrollregion=memo_canvas.bbox("all"))
    memo_canvas.itemconfigure(memo_window_id, width=memo_canvas.winfo_width())


memo_list_frame.bind("<Configure>", sync_memo_canvas)
memo_canvas.bind("<Configure>", sync_memo_canvas)


def find_memo(memo_id):
    for memo in data["memos"]:
        if memo.get("id") == memo_id:
            return memo
    return None


def toggle_memo(memo_id):
    memo = find_memo(memo_id)
    if not memo:
        return

    memo["completed"] = not memo.get("completed", False)
    memo["completed_at"] = now_iso() if memo["completed"] else ""

    save_data()
    refresh_memos()
    flash_saved("任务状态已更新")


def delete_memo(memo_id):
    data["memos"] = [
        memo for memo in data["memos"]
        if memo.get("id") != memo_id
    ]
    save_data()
    refresh_memos()
    flash_saved("任务已删除")


def edit_memo(memo_id):
    memo = find_memo(memo_id)
    if not memo:
        return

    win = tk.Toplevel(root)
    win.title("编辑备忘")
    win.geometry("430x300")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    card = tk.Frame(
        win,
        bg=CARD,
        highlightbackground=LINE,
        highlightthickness=1
    )
    card.pack(fill="both", expand=True, padx=18, pady=18)

    tk.Label(
        card,
        text="编辑备忘",
        font=("Microsoft YaHei UI", 16, "bold"),
        fg=TEXT,
        bg=CARD,
    ).pack(anchor="w", padx=20, pady=(18, 14))

    edit_text = ttk.Entry(card, style="Desk.TEntry")
    edit_text.pack(fill="x", padx=20)
    edit_text.insert(0, memo["text"])

    due = memo_due_datetime(memo)

    fields = tk.Frame(card, bg=CARD)
    fields.pack(fill="x", padx=20, pady=12)

    edit_date = ttk.Entry(fields, style="Desk.TEntry")
    edit_date.pack(side="left", fill="x", expand=True, padx=(0, 6))

    edit_time = ttk.Entry(fields, style="Desk.TEntry", width=10)
    edit_time.pack(side="left")

    if due:
        edit_date.insert(0, due.strftime("%Y-%m-%d"))
        edit_time.insert(0, due.strftime("%H:%M"))

    buttons = tk.Frame(card, bg=CARD)
    buttons.pack(fill="x", padx=20, pady=(8, 16))

    def save_edit():
        text = edit_text.get().strip()
        if not text:
            return

        try:
            due_at = build_due_at(edit_date.get(), edit_time.get())
        except ValueError as error:
            messagebox.showwarning("时间格式错误", str(error), parent=win)
            return

        memo["text"] = text
        memo["due_at"] = due_at
        save_data()
        refresh_memos()
        flash_saved("备忘已修改")
        win.destroy()

    ttk.Button(
        buttons,
        text="保存",
        style="Accent.TButton",
        command=save_edit
    ).pack(side="left")

    ttk.Button(
        buttons,
        text="取消",
        style="Desk.TButton",
        command=win.destroy
    ).pack(side="right")

    edit_text.focus_set()


def refresh_memos():
    global data

    # 每次刷新都清掉完成满 24h 的任务
    cleaned, changed = clean_completed_memos(data["memos"])
    if changed:
        data["memos"] = cleaned
        save_data()

    for child in memo_list_frame.winfo_children():
        child.destroy()

    memos = sorted_memos()

    if not memos:
        tk.Label(
            memo_list_frame,
            text="暂无备忘任务",
            font=("Microsoft YaHei UI", 10),
            fg=SUBTEXT,
            bg=CARD,
        ).pack(anchor="w", pady=12)
        sync_memo_canvas()
        return

    for memo in memos:
        completed = memo.get("completed", False)
        urgent = memo_is_urgent(memo)

        row_bg = URGENT_BG if urgent else CARD

        row = tk.Frame(
            memo_list_frame,
            bg=row_bg,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        row.pack(fill="x", pady=4)

        status = tk.Label(
            row,
            text="✓" if completed else "○",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=SUCCESS if completed else (DANGER if urgent else ACCENT),
            bg=row_bg,
            cursor="hand2",
            width=2,
        )
        status.pack(side="left", padx=(8, 4), pady=9)

        middle = tk.Frame(row, bg=row_bg)
        middle.pack(side="left", fill="x", expand=True, pady=7)

        tk.Label(
            middle,
            text=memo["text"],
            font=("Microsoft YaHei UI", 9),
            fg=SUBTEXT if completed else (DANGER if urgent else TEXT),
            bg=row_bg,
            anchor="w",
            justify="left",
            wraplength=230,
        ).pack(fill="x", anchor="w")

        tk.Label(
            middle,
            text=("已完成 · " if completed else "") + format_due(memo),
            font=("Microsoft YaHei UI", 7),
            fg=SUBTEXT if completed else (DANGER if urgent else SUBTEXT),
            bg=row_bg,
            anchor="w",
        ).pack(fill="x", anchor="w", pady=(2, 0))

        actions = tk.Frame(row, bg=row_bg)
        actions.pack(side="right", padx=5)

        edit_label = tk.Label(
            actions,
            text="编辑",
            font=("Microsoft YaHei UI", 7),
            fg=SUBTEXT,
            bg=row_bg,
            cursor="hand2",
        )
        edit_label.pack(pady=(6, 2))

        delete_label = tk.Label(
            actions,
            text="删除",
            font=("Microsoft YaHei UI", 7),
            fg=DANGER,
            bg=row_bg,
            cursor="hand2",
        )
        delete_label.pack(pady=(2, 6))

        status.bind(
            "<Button-1>",
            lambda event, mid=memo["id"]: toggle_memo(mid)
        )
        edit_label.bind(
            "<Button-1>",
            lambda event, mid=memo["id"]: edit_memo(mid)
        )
        delete_label.bind(
            "<Button-1>",
            lambda event, mid=memo["id"]: delete_memo(mid)
        )

    sync_memo_canvas()


def add_memo():
    text = memo_entry.get().strip()

    if not text:
        return

    try:
        due_at = build_due_at(date_entry.get(), time_entry.get())
    except ValueError as error:
        messagebox.showwarning("时间格式错误", str(error), parent=root)
        return

    data["memos"].append(
        {
            "id": uuid.uuid4().hex,
            "text": text,
            "due_at": due_at,
            "completed": False,
            "completed_at": "",
            "created_at": now_iso(),
        }
    )

    save_data()

    memo_entry.delete(0, tk.END)
    date_entry.delete(0, tk.END)
    time_entry.delete(0, tk.END)

    refresh_memos()
    flash_saved("备忘已添加")


add_button.config(command=add_memo)
memo_entry.bind("<Return>", lambda event: add_memo())

refresh_memos()


def periodic_memo_cleanup():
    refresh_memos()
    root.after(60_000, periodic_memo_cleanup)


root.after(60_000, periodic_memo_cleanup)


def on_close():
    save_data()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
