import tkinter as tk
from tkinter import ttk


root = tk.Tk()

root.title("DeskPlan")
root.geometry("1000x650")

title = ttk.Label(
    root,
    text="DeskPlan",
    font=("Microsoft YaHei UI", 24, "bold")
)

title.pack(pady=20)

subtitle = ttk.Label(
    root,
    text="我的课表与备忘录",
    font=("Microsoft YaHei UI", 12)
)

subtitle.pack()

root.mainloop()