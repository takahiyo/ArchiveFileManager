# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 拡張子自動補正
ファイルの先頭バイト（マジックバイト）を読み取り、
拡張子が間違っている場合は正しいものにリネームします。
"""

import os
import logging

import config

logger = logging.getLogger(__name__)


def detect_real_format(file_path: str) -> str | None:
    """
    ファイルの先頭バイトを読んで、実際の圧縮形式を判定する。

    戻り値:
        "zip" / "rar" / "7z" のいずれか。
        判定できなかった場合は None。
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
    except OSError as e:
        logger.warning("ファイルを読み取れませんでした: %s (%s)", file_path, e)
        return None

    if len(header) < 2:
        return None

    # マジックバイトの長い順にチェック（誤判定を防ぐ）
    for fmt, magic in sorted(config.MAGIC_BYTES.items(), key=lambda x: len(x[1]), reverse=True):
        if header.startswith(magic):
            return fmt

    return None


def fix_extension(file_path: str, dry_run: bool = False) -> tuple[str, str | None]:
    """
    拡張子が中身と合っていなければリネームする。

    引数:
        file_path: 対象ファイルのパス
        dry_run:   True の場合、実際にはリネームしない（確認用）

    戻り値:
        (新しいファイルパス, 修正内容の説明)
        修正不要の場合は (元のパス, None)
    """
    if not os.path.isfile(file_path):
        return file_path, None

    current_ext = os.path.splitext(file_path)[1].lower()

    # 対応していない拡張子はスキップ
    if current_ext not in config.SUPPORTED_EXTENSIONS:
        return file_path, None

    real_format = detect_real_format(file_path)
    if real_format is None:
        logger.info("形式を判定できませんでした: %s", file_path)
        return file_path, None

    # 現在の拡張子が示す形式を取得
    current_format = config.EXTENSION_TO_FORMAT.get(current_ext)

    # 形式が一致する場合は修正不要
    if current_format == real_format:
        return file_path, None

    # コミック系の拡張子（.cbz/.cbr/.cb7）はそのまま維持する
    # ただし形式が対応していない場合のみ修正
    comic_extensions = {".cbz": "zip", ".cbr": "rar", ".cb7": "7z"}
    if current_ext in comic_extensions:
        # コミック拡張子の場合は、対応する正しいコミック拡張子に変更
        comic_ext_map = {"zip": ".cbz", "rar": ".cbr", "7z": ".cb7"}
        correct_ext = comic_ext_map.get(real_format)
    else:
        correct_ext = config.FORMAT_TO_EXTENSION.get(real_format)

    if correct_ext is None:
        return file_path, None

    if correct_ext == current_ext:
        return file_path, None

    # 新しいファイル名を生成
    base = os.path.splitext(file_path)[0]
    new_path = base + correct_ext

    # 同名ファイルが既に存在する場合は番号を付与
    counter = 1
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{correct_ext}"
        counter += 1

    message = f"拡張子を修正: {current_ext} → {correct_ext}"

    if not dry_run:
        try:
            os.rename(file_path, new_path)
            logger.info("%s: %s", os.path.basename(file_path), message)
        except OSError as e:
            logger.error("リネーム失敗: %s (%s)", file_path, e)
            return file_path, None

    return new_path, message


def scan_and_fix_extensions(root_dir: str, recursive: bool = True,
                            dry_run: bool = False) -> list[dict]:
    """
    指定フォルダ内の圧縮ファイルの拡張子をまとめてチェック・修正する。

    戻り値:
        修正結果のリスト。各要素は dict:
        {"original": 元のパス, "fixed": 修正後のパス, "message": 説明}
    """
    results = []

    if recursive:
        walker = os.walk(root_dir)
    else:
        # 再帰しない場合はルートディレクトリのみ
        walker = [(root_dir, [], os.listdir(root_dir))]

    for dirpath, _dirnames, filenames in walker:
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in config.SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(dirpath, fname)
            new_path, message = fix_extension(file_path, dry_run=dry_run)

            if message is not None:
                results.append({
                    "original": file_path,
                    "fixed": new_path,
                    "message": message,
                })

    return results
