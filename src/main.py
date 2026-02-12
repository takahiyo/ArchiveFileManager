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

def main():
    # ログ出力先の設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            # 実行ファイルと同じ場所にログを出す場合はここを有効に
            # logging.FileHandler("app.log", encoding="utf-8")
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
