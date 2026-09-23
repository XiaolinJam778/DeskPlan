import tkinter as tk
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys


# ============================================================
# DeskPlan Desktop Widget
# v3 - 壁纸适配版（支持解锁后任意位置拖动 + 位置微调）
# ============================================================

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

# 与你当前壁纸右侧框内部接近的颜色。
# 不再使用 -transparentcolor，避免绿色抗锯齿边缘和鼠标事件失效。
BG_COLOR = "#F0F0F0"
TEXT_COLOR = "#222222"
SECONDARY_COLOR = "#666666"
LIGHT_COLOR = "#929292"
CURRENT_COLOR = "#111111"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def save_json(path, value):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=4)
    except OSError:
        pass


def load_data():
    return load_json(
        DATA_FILE,
        {
            "schedule": {},
            "memos": [],
        },
    )


def time_to_minutes(text):
    hour, minute = map(int, text.split(":"))
    return hour * 60 + minute


def get_today_name():
    index = datetime.now().weekday()
    return WEEKDAYS[index] if index < 5 else None


# ============================================================
# 主窗口
# ============================================================

root = tk.Tk()
root.title("DeskPlan Widget")
root.overrideredirect(True)
root.configure(bg=BG_COLOR)
root.attributes("-topmost", False)

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# 默认位置：针对你截图中的右侧“杂七杂八”框。
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

# v3 首次运行时，把旧版本位置轻微下移，适配当前壁纸。
if int(settings.get("settings_version", 0)) < 3:
    settings["y"] = int(settings.get("y", default_geometry["y"])) + max(
        20, int(screen_height * 0.025)
    )
    settings["settings_version"] = 3

# 防止换显示器/分辨率后窗口彻底跑出屏幕。
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
    anchor="w",
)
date_label.pack(anchor="w")

week_label = tk.Label(
    header,
    text="",
    font=("Microsoft YaHei UI", 10),
    fg=SECONDARY_COLOR,
    bg=BG_COLOR,
    anchor="w",
)
week_label.pack(anchor="w", pady=(2, 0))

# 今日课程
course_title = tk.Label(
    container,
    text="TODAY  今日课程",
    font=("Microsoft YaHei UI", 11, "bold"),
    fg=TEXT_COLOR,
    bg=BG_COLOR,
    anchor="w",
)
course_title.pack(fill="x", padx=20, pady=(24, 8))

course_frame = tk.Frame(container, bg=BG_COLOR)
course_frame.pack(fill="x", padx=20)

# 给壁纸中部的小猫留白。
cat_space = tk.Frame(container, bg=BG_COLOR, height=max(140, int(screen_height * 0.16)))
cat_space.pack(fill="x")
cat_space.pack_propagate(False)

# 待办
memo_title = tk.Label(
    container,
    text="TODO  待办",
    font=("Microsoft YaHei UI", 11, "bold"),
    fg=TEXT_COLOR,
    bg=BG_COLOR,
    anchor="w",
)
memo_title.pack(fill="x", padx=20, pady=(8, 8))

memo_frame = tk.Frame(container, bg=BG_COLOR)
memo_frame.pack(fill="both", expand=True, padx=20)

status_label = tk.Label(
    container,
    text="",
    font=("Microsoft YaHei UI", 8),
    fg=LIGHT_COLOR,
    bg=BG_COLOR,
    anchor="w",
)
status_label.pack(fill="x", padx=20, pady=(8, 14))

course_widgets = []
memo_widgets = []


def destroy_widgets(widgets):
    for widget in widgets:
        try:
            widget.destroy()
        except tk.TclError:
            pass
    widgets.clear()


def open_editor(event=None):
    if not MAIN_FILE.exists():
        status_label.config(text="未找到 main.py")
        return
    try:
        subprocess.Popen([sys.executable, str(MAIN_FILE)], cwd=str(BASE_DIR))
    except OSError:
        status_label.config(text="无法打开课表编辑器")


