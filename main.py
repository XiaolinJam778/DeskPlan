import tkinter as tk
from tkinter import ttk


# =========================
# 创建主窗口
# =========================
root = tk.Tk()

root.title("DeskPlan")
root.geometry("1200x850")
root.minsize(1000, 750)



# =========================
# 主标题
# =========================
title_label = ttk.Label(
    root,
    text="DeskPlan",
    font=("Microsoft YaHei UI", 24, "bold")
)

title_label.pack(pady=(20, 5))

subtitle_label = ttk.Label(
    root,
    text="我的课表与备忘录",
    font=("Microsoft YaHei UI", 11)
)

subtitle_label.pack(pady=(0, 15))


# =========================
# 主内容区域
# =========================
main_frame = ttk.Frame(root)

main_frame.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=10
)

# 左边课表占更多空间
main_frame.columnconfigure(0, weight=3)

# 右边备忘录占较少空间
main_frame.columnconfigure(1, weight=2)

main_frame.rowconfigure(0, weight=1)


# ============================================================
# 左侧：课表
# ============================================================
schedule_frame = ttk.LabelFrame(
    main_frame,
    text="本周课表"
)

schedule_frame.grid(
    row=0,
    column=0,
    sticky="nsew",
    padx=(0, 10)
)


# 星期
days = [
    "时间",
    "周一",
    "周二",
    "周三",
    "周四",
    "周五"
]

# 课程时间
periods = [
    "第1节\n08:00-08:45",
    "第2节\n08:50-09:35",
    "第3节\n10:00-10:45",
    "第4节\n10:50-11:35",
    "第5节\n11:40-12:25",
    "第6节\n13:25-14:10",
    "第7节\n14:15-15:00",
    "第8节\n15:05-15:50",
    "第9节\n16:15-17:00",
    "第10节\n17:05-17:50",
    "第11节\n18:50-19:35",
    "第12节\n19:40-20:25",
    "第13节\n20:30-21:15"
]


# 设置课表网格大小
for column in range(6):
    schedule_frame.columnconfigure(
        column,
        weight=1
    )

for row in range(len(periods) + 1):
    schedule_frame.rowconfigure(
        row,
        weight=1
    )


# =========================
# 课表第一行：星期
# =========================
for column, day in enumerate(days):

    label = ttk.Label(
        schedule_frame,
        text=day,
        anchor="center",
        font=("Microsoft YaHei UI", 10, "bold")
    )

    label.grid(
        row=0,
        column=column,
        sticky="nsew",
        padx=2,
        pady=2
    )


# =========================
# 课表内容
# =========================
for row, period in enumerate(periods, start=1):

    # 左边时间
    period_label = ttk.Label(
        schedule_frame,
        text=period,
        anchor="center"
    )

    period_label.grid(
        row=row,
        column=0,
        sticky="nsew",
        padx=2,
        pady=2
    )

    # 周一到周五
    for column in range(1, 6):

        course_label = ttk.Label(
            schedule_frame,
            text="",
            anchor="center",
            relief="solid"
        )

        course_label.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=2,
            pady=2
        )


# ============================================================
# 右侧：备忘录
# ============================================================
memo_frame = ttk.LabelFrame(
    main_frame,
    text="今日备忘"
)

memo_frame.grid(
    row=0,
    column=1,
    sticky="nsew",
    padx=(10, 0)
)

memo_frame.columnconfigure(
    0,
    weight=1
)

memo_frame.rowconfigure(
    1,
    weight=1
)


# =========================
# 输入区域
# =========================
input_frame = ttk.Frame(memo_frame)

input_frame.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=10,
    pady=10
)

input_frame.columnconfigure(
    0,
    weight=1
)


memo_entry = ttk.Entry(
    input_frame,
    font=("Microsoft YaHei UI", 10)
)

memo_entry.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=(0, 5)
)


# =========================
# 备忘录显示区域
# =========================
memo_list = tk.Listbox(
    memo_frame,
    font=("Microsoft YaHei UI", 11),
    activestyle="none"
)

memo_list.grid(
    row=1,
    column=0,
    sticky="nsew",
    padx=10,
    pady=(0, 10)
)


# =========================
# 添加备忘录
# =========================
def add_memo():

    memo_text = memo_entry.get().strip()

    if memo_text:

        memo_list.insert(
            tk.END,
            "□ " + memo_text
        )

        memo_entry.delete(
            0,
            tk.END
        )


add_button = ttk.Button(
    input_frame,
    text="添加",
    command=add_memo
)

add_button.grid(
    row=0,
    column=1
)


# 按 Enter 也可以添加
memo_entry.bind(
    "<Return>",
    lambda event: add_memo()
)


# =========================
# 删除备忘录
# =========================
def delete_memo():

    selected = memo_list.curselection()

    if selected:

        memo_list.delete(
            selected[0]
        )


delete_button = ttk.Button(
    memo_frame,
    text="删除选中备忘",
    command=delete_memo
)

delete_button.grid(
    row=2,
    column=0,
    sticky="ew",
    padx=10,
    pady=(0, 10)
)


# =========================
# 启动程序
# =========================
root.mainloop()