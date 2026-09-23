import tkinter as tk
from tkinter import ttk
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys


# ============================================================
# 文件路径
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "deskplan.json"
MAIN_FILE = BASE_DIR / "main.py"


# ============================================================
# 星期和课程时间
# ============================================================

WEEKDAYS = [
    "周一",
    "周二",
    "周三",
    "周四",
    "周五"
]

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
    ("第13节", "20:30", "21:15")
]


# ============================================================
# 读取数据
# ============================================================

def load_data():

    if not DATA_FILE.exists():
        return {
            "schedule": {},
            "memos": []
        }

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (OSError, json.JSONDecodeError):

        return {
            "schedule": {},
            "memos": []
        }


# ============================================================
# 主窗口
# ============================================================

root = tk.Tk()

root.title("DeskPlan Widget")

# 无标题栏
root.overrideredirect(True)

# 半透明
root.attributes("-alpha", 0.94)

# 初始大小与位置
root.geometry("390x780+40+80")

# 防止缩放
root.resizable(False, False)


# ============================================================
# 状态
# ============================================================

locked = False

drag_start_x = 0
drag_start_y = 0


# ============================================================
# 外层
# ============================================================

container = tk.Frame(
    root,
    bg="#202124",
    bd=1,
    relief="solid"
)

container.pack(
    fill="both",
    expand=True
)


# ============================================================
# 顶部
# ============================================================

header = tk.Frame(
    container,
    bg="#202124",
    height=70
)

header.pack(
    fill="x",
    padx=15,
    pady=(12, 5)
)


title_label = tk.Label(
    header,
    text="DeskPlan",
    font=("Microsoft YaHei UI", 18, "bold"),
    fg="white",
    bg="#202124"
)

title_label.pack(
    anchor="w"
)


date_label = tk.Label(
    header,
    text="",
    font=("Microsoft YaHei UI", 10),
    fg="#bbbbbb",
    bg="#202124"
)

date_label.pack(
    anchor="w",
    pady=(2, 0)
)


# ============================================================
# 今日课程标题
# ============================================================

course_title = tk.Label(
    container,
    text="TODAY",
    font=("Microsoft YaHei UI", 10, "bold"),
    fg="#999999",
    bg="#202124"
)

course_title.pack(
    anchor="w",
    padx=15,
    pady=(6, 5)
)


# ============================================================
# 课程区域
# ============================================================

course_frame = tk.Frame(
    container,
    bg="#202124"
)

course_frame.pack(
    fill="x",
    padx=15
)


course_rows = []


for index, (period, start, end) in enumerate(PERIODS):

    row = tk.Frame(
        course_frame,
        bg="#202124"
    )

    row.pack(
        fill="x",
        pady=2
    )


    time_label = tk.Label(
        row,
        text=start,
        width=6,
        anchor="w",
        font=("Microsoft YaHei UI", 9),
        fg="#aaaaaa",
        bg="#202124"
    )

    time_label.pack(
        side="left"
    )


    period_label = tk.Label(
        row,
        text=period,
        width=7,
        anchor="w",
        font=("Microsoft YaHei UI", 9),
        fg="#777777",
        bg="#202124"
    )

    period_label.pack(
        side="left"
    )


    course_label = tk.Label(
        row,
        text="",
        anchor="w",
        font=("Microsoft YaHei UI", 10),
        fg="white",
        bg="#202124"
    )

    course_label.pack(
        side="left",
        fill="x",
        expand=True
    )


    course_rows.append(
        course_label
    )


# ============================================================
# 分割线
# ============================================================

separator = tk.Frame(
    container,
    height=1,
    bg="#444444"
)

separator.pack(
    fill="x",
    padx=15,
    pady=12
)


# ============================================================
# 备忘录
# ============================================================

memo_title = tk.Label(
    container,
    text="TODO",
    font=("Microsoft YaHei UI", 10, "bold"),
    fg="#999999",
    bg="#202124"
)

memo_title.pack(
    anchor="w",
    padx=15,
    pady=(0, 5)
)


memo_frame = tk.Frame(
    container,
    bg="#202124"
)

memo_frame.pack(
    fill="both",
    expand=True,
    padx=15
)


memo_labels = []


# ============================================================
# 底部状态
# ============================================================

status_frame = tk.Frame(
    container,
    bg="#202124"
)

status_frame.pack(
    fill="x",
    padx=15,
    pady=(5, 10)
)


status_label = tk.Label(
    status_frame,
    text="右键查看更多选项",
    font=("Microsoft YaHei UI", 8),
    fg="#777777",
    bg="#202124"
)

status_label.pack(
    side="left"
)


# ============================================================
# 获取今天星期
# ============================================================