def refresh_courses(data, today):
    destroy_widgets(course_widgets)

    if today is None:
        label = tk.Label(
            course_frame,
            text="今天没有课程",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w",
        )
        label.pack(fill="x", pady=4)
        course_widgets.append(label)
        return

    schedule = data.get("schedule", {}).get(today, [])
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    has_course = False

    for index, info in enumerate(schedule[: len(PERIODS)]):
        if not isinstance(info, dict):
            continue

        course = str(info.get("course", "")).strip()
        location = str(info.get("location", "")).strip()
        if not course:
            continue

        has_course = True
        period_name, start_time, end_time = PERIODS[index]
        is_current = (
            time_to_minutes(start_time)
            <= current_minutes
            <= time_to_minutes(end_time)
        )

        row = tk.Frame(course_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)

        time_label = tk.Label(
            row,
            text=start_time,
            width=6,
            font=("Microsoft YaHei UI", 9),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w",
        )
        time_label.pack(side="left")

        marker = "●" if is_current else "○"
        text = f"{marker}  {course}"
        if location:
            text += f" · {location}"

        detail_label = tk.Label(
            row,
            text=text,
            font=("Microsoft YaHei UI", 10, "bold" if is_current else "normal"),
            fg=CURRENT_COLOR if is_current else TEXT_COLOR,
            bg=BG_COLOR,
            anchor="w",
            justify="left",
            wraplength=max(240, int(settings["width"]) - 105),
        )
        detail_label.pack(side="left", fill="x", expand=True)

        course_widgets.extend([row])

    if not has_course:
        label = tk.Label(
            course_frame,
            text="今天没有课程",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w",
        )
        label.pack(fill="x", pady=4)
        course_widgets.append(label)


def refresh_memos(data):
    destroy_widgets(memo_widgets)

    memos = data.get("memos", [])
    if not isinstance(memos, list):
        memos = []

    if not memos:
        label = tk.Label(
            memo_frame,
            text="今天没有待办事项",
            font=("Microsoft YaHei UI", 10),
            fg=SECONDARY_COLOR,
            bg=BG_COLOR,
            anchor="w",
        )
        label.pack(fill="x", pady=4)
        memo_widgets.append(label)
        return

    for memo in memos[:8]:
        label = tk.Label(
            memo_frame,
            text=f"□  {memo}",
            font=("Microsoft YaHei UI", 10),
            fg=TEXT_COLOR,
            bg=BG_COLOR,
            anchor="w",
            justify="left",
            wraplength=max(240, int(settings["width"]) - 50),
        )
        label.pack(fill="x", pady=4)
        memo_widgets.append(label)


def update_status():
    if locked:
        status_label.config(text="位置已锁定  ·  右键解锁/微调  ·  双击编辑")
    else:
        status_label.config(text="位置未锁定  ·  拖动任意位置移动  ·  右键锁定")


def refresh_widget():
    data = load_data()
    now = datetime.now()
    today = get_today_name()

    date_label.config(text=now.strftime("%m月%d日"))
    week_label.config(text=today if today else "周末")

    refresh_courses(data, today)
    refresh_memos(data)
    update_status()

    root.after(2000, refresh_widget)


# ============================================================
# 鼠标交互
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
    global drag_offset_x, drag_offset_y
    if locked:
        return
    drag_offset_x = event.x_root - root.winfo_x()
    drag_offset_y = event.y_root - root.winfo_y()


def drag_window(event):
    if locked:
        return
    x = event.x_root - drag_offset_x
    y = event.y_root - drag_offset_y
    root.geometry(f"+{x}+{y}")


def end_drag(event=None):
    if not locked:
        save_current_settings()


def update_drag_cursor():
    # 解锁时显示移动光标，明确提示当前可以拖动。
    root.configure(cursor="arrow" if locked else "fleur")


# 解锁后，整个小组件任意位置都可以拖动。
# bind_all 也覆盖动态生成的课程和待办标签。
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
    menu.entryconfig(0, label="解锁并拖动" if locked else "锁定位置")


def move_by(dx, dy):
    x = root.winfo_x() + dx
    y = root.winfo_y() + dy

    # 不让窗口完全跑出屏幕。
    x = max(0, min(x, screen_width - 120))
    y = max(0, min(y, screen_height - 120))

    root.geometry(f"+{x}+{y}")
    save_current_settings()


def set_alpha(alpha):
    root.attributes("-alpha", alpha)
    settings["alpha"] = alpha
    save_current_settings()


def reset_position():
    settings.update(default_geometry)
    settings["settings_version"] = 3
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


menu.add_command(label="解锁并拖动" if locked else "锁定位置", command=toggle_lock)
menu.add_separator()
menu.add_command(label="打开课表编辑器", command=open_editor)
menu.add_command(label="立即刷新", command=refresh_widget)

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
menu.add_command(label="退出 DeskPlan", command=root.destroy)

# 关键修复：不再使用透明色，因此整个窗口都能收到鼠标事件。
# bind_all 让动态生成的课程/待办标签也能右键和双击。
root.bind_all("<Button-3>", show_menu)
root.bind_all("<Double-Button-1>", open_editor)


def on_close():
    save_current_settings()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

update_drag_cursor()
refresh_widget()
root.mainloop()
