"""Logging to GUI console."""


class Logger:
    def __init__(self, widget):
        self.widget = widget

    def log(self, message):
        self.widget.insert("end", message + "\n")
        self.widget.see("end")
