# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 圧縮変換タブ（機能強化版）
複数フォルダ指定、履歴、お気に入り、アーカイブ内削除機能を含みます。
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
    from archive_handler import scan_archives, batch_convert, get_archive_list, remove_from_archive
    from storage import Storage
except ImportError:
    from ..config import (
        TARGET_FORMATS, 
        COMPRESSION_LEVEL_NAMES, 
        COMPRESSION_LEVELS,
        validate_environment,
        update_winrar_path,
        WINRAR_DIR
    )
    from ..archive_handler import scan_archives, batch_convert, get_archive_list, remove_from_archive
    from ..storage import Storage

logger = logging.getLogger(__name__)

class ConvertTab(ttk.Frame):
    """
    「圧縮変換」タブ。複数フォルダ、履歴、各種便利機能を追加。
    """
    def __init__(self, parent, log_callback=None):
        super().__init__(parent, padding="10")
        self.log_callback = log_callback
        self.is_running = False
        self.cancel_requested = False
        self.storage = Storage()
        
        # WinRARパスの復元
        saved_rar = self.storage.get_winrar_dir()
        if saved_rar:
            update_winrar_path(saved_rar)
            
        self._setup_ui()
        self.check_rar_env()

    def _setup_ui(self):
        # 1. WinRAR警告エリア
        self.warn_frame = ttk.Frame(self)
        self.warn_label = ttk.Label(self.warn_frame, text="⚠ WinRAR 未検出。設定が必要です。", foreground="red", font=("MS Gothic", 9, "bold"))
        self.warn_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.warn_frame, text="設定する...", command=self._browse_winrar_path).pack(side=tk.LEFT)

        # 2. 対象フォルダエリア（複数指定）
        dir_frame = ttk.LabelFrame(self, text=" 対象フォルダ（複数可） ", padding="5")
        dir_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        list_frame = ttk.Frame(dir_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.dir_listbox = tk.Listbox(list_frame, height=4, selectmode=tk.MULTIPLE, font=("Consolas", 9))
        self.dir_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        dir_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.dir_listbox.yview)
        dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_listbox.config(yscrollcommand=dir_scroll.set)

        btn_bar = ttk.Frame(dir_frame)
        btn_bar.pack(fill=tk.X, pady=2)
        ttk.Button(btn_bar, text="追加...", width=8, command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="削除", width=8, command=self._remove_selected_folders).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="クリア", width=8, command=lambda: self.dir_listbox.delete(0, tk.END)).pack(side=tk.LEFT, padx=2)
        
        # 履歴・お気に入り
        self.fav_btn = ttk.Menubutton(btn_bar, text="履歴/★", width=12)
        self.fav_menu = tk.Menu(self.fav_btn, tearoff=0)
        self.fav_btn.config(menu=self.fav_menu)
        self.fav_btn.pack(side=tk.RIGHT, padx=2)
        self.fav_btn.bind("<Button-1>", lambda e: self._update_fav_menu())

        # 3. 変換設定
        settings_frame = ttk.LabelFrame(self, text=" 変換設定 ", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # 変換形式・圧縮率
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="形式:").pack(side=tk.LEFT)
        self.target_fmt_var = tk.StringVar(value="ZIP")
        for fmt in TARGET_FORMATS.keys():
            ttk.Radiobutton(row1, text=fmt, value=fmt, variable=self.target_fmt_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="  圧縮率:").pack(side=tk.LEFT)
        self.comp_level_var = tk.StringVar(value="標準")
        ttk.Combobox(row1, textvariable=self.comp_level_var, values=COMPRESSION_LEVEL_NAMES, state="readonly", width=8).pack(side=tk.LEFT)

        # アーカイブ内操作ボタン
        ttk.Button(row1, text="アーカイブ内容の確認/削除...", command=self._open_archive_explorer).pack(side=tk.RIGHT)

        # オプション
        opt_frame = ttk.Frame(settings_frame)
        opt_frame.pack(fill=tk.X, pady=2)
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="下層も対象", variable=self.recursive_var).pack(side=tk.LEFT, padx=5)
        self.flatten_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="階層解消", variable=self.flatten_var).pack(side=tk.LEFT, padx=5)
        self.fix_ext_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="拡張子補正", variable=self.fix_ext_var).pack(side=tk.LEFT, padx=5)
        self.delete_orig_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="元削除", variable=self.delete_orig_var).pack(side=tk.LEFT, padx=5)

        # 4. 実行セクション
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        self.start_btn = ttk.Button(btn_frame, text="▶ 処理開始", command=self._start_convert_process)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.cancel_btn = ttk.Button(btn_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)

        # 5. ログ
        log_frame = ttk.LabelFrame(self, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 進捗
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
        self.status_var = tk.StringVar(value="待機中...")
        ttk.Label(self, textvariable=self.status_var, font=("MS Gothic", 9)).pack(anchor=tk.W)

    def check_rar_env(self):
        errors = validate_environment()
        if errors:
            self.warn_frame.pack(fill=tk.X, before=self.start_btn.master, pady=(0, 10))
            self.start_btn.config(state=tk.DISABLED)
        else:
            self.warn_frame.pack_forget()
            self.start_btn.config(state=tk.NORMAL)

    def _browse_winrar_path(self):
        path = filedialog.askdirectory(title="WinRARの場所（WinRAR.exeがあるフォルダ）", initialdir=WINRAR_DIR)
        if path:
            update_winrar_path(os.path.normpath(path))
            self.storage.set_winrar_dir(path)
            self.check_rar_env()

    def _add_folder(self, path=None):
        if not path:
            path = filedialog.askdirectory()
        if path:
            norm_path = os.path.normpath(path)
            if norm_path not in self.dir_listbox.get(0, tk.END):
                self.dir_listbox.insert(tk.END, norm_path)
                self.storage.add_history(norm_path)

    def _remove_selected_folders(self):
        sel = list(self.dir_listbox.curselection())
        for i in reversed(sel):
            self.dir_listbox.delete(i)

    def _update_fav_menu(self):
        self.fav_menu.delete(0, tk.END)
        
        # 履歴
        history = self.storage.data.get("history", [])
        if history:
            self.fav_menu.add_command(label="[履歴]", state=tk.DISABLED)
            for path in history:
                self.fav_menu.add_command(label=f"  {path}", command=lambda p=path: self._add_folder(p))
            self.fav_menu.add_separator()
        
        # お気に入り
        favorites = self.storage.data.get("favorites", [])
        self.fav_menu.add_command(label="[お気に入り]", state=tk.DISABLED)
        for path in favorites:
            self.fav_menu.add_command(label=f"★ {path}", command=lambda p=path: self._add_folder(p))
        
        if self.dir_listbox.size() > 0:
            self.fav_menu.add_separator()
            last_path = self.dir_listbox.get(tk.END)
            self.fav_menu.add_command(label=f"リスト最後を ★登録", command=lambda: self.storage.add_favorite(last_path))

    def _log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        if self.log_callback:
            self.log_callback(message)

    def _start_convert_process(self):
        folders = self.dir_listbox.get(0, tk.END)
        if not folders:
            messagebox.showwarning("入力エラー", "対象フォルダを追加してください。")
            return

        self.is_running = True
        self.cancel_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        opts = {
            "recursive": self.recursive_var.get(),
            "target_format": self.target_fmt_var.get(),
            "compression_level": COMPRESSION_LEVELS.get(self.comp_level_var.get(), 3),
            "fix_extensions": self.fix_ext_var.get(),
            "flatten_folders": self.flatten_var.get(),
            "delete_original": self.delete_orig_var.get(),
            "preserve_timestamp": self.preserve_timestamp_var.get(),
        }

        threading.Thread(target=self._run_multi_folder_batch, args=(folders, opts), daemon=True).start()

    def _run_multi_folder_batch(self, folders, opts):
        try:
            total_archives = []
            for folder in folders:
                if self.cancel_requested: break
                self.status_var.set(f"検索中: {os.path.basename(folder)}")
                total_archives.extend(scan_archives(folder, opts["recursive"]))
            
            if not total_archives:
                self.after(0, lambda: messagebox.showinfo("完了", "対象が見つかりませんでした。"))
                self._finish_convert_process()
                return

            batch_convert(
                archive_list=total_archives,
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
            logger.exception("マルチフォルダバッチ処理エラー")
            self._log(f"エラー: {e}")
        self._finish_convert_process()

    def _finish_convert_process(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)

    def _update_progress(self, current, total):
        p = (current / total) * 100
        self.progress_var.set(p)
        self.status_var.set(f"処理中... {current}/{total} ({int(p)}%)")

    def _request_cancel(self):
        if messagebox.askyesno("キャンセル", "処理を中断しますか？"):
            self.cancel_requested = True
            self.cancel_btn.config(state=tk.DISABLED)

    def _open_archive_explorer(self):
        # この機能は次のステップで実装するダイアログを呼び出します
        messagebox.showinfo("開発中", "アーカイブ内探索・詳細削除機能は現在実装中です。")
