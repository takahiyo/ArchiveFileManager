# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 書庫内ファイル削除および正規化（書庫クリーン）
書庫ファイル内のファイル一覧を取得し、指定パターンに一致するファイルを削除します。
また、書庫内の不要なフォルダ階層の解消や、長すぎるファイル名の短縮も行います。
"""

import os
import subprocess
import fnmatch
import logging
import tempfile
import shutil
import hashlib

from config import (
    UNRAR_EXE,
    WINRAR_EXE,
    SUPPORTED_EXTENSIONS,
    DEFAULT_CLEAN_PATTERNS,
    MAX_NAME_LENGTH,
)
from archive_handler import scan_archives, extract_archive, compress_directory, restore_file_timestamp
from folder_normalizer import normalize_folder_structure

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# パターンマッチングと短縮判定
# ---------------------------------------------------------------------------

def find_matching_files(file_list: list[str], patterns: list[str]) -> list[str]:
    """ファイル一覧からグロブパターンに一致するものを抽出"""
    matched = []
    for file_path in file_list:
        filename = file_path.replace("\\", "/").split("/")[-1]
        for pattern in patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                matched.append(file_path)
                break
    return matched

def find_long_names(file_list: list[str], max_length: int = MAX_NAME_LENGTH) -> list[str]:
    """ファイル一覧から長すぎるファイル名/フォルダ名を抽出（相対パス文字列で評価）"""
    long_items = []
    for file_path in file_list:
        parts = file_path.replace("\\", "/").split("/")
        for part in parts:
            name_without_ext = os.path.splitext(part)[0]
            if len(name_without_ext) > max_length:
                long_items.append(file_path)
                break
    return long_items


# ---------------------------------------------------------------------------
# スキャン（プレビュー）
# ---------------------------------------------------------------------------

class ScanResult:
    def __init__(self, archive_path: str):
        self.archive_path = archive_path
        self.archive_name = os.path.basename(archive_path)
        self.matched_files: list[str] = []
        self.long_name_files: list[str] = []
        self.has_nested_folders: bool = False
        self.needs_processing: bool = False
        self.error: str | None = None

def list_archive_contents(archive_path: str) -> list[str]:
    """書庫内ファイル一覧取得（UnRAR lb）"""
    if not os.path.isfile(archive_path):
        return []

    cmd = [UNRAR_EXE, "lb", archive_path]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode not in (0, 1):
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as e:
        logger.error("一覧取得失敗: %s", e)
        return []

def check_nested_folders(file_list: list[str]) -> bool:
    """リストから単一フォルダの入れ子を簡易推測"""
    if not file_list:
        return False
    # 全てのファイルが同じトップレベルフォルダに入っているか？
    first_parts = file_list[0].replace("\\", "/").split("/")
    if len(first_parts) < 2:
        return False
    top_folder = first_parts[0]
    for file_path in file_list:
        parts = file_path.replace("\\", "/").split("/")
        if len(parts) < 2 or parts[0] != top_folder:
            return False
    return True


def scan_archives_for_cleaning(
    root_dir: str,
    patterns: list[str],
    recursive: bool = True,
    check_nesting: bool = True,
    check_long_names: bool = True,
    progress_callback=None,
    cancel_check=None,
) -> list[ScanResult]:
    """指定フォルダ内の書庫をスキャンし、最適化対象をプレビューする"""
    archives = scan_archives(root_dir, recursive)
    results = []
    total = len(archives)

    for i, archive_path in enumerate(archives):
        if cancel_check and cancel_check():
            break

        contents = list_archive_contents(archive_path)
        if contents:
            scan_result = ScanResult(archive_path)
            
            # 1. パターンマッチ
            scan_result.matched_files = find_matching_files(contents, patterns)
            
            # 2. 入れ子判定（簡易）
            if check_nesting:
                scan_result.has_nested_folders = check_nested_folders(contents)
                
            # 3. 長い名前判定
            if check_long_names:
                scan_result.long_name_files = find_long_names(contents, MAX_NAME_LENGTH)

            # 何らかの処理が必要か
            if scan_result.matched_files or scan_result.has_nested_folders or scan_result.long_name_files:
                scan_result.needs_processing = True
                results.append(scan_result)

        if progress_callback:
            progress_callback(i + 1, total)

    return results


# ---------------------------------------------------------------------------
# バッチ処理実行
# ---------------------------------------------------------------------------

class CleanResult:
    def __init__(self, archive_path: str):
        self.archive_path = archive_path
        self.archive_name = os.path.basename(archive_path)
        self.success: bool = False
        self.message: str = ""
        self.deleted_count: int = 0
        self.flattened_count: int = 0
        self.shortened_count: int = 0


def shorten_name(name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """名前を短縮（先頭 + ハッシュ + 拡張子）"""
    base, ext = os.path.splitext(name)
    if len(base) <= max_length:
        return name
    
    # ハッシュ生成（一意性確保）
    hash_str = hashlib.md5(base.encode('utf-8')).hexdigest()[:6]
    
    # 残りの文字数
    keep_len = max_length - len(hash_str) - 2 # "~" と余白
    if keep_len < 5:
        keep_len = 5
        
    shortened = f"{base[:keep_len]}~{hash_str}{ext}"
    return shortened

def shorten_long_names_in_dir(target_dir: str, max_length: int = MAX_NAME_LENGTH) -> int:
    """ディレクトリ内の長すぎるファイル/フォルダ名を再帰的に短縮"""
    shortened_count = 0
    # ボトムアップで処理（深い階層からリネーム）
    for dirpath, dirnames, filenames in os.walk(target_dir, topdown=False):
        # フォルダのリネーム
        for i, dirname in enumerate(dirnames):
            if len(dirname) > max_length:
                new_name = shorten_name(dirname, max_length)
                src = os.path.join(dirpath, dirname)
                dst = os.path.join(dirpath, new_name)
                # 競合回避
                counter = 1
                while os.path.exists(dst):
                    new_name = shorten_name(f"{dirname}_{counter}", max_length)
                    dst = os.path.join(dirpath, new_name)
                    counter += 1
                try:
                    os.rename(src, dst)
                    dirnames[i] = new_name # walker更新
                    shortened_count += 1
                except OSError as e:
                    logger.error("フォルダリネーム失敗: %s -> %s (%s)", src, dst, e)

        # ファイルのリネーム
        for filename in filenames:
            base, _ = os.path.splitext(filename)
            if len(base) > max_length:
                new_name = shorten_name(filename, max_length)
                src = os.path.join(dirpath, filename)
                dst = os.path.join(dirpath, new_name)
                # 競合回避
                counter = 1
                while os.path.exists(dst):
                    b, e = os.path.splitext(filename)
                    new_name = shorten_name(f"{b}_{counter}{e}", max_length)
                    dst = os.path.join(dirpath, new_name)
                    counter += 1
                try:
                    os.rename(src, dst)
                    shortened_count += 1
                except OSError as e:
                    logger.error("ファイルリネーム失敗: %s -> %s (%s)", src, dst, e)

    return shortened_count

def process_single_archive(
    scan_result: ScanResult,
    do_nesting: bool,
    do_shorten: bool,
) -> CleanResult:
    """1つの書庫を処理する（解凍→修正→再圧縮、または直接削除）"""
    res = CleanResult(scan_result.archive_path)
    archive_path = scan_result.archive_path
    
    # 入れ子解消か名前短縮が必要なら、「解凍→再圧縮」フロー
    need_repack = (do_nesting and scan_result.has_nested_folders) or \
                  (do_shorten and scan_result.long_name_files)
                  
    # さらに、パターンマッチがあり、かつUnrarで解凍する場合は再圧縮フローの中で削除する方が安全・確実
    # WinRAR dコマンドは高速だが、複雑な処理と混ざるなら一貫性を優先
    
    if not need_repack and scan_result.matched_files:
        # 削除のみで済む場合（高速フロー: WinRAR dコマンド）
        cmd = [WINRAR_EXE, "d", "-ibck", "-y", archive_path]
        cmd.extend(scan_result.matched_files)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode in (0, 1):
                res.success = True
                res.deleted_count = len(scan_result.matched_files)
                res.message = f"✓ {res.deleted_count}件のファイルを削除"
                return res
            else:
                res.message = f"✗ 削除失敗: {r.stderr.strip()}"
                return res
        except Exception as e:
            res.message = f"✗ コマンド例外: {e}"
            return res

    elif need_repack:
        # 解凍・修正・再圧縮フロー
        temp_dir = tempfile.mkdtemp(prefix="afm_clean_")
        try:
            # タイムスタンプ保持
            try:
                original_stat = os.stat(archive_path)
            except:
                original_stat = None

            # 1. 解凍
            if not extract_archive(archive_path, temp_dir):
                res.message = "✗ 解凍に失敗しました"
                return res
                
            # 2. パターンマッチファイルの物理削除
            if scan_result.matched_files:
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        for p in [os.path.basename(m) for m in scan_result.matched_files]:
                            if fnmatch.fnmatch(f.lower(), p.lower()):
                                try:
                                    os.remove(os.path.join(root, f))
                                    res.deleted_count += 1
                                except:
                                    pass

            # 3. 入れ子解消
            if do_nesting and scan_result.has_nested_folders:
                res.flattened_count = normalize_folder_structure(temp_dir)
                
            # 4. 名前短縮
            if do_shorten:
                res.shortened_count = shorten_long_names_in_dir(temp_dir, MAX_NAME_LENGTH)
                
            # 5. 再圧縮
            # 現在の拡張子からフォーマットを判定し、同じ形式で圧縮
            ext = os.path.splitext(archive_path)[1].lower()
            target_format = "ZIP"
            if ext in (".rar", ".cbr"): target_format = "RAR"
            elif ext in (".7z", ".cb7"): target_format = "7z"
            
            # 再圧縮実行 (標準圧縮)
            temp_out = archive_path + ".tmp"
            succ, err = compress_directory(temp_dir, temp_out, target_format, 3)
            
            if succ:
                # 成功したら元ファイルと置き換え
                os.remove(archive_path)
                os.rename(temp_out, archive_path)
                
                # タイムスタンプ復元
                if original_stat:
                    restore_file_timestamp(archive_path, original_stat)
                    
                res.success = True
                msgs = []
                if res.deleted_count: msgs.append(f"削除:{res.deleted_count}件")
                if res.flattened_count: msgs.append(f"階層解消:{res.flattened_count}段")
                if res.shortened_count: msgs.append(f"名前短縮:{res.shortened_count}件")
                res.message = "✓ " + ", ".join(msgs)
            else:
                if os.path.exists(temp_out): os.remove(temp_out)
                res.message = f"✗ 再圧縮失敗: {err}"
                
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    else:
        # 何も処理対象がない
        res.success = True
        res.message = "ℹ 処理不要"
        
    return res


def batch_clean_archives(
    scan_results: list[ScanResult],
    do_nesting: bool = True,
    do_shorten: bool = True,
    progress_callback=None,
    log_callback=None,
    cancel_check=None,
) -> list[CleanResult]:
    """スキャン結果に基づき、書庫内を一括最適化する"""
    results = []
    total = len(scan_results)

    for i, scan_result in enumerate(scan_results):
        if cancel_check and cancel_check():
            if log_callback: log_callback("処理がキャンセルされました")
            break

        if log_callback:
            log_callback(f"[{i + 1}/{total}] {scan_result.archive_name} 処理中...")

        clean_result = process_single_archive(scan_result, do_nesting, do_shorten)
        
        if log_callback:
            log_callback(f"  {clean_result.message}")

        results.append(clean_result)

        if progress_callback:
            progress_callback(i + 1, total)

    return results
