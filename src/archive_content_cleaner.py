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
import zipfile
import time
from datetime import datetime


import config
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

def find_long_names(file_list: list[str], max_length: int = None) -> list[str]:
    """ファイル一覧から長すぎるファイル名/フォルダ名を抽出（相対パス文字列で評価）"""
    if max_length is None:
        max_length = config.MAX_NAME_LENGTH
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
        self.symbol_name_files: list[str] = []
        self.has_nested_folders: bool = False
        self.has_chapter_folders: bool = False
        self.needs_processing: bool = False
        self.error: str | None = None
        self.is_checked: bool = True
        self.mtime: float = 0.0
        self.mtime_str: str = ""

def list_archive_contents(archive_path: str) -> list[str]:
    """書庫内ファイル一覧取得（ZIPは標準ライブラリ、他は Rar/UnRAR vb）"""
    if not os.path.isfile(archive_path):
        return []

    ext = os.path.splitext(archive_path)[1].lower()
    
    # 1. ZIP/CBZ は Python 標準の zipfile で確実に取得
    if ext in (".zip", ".cbz"):
        try:
            with zipfile.ZipFile(archive_path, 'r') as z:
                # 日本語ファイル名のエンコーディング修正（zipfile の既定の挙動対応）
                file_list = []
                for info in z.infolist():
                    name = info.filename
                    # zipfile は cp437 か utf-8 しか解釈しないため、cp932 を考慮 (UTF-8フラグに関わらずデコードを試みる)
                    try:
                        name = name.encode('cp437').decode('cp932')
                    except Exception:
                        try:
                            name = name.encode('cp437').decode('cp932', errors='replace')
                        except Exception:
                            pass
                    file_list.append(name)
                return file_list
        except Exception as e:
            logger.debug(f"zipfile での取得失敗 {archive_path}: {e}")
            # 失敗時は Rar.exe へフォールバック

    # 2. RAR/7z 等は Rar.exe vb で取得
    abs_path = os.path.abspath(archive_path)
    cmd = [config.RAR_EXE, "vb", "-c-", abs_path]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=False, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW
        )
        raw_out = result.stdout
        
        # 3. エラーまたは空、かつ UnRAR があれば試す (念のため)
        if (result.returncode not in (0, 1) or not raw_out.strip()) and config.UNRAR_EXE != config.RAR_EXE:
            cmd_unrar = [config.UNRAR_EXE, "vb", "-c-", abs_path]
            res_un_raw = subprocess.run(cmd_unrar, capture_output=True, text=False, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            if res_un_raw.stdout.strip():
                raw_out = res_un_raw.stdout

        # デコード
        decoded_text = ""
        for enc in ["cp932", "utf-8"]:
            try:
                decoded_text = raw_out.decode(enc)
                if decoded_text.strip():
                    break
            except:
                pass
        
        if not decoded_text and raw_out:
            decoded_text = raw_out.decode("utf-8", errors="replace")

        return [line.strip() for line in decoded_text.splitlines() if line.strip()]
    except Exception as e:
        logger.error("一覧取得失敗: %s", e)
        return []

def check_nested_folders(file_list: list[str]) -> bool:
    """リストから単一フォルダの入れ子を簡易推測"""
    # ディレクトリと思われるエントリ（末尾が / や \\ 、または他のエントリの親になっているもの）を除外する
    normalized_paths = [f.replace("\\", "/") for f in file_list]
    
    # 他のファイルの親ディレクトリになっているパスを特定する
    dir_paths = set()
    for path in normalized_paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dir_paths.add("/".join(parts[:i]))
            
    # dir_paths に含まれるパス、または末尾が / のパスはディレクトリとみなして除外
    only_files = []
    for path in normalized_paths:
        if path.endswith("/"):
            continue
        if path in dir_paths:
            continue
        only_files.append(path)

    if not only_files:
        return False

    # すべてのファイルが同じトップレベルフォルダに入っているか？
    first_parts = only_files[0].split("/")
    if len(first_parts) < 2:
        return False
    top_folder = first_parts[0]
    
    for file_path in only_files:
        parts = file_path.split("/")
        if len(parts) < 2 or parts[0] != top_folder:
            return False
            
    return True


def scan_archives_for_cleaning(
    root_dir: str,
    patterns: list[str] | None = None,
    recursive: bool = True,
    check_nesting: bool = True,
    check_long_names: bool = True,
    days_within: int | None = None,
    target_format: str | None = None,
    fix_extensions: bool = True,
    check_chapter_organize: bool = False,
    progress_callback=None,
    cancel_check=None,
    normalize_symbols: bool = True,
    exclude_original: bool = True,
) -> list[ScanResult]:
    """指定フォルダ内の書庫をスキャンし、最適化対象をプレビューする"""
    archives = scan_archives(root_dir, recursive)
    # 退避書庫は内容検査・拡張子補正より前に除外して再処理を防ぐ。
    if exclude_original:
        archives = [path for path in archives
                    if config.ORIGINAL_ARCHIVE_MARKER.casefold()
                    not in os.path.splitext(os.path.basename(path))[0].casefold()]
    results = []
    total = len(archives)

    # フィルタ条件のタイムスタンプ計算
    threshold_time = None
    if days_within is not None and days_within > 0:
        threshold_time = time.time() - (days_within * 86400)

    for i, archive_path in enumerate(archives):
        if cancel_check and cancel_check():
            break

        # 更新日時チェック
        try:
            mtime = os.path.getmtime(archive_path)
            dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            mtime = 0.0
            dt_str = ""

        if threshold_time is not None and mtime < threshold_time:
            if progress_callback:
                progress_callback(i + 1, total)
            continue

        # サイズ取得
        try:
            sz = os.path.getsize(archive_path)
            if sz > 1024 * 1024:
                sz_str = f"{sz / (1024 * 1024):.1f} MB"
            else:
                sz_str = f"{sz / 1024:.1f} KB"
        except OSError:
            sz = 0
            sz_str = "不明"

        # 拡張子の補正判定
        ext = os.path.splitext(archive_path)[1].lower()
        original_format = config.EXTENSION_TO_FORMAT.get(ext, "").upper()
        ext_msg = None
        if fix_extensions:
            from extension_fixer import fix_extension
            _, ext_msg = fix_extension(archive_path, dry_run=True)
            if ext_msg:
                from extension_fixer import detect_real_format
                real_fmt = detect_real_format(archive_path)
                if real_fmt:
                    original_format = real_fmt.upper()

        # ターゲット形式の決定
        real_target_format = None
        needs_conversion = False
        if target_format and target_format != "PRESERVE":
            real_target_format = target_format
            if original_format != target_format:
                needs_conversion = True
        else:
            real_target_format = original_format

        contents = list_archive_contents(archive_path)
        if contents or ext_msg or needs_conversion or (normalize_symbols and '!' in os.path.basename(archive_path)):
            scan_result = ScanResult(archive_path)
            scan_result.mtime = mtime
            scan_result.mtime_str = dt_str
            scan_result.size = sz
            scan_result.size_str = sz_str
            scan_result.original_format = original_format
            scan_result.target_format = real_target_format
            scan_result.needs_conversion = needs_conversion
            scan_result.extension_fixed_msg = ext_msg

            # 1. パターンマッチ
            if patterns:
                scan_result.matched_files = find_matching_files(contents, patterns)
            
            # 2. 話数整理および入れ子判定（簡易）
            if check_chapter_organize:
                from folder_normalizer import is_chapter_structured
                remaining_contents = [f for f in contents if f not in scan_result.matched_files]
                if is_chapter_structured(remaining_contents):
                    scan_result.has_chapter_folders = True

            if check_nesting and not scan_result.has_chapter_folders:
                remaining_contents = [f for f in contents if f not in scan_result.matched_files]
                scan_result.has_nested_folders = check_nested_folders(remaining_contents)
                
            # 3. 長い名前判定
            if check_long_names:
                scan_result.long_name_files = find_long_names(contents, config.MAX_NAME_LENGTH)

            # 何らかの処理が必要か
            if normalize_symbols:
                scan_result.symbol_name_files = [name for name in contents if '!' in name]
            if (scan_result.matched_files or 
                scan_result.symbol_name_files or
                (normalize_symbols and '!' in scan_result.archive_name) or
                scan_result.has_nested_folders or 
                scan_result.has_chapter_folders or
                scan_result.long_name_files or 
                scan_result.extension_fixed_msg or 
                scan_result.needs_conversion):
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
        self.error_detail: str = ""
        self.deleted_count: int = 0
        self.flattened_count: int = 0
        self.shortened_count: int = 0
        self.symbol_count: int = 0
        self.chapter_organized: bool = False
        self.chapter_count: int = 0
        self.cover_count: int = 0
        self.organized_files_count: int = 0


def shorten_name(name: str, max_length: int = None) -> str:
    """名前を短縮（先頭 + ハッシュ + 拡張子）"""
    if max_length is None:
        max_length = config.MAX_NAME_LENGTH
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

def shorten_long_names_in_dir(target_dir: str, max_length: int = None) -> int:
    """ディレクトリ内の長すぎるファイル/フォルダ名を再帰的に短縮"""
    if max_length is None:
        max_length = config.MAX_NAME_LENGTH
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


def normalize_symbol_path(path: str) -> str:
    """! を全角に置換し、衝突時は連番を付けて名前を変更する。"""
    parent, name = os.path.split(path)
    if '!' not in name:
        return path
    name = name.replace('!', '！')
    base, ext = os.path.splitext(name)
    destination = os.path.join(parent, name)
    counter = 1
    while os.path.lexists(destination):
        destination = os.path.join(parent, f'{base}_{counter}{ext}')
        counter += 1
    os.rename(path, destination)
    return destination


def normalize_symbols_in_dir(directory: str) -> int:
    """子から親へ変換し、フォルダ移動で走査先が失われることを防ぐ。"""
    count = 0
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in sorted(files + dirs):
            if '!' in name:
                normalize_symbol_path(os.path.join(root, name))
                count += 1
    return count


def process_single_archive(
    scan_result: ScanResult,
    do_clean: bool = True,
    do_nesting: bool = True,
    do_shorten: bool = True,
    fix_extensions: bool = True,
    delete_original: bool = False,
    preserve_timestamp: bool = True,
    compression_level: int = 3,
    do_chapter_organize: bool = False,
    status_callback=None,
    normalize_symbols: bool = True,
) -> CleanResult:
    """1つの書庫を処理する（解凍→修正→再圧縮、または直接削除）"""
    res = CleanResult(scan_result.archive_path)
    archive_path = scan_result.archive_path
    
    # 1. 拡張子の補正（実際に適用する）
    current_path = archive_path
    if fix_extensions and scan_result.extension_fixed_msg:
        from extension_fixer import fix_extension
        new_path, fix_msg = fix_extension(archive_path, dry_run=False)
        if fix_msg:
            current_path = new_path
            res.archive_path = new_path
            res.archive_name = os.path.basename(new_path)
            res.message = fix_msg

    # ターゲット形式の拡張子
    fmt_info = config.TARGET_FORMATS.get(scan_result.target_format)
    if fmt_info is None:
        target_ext = os.path.splitext(current_path)[1].lower()
        target_format_key = scan_result.original_format
    else:
        target_ext = fmt_info["extension"]
        target_format_key = scan_result.target_format

    current_ext = os.path.splitext(current_path)[1].lower()
    original_dir = os.path.dirname(current_path)
    base_name = os.path.splitext(os.path.basename(current_path))[0]
    
    # 上書きか、別ファイルか
    is_same_file = (os.path.normcase(current_ext) == os.path.normcase(target_ext))
    
    if is_same_file:
        output_path = current_path
    else:
        output_path = os.path.join(original_dir, base_name + target_ext)
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(original_dir, f"{base_name}_{counter}{target_ext}")
            counter += 1

    has_clean = do_clean and len(scan_result.matched_files) > 0
    has_chapter = do_chapter_organize and scan_result.has_chapter_folders
    has_nesting = do_nesting and scan_result.has_nested_folders and not has_chapter
    has_shorten = do_shorten and len(scan_result.long_name_files) > 0
    has_symbols = normalize_symbols and bool(scan_result.symbol_name_files)
    has_conversion = not is_same_file

    # 話数別フォルダ整理が適用される場合：
    # 変換後ファイルは本来の名前（output_path）で残し、元ファイル削除フラグは無効化する
    if has_chapter:
        delete_original = False
    
    # 全く変更がない場合はスキップ
    if not (has_clean or has_chapter or has_nesting or has_shorten or has_symbols or has_conversion):
        res.success = True
        res.message = "ℹ 処理不要"
        if normalize_symbols and '!' in os.path.basename(current_path):
            try:
                res.archive_path = res.output_path = normalize_symbol_path(current_path)
                res.archive_name = os.path.basename(res.output_path)
                res.symbol_count = 1
                res.message = '✓ 書庫名の記号を整理'
            except OSError as exc:
                res.success = False
                res.message = f'✗ 書庫名の変更失敗: {exc}'
        return res

    is_zip = current_path.lower().endswith((".zip", ".cbz"))

    # 2. 直接削除 (Rar.exe d) フロー
    # 条件: クリーン処理のみ必要、かつ ZIP ではなく、かつ出力ファイル形式が変わらない、話数整理もない
    if (has_clean and not has_chapter and not has_nesting and not has_shorten and not has_symbols and not (normalize_symbols and '!' in os.path.basename(current_path)) and not has_conversion and not is_zip):
        temp_list = None
        try:
            cmd = [config.RAR_EXE, "d", "-idq", "-y", current_path]
            if len(scan_result.matched_files) > 20:
                fd, temp_list = tempfile.mkstemp(prefix="afm_del_", suffix=".lst", text=True)
                with os.fdopen(fd, 'w', encoding='cp932', errors='replace') as f:
                    for m in scan_result.matched_files:
                        f.write(m + "\n")
                cmd.append(f"@{temp_list}")
            else:
                cmd.extend(scan_result.matched_files)

            logger.info(f"直接削除実行: {os.path.basename(current_path)}")
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if r.returncode in (0, 1):
                res.success = True
                res.deleted_count = len(scan_result.matched_files)
                res.message = f"✓ {res.deleted_count}件のファイルを削除"
                return res
            else:
                err_msg = r.stderr.strip() or r.stdout.strip() or f"終了コード {r.returncode}"
                res.message = f"✗ 削除失敗 (code:{r.returncode})"
                res.error_detail = f"Rar.exe d コマンド失敗 (code:{r.returncode}): {err_msg}"
                return res
        except Exception as e:
            res.message = f"✗ コマンド例外: {e}"
            res.error_detail = f"直接削除実行中の例外: {e}"
            return res
        finally:
            if temp_list and os.path.exists(temp_list):
                try: os.remove(temp_list)
                except: pass

    # 3. 解凍・修正・再圧縮フロー
    temp_dir = tempfile.mkdtemp(prefix="afm_unified_")
    logger.info(f"再パックフロー開始: {os.path.basename(current_path)} -> temp:{temp_dir}")
    try:
        # タイムスタンプ保持
        original_stat = None
        if preserve_timestamp:
            try:
                original_stat = os.stat(current_path)
            except:
                pass

        # 解凍
        if status_callback:
            status_callback("解凍中...")
        if not extract_archive(current_path, temp_dir):
            res.message = "✗ 解凍に失敗しました"
            res.error_detail = "書庫の解凍に失敗しました（ファイル破損・ロック、または解凍ツール非対応の可能性）"
            return res
            
        # 不要ファイル削除
        if has_clean:
            if status_callback:
                status_callback("不要ファイル削除中...")
            matched_basenames = [os.path.basename(m).lower() for m in scan_result.matched_files]
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower() in matched_basenames:
                        try:
                            os.remove(os.path.join(root, f))
                            res.deleted_count += 1
                        except:
                            pass
                            
        # 話数別フォルダ・ファイル名整理 または 入れ子解消
        if has_chapter:
            if status_callback:
                status_callback("話数別整理中...")
            from folder_normalizer import organize_chapters_and_flatten
            cov_count, ch_count, total_renamed = organize_chapters_and_flatten(temp_dir)
            if total_renamed > 0:
                res.chapter_organized = True
                res.cover_count = cov_count
                res.chapter_count = ch_count
                res.organized_files_count = total_renamed
        elif has_nesting:
            if status_callback:
                status_callback("入れ子解消中...")
            res.flattened_count = normalize_folder_structure(temp_dir)
            
        # 名前短縮
        if has_symbols:
            res.symbol_count = normalize_symbols_in_dir(temp_dir)
        if has_shorten:
            if status_callback:
                status_callback("名前短縮中...")
            res.shortened_count = shorten_long_names_in_dir(temp_dir, config.MAX_NAME_LENGTH)
            
        # 再圧縮
        if is_same_file:
            temp_out = current_path + ".tmp"
        else:
            temp_out = output_path + ".tmp"
            
        if status_callback:
            status_callback("再圧縮中...")
            
        succ, err = compress_directory(temp_dir, temp_out, target_format_key, compression_level)
        if succ:
            try:
                if has_chapter:
                    # 話数別フォルダ整理:
                    # 1. 元ファイルを _Original にリネームして退避保護
                    orig_backup_path = os.path.join(original_dir, f"{base_name}{config.ORIGINAL_ARCHIVE_MARKER}{current_ext}")
                    counter = 1
                    while os.path.exists(orig_backup_path):
                        orig_backup_path = os.path.join(original_dir, f"{base_name}{config.ORIGINAL_ARCHIVE_MARKER}_{counter}{current_ext}")
                        counter += 1
                    if os.path.exists(current_path):
                        os.rename(current_path, orig_backup_path)
                    
                    # 2. 変換後ファイルを本来のファイル名として配置
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(temp_out, output_path)
                    res.output_path = output_path
                elif is_same_file:
                    if os.path.exists(current_path):
                        os.remove(current_path)
                    os.rename(temp_out, current_path)
                    res.output_path = current_path
                else:
                    if os.path.exists(temp_out):
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        os.rename(temp_out, output_path)
                    res.output_path = output_path
                    
                    if delete_original and os.path.exists(current_path):
                        try:
                            os.remove(current_path)
                        except OSError as e:
                            logger.warning(f"元ファイルの削除に失敗: {current_path} ({e})")
                            
                res.success = True
                if normalize_symbols and '!' in os.path.basename(res.output_path):
                    res.output_path = normalize_symbol_path(res.output_path)
                    res.symbol_count += 1
                res.archive_path = res.output_path
                res.archive_name = os.path.basename(res.output_path)
                
                msgs = []
                if res.deleted_count: msgs.append(f"削除:{res.deleted_count}件")
                if res.chapter_organized:
                    msgs.append(f"話数整理:{res.chapter_count}話({res.organized_files_count}件)")
                elif res.flattened_count:
                    msgs.append(f"階層解消:{res.flattened_count}段")
                if res.shortened_count: msgs.append(f"名前短縮:{res.shortened_count}件")
                if res.symbol_count: msgs.append(f"記号整理:{res.symbol_count}件")
                if has_conversion and not res.chapter_organized:
                    msgs.append(f"形式変換:{scan_result.original_format}->{target_format_key}")
                if scan_result.extension_fixed_msg:
                    msgs.append("拡張子修正")
                    
                if not msgs:
                    msgs.append("完了")
                res.message = "✓ " + ", ".join(msgs)
                
                if preserve_timestamp and original_stat:
                    restore_file_timestamp(res.output_path, original_stat)
            except Exception as e:
                res.message = f"✗ 置換失敗: {e}"
                res.error_detail = f"出力ファイルの配置失敗: {e}"
                return res
        else:
            if os.path.exists(temp_out):
                try: os.remove(temp_out)
                except: pass
            res.message = f"✗ 再圧縮失敗: {err}"
            res.error_detail = f"再圧縮エラー: {err}"
            
    except Exception as exc:
        logger.exception("書庫の再パック中に失敗: %s", current_path)
        res.success = False
        res.message = f"✗ 書庫処理失敗: {exc}"
        res.error_detail = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    return res


def batch_clean_archives(
    scan_results: list[ScanResult],
    do_clean: bool = True,
    do_nesting: bool = True,
    do_shorten: bool = True,
    fix_extensions: bool = True,
    delete_original: bool = False,
    preserve_timestamp: bool = True,
    compression_level: int = 3,
    do_chapter_organize: bool = False,
    progress_callback=None,
    log_callback=None,
    status_callback=None,
    cancel_check=None,
    normalize_symbols: bool = True,
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

        clean_result = process_single_archive(
            scan_result=scan_result,
            do_clean=do_clean,
            do_nesting=do_nesting,
            do_shorten=do_shorten,
            normalize_symbols=normalize_symbols,
            fix_extensions=fix_extensions,
            delete_original=delete_original,
            preserve_timestamp=preserve_timestamp,
            compression_level=compression_level,
            do_chapter_organize=do_chapter_organize,
            status_callback=lambda step: status_callback(f"[{i + 1}/{total}] {step}") if status_callback else None
        )
        
        if log_callback:
            log_callback(f"  {clean_result.message}")

        results.append(clean_result)

        if progress_callback:
            progress_callback(i + 1, total)

    # 失敗した項目があればログにまとめて出力
    failed_results = [r for r in results if not r.success]
    if failed_results:
        logger.error(f"=== 書庫クリーン失敗サマリー ({len(failed_results)}/{total}件失敗) ===")
        for fr in failed_results:
            logger.error(f"  [対象ファイル] {fr.archive_path}")
            logger.error(f"  [失敗原因]     {fr.error_detail or fr.message}")

    return results
