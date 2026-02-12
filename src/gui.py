# -*- coding: utf-8 -*-
"""
ArchiveFileManager - GUI 実装
tkinter と ttk を使用して、クリーンで使いやすいインターフェースを提供します。
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

from config import (
    APP_NAME, 
    APP_VERSION, 
    TARGET_FORMATS, 
    COMPRESSION_LEVEL_NAMES, 
    COMPRESSION_LEVELS,
    validate_environment
)
from archive_handler import scan_archives, batch_convert

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class ArchiveFileManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("600x700")
        self.root.minsize(550, 650)
        
        # 処理状態管理
        self.is_running = False
        self.cancel_requested = False
        
        # スタイル設定
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5)
        self.style.configure("Header.TLabel", font=("MS Gothic", 12, "bold"))
        self.style.configure("Status.TLabel", font=("MS Gothic", 9))
        
        self._setup_ui()
        self._check_env()

    def _setup_ui(self):
        """UIコンポーネントの配置"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- フォルダ選択 ---
        dir_frame = ttk.LabelFrame(main_frame, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_path_var = tk.StringVar()
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_path_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ref_btn = ttk.Button(dir_frame, text="参照...", command=self._browse_folder)
        ref_btn.pack(side=tk.RIGHT)

        # --- 設定エリア ---
        settings_frame = ttk.LabelFrame(main_frame, text=" 変換設定 ", padding="10")
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
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.start_btn = ttk.Button(btn_frame, text="▶ 処理開始", command=self._start_process, style="Accent.TButton")
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.cancel_btn = ttk.Button(btn_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)

        # --- ログ表示 ---
        log_frame = ttk.LabelFrame(main_frame, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # --- 進捗バー ---
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.TOP)
        
        self.status_var = tk.StringVar(value="待機中...")
        ttk.Label(progress_frame, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT, pady=2)

    def _check_env(self):
        """環境チェック"""
        errors = validate_environment()
        if errors:
            msg = "環境に問題が見つかりました:\n\n" + "\n".join(errors)
            messagebox.showerror("環境エラー", msg)
            self._log("環境エラー: " + ", ".join(errors))
            self.start_btn.config(state=tk.DISABLED)

    def _browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.dir_path_var.set(os.path.normpath(path))

    def _log(self, message):
        """ログを追加"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        logger.info(message)

    def _update_progress(self, current, total):
        """進捗更新"""
        percent = (current / total) * 100
        self.progress_var.set(percent)
        self.status_var.set(f"処理中... {current} / {total} ({int(percent)}%)")

    def _request_cancel(self):
        if messagebox.askyesno("キャンセル", "処理を中断しますか？"):
            self.cancel_requested = True
            self._log("!!! 中断リクエストを受け付けました。現在の処理が完了次第停止します。")
            self.cancel_btn.config(state=tk.DISABLED)

    def _start_process(self):
        path = self.dir_path_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return

        # UIの無効化
        self.is_running = True
        self.cancel_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        
        # ログクリア
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # 設定の取得
        target_fmt = self.target_fmt_var.get()
        level_name = self.comp_level_var.get()
        comp_level = COMPRESSION_LEVELS.get(level_name, 3)
        
        opts = {
            "recursive": self.recursive_var.get(),
            "target_format": target_fmt,
            "compression_level": comp_level,
            "fix_extensions": self.fix_ext_var.get(),
            "flatten_folders": self.flatten_var.get(),
            "delete_original": self.delete_orig_var.get(),
            "preserve_timestamp": self.preserve_timestamp_var.get(),
        }

        # スレッドで処理開始
        threading.Thread(target=self._run_batch, args=(path, opts), daemon=True).start()

    def _run_batch(self, path, opts):
        """バックグラウンドでの一括処理実行"""
        try:
            # アーカイブの検索
            self.status_var.set("ファイルを検索中...")
            archives = scan_archives(path, opts["recursive"])
            
            if not archives:
                self.root.after(0, lambda: messagebox.showinfo("完了", "対象の圧縮ファイルが見つかりませんでした。"))
                self._finish_process()
                return

            self._log(f"処理対象: {len(archives)} 件")
            
            # 実行
            batch_convert(
                archive_list=archives,
                target_format=opts["target_format"],
                compression_level=opts["compression_level"],
                fix_extensions=opts["fix_extensions"],
                flatten_folders=opts["flatten_folders"],
                delete_original=opts["delete_original"],
                preserve_timestamp=opts["preserve_timestamp"],
                progress_callback=lambda c, t: self.root.after(0, self._update_progress, c, t),
                log_callback=lambda msg: self.root.after(0, self._log, msg),
                cancel_check=lambda: self.cancel_requested
            )
            
            if self.cancel_requested:
                self.status_var.set("中断されました")
            else:
                self.status_var.set("完了")
                self.root.after(0, lambda: messagebox.showinfo("完了", "すべての処理が終了しました。"))

        except Exception as e:
            self._log(f"エラー発生: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("エラー", f"予期せぬエラーが発生しました:\n{str(e)}"))
        
        self._finish_process()

    def _finish_process(self):
        """完了後のUI復旧"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        if not self.cancel_requested:
            self.status_var.set("待機中")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArchiveFileManagerGUI(root)
    root.mainloop()
