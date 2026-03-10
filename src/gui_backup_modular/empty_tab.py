# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 空フォルダタブ
WinRAR無しでも動作します。
"""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

try:
    from empty_folder_scanner import scan_empty_folders, delete_folders
except ImportError:
    from ..empty_folder_scanner import scan_empty_folders, delete_folders

logger = logging.getLogger(__name__)

class EmptyTab(ttk.Frame):
    """
    「空フォルダ」タブのUIとロジック。
    """
    def __init__(self, parent, log_callback=None):
        super().__init__(parent, padding="10")
        self.log_callback = log_callback
        self.empty_folders_data = []
        self._setup_ui()

    def _setup_ui(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        self.empty_dir_var = tk.StringVar()
        ttk.Label(top_frame, text="対象フォルダ:").pack(side=tk.LEFT)
        ttk.Entry(top_frame, textvariable=self.empty_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(top_frame, text="参照...", command=lambda: self._browse_folder(self.empty_dir_var)).pack(side=tk.LEFT)
        ttk.Button(top_frame, text="🔍 検索開始", command=self._scan_empty_folders).pack(side=tk.LEFT, padx=(10, 0))

        # フィルタ
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(filter_frame, text="フィルタ:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace("w", self._apply_filter)
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.count_label = ttk.Label(filter_frame, text="件数: 0件")
        self.count_label.pack(side=tk.RIGHT)

        # 一覧 (Treeview)
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("checked", "name", "path", "modified")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        self.tree.heading("checked", text="☑")
        self.tree.heading("name", text="フォルダ名")
        self.tree.heading("path", text="フルパス")
        self.tree.heading("modified", text="更新日時")
        
        self.tree.column("checked", width=40, anchor="center", stretch=False)
        self.tree.column("name", width=150)
        self.tree.column("path", width=300)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # ボタン
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="全選択", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="全解除", command=self._deselect_all).pack(side=tk.LEFT, padx=2)
        self.delete_btn = ttk.Button(btn_frame, text="選択したフォルダを削除", command=self._delete_selected, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.RIGHT)

    def _browse_folder(self, target_var):
        path = filedialog.askdirectory()
        if path:
            target_var.set(os.path.normpath(path))

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _scan_empty_folders(self):
        path = self.empty_dir_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("入力エラー", "対象フォルダを正しく指定してください。")
            return
        
        try:
            self._log(f"空フォルダ検索開始: {path}")
            folders = scan_empty_folders(path)
            for f in folders:
                f["checked"] = True
            self.empty_folders_data = folders
            self._apply_filter()
            messagebox.showinfo("完了", f"{len(folders)} 件の空フォルダが見つかりました。")
        except Exception as e:
            logger.exception("検索エラー")
            self._log(f"エラー: {e}")

    def _apply_filter(self, *args):
        query = self.filter_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        count = 0
        for item in self.empty_folders_data:
            if query in item["name"].lower() or query in item["path"].lower():
                mark = "☑" if item["checked"] else "☐"
                self.tree.insert("", tk.END, values=(mark, item["name"], item["path"], item["modified_str"]))
                count += 1
        self.count_label.config(text=f"件数: {count}件")
        self._update_delete_btn()

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item_id and col == "#1":
            path = self.tree.item(item_id, "values")[2]
            for item in self.empty_folders_data:
                if item["path"] == path:
                    item["checked"] = not item["checked"]
                    break
            self._apply_filter()

    def _on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            path = self.tree.item(item_id, "values")[2]
            if os.path.isdir(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])

    def _select_all(self):
        for item in self.empty_folders_data:
            item["checked"] = True
        self._apply_filter()

    def _deselect_all(self):
        for item in self.empty_folders_data:
            item["checked"] = False
        self._apply_filter()

    def _update_delete_btn(self):
        count = sum(1 for x in self.empty_folders_data if x["checked"])
        self.delete_btn.config(state=tk.NORMAL if count > 0 else tk.DISABLED)

    def _delete_selected(self):
        targets = [x["path"] for x in self.empty_folders_data if x["checked"]]
        if not targets or not messagebox.askyesno("確認", f"{len(targets)} 件の空フォルダを削除しますか？"):
            return
        
        self._log(f"空フォルダ削除開始: {len(targets)}件")
        results = delete_folders(targets)
        for r in results:
            if r["success"]:
                self._log(f"  [OK] {r['path']}")
                self.empty_folders_data = [x for x in self.empty_folders_data if x["path"] != r["path"]]
            else:
                self._log(f"  [FAIL] {r['path']}: {r['message']}")
        self._apply_filter()
        messagebox.showinfo("完了", "削除処理が完了しました。")
