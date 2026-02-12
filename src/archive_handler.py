# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 圧縮ファイル操作の中核処理
WinRAR (Rar.exe / UnRAR.exe) を使って解凍・再圧縮を行います。
"""

import os
import subprocess
import tempfile
import shutil
import logging

from config import (
    RAR_EXE,
    UNRAR_EXE,
    SUPPORTED_EXTENSIONS,
    TARGET_FORMATS,
    COMPRESSION_LEVELS,
)
from extension_fixer import fix_extension
from folder_normalizer import normalize_folder_structure

logger = logging.getLogger(__name__)


def scan_archives(root_dir: str, recursive: bool = True) -> list[str]:
    """
    指定フォルダ内の圧縮ファイルを検索して一覧を返す。

    引数:
        root_dir:   検索対象のフォルダパス
        recursive:  True の場合、下層フォルダも検索する

    戻り値:
        圧縮ファイルのフルパスのリスト
    """
    archives = []

    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                    archives.append(os.path.join(dirpath, fname))
    else:
        for fname in os.listdir(root_dir):
            full_path = os.path.join(root_dir, fname)
            if os.path.isfile(full_path):
                if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                    archives.append(full_path)

    return sorted(archives)


def extract_archive(archive_path: str, dest_dir: str) -> bool:
    """
    圧縮ファイルを指定フォルダに解凍する。

    引数:
        archive_path: 解凍する圧縮ファイルのパス
        dest_dir:     解凍先フォルダ

    戻り値:
        成功した場合 True
    """
    if not os.path.isfile(archive_path):
        logger.error("ファイルが存在しません: %s", archive_path)
        return False

    # UnRAR.exe は ZIP, RAR, 7z すべて解凍できる
    cmd = [
        UNRAR_EXE,
        "x",            # フォルダ構造を保持して解凍
        "-o+",          # 既存ファイルは上書き
        "-y",           # すべての確認に「はい」で応答
        archive_path,
        dest_dir + os.sep,  # 末尾にセパレータが必要
    ]

    logger.debug("解凍コマンド: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,  # 10分でタイムアウト
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            logger.error("解凍失敗 (コード %d): %s\n%s",
                         result.returncode, archive_path, result.stderr)
            return False
        return True

    except subprocess.TimeoutExpired:
        logger.error("解凍がタイムアウトしました: %s", archive_path)
        return False
    except OSError as e:
        logger.error("解凍コマンドの実行に失敗: %s (%s)", archive_path, e)
        return False


def compress_directory(source_dir: str, output_path: str,
                       target_format: str, compression_level: int) -> bool:
    """
    フォルダの中身を圧縮して新しいアーカイブを作成する。

    引数:
        source_dir:        圧縮するフォルダのパス
        output_path:       出力ファイルのパス
        target_format:     変換先の形式キー（"ZIP" / "RAR" / "7z"）
        compression_level: 圧縮率（0〜5）

    戻り値:
        成功した場合 True
    """
    fmt_info = TARGET_FORMATS.get(target_format)
    if fmt_info is None:
        logger.error("未対応の形式: %s", target_format)
        return False

    # Rar.exe のコマンドを組み立て
    cmd = [
        RAR_EXE,
        "a",                        # アーカイブに追加（新規作成）
        f"-m{compression_level}",   # 圧縮率
        "-ep1",                     # ルートフォルダのパスを除外
        "-r",                       # 再帰的に処理
        "-y",                       # すべての確認に「はい」
    ]

    # 出力形式の指定
    format_switch = fmt_info.get("rar_switch", "")
    if format_switch:
        cmd.append(format_switch)

    cmd.append(output_path)

    # ソースフォルダ内のすべてのファイルを対象にする
    cmd.append(os.path.join(source_dir, "*"))

    logger.debug("圧縮コマンド: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            logger.error("圧縮失敗 (コード %d): %s\n%s",
                         result.returncode, output_path, result.stderr)
            return False
        return True

    except subprocess.TimeoutExpired:
        logger.error("圧縮がタイムアウトしました: %s", output_path)
        return False
    except OSError as e:
        logger.error("圧縮コマンドの実行に失敗: %s (%s)", output_path, e)
        return False


class ConversionResult:
    """1ファイルの変換結果を保持するクラス"""

    def __init__(self, original_path: str):
        self.original_path = original_path
        self.output_path: str | None = None
        self.success: bool = False
        self.skipped: bool = False
        self.messages: list[str] = []

    def add_message(self, msg: str):
        self.messages.append(msg)


def convert_archive(
    archive_path: str,
    target_format: str,
    compression_level: int,
    fix_extensions: bool = True,
    flatten_folders: bool = True,
    delete_original: bool = False,
    progress_callback=None,
) -> ConversionResult:
    """
    1つの圧縮ファイルを変換する。

    処理の流れ:
    1. （オプション）拡張子の補正
    2. 一時フォルダに解凍
    3. （オプション）フォルダ階層の正規化
    4. 指定形式で再圧縮
    5. （オプション）元ファイルの削除

    引数:
        archive_path:       変換対象のファイルパス
        target_format:      変換先の形式（"ZIP" / "RAR" / "7z"）
        compression_level:  圧縮率（0〜5）
        fix_extensions:     拡張子補正を行うか
        flatten_folders:    フォルダ階層の正規化を行うか
        delete_original:    変換後に元ファイルを削除するか
        progress_callback:  進捗報告用のコールバック関数
    """
    result = ConversionResult(archive_path)
    current_path = archive_path

    # 1. 拡張子の補正
    if fix_extensions:
        new_path, fix_msg = fix_extension(current_path)
        if fix_msg:
            result.add_message(fix_msg)
            current_path = new_path

    # 変換先の拡張子と現在の拡張子が同じで、階層修正も不要なら最適化
    fmt_info = TARGET_FORMATS.get(target_format)
    current_ext = os.path.splitext(current_path)[1].lower()
    target_ext = fmt_info["extension"]

    # 一時フォルダを作成
    temp_dir = tempfile.mkdtemp(prefix="afm_")

    try:
        # 2. 解凍
        result.add_message("解凍中...")
        if not extract_archive(current_path, temp_dir):
            result.add_message("✗ 解凍に失敗しました")
            return result

        # 3. フォルダ階層の正規化
        if flatten_folders:
            flattened = normalize_folder_structure(temp_dir)
            if flattened > 0:
                result.add_message(f"フォルダ階層を {flattened} 段解消しました")

        # 4. 再圧縮
        # 出力ファイル名を決定（元ファイルと同じフォルダに作成）
        original_dir = os.path.dirname(current_path)
        base_name = os.path.splitext(os.path.basename(current_path))[0]
        output_path = os.path.join(original_dir, base_name + target_ext)

        # 同名ファイルが存在する場合（＝同じ形式への変換）
        if os.path.normcase(os.path.abspath(output_path)) == \
           os.path.normcase(os.path.abspath(current_path)):
            # 一時的な名前で出力して後でリネーム
            temp_output = os.path.join(original_dir, base_name + "_temp" + target_ext)
            result.add_message(f"{target_format} 形式で再圧縮中...")
            if not compress_directory(temp_dir, temp_output, target_format, compression_level):
                result.add_message("✗ 圧縮に失敗しました")
                # 一時出力ファイルを片付け
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return result

            # 元ファイルを削除して一時ファイルをリネーム
            os.remove(current_path)
            os.rename(temp_output, output_path)
        else:
            # 出力先に同名ファイルがある場合は番号を付与
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(
                    original_dir, f"{base_name}_{counter}{target_ext}"
                )
                counter += 1

            result.add_message(f"{target_format} 形式で圧縮中...")
            if not compress_directory(temp_dir, output_path, target_format, compression_level):
                result.add_message("✗ 圧縮に失敗しました")
                return result

            # 5. 元ファイルの削除（オプション）
            if delete_original and os.path.exists(current_path):
                try:
                    os.remove(current_path)
                    result.add_message("元ファイルを削除しました")
                except OSError as e:
                    result.add_message(f"元ファイルの削除に失敗: {e}")

        result.output_path = output_path
        result.success = True
        result.add_message("✓ 変換完了")

    finally:
        # 一時フォルダは必ず削除する
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return result


def batch_convert(
    archive_list: list[str],
    target_format: str,
    compression_level: int,
    fix_extensions: bool = True,
    flatten_folders: bool = True,
    delete_original: bool = False,
    progress_callback=None,
    log_callback=None,
    cancel_check=None,
) -> list[ConversionResult]:
    """
    複数の圧縮ファイルをまとめて変換する。

    引数:
        archive_list:       変換対象ファイルのリスト
        target_format:      変換先の形式
        compression_level:  圧縮率
        fix_extensions:     拡張子補正を行うか
        flatten_folders:    フォルダ階層の正規化を行うか
        delete_original:    変換後に元ファイルを削除するか
        progress_callback:  進捗報告 (current, total) を受け取る関数
        log_callback:       ログメッセージ (str) を受け取る関数
        cancel_check:       キャンセル判定の関数（True を返したら中断）

    戻り値:
        ConversionResult のリスト
    """
    results = []
    total = len(archive_list)

    for i, archive_path in enumerate(archive_list):
        # キャンセルチェック
        if cancel_check and cancel_check():
            if log_callback:
                log_callback("処理がキャンセルされました")
            break

        filename = os.path.basename(archive_path)
        if log_callback:
            log_callback(f"[{i + 1}/{total}] {filename}")

        conv_result = convert_archive(
            archive_path=archive_path,
            target_format=target_format,
            compression_level=compression_level,
            fix_extensions=fix_extensions,
            flatten_folders=flatten_folders,
            delete_original=delete_original,
        )

        results.append(conv_result)

        # ログを出力
        if log_callback:
            for msg in conv_result.messages:
                log_callback(f"  {msg}")

        # 進捗報告
        if progress_callback:
            progress_callback(i + 1, total)

    return results
