# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 圧縮変換タブ
WinRARパスの設定機能を含みます。
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

try:
    from config import (
        TARGET_FORMATS, 
        COMPRESSION_LEVEL_NAMES, 
        COMPRESSION_LEVELS,
        validate_environment,
        update_winrar_path,
        WINRAR_DIR
    )
    from archive_handler import scan_archives, batch_convert
except ImportError:
    from ..config import (
        TARGET_FORMATS, 
        COMPRESSION_LEVEL_NAMES, 
        COMPRESSION_LEVELS,
        validate_environment,
        update_winrar_path,
        WINRAR_DIR
    )
    from ..archive_handler import scan_archives, batch_convert

logger = logging.getLogger(__name__)

class ConvertTab(ttk.Frame):
    """
    「圧縮変換」タブのUIとロジック。
    WinRARが見つからない場合の警告と設定機能を提供します。
    """
    def __init__(self, parent, log_callback=None):
        super().__init__(parent, padding="10")
        self.log_callback = log_callback
        self.is_running = False
        self.cancel_requested = False
        
        self._setup_ui()
        self.check_rar_env()

    def _setup_ui(self):
        # --- 警告エリア (WinRAR未検出時用) ---
        self.warn_frame = ttk.Frame(self)
        self.warn_label = ttk.Label(self.warn_frame, text="⚠ WinRAR が見つかりません。圧縮変換を利用するにはパスの設定が必要です。", foreground="red", font=("MS Gothic", 9, "bold"))
        self.warn_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.warn_frame, text="パスを設定する...", command=self._browse_winrar_path).pack(side=tk.LEFT)
        # 初期状態では隠す
        
        # --- フォルダ選択 ---
        dir_frame = ttk.LabelFrame(self, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_path_var = tk.StringVar()
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_path_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ref_btn = ttk.Button(dir_frame, text="参照...", command=lambda: self._browse_folder(self.dir_path_var))
        ref_btn.pack(side=tk.RIGHT)

        # --- 設定エリア ---
        settings_frame = ttk.LabelFrame(self, text=" 変換設定 ", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 15))

        # 変換形式
        fmt_frame = ttk.Frame(settings_frame)
        fmt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(fmt_frame, text="変換先の形式:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.target_fmt_var = tk.StringVar(value="ZIP")
        for fmt in TARGET_FORMATS.keys():
            ttk.Radiobutton(fmt_frame, text=fmt, value=fmt, variable=self.target_fmt_var).pack(side=tk.LEFT, padx=5)

        # 圧縮率
        level_frame = ttk.Frame(settings_frame)
        level_frame.pack(fill=tk.X, pady=5)
        ttk.Label(level_frame, text="圧縮率:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.comp_level_var = tk.StringVar(value="標準")
        level_combo = ttk.Combobox(level_frame, textvariable=self.comp_level_var, values=COMPRESSION_LEVEL_NAMES, state="readonly", width=10)
        level_combo.pack(side=tk.LEFT)

        # オプション
        opt_frame = ttk.Frame(settings_frame)
        opt_frame.pack(fill=tk.X, pady=(10, 0))

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="下層フォルダも対象にする", variable=self.recursive_var).pack(anchor=tk.W, pady=2)

        self.flatten_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="フォルダ階層の余分な入れ子を解消する", variable=self.flatten_var).pack(anchor=tk.W, pady=2)

        self.fix_ext_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="拡張子が間違っていたら自動で直す", variable=self.fix_ext_var).pack(anchor=tk.W, pady=2)

        self.delete_orig_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="変換後に元ファイルを削除する (注意)", variable=self.delete_orig_var).pack(anchor=tk.W, pady=2)

        self.preserve_timestamp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="変換後ファイルのタイムスタンプを据え置く", variable=self.preserve_timestamp_var).pack(anchor=tk.W, pady=2)

        # --- 実行ボタン ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.start_btn = ttk.Button(btn_frame, text="▶ 処理開始", command=self._start_convert_process)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.cancel_btn = ttk.Button(btn_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)

        # --- ログ表示 ---
        log_frame = ttk.LabelFrame(self, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # --- 進捗バー ---
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.TOP)
        
        self.status_var = tk.StringVar(value="待機中...")
        ttk.Label(progress_frame, textvariable=self.status_var, font=("MS Gothic", 9)).pack(side=tk.LEFT, pady=2)

    def check_rar_env(self):
        """WinRAR環境をチェックし、UIを更新する"""
        errors = validate_environment()
        if errors:
            self.warn_frame.pack(fill=tk.X, before=self.start_btn.master, pady=(0, 10))
            self.start_btn.config(state=tk.DISABLED)
        else:
            self.warn_frame.pack_forget()
            self.start_btn.config(state=tk.NORMAL)

    def _browse_winrar_path(self):
        path = filedialog.askdirectory(title="WinRARのインストールフォルダを選択", initialdir=WINRAR_DIR)
        if path:
            update_winrar_path(os.path.normpath(path))
            self.check_rar_env()
            if not validate_environment():
                messagebox.showinfo("設定完了", "WinRARパスが設定されました。")
            else:
                messagebox.showerror("エラー", "指定されたフォルダに Rar.exe 等が見つかりません。")

    def _browse_folder(self, target_var):
        path = filedialog.askdirectory()
        if path:
            target_var.set(os.path.normpath(path))

    def _log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        if self.log_callback:
            self.log_callback(message)

    def _update_progress(self, current, total):
        percent = (current / total) * 100
        self.progress_var.set(percent)
        self.status_var.set(f"処理中... {current} / {total} ({int(percent)}%)")

    def _request_cancel(self):
        if messagebox.askyesno("キャンセル", "処理を中断しますか？"):
            self.cancel_requested = True
            self._log("!!! 中断リクエストを受け付けました。")
            self.cancel_btn.config(state=tk.DISABLED)

    def _start_convert_process(self):
        # 最終チェック
        if validate_environment():
            messagebox.showerror("環境エラー", "WinRARの設定が必要です。")
            return

        path = self.dir_path_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return

        self.is_running = True
        self.cancel_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        target_fmt = self.target_fmt_var.get()
        comp_level = COMPRESSION_LEVELS.get(self.comp_level_var.get(), 3)
        
        opts = {
            "recursive": self.recursive_var.get(),
            "target_format": target_fmt,
            "compression_level": comp_level,
            "fix_extensions": self.fix_ext_var.get(),
            "flatten_folders": self.flatten_var.get(),
            "delete_original": self.delete_orig_var.get(),
            "preserve_timestamp": self.preserve_timestamp_var.get(),
        }

        threading.Thread(target=self._run_convert_batch, args=(path, opts), daemon=True).start()

    def _run_convert_batch(self, path, opts):
        try:
            self.status_var.set("ファイルを検索中...")
            archives = scan_archives(path, opts["recursive"])
            
            if not archives:
                self.after(0, lambda: messagebox.showinfo("完了", "対象が見つかりませんでした。"))
                self._finish_convert_process()
                return

            batch_convert(
                archive_list=archives,
                target_format=opts["target_format"],
                compression_level=opts["compression_level"],
                fix_extensions=opts["fix_extensions"],
                flatten_folders=opts["flatten_folders"],
                delete_original=opts["delete_original"],
                preserve_timestamp=opts["preserve_timestamp"],
                progress_callback=lambda c, t: self.after(0, self._update_progress, c, t),
                log_callback=lambda msg: self.after(0, self._log, msg),
                cancel_check=lambda: self.cancel_requested
            )
            
            self.status_var.set("完了" if not self.cancel_requested else "中断")
        except Exception as e:
            logger.exception("バッチ処理エラー")
            self._log(f"エラー: {e}")
        
        self._finish_convert_process()

    def _finish_convert_process(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
