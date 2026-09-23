import tkinter as tk
from pathlib import Path
from datetime import datetime, timedelta
import json
import subprocess
import sys
import ctypes
import re
import uuid


# ============================================================
# DeskPlan Desktop Widget
# v8 - 防闪烁刷新版
#
# 备忘支持：
# - 单击任务切换完成状态
# - 已完成任务显示在上方
# - 完成 24 小时后自动消失
# - 显示截止日期/时间
# - 截止前 1 小时及已超时任务显示红色
# ============================================================

VERSION = "v8.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "deskplan.json"
SETTINGS_FILE = DATA_DIR / "widget_settings.json"
MAIN_FILE = BASE_DIR / "main.py"

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

BG_COLOR = "#F0F0F0"

TEXT_COLOR = "#222222"
SECONDARY_COLOR = "#666666"
LIGHT_COLOR = "#9A9A9A"
ENDED_COLOR = "#A3A3A3"
CURRENT_COLOR = "#111111"
FUTURE_COLOR = "#333333"
NEXT_COLOR = "#555555"
DANGER_COLOR = "#D92D20"
COMPLETED_COLOR = "#8A8A8A"


# ============================================================
# JSON / 备忘数据迁移
# ============================================================

def load_json(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def save_json(path, value):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def normalize_memo(item):
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

    if not memo.get("created_at"):
        memo["created_at"] = now_iso()
        changed = True

    if memo["completed"] and not memo["completed_at"]:
        memo["completed_at"] = now_iso()
        changed = True

    return memo, changed


def clean_completed_memos(memos):
    cutoff = datetime.now() - timedelta(hours=COMPLETED_KEEP_HOURS)
    result = []
    changed = False

    for memo in memos:
        if memo.get("completed"):
            completed_at = parse_iso(memo.get("completed_at"))
            if completed_at and completed_at <= cutoff:
                changed = True
                continue

        result.append(memo)

    return result, changed


def load_data():
    data = load_json(
        DATA_FILE,
        {
            "schedule": {},
            "memos": [],
        },
    )

    if not isinstance(data, dict):
        data = {"schedule": {}, "memos": []}

    if not isinstance(data.get("schedule"), dict):
        data["schedule"] = {}

    raw_memos = data.get("memos", [])
    if not isinstance(raw_memos, list):
        raw_memos = []

    memos = []
    changed = False

    for item in raw_memos:
        memo, item_changed = normalize_memo(item)
        changed = changed or item_changed

        if memo and memo["text"]:
            memos.append(memo)

    memos, cleaned_changed = clean_completed_memos(memos)
    changed = changed or cleaned_changed

    data["memos"] = memos

    if changed:
        save_json(DATA_FILE, data)

    return data


# ============================================================
# 时间 / 课表
# ============================================================

def time_to_minutes(text):
    hour, minute = map(int, text.split(":"))
    return hour * 60 + minute


def get_today_name():
    index = datetime.now().weekday()
    return WEEKDAYS[index] if index < 5 else None


def adjacent_gap_minutes(left_index, right_index):
    left_end = time_to_minutes(PERIODS[left_index][2])
    right_start = time_to_minutes(PERIODS[right_index][1])
    return right_start - left_end


def normalize_compare_text(text):
    text = str(text or "")
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def merge_continuous_courses(schedule):
    groups = []

    if not isinstance(schedule, list):
        return groups

    for index in range(min(len(schedule), len(PERIODS))):
        info = schedule[index]

        if not isinstance(info, dict):
            continue

        raw_course = str(info.get("course", "")).strip()
        raw_location = str(info.get("location", "")).strip()

        course_key = normalize_compare_text(raw_course)
        location_key = normalize_compare_text(raw_location)

        if not course_key:
            continue

        if groups:
            previous = groups[-1]

            can_merge = (
                previous["course_key"] == course_key
                and previous["location_key"] == location_key
                and previous["end_index"] + 1 == index
                and adjacent_gap_minutes(previous["end_index"], index) == 5
            )

            if can_merge:
                previous["end_index"] = index
                continue

        groups.append(
            {
                "course": raw_course,
                "location": raw_location,
                "course_key": course_key,
                "location_key": location_key,
                "start_index": index,
                "end_index": index,
            }
        )

    return groups


def group_start_minutes(group):
    return time_to_minutes(PERIODS[group["start_index"]][1])


def group_end_minutes(group):
    return time_to_minutes(PERIODS[group["end_index"]][2])


def group_time_text(group):
    start_time = PERIODS[group["start_index"]][1]
    end_time = PERIODS[group["end_index"]][2]

    if group["start_index"] == group["end_index"]:
        return start_time

    return f"{start_time}–{end_time}"


def get_group_status(group, now_minutes):
    start = group_start_minutes(group)
    end = group_end_minutes(group)

    if now_minutes < start:
        return "future"

    if now_minutes > end:
        return "ended"

    return "current"


# ============================================================
# 备忘排序 / 时间显示
# ============================================================

def memo_due_datetime(memo):
    return parse_iso(memo.get("due_at"))


def memo_is_urgent(memo):
    if memo.get("completed"):
        return False

    due = memo_due_datetime(memo)

    if not due:
        return False

    return (due - datetime.now()) <= timedelta(minutes=URGENT_MINUTES)


def memo_sort_key(memo):
    # 已完成放上边
    if memo.get("completed"):
        completed_at = parse_iso(memo.get("completed_at"))
        stamp = completed_at.timestamp() if completed_at else 0
        return (0, -stamp)

    # 未完成放下边，有时间的越早越靠上
    due = memo_due_datetime(memo)
    if due:
        return (1, due.timestamp())

    created = parse_iso(memo.get("created_at"))
    return (2, created.timestamp() if created else 0)


def format_due(memo):
    due = memo_due_datetime(memo)

    if not due:
        return ""

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


# ============================================================
# 单实例保护
# ============================================================

MUTEX_NAME = "DeskPlan_Desktop_Widget_Single_Instance"
ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.windll.kernel32

mutex_handle = kernel32.CreateMutexW(
    None,
    False,
    MUTEX_NAME
)

if not mutex_handle:
    sys.exit(0)

if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
    kernel32.CloseHandle(mutex_handle)
    sys.exit(0)


# ============================================================
# 主窗口 / 位置
# ============================================================

root = tk.Tk()
root.title("DeskPlan Widget")
root.overrideredirect(True)
root.configure(bg=BG_COLOR)
root.attributes("-topmost", False)

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

default_geometry = {
    "width": max(360, int(screen_width * 0.215)),
    "height": max(760, int(screen_height * 0.78)),
    "x": int(screen_width * 0.768),
    "y": int(screen_height * 0.115),
    "locked": True,
    "alpha": 1.0,
}

settings = load_json(SETTINGS_FILE, default_geometry.copy())

for key, value in default_geometry.items():
    settings.setdefault(key, value)

settings["width"] = min(int(settings["width"]), screen_width)
settings["height"] = min(int(settings["height"]), screen_height)
settings["x"] = max(0, min(int(settings["x"]), screen_width - 120))
settings["y"] = max(0, min(int(settings["y"]), screen_height - 120))
settings["alpha"] = float(settings.get("alpha", 1.0))

root.geometry(
    f'{settings["width"]}x{settings["height"]}'
    f'+{settings["x"]}+{settings["y"]}'
)
root.attributes("-alpha", settings["alpha"])

locked = bool(settings.get("locked", True))
drag_offset_x = 0
drag_offset_y = 0


# ============================================================
# UI
# ============================================================

container = tk.Frame(root, bg=BG_COLOR)
container.pack(fill="both", expand=True)

header = tk.Frame(container, bg=BG_COLOR)
header.pack(fill="x", padx=20, pady=(14, 0))

date_label = tk.Label(
    header,
    text="",
    font=("Microsoft YaHei UI", 15, "bold"),
    fg=TEXT_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
date_label.pack(anchor="w")

week_label = tk.Label(
    header,
    text="",
    font=("Microsoft YaHei UI", 10),
    fg=SECONDARY_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
week_label.pack(anchor="w", pady=(2, 0))


# TODAY
course_title = tk.Label(
    container,
    text="TODAY  今日课程",
    font=("Microsoft YaHei UI", 11, "bold"),
    fg=TEXT_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
course_title.pack(fill="x", padx=20, pady=(24, 7))

course_frame = tk.Frame(container, bg=BG_COLOR)
course_frame.pack(fill="x", padx=20)

course_widgets = []

# 渲染缓存：只有显示内容真的变化时才重建控件，
# 避免每次定时刷新都 destroy/recreate 导致文字闪动。
last_course_signature = None
last_memo_signature = None
last_date_signature = None


# NEXT
next_frame = tk.Frame(container, bg=BG_COLOR)
next_frame.pack(fill="x", padx=20, pady=(10, 0))

next_title_label = tk.Label(
    next_frame,
    text="",
    font=("Microsoft YaHei UI", 8, "bold"),
    fg=LIGHT_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
next_title_label.pack(anchor="w")

next_course_label = tk.Label(
    next_frame,
    text="",
    font=("Microsoft YaHei UI", 9),
    fg=NEXT_COLOR,
    bg=BG_COLOR,
    anchor="w",
    justify="left"
)
next_course_label.pack(fill="x", anchor="w", pady=(2, 0))


# 小猫留白
cat_space = tk.Frame(
    container,
    bg=BG_COLOR,
    height=max(120, int(screen_height * 0.12))
)
cat_space.pack(fill="x")
cat_space.pack_propagate(False)


# TODO
memo_title = tk.Label(
    container,
    text="TODO  待办",
    font=("Microsoft YaHei UI", 11, "bold"),
    fg=TEXT_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
memo_title.pack(fill="x", padx=20, pady=(6, 6))

memo_frame = tk.Frame(container, bg=BG_COLOR)
memo_frame.pack(fill="both", expand=True, padx=20)

memo_widgets = []

status_label = tk.Label(
    container,
    text="",
    font=("Microsoft YaHei UI", 8),
    fg=LIGHT_COLOR,
    bg=BG_COLOR,
    anchor="w"
)
status_label.pack(fill="x", padx=20, pady=(8, 14))


# ============================================================
# 通用
# ============================================================

def destroy_widgets(widgets):
    for widget in widgets:
        try:
            widget.destroy()
        except tk.TclError:
            pass
    widgets.clear()


def build_course_signature(data, today):
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute

    if today is None:
        return ("weekend",)

    schedule = data.get("schedule", {}).get(today, [])
    groups = merge_continuous_courses(schedule)

    group_signature = []

    for group in groups:
        group_signature.append(
            (
                group["course"],
                group["location"],
                group["start_index"],
                group["end_index"],
                get_group_status(group, now_minutes),
            )
        )

    return tuple(group_signature)


def build_memo_signature(data):
    memos = data.get("memos", [])
    if not isinstance(memos, list):
        memos = []

    ordered = sorted(memos, key=memo_sort_key)

    signature = []

    for memo in ordered[:8]:
        signature.append(
            (
                memo.get("id", ""),
                memo.get("text", ""),
                memo.get("due_at", ""),
                bool(memo.get("completed", False)),
                memo.get("completed_at", ""),
                memo_is_urgent(memo),
                format_due(memo),
            )
        )

    return tuple(signature)


def open_editor(event=None):
    if not MAIN_FILE.exists():
        status_label.config(text="未找到 main.py")
        return

    try:
        subprocess.Popen(
            [sys.executable, str(MAIN_FILE)],
            cwd=str(BASE_DIR)
        )
    except OSError:
        status_label.config(text="无法打开课表编辑器")


# ============================================================
# 课程刷新
# ============================================================

def refresh_courses(data, today):
    destroy_widgets(course_widgets)

    next_title_label.config(text="")
    next_course_label.config(text="")

    if today is None:
        label = tk.Label(
            course_frame,
            text="今天没有课程",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w"
        )
        label.pack(fill="x", pady=4)
        course_widgets.append(label)
        return

    schedule = data.get("schedule", {}).get(today, [])
    groups = merge_continuous_courses(schedule)

    if not groups:
        label = tk.Label(
            course_frame,
            text="今天没有课程",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w"
        )
        label.pack(fill="x", pady=4)
        course_widgets.append(label)
        return

    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute

    next_group = None

    for group in groups:
        status = get_group_status(group, now_minutes)

        if status == "future" and next_group is None:
            next_group = group

        row = tk.Frame(course_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)

        time_label = tk.Label(
            row,
            text=group_time_text(group),
            width=12,
            font=("Microsoft YaHei UI", 9),
            fg=ENDED_COLOR if status == "ended" else SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w"
        )
        time_label.pack(side="left", anchor="n")

        if status == "current":
            marker = "●"
            color = CURRENT_COLOR
            font = ("Microsoft YaHei UI", 10, "bold")
        elif status == "ended":
            marker = "✓"
            color = ENDED_COLOR
            font = ("Microsoft YaHei UI", 10)
        else:
            marker = "○"
            color = FUTURE_COLOR
            font = ("Microsoft YaHei UI", 10)

        detail_text = f"{marker}  {group['course']}"

        if group["location"]:
            detail_text += f" · {group['location']}"

        detail_label = tk.Label(
            row,
            text=detail_text,
            font=font,
            fg=color,
            bg=BG_COLOR,
            anchor="w",
            justify="left",
            wraplength=max(160, int(root.winfo_width()) - 150)
        )
        detail_label.pack(side="left", fill="x", expand=True, anchor="n")

        course_widgets.append(row)

    current_group = next(
        (
            group for group in groups
            if get_group_status(group, now_minutes) == "current"
        ),
        None
    )

    if next_group:
        next_title_label.config(text="NEXT  下一节")

        text = f"{group_time_text(next_group)}  {next_group['course']}"

        if next_group["location"]:
            text += f" · {next_group['location']}"

        next_course_label.config(
            text=text,
            wraplength=max(220, int(root.winfo_width()) - 45)
        )

    elif current_group:
        next_title_label.config(text="NEXT")
        next_course_label.config(text="这是今天最后一段课程")
    else:
        next_title_label.config(text="TODAY")
        next_course_label.config(text="今天的课程已经结束")


# ============================================================
# 备忘：点击完成
# ============================================================

def toggle_memo(memo_id):
    data = load_data()

    found = False

    for memo in data.get("memos", []):
        if memo.get("id") == memo_id:
            memo["completed"] = not memo.get("completed", False)
            memo["completed_at"] = now_iso() if memo["completed"] else ""
            found = True
            break

    if found:
        save_json(DATA_FILE, data)
        refresh_widget(force=True)


def bind_memo_click(widget, memo_id):
    def single_click(event):
        toggle_memo(memo_id)
        return "break"

    def double_click(event):
        # 避免双击任务时触发全局“双击打开编辑器”
        return "break"

    widget.bind("<Button-1>", single_click)
    widget.bind("<Double-Button-1>", double_click)


def refresh_memos(data):
    destroy_widgets(memo_widgets)

    memos = data.get("memos", [])
    if not isinstance(memos, list):
        memos = []

    memos = sorted(memos, key=memo_sort_key)

    if not memos:
        label = tk.Label(
            memo_frame,
            text="今天没有待办事项",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w"
        )
        label.pack(fill="x", pady=4)
        memo_widgets.append(label)
        return

    # 控制桌面区域高度，默认最多显示 8 项
    for memo in memos[:8]:
        completed = memo.get("completed", False)
        urgent = memo_is_urgent(memo)

        row = tk.Frame(
            memo_frame,
            bg=BG_COLOR,
            cursor="hand2"
        )
        row.pack(fill="x", pady=3)

        marker_color = (
            COMPLETED_COLOR
            if completed
            else (DANGER_COLOR if urgent else TEXT_COLOR)
        )

        marker = tk.Label(
            row,
            text="✓" if completed else "□",
            width=2,
            font=("Microsoft YaHei UI", 10, "bold"),
            fg=marker_color,
            bg=BG_COLOR,
            anchor="w",
            cursor="hand2"
        )
        marker.pack(side="left", anchor="n")

        middle = tk.Frame(
            row,
            bg=BG_COLOR,
            cursor="hand2"
        )
        middle.pack(side="left", fill="x", expand=True)

        text_label = tk.Label(
            middle,
            text=memo.get("text", ""),
            font=("Microsoft YaHei UI", 10),
            fg=marker_color,
            bg=BG_COLOR,
            anchor="w",
            justify="left",
            wraplength=max(210, int(root.winfo_width()) - 65),
            cursor="hand2"
        )
        text_label.pack(fill="x", anchor="w")

        due_text = format_due(memo)

        if completed:
            due_text = (
                f"已完成 · {due_text}"
                if due_text
                else "已完成 · 24小时后自动移除"
            )

        if due_text:
            due_label = tk.Label(
                middle,
                text=due_text,
                font=("Microsoft YaHei UI", 7),
                fg=marker_color if urgent else LIGHT_COLOR,
                bg=BG_COLOR,
                anchor="w",
                cursor="hand2"
            )
            due_label.pack(fill="x", anchor="w", pady=(1, 0))
        else:
            due_label = None

        for widget in (row, marker, middle, text_label):
            bind_memo_click(widget, memo["id"])

        if due_label:
            bind_memo_click(due_label, memo["id"])

        memo_widgets.append(row)


def update_status():
    if locked:
        status_label.config(
            text="位置已锁定  ·  单击待办切换完成  ·  双击空白处编辑"
        )
    else:
        status_label.config(
            text="位置未锁定  ·  拖动空白处移动  ·  单击待办切换完成"
        )


def refresh_widget(force=False):
    global last_course_signature
    global last_memo_signature
    global last_date_signature

    data = load_data()
    now = datetime.now()
    today = get_today_name()

    # 日期文字只在日期/星期变化时更新
    date_signature = (
        now.strftime("%m月%d日"),
        today if today else "周末",
    )

    if force or date_signature != last_date_signature:
        date_label.config(text=date_signature[0])
        week_label.config(text=date_signature[1])
        last_date_signature = date_signature

    # 课程只有在内容或“已结束/进行中/未开始”状态变化时才重绘
    course_signature = build_course_signature(data, today)

    if force or course_signature != last_course_signature:
        refresh_courses(data, today)
        last_course_signature = course_signature

    # 待办只有在内容、完成状态、时间状态发生变化时才重绘
    memo_signature = build_memo_signature(data)

    if force or memo_signature != last_memo_signature:
        refresh_memos(data)
        last_memo_signature = memo_signature

    update_status()

    # 10 秒检查一次即可；界面不显示秒级倒计时，
    # 没必要每 2 秒整页重绘。
    root.after(10_000, refresh_widget)


# ============================================================
# 位置 / 拖动
# ============================================================

def save_current_settings():
    settings["x"] = root.winfo_x()
    settings["y"] = root.winfo_y()
    settings["width"] = root.winfo_width()
    settings["height"] = root.winfo_height()
    settings["locked"] = locked

    try:
        settings["alpha"] = float(root.attributes("-alpha"))
    except (TypeError, ValueError, tk.TclError):
        settings["alpha"] = 1.0

    save_json(SETTINGS_FILE, settings)


def start_drag(event):
    global drag_offset_x
    global drag_offset_y

    if locked:
        return

    drag_offset_x = event.x_root - root.winfo_x()
    drag_offset_y = event.y_root - root.winfo_y()


def drag_window(event):
    if locked:
        return

    root.geometry(
        f"+{event.x_root - drag_offset_x}+{event.y_root - drag_offset_y}"
    )


def end_drag(event=None):
    if not locked:
        save_current_settings()


def update_drag_cursor():
    root.configure(cursor="arrow" if locked else "fleur")


root.bind_all("<ButtonPress-1>", start_drag, add="+")
root.bind_all("<B1-Motion>", drag_window, add="+")
root.bind_all("<ButtonRelease-1>", end_drag, add="+")


# ============================================================
# 右键菜单
# ============================================================

menu = tk.Menu(root, tearoff=False)


def toggle_lock():
    global locked

    locked = not locked
    save_current_settings()
    update_status()
    update_drag_cursor()

    menu.entryconfig(
        0,
        label="解锁并拖动" if locked else "锁定位置"
    )


def move_by(dx, dy):
    x = max(0, min(root.winfo_x() + dx, screen_width - 120))
    y = max(0, min(root.winfo_y() + dy, screen_height - 120))

    root.geometry(f"+{x}+{y}")
    save_current_settings()


def set_alpha(alpha):
    root.attributes("-alpha", alpha)
    settings["alpha"] = alpha
    save_current_settings()


def reset_position():
    settings.update(default_geometry)

    root.geometry(
        f'{default_geometry["width"]}x{default_geometry["height"]}'
        f'+{default_geometry["x"]}+{default_geometry["y"]}'
    )

    save_current_settings()


def show_menu(event):
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def close_widget():
    save_current_settings()

    try:
        kernel32.ReleaseMutex(mutex_handle)
    except Exception:
        pass

    try:
        kernel32.CloseHandle(mutex_handle)
    except Exception:
        pass

    root.destroy()


menu.add_command(
    label="解锁并拖动" if locked else "锁定位置",
    command=toggle_lock
)
menu.add_separator()
menu.add_command(label="打开课表编辑器", command=open_editor)
menu.add_command(label="立即刷新", command=lambda: refresh_widget(force=True))

position_menu = tk.Menu(menu, tearoff=False)
position_menu.add_command(label="上移 10 px", command=lambda: move_by(0, -10))
position_menu.add_command(label="下移 10 px", command=lambda: move_by(0, 10))
position_menu.add_command(label="左移 10 px", command=lambda: move_by(-10, 0))
position_menu.add_command(label="右移 10 px", command=lambda: move_by(10, 0))
position_menu.add_separator()
position_menu.add_command(label="恢复默认位置", command=reset_position)
menu.add_cascade(label="微调位置", menu=position_menu)

menu.add_separator()
menu.add_command(label="透明度 100%", command=lambda: set_alpha(1.00))
menu.add_command(label="透明度 96%", command=lambda: set_alpha(0.96))
menu.add_command(label="透明度 92%", command=lambda: set_alpha(0.92))

menu.add_separator()
menu.add_command(label=f"版本 {VERSION}", state="disabled")
menu.add_command(label="退出 DeskPlan", command=close_widget)

root.bind_all("<Button-3>", show_menu)
root.bind_all("<Double-Button-1>", open_editor)


def on_close():
    close_widget()


root.protocol("WM_DELETE_WINDOW", on_close)

update_drag_cursor()
refresh_widget(force=True)
root.mainloop()
