# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 空フォルダ検索・削除
指定フォルダ以下の空フォルダを再帰的に検索し、削除する機能を提供します。
"""

import os
import datetime
import logging
import shutil

logger = logging.getLogger(__name__)


def scan_empty_folders(root_dir: str, days_within: int | None = None) -> list[dict]:
    """
    指定フォルダ以下（複数指定可）の空フォルダを再帰的に検索する。

    「空」の定義: フォルダの中にファイルもサブフォルダも存在しない状態。

    引数:
        root_dir: 検索対象のルートフォルダパス（セミコロン区切りで複数指定可）
        days_within: 指定された日数以内に更新されたフォルダのみ対象にする

    戻り値:
        空フォルダ情報の辞書リスト。各要素は以下のキーを持つ:
        - "name":      フォルダ名
        - "path":      フルパス
        - "modified":  更新日時（datetime オブジェクト）
        - "modified_str": 更新日時の表示用文字列
    """
    dirs = [d.strip() for d in root_dir.split(";") if d.strip()]
    empty_folders = []

    # フィルタ条件のタイムスタンプ計算
    threshold_time = None
    if days_within is not None and days_within > 0:
        import time
        threshold_time = time.time() - (days_within * 86400)

    for d in dirs:
        if not os.path.isdir(d):
            continue
        try:
            # ボトムアップで走査（深い階層から先に処理）
            for dirpath, dirnames, filenames in os.walk(d, topdown=False):
                # ルートフォルダ自体は対象外
                if os.path.normcase(os.path.abspath(dirpath)) == \
                   os.path.normcase(os.path.abspath(d)):
                    continue

                # ファイルもサブフォルダも含まなければ空
                if not dirnames and not filenames:
                    try:
                        mtime = os.path.getmtime(dirpath)
                        modified = datetime.datetime.fromtimestamp(mtime)
                        modified_str = modified.strftime("%Y/%m/%d %H:%M")
                    except OSError:
                        mtime = 0.0
                        modified = datetime.datetime.min
                        modified_str = "不明"

                    if threshold_time is not None and mtime < threshold_time:
                        # 期間外のためスキップ
                        continue

                    empty_folders.append({
                        "name": os.path.basename(dirpath),
                        "path": dirpath,
                        "modified": modified,
                        "modified_str": modified_str,
                    })
        except Exception as e:
            logger.error(f"空フォルダ検索エラー ({d}): {e}")

    return empty_folders


def delete_folders(folder_paths: list[str]) -> list[dict]:
    """
    指定されたフォルダを削除する。

    引数:
        folder_paths: 削除するフォルダのフルパスのリスト

    戻り値:
        削除結果のリスト。各要素は以下のキーを持つ:
        - "path":    フォルダパス
        - "success": 成功したか
        - "message": 結果メッセージ
    """
    import ctypes
    from ctypes import wintypes
    
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR)
        ]

    results = []
    
    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    FOF_NOERRORUI = 0x0400

    for folder_path in folder_paths:
        try:
            if not os.path.isdir(folder_path):
                results.append({
                    "path": folder_path,
                    "success": False,
                    "message": "フォルダが見つかりません（既に削除済み？）",
                })
                continue

            abs_path = os.path.abspath(folder_path)
            
            # ごみ箱へ移動 (SHFileOperationW)
            # pFromはダブルNULL終端である必要がある
            path_buffer = abs_path + '\0\0'
            
            shfos = SHFILEOPSTRUCTW()
            shfos.hwnd = None
            shfos.wFunc = FO_DELETE
            shfos.pFrom = path_buffer
            shfos.pTo = None
            shfos.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            
            ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(shfos))
            
            # 実際にフォルダが消えたか(またはごみ箱に入ったか)確認
            if not os.path.exists(abs_path):
                results.append({
                    "path": folder_path,
                    "success": True,
                    "message": "ごみ箱へ移動しました",
                })
                logger.info("削除完了（ごみ箱へ移動）: %s", folder_path)
            else:
                results.append({
                    "path": folder_path,
                    "success": False,
                    "message": f"削除失敗 (Error Code: {ret}) - ロックされている可能性があります",
                })
                logger.error("削除失敗: %s (Error Code: %s)", folder_path, ret)

        except Exception as e:
            results.append({
                "path": folder_path,
                "success": False,
                "message": f"例外エラー: {e}",
            })
            logger.error("削除失敗（例外）: %s (%s)", folder_path, e)

    return results
