from __future__ import annotations

import tkinter as tk

"""Logging to GUI console."""


class Logger:
    def __init__(self, widget: tk.Text) -> None:
        self.widget: tk.Text = widget

    def log(self, message: str) -> None:
        self.widget.insert("end", message + "\n")
        self.widget.see("end")
