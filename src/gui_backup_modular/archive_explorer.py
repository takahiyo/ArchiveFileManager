# -*- coding: utf-8 -*-
"""
ArchiveFileManager - アーカイブ内探索ダイアログ
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging

try:
    from archive_handler import get_archive_list, remove_from_archive
except ImportError:
    from ..archive_handler import get_archive_list, remove_from_archive

logger = logging.getLogger(__name__)

class ArchiveExplorerDialog(tk.Toplevel):
    def __init__(self, parent, archive_path):
        super().__init__(parent)
        self.title(f"アーカイブ探索: {os.path.basename(archive_path)}")
        self.geometry("600x400")
        self.archive_path = archive_path
        self._setup_ui()
        self._load_list()

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"場所: {self.archive_path}", font=("Consolas", 8)).pack(fill=tk.X, pady=(0, 5))

        # リスト
        self.tree = ttk.Treeview(main_frame, columns=("name"), show="headings")
        self.tree.heading("name", text="ファイル名 / パス")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scroll.set)

        # ボタン
        btn_frame = ttk.Frame(self, padding="5")
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="選択ファイルを削除", command=self._delete_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="閉じる", command=self.destroy).pack(side=tk.RIGHT)

    def _load_list(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        files = get_archive_list(self.archive_path)
        for f in sorted(files):
            self.tree.insert("", tk.END, values=(f,))

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected: return
        
        targets = [self.tree.item(i, "values")[0] for i in selected]
        if not messagebox.askyesno("削除確認", f"以下の {len(targets)} 件をアーカイブ内から直接削除しますか？\n（この操作は取り消せません）"):
            return
        
        if remove_from_archive(self.archive_path, targets):
            messagebox.showinfo("完了", "削除しました。")
            self._load_list()
        else:
            messagebox.showerror("エラー", "削除に失敗しました。")
