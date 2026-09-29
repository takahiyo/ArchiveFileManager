# -*- coding: utf-8 -*-
"""
ArchiveFileManager - エントリポイント
アプリケーションを起動します。
"""

import sys
import os
import tkinter as tk
import logging

# src ディレクトリをパスに追加（exe化の際にも必要）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui import ArchiveFileManagerGUI
import config

def main():
    # ログ出力先の設定（実行ファイルと同じパスに archive_cleaner.log を出力）
    log_file = os.path.join(config.get_exe_dir(), "archive_cleaner.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )
    
    root = tk.Tk()
    
    # ウィンドウアイコンの設定（ある場合）
    # icon_path = get_resource_path("icon.ico")
    # if os.path.exists(icon_path):
    #     root.iconbitmap(icon_path)
    
    app = ArchiveFileManagerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