def get_today():

    weekday_index = datetime.now().weekday()

    if weekday_index < 5:
        return WEEKDAYS[weekday_index]

    return None


# ============================================================
# 刷新界面
# ============================================================

def refresh_widget():

    data = load_data()

    now = datetime.now()

    today = get_today()


    date_label.config(
        text=now.strftime("%Y年%m月%d日")
        + (
            f" · {today}"
            if today
            else " · 周末"
        )
    )


    # 清空课程
    for label in course_rows:

        label.config(
            text="—",
            fg="#666666"
        )


    # 显示今日课程
    if today:

        day_schedule = (
            data
            .get("schedule", {})
            .get(today, [])
        )


        for index in range(
            min(
                len(day_schedule),
                len(course_rows)
            )
        ):

            course_info = day_schedule[index]

            course = course_info.get(
                "course",
                ""
            )

            location = course_info.get(
                "location",
                ""
            )


            if course:

                text = course

                if location:
                    text += f"  ·  {location}"


                course_rows[index].config(
                    text=text,
                    fg="white"
                )


    # 删除旧备忘显示
    for label in memo_labels:

        label.destroy()


    memo_labels.clear()


    memos = data.get(
        "memos",
        []
    )


    # 最多显示 5 条
    for memo in memos[:5]:

        label = tk.Label(
            memo_frame,
            text="□  " + memo,
            anchor="w",
            font=("Microsoft YaHei UI", 10),
            fg="#dddddd",
            bg="#202124"
        )

        label.pack(
            fill="x",
            pady=2
        )

        memo_labels.append(
            label
        )


    if not memos:

        empty_label = tk.Label(
            memo_frame,
            text="暂无备忘",
            anchor="w",
            font=("Microsoft YaHei UI", 9),
            fg="#666666",
            bg="#202124"
        )

        empty_label.pack(
            fill="x"
        )

        memo_labels.append(
            empty_label
        )


    # 每 2 秒重新读取一次 JSON
    root.after(
        2000,
        refresh_widget
    )


# ============================================================
# 窗口拖动
# ============================================================

def start_drag(event):

    global drag_start_x
    global drag_start_y

    if locked:
        return

    drag_start_x = event.x_root - root.winfo_x()
    drag_start_y = event.y_root - root.winfo_y()


def drag_window(event):

    if locked:
        return

    x = event.x_root - drag_start_x
    y = event.y_root - drag_start_y

    root.geometry(
        f"+{x}+{y}"
    )


header.bind(
    "<ButtonPress-1>",
    start_drag
)

header.bind(
    "<B1-Motion>",
    drag_window
)

title_label.bind(
    "<ButtonPress-1>",
    start_drag
)

title_label.bind(
    "<B1-Motion>",
    drag_window
)

date_label.bind(
    "<ButtonPress-1>",
    start_drag
)

date_label.bind(
    "<B1-Motion>",
    drag_window
)


# ============================================================
# 打开完整编辑器
# ============================================================

def open_editor():

    subprocess.Popen(
        [
            sys.executable,
            str(MAIN_FILE)
        ]
    )


# ============================================================
# 锁定 / 解锁
# ============================================================

def toggle_lock():

    global locked

    locked = not locked

    if locked:

        status_label.config(
            text="位置已锁定"
        )

        menu.entryconfig(
            0,
            label="解锁位置"
        )

    else:

        status_label.config(
            text="可拖动位置"
        )

        menu.entryconfig(
            0,
            label="锁定位置"
        )


# ============================================================
# 透明度
# ============================================================

def set_alpha(value):

    root.attributes(
        "-alpha",
        value
    )


# ============================================================
# 右键菜单
# ============================================================

menu = tk.Menu(
    root,
    tearoff=False
)

menu.add_command(
    label="锁定位置",
    command=toggle_lock
)

menu.add_separator()

menu.add_command(
    label="打开课表编辑器",
    command=open_editor
)

menu.add_separator()

menu.add_command(
    label="透明度 100%",
    command=lambda: set_alpha(1.0)
)

menu.add_command(
    label="透明度 90%",
    command=lambda: set_alpha(0.9)
)

menu.add_command(
    label="透明度 80%",
    command=lambda: set_alpha(0.8)
)

menu.add_separator()

menu.add_command(
    label="退出 DeskPlan",
    command=root.destroy
)


def show_menu(event):

    menu.tk_popup(
        event.x_root,
        event.y_root
    )


root.bind_all(
    "<Button-3>",
    show_menu
)


# ============================================================
# 双击打开编辑器
# ============================================================

root.bind_all(
    "<Double-Button-1>",
    lambda event: open_editor()
)


# ============================================================
# 启动
# ============================================================

refresh_widget()

root.mainloop()