# -*- coding: utf-8 -*-
"""
ArchiveFileManager - GUIログハンドラ
logging モジュールのログを tkinter の Text ウィジェットに出力します。
"""

import logging
import tkinter as tk

class GuiLogHandler(logging.Handler):
    """
    Python の logging メッセージを tkinter の Text ウィジェットに転送するハンドラ。
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            try:
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.insert(tk.END, msg + "\n")
                self.text_widget.see(tk.END)
                self.text_widget.config(state=tk.DISABLED)
            except tk.TclError:
                pass
        
        # GUIスレッドで実行
        try:
            self.text_widget.after(0, append)
        except Exception:
            pass
