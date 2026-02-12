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


def scan_empty_folders(root_dir: str) -> list[dict]:
    """
    指定フォルダ以下の空フォルダを再帰的に検索する。

    「空」の定義: フォルダの中にファイルもサブフォルダも存在しない状態。

    引数:
        root_dir: 検索対象のルートフォルダパス

    戻り値:
        空フォルダ情報の辞書リスト。各要素は以下のキーを持つ:
        - "name":      フォルダ名
        - "path":      フルパス
        - "modified":  更新日時（datetime オブジェクト）
        - "modified_str": 更新日時の表示用文字列
    """
    empty_folders = []

    # ボトムアップで走査（深い階層から先に処理）
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # ルートフォルダ自体は対象外
        if os.path.normcase(os.path.abspath(dirpath)) == \
           os.path.normcase(os.path.abspath(root_dir)):
            continue

        # ファイルもサブフォルダも含まなければ空
        if not dirnames and not filenames:
            try:
                mtime = os.path.getmtime(dirpath)
                modified = datetime.datetime.fromtimestamp(mtime)
                modified_str = modified.strftime("%Y/%m/%d %H:%M")
            except OSError:
                modified = datetime.datetime.min
                modified_str = "不明"

            empty_folders.append({
                "name": os.path.basename(dirpath),
                "path": dirpath,
                "modified": modified,
                "modified_str": modified_str,
            })

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
    results = []

    for folder_path in folder_paths:
        try:
            if not os.path.isdir(folder_path):
                results.append({
                    "path": folder_path,
                    "success": False,
                    "message": "フォルダが見つかりません（既に削除済み？）",
                })
                continue

            # 空フォルダなので os.rmdir で削除（安全策：中身があれば失敗する）
            os.rmdir(folder_path)

            results.append({
                "path": folder_path,
                "success": True,
                "message": "削除しました",
            })
            logger.info("削除完了: %s", folder_path)

        except OSError as e:
            # 中身がある場合や権限エラーなど
            results.append({
                "path": folder_path,
                "success": False,
                "message": f"削除失敗: {e}",
            })
            logger.error("削除失敗: %s (%s)", folder_path, e)

    return results
