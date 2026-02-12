# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 設定管理
アプリ全体で使う定数・パスをこのファイルで一元管理します。
"""

import os
import sys

# ---------------------------------------------------------------------------
# アプリ情報
# ---------------------------------------------------------------------------
APP_NAME = "ArchiveFileManager"
APP_VERSION = "1.1.0"

# ---------------------------------------------------------------------------
# WinRAR 実行ファイルのパス
# ---------------------------------------------------------------------------
WINRAR_DIR = r"C:\Program Files\WinRAR"
RAR_EXE = os.path.join(WINRAR_DIR, "Rar.exe")
UNRAR_EXE = os.path.join(WINRAR_DIR, "UnRAR.exe")
WINRAR_EXE = os.path.join(WINRAR_DIR, "WinRAR.exe")

# ---------------------------------------------------------------------------
# 対応する圧縮ファイルの拡張子（小文字で統一）
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {
    ".zip", ".rar", ".7z",
    ".cbz", ".cbr", ".cb7",
}

# ---------------------------------------------------------------------------
# 変換先として選べる形式
# ---------------------------------------------------------------------------
TARGET_FORMATS = {
    "ZIP": {"extension": ".zip", "rar_switch": "-afzip"},
    "RAR": {"extension": ".rar", "rar_switch": ""},       # RAR がデフォルト
    "7z":  {"extension": ".7z",  "rar_switch": "-af7z"},   # WinRAR 7.x 以降
}

# ---------------------------------------------------------------------------
# 圧縮率の選択肢（WinRAR の -m スイッチに対応）
# ---------------------------------------------------------------------------
COMPRESSION_LEVELS = {
    "無圧縮": 0,   # -m0: ストア（圧縮なし）
    "最速":   1,   # -m1: 最速
    "標準":   3,   # -m3: 標準（デフォルト）
    "最高":   5,   # -m5: 最高圧縮
}

# 画面のドロップダウンに表示する順番
COMPRESSION_LEVEL_NAMES = ["無圧縮", "最速", "標準", "最高"]

# ---------------------------------------------------------------------------
# マジックバイト（ファイル先頭を読んで実際の形式を判別する）
# ---------------------------------------------------------------------------
MAGIC_BYTES = {
    "zip": b"PK",                          # 0x50 0x4B
    "rar": b"Rar!\x1a\x07",               # Rar!..
    "7z":  b"\x37\x7a\xbc\xaf\x27\x1c",   # 7z¼¯'.
}

# 拡張子 → 正式な形式名の対応
EXTENSION_TO_FORMAT = {
    ".zip": "zip",
    ".cbz": "zip",
    ".rar": "rar",
    ".cbr": "rar",
    ".7z":  "7z",
    ".cb7": "7z",
}

# 形式名 → 代表的な拡張子
FORMAT_TO_EXTENSION = {
    "zip": ".zip",
    "rar": ".rar",
    "7z":  ".7z",
}

# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def get_resource_path(relative_path: str) -> str:
    """PyInstaller で exe 化した場合にも正しくリソースパスを解決する"""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def validate_environment() -> list[str]:
    """
    起動時に実行環境をチェックし、問題があればメッセージのリストを返す。
    問題がなければ空リストを返す。
    """
    errors = []
    if not os.path.isfile(RAR_EXE):
        errors.append(f"Rar.exe が見つかりません: {RAR_EXE}")
    if not os.path.isfile(UNRAR_EXE):
        errors.append(f"UnRAR.exe が見つかりません: {UNRAR_EXE}")
    if not os.path.isfile(WINRAR_EXE):
        errors.append(f"WinRAR.exe が見つかりません: {WINRAR_EXE}")
    return errors
