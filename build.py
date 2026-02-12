# -*- coding: utf-8 -*-
"""
ArchiveFileManager - ビルド設定 (PyInstaller)
コマンド: pyinstaller build.spec
"""

import os
from PyInstaller.utils.win32 import icon

# --- 設定 ---
APP_NAME = "ArchiveFileManager"
ENTRY_POINT = "src/main.py"
ICON_FILE = None # "assets/icon.ico"  (アイコンがあれば指定)

# --- スペックファイルの内容生成 ---
# 通常はコマンドラインで生成しますが、手動で定義することも可能です。
# ここでは簡易的なビルドスクリプトとして build.py を作成します。

import subprocess

def build():
    print("Building executable...")
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",          # GUIなのでコンソールを表示しない
        "--name", APP_NAME,
        "--clean",
        # "--icon", ICON_FILE, # アイコン指定時に有効化
        "--add-data", "src;src", # スクリプトディレクトリを含める
        ENTRY_POINT
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild successful! -> dist/" + APP_NAME + ".exe")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")
    except FileNotFoundError:
        print("\nError: PyInstaller not found. Please run 'pip install pyinstaller'.")

if __name__ == "__main__":
    build()
