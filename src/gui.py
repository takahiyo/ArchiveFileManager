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
from functools import partial

import config
from ui_settings import load_settings, save_settings
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
        self.root.geometry(f"{config.DEFAULT_WINDOW_WIDTH}x{config.DEFAULT_WINDOW_HEIGHT}")
        self.root.minsize(900, 700)
        
        # 処理状態管理
        self.is_running = False
        self.cancel_requested = False
        
        # 空フォルダ検索結果の保持用
        self.empty_folders_data = []  # 全データ
        self.sort_column = "path"
        self.dir_history = []
        self._load_history()
        self.sort_reverse = False
        
        # スタイル設定
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5)
        self.style.configure("Header.TLabel", font=("MS Gothic", 12, "bold"))
        self.style.configure("Status.TLabel", font=("MS Gothic", 9))
        self.style.configure("Bold.TCheckbutton", font=("MS Gothic", 9, "bold"))
        
        self._setup_ui()
        self._restore_settings()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._check_env()

    def _restore_settings(self):
        """保存済みの入力値を戻し、表示状態と保存イベントを設定する。"""
        self._saved_vars = {
            name: value for name, value in vars(self).items()
            if isinstance(value, (tk.BooleanVar, tk.StringVar))
            and name not in ('clean_pat_var', 'clean_status_var')
        }
        settings = load_settings()
        for name, variable in self._saved_vars.items():
            if name in settings:
                try:
                    if isinstance(variable, tk.BooleanVar):
                        if settings[name] not in ('True', 'False', '0', '1'):
                            continue
                        variable.set(settings[name] in ('True', '1'))
                    else:
                        variable.set(settings[name])
                except tk.TclError:
                    pass
        self.clean_date_filter_combo.set(settings.get('date_filter', '30日以内'))
        self._toggle_clean_patterns_widget()
        self._toggle_nesting_options()
        self._toggle_clean_date_widgets()
        self._on_target_fmt_changed()
        self.root.update_idletasks()
        width = max(config.DEFAULT_WINDOW_WIDTH, self.root.winfo_reqwidth())
        height = max(config.DEFAULT_WINDOW_HEIGHT, self.root.winfo_reqheight())
        try:
            width = max(self.root.winfo_reqwidth(), int(settings.get('width', width)))
            height = max(self.root.winfo_reqheight(), int(settings.get('height', height)))
        except ValueError:
            pass
        self.root.geometry(f'{min(width, self.root.winfo_screenwidth())}x{min(height, self.root.winfo_screenheight() - 80)}')
        if settings.get('maximized') == 'True' or height > self.root.winfo_screenheight() - 80:
            self.root.state('zoomed')
        for variable in self._saved_vars.values():
            variable.trace_add('write', self._persist_settings)
        self.clean_date_filter_combo.bind('<<ComboboxSelected>>', self._persist_settings, add='+')

    def _persist_settings(self, *args):
        """チェック状態・入力値・現在のウィンドウサイズを保存する。"""
        values = {name: variable.get() for name, variable in self._saved_vars.items()}
        values.update(date_filter=self.clean_date_filter_combo.get(),
                      width=self.root.winfo_width(), height=self.root.winfo_height(),
                      maximized=self.root.state() == 'zoomed')
        save_settings(values)

    def _close(self):
        """最後のサイズを保存して画面を終了する。"""
        self._persist_settings()
        self.root.destroy()

    def _show_filename_options(self):
        """ファイル名整理の各項目を選択するダイアログを開く。"""
        dialog = tk.Toplevel(self.root)
        dialog.title('ファイル名整理')
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        for label, variable in [
            ('半角 ! を全角 ！ に変換する（書庫名・書庫内の名前）', self.clean_symbols_var),
            ('長すぎるファイル名を短縮する', self.clean_shorten_var),
            ('拡張子を自動補正する', self.clean_fix_ext_var),
        ]:
            ttk.Checkbutton(frame, text=label, variable=variable).pack(anchor='w', pady=6)
        ttk.Button(frame, text='閉じる', command=dialog.destroy).pack(anchor='e', pady=(12, 0))
        dialog.grab_set()

    def _setup_ui(self):
        """UIコンポーネントの配置"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タブコントロール
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # タブ1: 書庫クリーン・変換
        self.tab_clean = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_clean, text=" 🧹 書庫クリーン・変換 ")
        self._setup_clean_tab(self.tab_clean)

        # タブ2: 空フォルダ
        self.tab_empty = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_empty, text=" 🗂 空フォルダ ")
        self._setup_empty_tab(self.tab_empty)
    def _setup_empty_tab(self, parent):
        dir_frame = ttk.LabelFrame(parent, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        path_frame = ttk.Frame(dir_frame)
        path_frame.pack(fill=tk.X)
        self.empty_dir_var = tk.StringVar()
        self.empty_dir_combo = ttk.Combobox(path_frame, textvariable=self.empty_dir_var, values=self.dir_history)
        self.empty_dir_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="参照...", command=partial(self._browse_folder, self.empty_dir_var)).pack(side=tk.RIGHT)
        
        # フィルタ
        filter_frame = ttk.LabelFrame(parent, text=" フィルタ ", padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        f_inner = ttk.Frame(filter_frame)
        f_inner.pack(fill=tk.X)
        ttk.Label(f_inner, text="フィルタ(名前):").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace("w", self._apply_filter)
        ttk.Entry(f_inner, textvariable=self.filter_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 結果表示エリア
        res_frame = ttk.Frame(parent)
        res_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scan_btn_frame = ttk.Frame(res_frame)
        scan_btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(scan_btn_frame, text="🔍 スキャン（プレビュー）", command=self._scan_empty_folders).pack(side=tk.LEFT)
        self.count_label = ttk.Label(scan_btn_frame, text="件数: 0件")
        self.count_label.pack(side=tk.LEFT, padx=10)

        # 一覧リスト (Treeview)
        tree_container = ttk.Frame(res_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_container, columns=("checked", "name", "path", "modified"), show="headings", selectmode="extended")
        
        # ヘッダー設定
        self.tree.heading("checked", text="☑", command=lambda: self._sort_tree("checked"))
        self.tree.heading("name", text="フォルダ名", command=lambda: self._sort_tree("name"))
        self.tree.heading("path", text="フルパス", command=lambda: self._sort_tree("path"))
        self.tree.heading("modified", text="更新日時", command=lambda: self._sort_tree("modified"))
        
        self.tree.column("checked", width=40, anchor="center", stretch=False)
        self.tree.column("name", width=150, anchor="w")
        self.tree.column("path", width=300, anchor="w")
        self.tree.column("modified", width=120, anchor="w")

        scrollbar_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ダブルクリックでチェック切り替えなど
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        btn_select_frame = ttk.Frame(res_frame)
        btn_select_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_select_frame, text="全選択", command=self._select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_select_frame, text="全解除", command=self._deselect_all).pack(side=tk.LEFT)

        exec_frame = ttk.Frame(parent)
        exec_frame.pack(fill=tk.X, pady=(0, 10))
        self.delete_btn = ttk.Button(exec_frame, text="▶ 選択したフォルダを削除", command=self._delete_selected, state=tk.DISABLED, style="Accent.TButton")
        self.delete_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # -------------------------------------------------------------------------
    # タブ3: 書庫クリーン
    # -------------------------------------------------------------------------
    def _setup_clean_tab(self, parent):
        self.clean_scan_results = []
        
        dir_frame = ttk.LabelFrame(parent, text=" 対象フォルダ ", padding="10")
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        path_frame = ttk.Frame(dir_frame)
        path_frame.pack(fill=tk.X)
        self.clean_dir_var = tk.StringVar()
        self.clean_dir_combo = ttk.Combobox(path_frame, textvariable=self.clean_dir_var, values=self.dir_history)
        self.clean_dir_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="参照...", command=partial(self._browse_folder, self.clean_dir_var)).pack(side=tk.RIGHT)
        
        opt_frame = ttk.Frame(dir_frame)
        opt_frame.pack(fill=tk.X, pady=(8, 0))
        self.clean_recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="下層フォルダも対象にする", variable=self.clean_recursive_var).pack(side=tk.LEFT, padx=(0, 15))

        self.clean_date_filter_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="更新日時で絞り込む", variable=self.clean_date_filter_enabled_var, command=self._toggle_clean_date_widgets).pack(side=tk.LEFT, padx=(0, 5))
        self.clean_date_filter_combo = ttk.Combobox(opt_frame, values=["7日以内", "30日以内", "90日以内", "365日以内", "カスタム"], state="readonly", width=12)
        self.clean_date_filter_combo.set("30日以内")
        self.clean_date_filter_combo.pack(side=tk.LEFT, padx=5)
        self.clean_date_filter_combo.bind("<<ComboboxSelected>>", self._on_clean_date_combo_changed)
        
        self.clean_custom_days_frame = ttk.Frame(opt_frame)
        self.clean_custom_days_frame.pack(side=tk.LEFT)
        self.clean_custom_days_var = tk.StringVar(value="14")
        self.clean_custom_days_entry = ttk.Entry(self.clean_custom_days_frame, textvariable=self.clean_custom_days_var, width=5)
        self.clean_custom_days_entry.pack(side=tk.LEFT)
        ttk.Label(self.clean_custom_days_frame, text="日以内").pack(side=tk.LEFT, padx=2)

        # 抽出・処理条件
        cond_frame = ttk.LabelFrame(parent, text=" 抽出・処理条件 ", padding="10")
        cond_frame.pack(fill=tk.X, pady=(0, 10))

        # 退避書庫の除外設定も既存の BooleanVar 自動保存に含める。
        self.clean_exclude_original_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cond_frame, text="_Original を含む書庫を対象外にする", variable=self.clean_exclude_original_var).pack(anchor="w", pady=(0, 4))

        cond_top_frame = ttk.Frame(cond_frame)
        cond_top_frame.pack(fill=tk.X, pady=(0, 4))
        
        self.clean_do_clean_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cond_top_frame, text="指定パターンの不要ファイルを削除する", variable=self.clean_do_clean_var, command=self._toggle_clean_patterns_widget).pack(side=tk.LEFT, anchor="n", padx=(0, 25))

        nest_block = ttk.Frame(cond_top_frame)
        nest_block.pack(side=tk.LEFT, anchor="n")

        self.clean_nesting_var = tk.BooleanVar(value=True)
        self.clean_nesting_chk = ttk.Checkbutton(
            nest_block, 
            text="余分な入れ子を解消する", 
            variable=self.clean_nesting_var, 
            command=self._toggle_nesting_options
        )
        self.clean_nesting_chk.pack(anchor="w")
        
        self.clean_chapter_organize_var = tk.BooleanVar(value=True)
        self.clean_chapter_organize_chk = ttk.Checkbutton(
            nest_block, 
            text="└ 話数別に整理（Cover優先・連番化・階層解消）", 
            variable=self.clean_chapter_organize_var
        )
        self.clean_chapter_organize_chk.pack(anchor="w", padx=(15, 0), pady=(2, 0))

        cond_bot_frame = ttk.Frame(cond_frame)
        cond_bot_frame.pack(fill=tk.X, pady=(4, 0))

        self.clean_shorten_var = tk.BooleanVar(value=True)
        
        self.clean_fix_ext_var = tk.BooleanVar(value=True)
        self.clean_symbols_var = tk.BooleanVar(value=True)
        ttk.Button(cond_bot_frame, text="ファイル名整理...", command=self._show_filename_options).pack(side=tk.LEFT, padx=(0, 15))
        
        self.clean_preserve_timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cond_bot_frame, text="タイムスタンプを維持する", variable=self.clean_preserve_timestamp_var).pack(side=tk.LEFT)

        out_frame = ttk.LabelFrame(parent, text=" 出力設定 (出力形式・圧縮率) ", padding="10")
        out_frame.pack(fill=tk.X, pady=(0, 10))
        
        fmt_frame = ttk.Frame(out_frame)
        fmt_frame.pack(fill=tk.X, pady=2)
        ttk.Label(fmt_frame, text="出力フォーマット:").pack(side=tk.LEFT, padx=(0, 5))
        self.target_fmt_var = tk.StringVar(value="元の形式を維持")
        fmt_values = ["元の形式を維持", "ZIP", "RAR", "7z"]
        self.target_fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.target_fmt_var, values=fmt_values, state="readonly", width=18)
        self.target_fmt_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.target_fmt_combo.bind("<<ComboboxSelected>>", self._on_target_fmt_changed)
        
        ttk.Label(fmt_frame, text="圧縮レベル:").pack(side=tk.LEFT, padx=(0, 5))
        self.comp_level_var = tk.StringVar(value="無圧縮")
        self.comp_level_combo = ttk.Combobox(fmt_frame, textvariable=self.comp_level_var, values=config.COMPRESSION_LEVEL_NAMES, state="readonly", width=10)
        self.comp_level_combo.pack(side=tk.LEFT, padx=(0, 15))
        
        self.delete_orig_var = tk.BooleanVar(value=False)
        self.delete_orig_chk = ttk.Checkbutton(fmt_frame, text="変換後に元ファイルを削除する", variable=self.delete_orig_var)
        self.delete_orig_chk.pack(side=tk.LEFT)

        self.pat_frame = ttk.LabelFrame(parent, text=" 削除パターン設定 ", padding="10")
        self.pat_frame.pack(fill=tk.X, pady=(0, 10))
        
        pat_input_frame = ttk.Frame(self.pat_frame)
        pat_input_frame.pack(fill=tk.X, pady=(0, 5))
        self.clean_pat_var = tk.StringVar()
        ttk.Entry(pat_input_frame, textvariable=self.clean_pat_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(pat_input_frame, text="追加", command=self._add_clean_pattern).pack(side=tk.RIGHT)
        
        list_frame = ttk.Frame(self.pat_frame)
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
        
        self._reset_clean_patterns()

        res_frame = ttk.Frame(parent)
        res_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scan_btn_frame = ttk.Frame(res_frame)
        scan_btn_frame.pack(fill=tk.X, pady=(0, 5))
        self.clean_scan_btn = ttk.Button(scan_btn_frame, text="🔍 スキャン（プレビュー）", command=self._scan_clean_archives)
        self.clean_scan_btn.pack(side=tk.LEFT)
        self.clean_res_label = ttk.Label(scan_btn_frame, text="待機中...")
        self.clean_res_label.pack(side=tk.LEFT, padx=10)

        tree_container = ttk.Frame(res_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.clean_tree = ttk.Treeview(tree_container, columns=("checked", "archive", "path", "clean", "nest_shorten", "convert", "mtime"), show="headings", height=5)
        self.clean_tree.heading("checked", text="☑", command=lambda: self._sort_clean_tree("checked"))
        self.clean_tree.heading("archive", text="書庫名", command=lambda: self._sort_clean_tree("archive"))
        self.clean_tree.heading("path", text="フルパス", command=lambda: self._sort_clean_tree("path"))
        self.clean_tree.heading("clean", text="クリーン削除", command=lambda: self._sort_clean_tree("clean"))
        self.clean_tree.heading("nest_shorten", text="階層/名前", command=lambda: self._sort_clean_tree("nest_shorten"))
        self.clean_tree.heading("convert", text="変換", command=lambda: self._sort_clean_tree("convert"))
        self.clean_tree.heading("mtime", text="更新日時", command=lambda: self._sort_clean_tree("mtime"))
        
        self.clean_tree.column("checked", width=40, anchor="center", stretch=False)
        self.clean_tree.column("archive", width=200, anchor="w")
        self.clean_tree.column("path", width=300, anchor="w")
        self.clean_tree.column("clean", width=120, anchor="center")
        self.clean_tree.column("nest_shorten", width=100, anchor="center")
        self.clean_tree.column("convert", width=130, anchor="center")
        self.clean_tree.column("mtime", width=120, anchor="w")
        
        clean_scroll_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.clean_tree.yview)
        clean_scroll_x = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.clean_tree.xview)
        self.clean_tree.configure(yscrollcommand=clean_scroll_y.set, xscrollcommand=clean_scroll_x.set)

        clean_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        clean_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.clean_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.clean_tree.bind("<Double-1>", self._on_clean_tree_double_click)
        self.clean_tree.bind("<ButtonRelease-1>", self._on_clean_tree_click)

        btn_select_frame = ttk.Frame(res_frame)
        btn_select_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_select_frame, text="全選択", command=self._clean_select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_select_frame, text="全解除", command=self._clean_deselect_all).pack(side=tk.LEFT)

        self._toggle_clean_date_widgets()
        self._on_target_fmt_changed()
        self._toggle_clean_patterns_widget()

        exec_frame = ttk.Frame(parent)
        exec_frame.pack(fill=tk.X, pady=(0, 10))
        self.clean_exec_btn = ttk.Button(exec_frame, text="▶ 処理実行", command=self._execute_clean, state=tk.DISABLED, style="Accent.TButton")
        self.clean_exec_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.clean_cancel_btn = ttk.Button(exec_frame, text="キャンセル", command=self._request_cancel, state=tk.DISABLED)
        self.clean_cancel_btn.pack(side=tk.RIGHT)
        
        log_frame = ttk.LabelFrame(parent, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.log_text = tk.Text(log_frame, height=5, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill=tk.X)
        self.clean_prog_var = tk.DoubleVar()
        self.clean_prog = ttk.Progressbar(prog_frame, variable=self.clean_prog_var, maximum=100)
        self.clean_prog.pack(fill=tk.X, side=tk.TOP)
        self.clean_status_var = tk.StringVar(value="待機中...")
        ttk.Label(prog_frame, textvariable=self.clean_status_var, style="Status.TLabel").pack(side=tk.LEFT, pady=2)
    def _check_env(self):
        """環境チェック"""
        errors = config.validate_environment()
        if errors:
            msg = "環境に問題が見つかりました:\n\n" + "\n".join(errors)
            messagebox.showerror("環境エラー", msg)
            self._log("環境エラー: " + ", ".join(errors))
            self.clean_exec_btn.config(state=tk.DISABLED)

    def _browse_folder(self, target_var):
        path = filedialog.askdirectory()
        if path:
            norm_path = os.path.normpath(path)
            current_val = target_var.get().strip()
            if current_val:
                # すでに入力がある場合、追加するか上書きするか確認する
                if messagebox.askyesno("フォルダの追加", "新しく選択したフォルダを追加しますか？\n（「いいえ」を選ぶと現在の内容を上書きします）"):
                    # 既存のパスリストを取得
                    existing_paths = [p.strip() for p in current_val.split(";") if p.strip()]
                    if norm_path not in existing_paths:
                        existing_paths.append(norm_path)
                    target_var.set(";".join(existing_paths))
                else:
                    target_var.set(norm_path)
            else:
                target_var.set(norm_path)

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
    def _request_cancel(self):
        if messagebox.askyesno("キャンセル", "処理を中断しますか？"):
            self.cancel_requested = True
            self._log("!!! 中断リクエストを受け付けました。現在の処理が完了次第停止します。")
            self.clean_cancel_btn.config(state=tk.DISABLED)

    def _scan_empty_folders(self):
        path = self.empty_dir_var.get()
        paths = [p.strip() for p in path.split(";") if p.strip()]
        if not paths:
            messagebox.showwarning("入力エラー", "対象フォルダを指定してください。")
            return
        for p in paths:
            if not os.path.isdir(p):
                messagebox.showwarning("入力エラー", f"フォルダが存在しません:\n{p}")
                return

        self._add_to_history(path)

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
            
        if not messagebox.askyesno("削除確認", f"{len(targets)} 件の空フォルダを削除します。\nよろしいですか？\n（フォルダはごみ箱へ移動されます）"):
            return
            
        # 削除実行
        results = delete_folders(targets)
        
        success_count = sum(1 for r in results if r["success"])
        failed_results = [r for r in results if not r["success"]]
        fail_count = len(failed_results)
        
        msg = f"削除完了: {success_count}件"
        if fail_count > 0:
            msg += f"\n\n▼ 削除失敗: {fail_count}件"
            msg += "\n----------------------------------------"
            for r in failed_results[:5]:
                folder_name = os.path.basename(r["path"])
                msg += f"\n・{folder_name} :\n  {r['message']}"
            if fail_count > 5:
                msg += f"\n・他 {fail_count - 5} 件..."
            msg += "\n----------------------------------------"
            msg += "\n※フォルダが別のアプリで開かれているか、権限がない可能性があります。"
            
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
    def _on_target_fmt_changed(self, event=None):
        if self.target_fmt_var.get() == "元の形式を維持":
            self.delete_orig_var.set(False)
            self.delete_orig_chk.configure(state=tk.DISABLED)
        else:
            self.delete_orig_chk.configure(state=tk.NORMAL)

    def _toggle_clean_patterns_widget(self):
        state = tk.NORMAL if self.clean_do_clean_var.get() else tk.DISABLED
        def set_state(widget, state):
            try:
                widget.configure(state=state)
            except:
                pass
            for child in widget.winfo_children():
                set_state(child, state)
        set_state(self.pat_frame, state)

    def _sort_clean_tree(self, col):
        if getattr(self, "clean_sort_column", None) == col:
            self.clean_sort_reverse = not getattr(self, "clean_sort_reverse", False)
        else:
            self.clean_sort_column = col
            self.clean_sort_reverse = False
            
        def get_val(item):
            if col == "checked": return item.is_checked
            if col == "archive": return item.archive_name.lower()
            if col == "path": return item.archive_path.lower()
            if col == "clean": return len(item.matched_files)
            if col == "nest_shorten": return f"{item.has_nested_folders}_{len(item.long_name_files)}"
            if col == "convert": return f"{item.needs_conversion}_{item.target_format}"
            if col == "mtime": return item.mtime
            return ""
            
        self.clean_scan_results.sort(key=get_val, reverse=self.clean_sort_reverse)
        
        for c in ["checked", "archive", "path", "clean", "nest_shorten", "convert", "mtime"]:
            text = self.clean_tree.heading(c, "text").replace(" ▲", "").replace(" ▼", "")
            if c == col:
                text += " ▼" if self.clean_sort_reverse else " ▲"
            self.clean_tree.heading(c, text=text)

        self._rebuild_clean_tree()

    def _rebuild_clean_tree(self):
        self.clean_tree.delete(*self.clean_tree.get_children())
        for r in self.clean_scan_results:
            mark = "☑" if r.is_checked else "☐"
            if r.matched_files:
                clean_str = f"{len(r.matched_files)}件"
            else:
                clean_str = "-"
            ns_list = []
            if r.has_chapter_folders: ns_list.append("話数整理")
            elif r.has_nested_folders: ns_list.append("階層")
            if r.long_name_files: ns_list.append("名前")
            if r.symbol_name_files or '!' in r.archive_name: ns_list.append("記号")
            ns_str = "+".join(ns_list) if ns_list else "-"
            
            conv_list = []
            if r.extension_fixed_msg:
                conv_list.append("拡張子修正")
            if r.needs_conversion:
                conv_list.append(f"{r.original_format}->{r.target_format}")
            elif r.target_format and r.target_format != r.original_format:
                conv_list.append(f"->{r.target_format}")
            conv_str = ", ".join(conv_list) if conv_list else "維持"
            
            self.clean_tree.insert("", tk.END, values=(mark, r.archive_name, r.archive_path, clean_str, ns_str, conv_str, r.mtime_str))

    def _scan_clean_archives(self):
        root_dir = self.clean_dir_var.get()
        paths = [p.strip() for p in root_dir.split(";") if p.strip()]
        if not paths:
            messagebox.showwarning("入力エラー", "対象フォルダを指定してください。")
            return
        for p in paths:
            if not os.path.isdir(p):
                messagebox.showwarning("入力エラー", f"フォルダが存在しません:\n{p}")
                return

        self._add_to_history(root_dir)

        self.clean_scan_btn.config(state=tk.DISABLED)
        self.clean_exec_btn.config(state=tk.DISABLED)
        self.clean_res_label.config(text="スキャン中...")
        self.clean_tree.delete(*self.clean_tree.get_children())
        self.clean_scan_results = []
        self.clean_prog_var.set(0)

        days_within = None
        if self.clean_date_filter_enabled_var.get():
            val = self.clean_date_filter_combo.get()
            if val == "7日以内":
                days_within = 7
            elif val == "30日以内":
                days_within = 30
            elif val == "90日以内":
                days_within = 90
            elif val == "365日以内":
                days_within = 365
            elif val == "カスタム":
                try:
                    days_within = int(self.clean_custom_days_var.get())
                    if days_within <= 0:
                        raise ValueError()
                except ValueError:
                    messagebox.showwarning("入力エラー", "日数は1以上の正の整数で指定してください。")
                    self.clean_scan_btn.config(state=tk.NORMAL)
                    self.clean_res_label.config(text="待機中...")
                    return

        is_nesting_on = self.clean_nesting_var.get()
        opts = {
            "root_dir": root_dir,
            "patterns": self._get_current_patterns() if self.clean_do_clean_var.get() else None,
            "recursive": self.clean_recursive_var.get(),
            "exclude_original": self.clean_exclude_original_var.get(),
            "check_nesting": is_nesting_on,
            "check_chapter_organize": is_nesting_on and self.clean_chapter_organize_var.get(),
            "check_shorten": self.clean_shorten_var.get(),
            "normalize_symbols": self.clean_symbols_var.get(),
            "days_within": days_within,
            "target_format": None if self.target_fmt_var.get() == "元の形式を維持" else self.target_fmt_var.get(),
            "fix_extensions": self.clean_fix_ext_var.get(),
        }

        threading.Thread(target=self._run_clean_scan, args=(opts,), daemon=True).start()

    def _run_clean_scan(self, opts):
        try:
            results = scan_archives_for_cleaning(
                root_dir=opts["root_dir"],
                patterns=opts["patterns"],
                recursive=opts["recursive"],
                exclude_original=opts["exclude_original"],
                check_nesting=opts["check_nesting"],
                check_long_names=opts["check_shorten"],
                normalize_symbols=opts["normalize_symbols"],
                days_within=opts["days_within"],
                target_format=opts["target_format"],
                fix_extensions=opts["fix_extensions"],
                check_chapter_organize=opts["check_chapter_organize"],
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
        for c in ["checked", "archive", "path", "clean", "nest_shorten", "convert", "mtime"]:
            text = self.clean_tree.heading(c, "text").replace(" ▲", "").replace(" ▼", "")
            self.clean_tree.heading(c, text=text)
        self.clean_sort_column = None
            
        self._rebuild_clean_tree()
        self.clean_res_label.config(text=f"対象: 書庫 {len(results)} 件")
        self.clean_scan_btn.config(state=tk.NORMAL)
        self._update_clean_exec_button()
        self.clean_status_var.set("スキャン完了")

    def _execute_clean(self):
        if not self.clean_scan_results:
            return

        checked_results = [r for r in self.clean_scan_results if r.is_checked]
        if not checked_results:
            messagebox.showwarning("警告", "対象の書庫が選択されていません。")
            return

        if not messagebox.askyesno("確認", f"選択された {len(checked_results)} 件の書庫の最適化・変換を実行します。\nよろしいですか？"):
            return

        self.is_running = True
        self.cancel_requested = False
        self.clean_scan_btn.config(state=tk.DISABLED)
        self.clean_exec_btn.config(state=tk.DISABLED)
        self.clean_cancel_btn.config(state=tk.NORMAL)
        self.clean_prog_var.set(0)
        self.clean_status_var.set(f"処理中... 0 / {len(checked_results)} (0%)")
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        level_name = self.comp_level_var.get()
        comp_level = config.COMPRESSION_LEVELS.get(level_name, 3)

        is_nesting_on = self.clean_nesting_var.get()
        opts = {
            "do_clean": self.clean_do_clean_var.get(),
            "do_nesting": is_nesting_on,
            "do_chapter_organize": is_nesting_on and self.clean_chapter_organize_var.get(),
            "do_shorten": self.clean_shorten_var.get(),
            "normalize_symbols": self.clean_symbols_var.get(),
            "fix_extensions": self.clean_fix_ext_var.get(),
            "delete_original": self.delete_orig_var.get(),
            "preserve_timestamp": self.clean_preserve_timestamp_var.get(),
            "compression_level": comp_level,
            "scan_results": checked_results,
        }

        threading.Thread(target=self._run_clean_batch, args=(opts,), daemon=True).start()

    def _run_clean_batch(self, opts):
        try:
            results = batch_clean_archives(
                scan_results=opts["scan_results"],
                do_clean=opts["do_clean"],
                do_nesting=opts["do_nesting"],
                do_shorten=opts["do_shorten"],
                normalize_symbols=opts["normalize_symbols"],
                fix_extensions=opts["fix_extensions"],
                delete_original=opts["delete_original"],
                preserve_timestamp=opts["preserve_timestamp"],
                compression_level=opts["compression_level"],
                do_chapter_organize=opts["do_chapter_organize"],
                progress_callback=lambda c, t: self.root.after(0, self._update_clean_progress, c, t),
                log_callback=self._log,
                status_callback=lambda status: self.root.after(0, self.clean_status_var.set, status),
                cancel_check=lambda: self.cancel_requested
            )
            
            success_count = sum(1 for r in results if r.success)
            fail_count = len(results) - success_count
            del_total = sum(r.deleted_count for r in results)
            flat_total = sum(r.flattened_count for r in results)
            short_total = sum(r.shortened_count for r in results)
            symbol_total = sum(r.symbol_count for r in results)
            org_total = sum(r.organized_files_count for r in results)
            
            msg = f"処理完了: {success_count}件\n"
            if org_total: msg += f"- 話数整理したファイル: {org_total}件\n"
            if del_total: msg += f"- 削除したファイル: {del_total}件\n"
            if flat_total: msg += f"- 解消した階層: {flat_total}段\n"
            if short_total: msg += f"- 短縮した名前: {short_total}件\n"
            if symbol_total: msg += f"- 記号を整理した名前: {symbol_total}件\n"
            
            if fail_count > 0:
                msg += f"\n\n※失敗: {fail_count}件\n※失敗原因の詳細は実行ファイルと同階層の 'archive_cleaner.log' を参照してください。"

            if self.cancel_requested:
                msg = "中断されました。\n\n" + msg
            self.root.after(0, lambda: messagebox.showinfo("完了", msg))

            self.root.after(0, self._clear_clean_results)

        except Exception as e:
            logger.exception("書庫クリーンの一括処理に失敗")
            self.root.after(0, lambda error=str(e): messagebox.showerror("エラー", f"予期せぬエラーが発生しました:\n{error}"))
            
        self.root.after(0, self._finish_clean_batch)

    def _clear_clean_results(self):
        self.clean_tree.delete(*self.clean_tree.get_children())
        self.clean_scan_results = []
        self.clean_res_label.config(text="待機中...")
        if self.cancel_requested:
            self.clean_status_var.set("中断されました")
        else:
            self.clean_status_var.set("完了")

    def _finish_clean_batch(self):
        self.is_running = False
        self.clean_scan_btn.config(state=tk.NORMAL)
        self.clean_cancel_btn.config(state=tk.DISABLED)
        self.clean_exec_btn.config(state=tk.DISABLED)

    def _add_clean_pattern(self):
        pat = self.clean_pat_var.get().strip()
        if pat:
            patterns = self._get_current_patterns()
            if pat not in patterns:
                self.clean_pat_listbox.insert(tk.END, pat)
                self.clean_pat_var.set("")
                self._save_patterns_to_file()

    def _toggle_nesting_options(self):
        """余分な入れ子を解消するチェックに応じて話数別整理の活性/非活性を切り替える"""
        if self.clean_nesting_var.get():
            self.clean_chapter_organize_chk.config(state=tk.NORMAL)
        else:
            self.clean_chapter_organize_chk.config(state=tk.DISABLED)

    def _remove_clean_pattern(self):
        selected = self.clean_pat_listbox.curselection()
        if selected:
            self.clean_pat_listbox.delete(selected[0])
            self._save_patterns_to_file()

    def _reset_clean_patterns(self):
        self.clean_pat_listbox.delete(0, tk.END)
        import os
        path = "clean_patterns.txt"
        if not os.path.exists(path):
            path = os.path.join("dist", "clean_patterns.txt")
        
        default_patterns = ["*.txt", "*.url", "*.lnk", "*.net", "Thumbs.db", "desktop.ini", ".DS_Store", ".com", "zhonyk.*", "*.rar"]
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    patterns = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
                for p in patterns:
                    self.clean_pat_listbox.insert(tk.END, p)
                return
            except Exception as e:
                logger.error(f"パターンファイル読み込み失敗: {e}")
        
        for p in default_patterns:
            self.clean_pat_listbox.insert(tk.END, p)

    def _save_patterns_to_file(self):
        import os
        path = "clean_patterns.txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# ArchiveFileManager - 書庫クリーン削除パターン設定\n")
                f.write("# 1行に1つのパターン（グロブ形式）を記述してください。\n")
                for p in self._get_current_patterns():
                    f.write(f"{p}\n")
        except Exception as e:
            logger.error(f"パターンファイル書き出し失敗: {e}")

    def _get_current_patterns(self) -> list[str]:
        return list(self.clean_pat_listbox.get(0, tk.END))

    def _on_clean_tree_click(self, event):
        region = self.clean_tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.clean_tree.identify_column(event.x)
            if col == "#1":
                item_id = self.clean_tree.identify_row(event.y)
                self._toggle_clean_check(item_id)

    def _on_clean_tree_double_click(self, event):
        item_id = self.clean_tree.identify_row(event.y)
        if not item_id:
            return
        values = self.clean_tree.item(item_id, "values")
        archive_path = values[2]
        target_item = next((x for x in self.clean_scan_results if x.archive_path == archive_path), None)
        if target_item and os.path.isfile(target_item.archive_path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(target_item.archive_path)])

    def _toggle_clean_check(self, item_id):
        if not item_id:
            return
        values = self.clean_tree.item(item_id, "values")
        archive_path = values[2]
        target_item = next((x for x in self.clean_scan_results if x.archive_path == archive_path), None)
        if target_item:
            target_item.is_checked = not target_item.is_checked
            new_mark = "☑" if target_item.is_checked else "☐"
            new_values = list(values)
            new_values[0] = new_mark
            self.clean_tree.item(item_id, values=new_values)
            self._update_clean_exec_button()

    def _clean_select_all(self):
        if not self.clean_scan_results:
            return
        for item in self.clean_scan_results:
            item.is_checked = True
        self._refresh_clean_tree_marks()

    def _clean_deselect_all(self):
        if not self.clean_scan_results:
            return
        for item in self.clean_scan_results:
            item.is_checked = False
        self._refresh_clean_tree_marks()

    def _refresh_clean_tree_marks(self):
        for item_id in self.clean_tree.get_children():
            values = self.clean_tree.item(item_id, "values")
            archive_path = values[2]
            target_item = next((x for x in self.clean_scan_results if x.archive_path == archive_path), None)
            if target_item:
                new_mark = "☑" if target_item.is_checked else "☐"
                new_values = list(values)
                new_values[0] = new_mark
                self.clean_tree.item(item_id, values=new_values)
        self._update_clean_exec_button()

    def _update_clean_exec_button(self):
        if not self.clean_scan_results:
            self.clean_exec_btn.config(state=tk.DISABLED, text="▶ 処理実行")
            return
        checked_count = sum(1 for r in self.clean_scan_results if r.is_checked)
        if checked_count > 0:
            self.clean_exec_btn.config(state=tk.NORMAL, text=f"▶ 選択した書庫の最適化・変換を実行 ({checked_count}件)")
        else:
            self.clean_exec_btn.config(state=tk.DISABLED, text="▶ 処理実行 (選択なし)")

    def _add_to_history(self, path):
        # セミコロンで分割して個別に標準化する
        paths = [os.path.normpath(p.strip()) for p in path.split(";") if p.strip()]
        normalized_path = ";".join(paths)
        if not normalized_path:
            return

        if normalized_path in self.dir_history:
            self.dir_history.remove(normalized_path)
        self.dir_history.insert(0, normalized_path)
        if len(self.dir_history) > 10:
            self.dir_history = self.dir_history[:10]
        self.clean_dir_combo['values'] = self.dir_history
        if hasattr(self, 'empty_dir_combo'):
            self.empty_dir_combo['values'] = self.dir_history
        self._save_history()

    def _save_history(self):
        try:
            with open("dir_history.txt", "w", encoding="utf-8") as f:
                for p in self.dir_history:
                    f.write(f"{p}\n")
        except Exception as e:
            logger.error(f"履歴保存失敗: {e}")

    def _load_history(self):
        self.dir_history = []
        if os.path.exists("dir_history.txt"):
            try:
                with open("dir_history.txt", "r", encoding="utf-8") as f:
                    self.dir_history = [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.error(f"履歴読み込み失敗: {e}")

    def _toggle_clean_date_widgets(self):
        state = tk.NORMAL if getattr(self, "clean_date_filter_enabled_var", tk.BooleanVar()).get() else tk.DISABLED
        if hasattr(self, "clean_date_filter_combo"):
            self.clean_date_filter_combo.config(state="readonly" if state == tk.NORMAL else tk.DISABLED)
            self._on_clean_date_combo_changed()

    def _on_clean_date_combo_changed(self, event=None):
        if not getattr(self, "clean_date_filter_enabled_var", tk.BooleanVar()).get():
            if hasattr(self, "clean_custom_days_entry"):
                self.clean_custom_days_entry.config(state=tk.DISABLED)
            return
            
        if hasattr(self, "clean_date_filter_combo") and self.clean_date_filter_combo.get() == "カスタム":
            self.clean_custom_days_entry.config(state=tk.NORMAL)
        elif hasattr(self, "clean_custom_days_entry"):
            self.clean_custom_days_entry.config(state=tk.DISABLED)
