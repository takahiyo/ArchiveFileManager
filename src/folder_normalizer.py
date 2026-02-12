# -*- coding: utf-8 -*-
"""
ArchiveFileManager - フォルダ階層の正規化
圧縮ファイルを解凍した結果「ルート直下にフォルダが1つだけ」
という余分な階層がある場合、それを解消します。
"""

import os
import shutil
import logging

logger = logging.getLogger(__name__)


def has_single_folder_nesting(extracted_dir: str) -> bool:
    """
    解凍先フォルダを調べて、直下にフォルダが1つだけ（かつファイルなし）
    という余分な入れ子になっているか判定する。

    例:
        extracted_dir/
          └── SomeFolder/     ← これだけの場合 True
                ├── file1.jpg
                └── file2.jpg

    引数:
        extracted_dir: 解凍先のフォルダパス

    戻り値:
        余分な階層がある場合 True
    """
    try:
        entries = os.listdir(extracted_dir)
    except OSError:
        return False

    # 直下にエントリが1つだけで、それがフォルダの場合
    if len(entries) == 1:
        single_entry = os.path.join(extracted_dir, entries[0])
        if os.path.isdir(single_entry):
            return True

    return False


def flatten_single_folder(extracted_dir: str) -> bool:
    """
    余分なフォルダ階層を解消する。
    直下のフォルダの中身をすべて一段上に移動し、空になったフォルダを削除する。

    例:
        変更前: extracted_dir/SomeFolder/file1.jpg
        変更後: extracted_dir/file1.jpg

    引数:
        extracted_dir: 解凍先のフォルダパス

    戻り値:
        処理が行われた場合 True
    """
    if not has_single_folder_nesting(extracted_dir):
        return False

    entries = os.listdir(extracted_dir)
    nested_dir = os.path.join(extracted_dir, entries[0])
    nested_name = entries[0]

    logger.info("余分なフォルダ階層を解消: %s", nested_name)

    try:
        # 入れ子フォルダ内の全エントリを一段上に移動
        for item in os.listdir(nested_dir):
            src = os.path.join(nested_dir, item)
            dst = os.path.join(extracted_dir, item)

            # 移動先に同名がある場合の処理
            if os.path.exists(dst):
                base, ext = os.path.splitext(item)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(extracted_dir, f"{base}_{counter}{ext}")
                    counter += 1

            shutil.move(src, dst)

        # 空になったフォルダを削除
        os.rmdir(nested_dir)
        return True

    except OSError as e:
        logger.error("フォルダ階層の解消に失敗: %s (%s)", nested_dir, e)
        return False


def normalize_folder_structure(extracted_dir: str) -> int:
    """
    余分なフォルダ階層を再帰的に解消する。
    （複数段の入れ子にも対応）

    例:
        変更前: extracted_dir/A/B/file.jpg  （A の中に B だけ、B の中にファイル）
        変更後: extracted_dir/file.jpg

    戻り値:
        解消した階層の数
    """
    count = 0
    # 入れ子が続く限り繰り返す（最大10回で安全弁）
    for _ in range(10):
        if flatten_single_folder(extracted_dir):
            count += 1
        else:
            break
    return count
