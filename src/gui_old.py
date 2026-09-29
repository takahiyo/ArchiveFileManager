# -*- coding: utf-8 -*-
"""
ArchiveFileManager - GUI 実装 (v1.1.0)
tkinter と ttk を使用して、クリーンで使いやすいインターフェースを提供します。
タブ機能により「圧縮変換」と「空フォルダ削除」を切り替えます。
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import datetime

import config
from archive_handler import scan_archives, batch_convert
from empty_folder_scanner import scan_empty_folders, delete_folders
from archive_content_cleaner import scan_archives_for_cleaning, batch_clean_archives
# from config import DEFAULT_CLEAN_PATTERNS (removed as using import config)

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class ArchiveFileManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.root.geometry("640x720")
        self.root.minsize(600, 650)
        
        # 処理状態管理
        self.is_running = False
        self.cancel_requested = False
        
        # 空フォルダ検索結果の保持用
        self.empty_folders_data = []  # 全データ
        self.sort_column = "path"
        self.sort_reverse = False
        
        # スタイル設定
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5)
        self.style.configure("Header.TLabel", font=("MS Gothic", 12, "bold"))
        self.style.configure("Status.TLabel", font=("MS Gothic", 9))
        self.style.configure("Bold.TCheckbutton", font=("MS Gothic", 9, "bold"))
        
        self._setup_ui()
        self._check_env()

    def _setup_ui(self):
        """UIコンポーネントの配置"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タブコントロール
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # タブ1: 圧縮変換
        self.tab_convert = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_convert, text=" 📦 圧縮変換 ")
        self._setup_convert_tab(self.tab_convert)

        # タブ2: 空フォルダ
        self.tab_empty = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_empty, text=" 🗂 空フォルダ ")
        self._setup_empty_tab(self.tab_empty)
        
        # タブ3: 書庫クリーン
        self.tab_clean = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_clean, text=" 🧹 書庫クリーン ")
        self._setup_clean_tab(self.tab_clean)

    # -------------------------------------------------------------------------
    # タブ1: 圧縮変換
    # -------------------------------------------------------------------------
    def _setup_convert_tab(self, parent):
        # --- フォルダ選択 ---
        dir_frame = ttk.LabelFrame(parent, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_path_var = tk.StringVar()
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_path_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ref_btn = ttk.Button(dir_frame, text="参照...", command=partial(self._browse_folder, self.dir_path_var))
        ref_btn.pack(side=tk.RIGHT)

        # --- 設定エリア ---
        settings_frame = ttk.LabelFrame(parent, text=" 変換設定 ", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 15))

        # 変換形式
        fmt_frame = ttk.Frame(settings_frame)
        fmt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(fmt_frame, text="変換先の形式:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.target_fmt_var = tk.StringVar(value="ZIP")
        for fmt in config.TARGET_FORMATS.keys():
            ttk.Radiobutton(fmt_frame, text=fmt, value=fmt, variable=self.target_fmt_var).pack(side=tk.LEFT, padx=5)

        # 圧縮率
        level_frame = ttk.Frame(settings_frame)
        level_frame.pack(fill=tk.X, pady=5)
        ttk.Label(level_frame, text="圧縮率:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.comp_level_var = tk.StringVar(value="標準")
        level_combo = ttk.Combobox(level_frame, textvariable=self.comp_level_var, values=config.COMPRESSION_LEVEL_NAMES, state="readonly", width=10)
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
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.start_btn = ttk.Button(btn_frame, text="▶ 処理開始", command=self._start_convert_process, style="Accent.TButton")
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.cancel_btn = ttk.Button(btn_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)

        # --- ログ表示 ---
        log_frame = ttk.LabelFrame(parent, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # --- 進捗バー ---
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.TOP)
        
        self.status_var = tk.StringVar(value="待機中...")
        ttk.Label(progress_frame, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT, pady=2)

    # -------------------------------------------------------------------------
    # タブ2: 空フォルダ
    # -------------------------------------------------------------------------
    def _setup_empty_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # フォルダ選択
        self.empty_dir_var = tk.StringVar()
        ttk.Label(top_frame, text="対象フォルダ:").pack(side=tk.LEFT)
        ttk.Entry(top_frame, textvariable=self.empty_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(top_frame, text="参照...", command=partial(self._browse_folder, self.empty_dir_var)).pack(side=tk.LEFT)
        
        # 検索ボタン
        ttk.Button(top_frame, text="🔍 検索開始", command=self._scan_empty_folders).pack(side=tk.LEFT, padx=(10, 0))

        # フィルタ
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(filter_frame, text="フィルタ(名前):").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace("w", self._apply_filter)
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.count_label = ttk.Label(filter_frame, text="件数: 0件")
        self.count_label.pack(side=tk.RIGHT)

        # 一覧リスト (Treeview)
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.tree = ttk.Treeview(tree_frame, columns=("checked", "name", "path", "modified"), show="headings", selectmode="extended")
        
        # ヘッダー設定
        self.tree.heading("checked", text="☑", command=lambda: self._sort_tree("checked"))
        self.tree.heading("name", text="フォルダ名", command=lambda: self._sort_tree("name"))
        self.tree.heading("path", text="フルパス", command=lambda: self._sort_tree("path"))
        self.tree.heading("modified", text="更新日時", command=lambda: self._sort_tree("modified"))
        
        self.tree.column("checked", width=40, anchor="center", stretch=False)
        self.tree.column("name", width=150, anchor="w")
        self.tree.column("path", width=300, anchor="w")
        self.tree.column("modified", width=120, anchor="w")

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar_y.set)
        
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscroll=scrollbar_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # ダブルクリックでチェック切り替え
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        # シングルクリックでチェック切り替え（簡易実装）
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        # 下部ボタン類
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=10)

        ttk.Button(bottom_frame, text="全選択", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="全解除", command=self._deselect_all).pack(side=tk.LEFT, padx=5)
        
        self.delete_btn = ttk.Button(bottom_frame, text="選択したフォルダを削除", command=self._delete_selected, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.RIGHT, padx=5)

    # -------------------------------------------------------------------------
    # タブ3: 書庫クリーン
    # -------------------------------------------------------------------------
    def _setup_clean_tab(self, parent):
        # 内部状態
        self.clean_scan_results = []
        
        # --- 対象フォルダ ---
        dir_frame = ttk.LabelFrame(parent, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        self.clean_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.clean_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dir_frame, text="参照...", command=partial(self._browse_folder, self.clean_dir_var)).pack(side=tk.RIGHT)
        
        # オプション群
        opt_frame = ttk.Frame(dir_frame)
        opt_frame.pack(fill=tk.X, pady=(5, 0))
        self.clean_recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="下層フォルダも対象にする", variable=self.clean_recursive_var).pack(side=tk.LEFT, padx=(0, 10))
        self.clean_nesting_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="余分な入れ子を解消する", variable=self.clean_nesting_var).pack(side=tk.LEFT, padx=(0, 10))
        self.clean_shorten_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="長すぎる名前を短縮する", variable=self.clean_shorten_var).pack(side=tk.LEFT)

        # --- 除外パターン設定 ---
        pat_frame = ttk.LabelFrame(parent, text=" 削除パターン設定 ", padding="10")
        pat_frame.pack(fill=tk.X, pady=(0, 10))
        
        pat_input_frame = ttk.Frame(pat_frame)
        pat_input_frame.pack(fill=tk.X, pady=(0, 5))
        self.clean_pat_var = tk.StringVar()
        ttk.Entry(pat_input_frame, textvariable=self.clean_pat_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(pat_input_frame, text="追加", command=self._add_clean_pattern).pack(side=tk.RIGHT)
        
        # パターンリスト表示
        list_frame = ttk.Frame(pat_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.clean_pat_listbox = tk.Listbox(list_frame, height=4, selectmode=tk.SINGLE)
        self.clean_pat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pat_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.clean_pat_listbox.yview)
        pat_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.clean_pat_listbox.configure(yscrollcommand=pat_scroll.set)
        
        pat_btn_frame = ttk.Frame(list_frame)
        pat_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(pat_btn_frame, text="削除", command=self._remove_clean_pattern).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(pat_btn_frame, text="リセット", command=self._reset_clean_patterns).pack(fill=tk.X)
        
        self._reset_clean_patterns() # 初期化

        # --- スキャン＆結果 ---
        res_frame = ttk.Frame(parent)
        res_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scan_btn_frame = ttk.Frame(res_frame)
        scan_btn_frame.pack(fill=tk.X, pady=(0, 5))
        self.clean_scan_btn = ttk.Button(scan_btn_frame, text="🔍 スキャン（プレビュー）", command=self._scan_clean_archives)
        self.clean_scan_btn.pack(side=tk.LEFT)
        self.clean_res_label = ttk.Label(scan_btn_frame, text="待機中...")
        self.clean_res_label.pack(side=tk.LEFT, padx=10)

        # 結果Treeview
        self.clean_tree = ttk.Treeview(res_frame, columns=("archive", "files", "nest_shorten"), show="headings", height=5)
        self.clean_tree.heading("archive", text="書庫名")
        self.clean_tree.heading("files", text="削除対象ファイル")
        self.clean_tree.heading("nest_shorten", text="階層/名前修正")
        self.clean_tree.column("archive", width=200, anchor="w")
        self.clean_tree.column("files", width=200, anchor="w")
        self.clean_tree.column("nest_shorten", width=80, anchor="center")
        
        clean_scroll = ttk.Scrollbar(res_frame, orient=tk.VERTICAL, command=self.clean_tree.yview)
        self.clean_tree.configure(yscrollcommand=clean_scroll.set)
        self.clean_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        clean_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- 実行ボタン ---
        exec_frame = ttk.Frame(parent)
        exec_frame.pack(fill=tk.X, pady=(0, 10))
        self.clean_exec_btn = ttk.Button(exec_frame, text="▶ 処理実行", command=self._execute_clean, state=tk.DISABLED, style="Accent.TButton")
        self.clean_exec_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.clean_cancel_btn = ttk.Button(exec_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.clean_cancel_btn.pack(side=tk.RIGHT)
        
        # 進捗バー（共有）
        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill=tk.X)
        self.clean_prog_var = tk.DoubleVar()
        self.clean_prog = ttk.Progressbar(prog_frame, variable=self.clean_prog_var, maximum=100)
        self.clean_prog.pack(fill=tk.X, side=tk.TOP)
        self.clean_status_var = tk.StringVar(value="")
        ttk.Label(prog_frame, textvariable=self.clean_status_var, style="Status.TLabel").pack(side=tk.LEFT, pady=2)


    # -------------------------------------------------------------------------
    # 共通・ユーティリティ
    # -------------------------------------------------------------------------
    def _check_env(self):
        """環境チェック"""
        errors = config.validate_environment()
        if errors:
            msg = "環境に問題が見つかりました:\n\n" + "\n".join(errors)
            messagebox.showerror("環境エラー", msg)
            self._log("環境エラー: " + ", ".join(errors))
            self.start_btn.config(state=tk.DISABLED)

    def _browse_folder(self, target_var):
        path = filedialog.askdirectory()
        if path:
            target_var.set(os.path.normpath(path))

    def _log(self, message):
        """ログを追加（圧縮タブ用）"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        logger.info(message)

    # -------------------------------------------------------------------------
    # 圧縮変換ロジック
    # -------------------------------------------------------------------------
    def _update_progress(self, current, total):
        percent = (current / total) * 100
        self.progress_var.set(percent)
        self.status_var.set(f"処理中... {current} / {total} ({int(percent)}%)")

    def _request_cancel(self):
        if messagebox.askyesno("キャンセル", "処理を中断しますか？"):
            self.cancel_requested = True
            self._log("!!! 中断リクエストを受け付けました。現在の処理が完了次第停止します。")
            self.cancel_btn.config(state=tk.DISABLED)

    def _start_convert_process(self):
        path = self.dir_path_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return

        self.is_running = True
        self.cancel_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

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

        threading.Thread(target=self._run_convert_batch, args=(path, opts), daemon=True).start()

    def _run_convert_batch(self, path, opts):
        try:
            self.status_var.set("ファイルを検索中...")
            archives = scan_archives(path, opts["recursive"])
            
            if not archives:
                self.root.after(0, lambda: messagebox.showinfo("完了", "対象の圧縮ファイルが見つかりませんでした。"))
                self._finish_convert_process()
                return

            self._log(f"処理対象: {len(archives)} 件")
            
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
        
        self._finish_convert_process()

    def _finish_convert_process(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        if not self.cancel_requested:
            self.status_var.set("待機中")

    # -------------------------------------------------------------------------
    # 空フォルダロジック
    # -------------------------------------------------------------------------
    def _scan_empty_folders(self):
        path = self.empty_dir_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return

        # 初期化
        self.tree.delete(*self.tree.get_children())
        self.empty_folders_data = []

        try:
            folders = scan_empty_folders(path)
            self.empty_folders_data = folders # リスト[dict]
            
            # 各データにチェック状態を追加
            for item in self.empty_folders_data:
                item["checked"] = True # デフォルトでチェックON

            self._apply_filter() # 表示更新
            
            if not folders:
                messagebox.showinfo("結果", "空フォルダは見つかりませんでした。")
            else:
                messagebox.showinfo("結果", f"{len(folders)} 件の空フォルダが見つかりました。")

        except Exception as e:
            messagebox.showerror("エラー", f"検索中にエラーが発生しました:\n{str(e)}")

    def _apply_filter(self, *args):
        query = self.filter_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        display_count = 0
        for item in self.empty_folders_data:
            if query in item["name"].lower() or query in item["path"].lower():
                check_mark = "☑" if item["checked"] else "☐"
                # Treeviewに挿入 (Valuesの順序はカラム定義順)
                # item["_id"] をtagsなどで持たせるか、indexで管理するか。
                # ここでは item の参照を保持するために iid を利用
                iid = self.tree.insert("", tk.END, values=(
                    check_mark,
                    item["name"],
                    item["path"],
                    item["modified_str"]
                ))
                # データとの紐付け用（簡易的に、itemそのものをいじるのは難しいので、indexで同期）
                # ここでは再描画時に常にフィルタリングするので、
                # self.empty_folders_data の中のどの要素かを特定する必要がある
                # pathをキーにするのが確実
                
                display_count += 1
        
        self.count_label.config(text=f"件数: {display_count}件")
        self._update_delete_button()

    def _on_tree_click(self, event):
        """クリックでチェックボックス切り替え"""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            if col == "#1": # 1列目（チェックボックス）
                item_id = self.tree.identify_row(event.y)
                self._toggle_check(item_id)

    def _on_tree_double_click(self, event):
        """ダブルクリックでフォルダをエクスプローラで開く"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        values = self.tree.item(item_id, "values")
        folder_path = values[2]  # フルパス列
        if os.path.isdir(folder_path):
            # フォルダが存在する場合はそのフォルダを選択した状態で開く
            subprocess.Popen(["explorer", "/select,", os.path.normpath(folder_path)])
        else:
            # 既に削除されている場合は親フォルダを開く
            parent_dir = os.path.dirname(folder_path)
            if os.path.isdir(parent_dir):
                os.startfile(parent_dir)

    def _toggle_check(self, item_id):
        if not item_id:
            return
            
        values = self.tree.item(item_id, "values")
        path = values[2] # path is 3rd column
        
        # データの検索して更新
        target_item = next((x for x in self.empty_folders_data if x["path"] == path), None)
        if target_item:
            target_item["checked"] = not target_item["checked"]
            new_mark = "☑" if target_item["checked"] else "☐"
            
            # Treeview更新
            new_values = list(values)
            new_values[0] = new_mark
            self.tree.item(item_id, values=new_values)
            
            self._update_delete_button()

    def _select_all(self):
        for item in self.empty_folders_data:
            item["checked"] = True
        self._apply_filter() # 再描画

    def _deselect_all(self):
        for item in self.empty_folders_data:
            item["checked"] = False
        self._apply_filter() # 再描画

    def _update_delete_button(self):
        # チェックがついている項目があるか
        count = sum(1 for x in self.empty_folders_data if x["checked"])
        if count > 0:
            self.delete_btn.config(state=tk.NORMAL, text=f"選択したフォルダを削除 ({count}件)")
        else:
            self.delete_btn.config(state=tk.DISABLED, text="選択したフォルダを削除")

    def _sort_tree(self, col):
        # ソート方向切り替え
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
            
        # データソート
        self.empty_folders_data.sort(
            key=lambda x: x[col], 
            reverse=self.sort_reverse
        )
        
        # ヘッダー表示更新（▼▲）
        for c in ["checked", "name", "path", "modified"]:
            text = self.tree.heading(c, "text").replace(" ▲", "").replace(" ▼", "")
            if c == col:
                text += " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(c, text=text)

        self._apply_filter() # 再描画

    def _delete_selected(self):
        targets = [x["path"] for x in self.empty_folders_data if x["checked"]]
        if not targets:
            return
            
        if not messagebox.askyesno("削除確認", f"{len(targets)} 件の空フォルダを削除します。\nよろしいですか？\n（ごみ箱には入らず、完全に削除されます）"):
            return
            
        # 削除実行
        results = delete_folders(targets)
        
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        
        msg = f"削除完了: {success_count}件"
        if fail_count > 0:
            msg += f"\n失敗: {fail_count}件\n詳細はログをご確認ください（未実装）"
            
        messagebox.showinfo("完了", msg)
        
        # リスト更新（削除されたものは除外）
        # 失敗したものは残す
        for res in results:
            if res["success"]:
                self.empty_folders_data = [x for x in self.empty_folders_data if x["path"] != res["path"]]
                
        self._apply_filter()


    # -------------------------------------------------------------------------
    # 書庫クリーン ロジック
    # -------------------------------------------------------------------------
    def _add_clean_pattern(self):
        pat = self.clean_pat_var.get().strip()
        if not pat:
            return
        # 重複チェック
        current = self.clean_pat_listbox.get(0, tk.END)
        if pat not in current:
            self.clean_pat_listbox.insert(tk.END, pat)
            self.clean_pat_var.set("") # クリア
            # 外部ファイルに保存
            config.save_clean_patterns(self._get_current_patterns())

    def _remove_clean_pattern(self):
        sel = self.clean_pat_listbox.curselection()
        if sel:
            self.clean_pat_listbox.delete(sel[0])
            # 外部ファイルに保存
            config.save_clean_patterns(self._get_current_patterns())

    def _reset_clean_patterns(self):
        """外部ファイルから再読み込みする（ファイルがなければ初期値）"""
        patterns = config.load_clean_patterns()
        self.clean_pat_listbox.delete(0, tk.END)
        for pat in patterns:
            self.clean_pat_listbox.insert(tk.END, pat)

    def _get_current_patterns(self) -> list[str]:
        return list(self.clean_pat_listbox.get(0, tk.END))

    def _scan_clean_archives(self):
        root_dir = self.clean_dir_var.get()
        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return

        self.clean_scan_btn.config(state=tk.DISABLED)
        self.clean_exec_btn.config(state=tk.DISABLED)
        self.clean_res_label.config(text="スキャン中...")
        self.clean_tree.delete(*self.clean_tree.get_children())
        self.clean_scan_results = []
        self.clean_prog_var.set(0)

        opts = {
            "root_dir": root_dir,
            "patterns": self._get_current_patterns(),
            "recursive": self.clean_recursive_var.get(),
            "check_nesting": self.clean_nesting_var.get(),
            "check_shorten": self.clean_shorten_var.get(),
        }

        threading.Thread(target=self._run_clean_scan, args=(opts,), daemon=True).start()

    def _run_clean_scan(self, opts):
        try:
            results = scan_archives_for_cleaning(
                root_dir=opts["root_dir"],
                patterns=opts["patterns"],
                recursive=opts["recursive"],
                check_nesting=opts["check_nesting"],
                check_long_names=opts["check_shorten"],
                progress_callback=lambda c, t: self.root.after(0, self._update_clean_progress, c, t),
            )
            self.root.after(0, self._finish_clean_scan, results)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"スキャン中にエラーが発生しました:\n{e}"))
            self.root.after(0, self._finish_clean_scan, [])

    def _update_clean_progress(self, current, total):
        if total > 0:
            percent = (current / total) * 100
            self.clean_prog_var.set(percent)
            self.clean_status_var.set(f"処理中... {current} / {total} ({int(percent)}%)")

    def _finish_clean_scan(self, results):
        self.clean_scan_results = results
        total_matched = 0

        for r in results:
            files_str = ", ".join([os.path.basename(f) for f in r.matched_files])
            if not files_str:
                files_str = "(なし)"
                
            nest_shorten = []
            if r.has_nested_folders: nest_shorten.append("階層")
            if r.long_name_files: nest_shorten.append("名前")
            ns_str = "+".join(nest_shorten) if nest_shorten else "-"

            self.clean_tree.insert("", tk.END, values=(r.archive_name, files_str, ns_str))
            total_matched += len(r.matched_files)

        self.clean_res_label.config(text=f"対象: 書庫 {len(results)} 件 / ファイル {total_matched} 個")
        self.clean_scan_btn.config(state=tk.NORMAL)
        
        if results:
            self.clean_exec_btn.config(state=tk.NORMAL)
        self.clean_status_var.set("スキャン完了")

    def _execute_clean(self):
        if not self.clean_scan_results:
            return

        if not messagebox.askyesno("確認", "リストアップされた書庫の最適化を実行します。\nよろしいですか？"):
            return

        self.is_running = True
        self.cancel_requested = False
        self.clean_scan_btn.config(state=tk.DISABLED)
        self.clean_exec_btn.config(state=tk.DISABLED)
        self.clean_cancel_btn.config(state=tk.NORMAL)
        self.clean_prog_var.set(0)

        opts = {
            "do_nesting": self.clean_nesting_var.get(),
            "do_shorten": self.clean_shorten_var.get(),
        }

        threading.Thread(target=self._run_clean_batch, args=(opts,), daemon=True).start()

    def _run_clean_batch(self, opts):
        try:
            results = batch_clean_archives(
                scan_results=self.clean_scan_results,
                do_nesting=opts["do_nesting"],
                do_shorten=opts["do_shorten"],
                progress_callback=lambda c, t: self.root.after(0, self._update_clean_progress, c, t),
                cancel_check=lambda: self.cancel_requested
            )
            
            # 結果集計
            success_count = sum(1 for r in results if r.success)
            fail_count = len(results) - success_count
            del_total = sum(r.deleted_count for r in results)
            flat_total = sum(r.flattened_count for r in results)
            short_total = sum(r.shortened_count for r in results)
            
            msg = f"処理完了: {success_count}件\n"
            msg += f"- 削除したファイル: {del_total}件\n"
            msg += f"- 解消した階層: {flat_total}段\n"
            msg += f"- 短縮した名前: {short_total}件"
            if fail_count > 0:
                msg += f"\n\n※失敗: {fail_count}件"

            self.root.after(0, lambda: messagebox.showinfo("完了", msg))

            # 一旦リストをクリア（再スキャンが必要なため）
            self.root.after(0, self._clear_clean_results)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"予期せぬエラーが発生しました:\n{e}"))
            
        self.root.after(0, self._finish_clean_batch)

    def _clear_clean_results(self):
        self.clean_tree.delete(*self.clean_tree.get_children())
        self.clean_scan_results = []
        self.clean_res_label.config(text="待機中...")
        self.clean_status_var.set("完了")

    def _finish_clean_batch(self):
        self.is_running = False
        self.clean_scan_btn.config(state=tk.NORMAL)
        self.clean_cancel_btn.config(state=tk.DISABLED)
        # 再スキャンするまで実行ボタンは無効
        self.clean_exec_btn.config(state=tk.DISABLED)


# 部分適用のためのヘルパー
from functools import partial

if __name__ == "__main__":
    root = tk.Tk()
    # アイコン等あれば
    app = ArchiveFileManagerGUI(root)
    root.mainloop()
