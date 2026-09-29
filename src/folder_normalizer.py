# -*- coding: utf-8 -*-
"""
ArchiveFileManager - フォルダ階層の正規化
圧縮ファイルを解凍した結果「ルート直下にフォルダが1つだけ」
という余分な階層がある場合、それを解消します。
"""

import os
import re
import shutil
import tempfile
import logging

logger = logging.getLogger(__name__)


def natural_sort_key(s: str) -> list:
    """自然順ソート用キー関数（数字を数値として比較）"""
    # isdigit() は int() で変換できない丸数字（❺、①など）も含む。
    # 分割パターンの \d と同じ十進数字だけを数値として扱う。
    return [int(text) if text.isdecimal() else text.lower() for text in re.split(r'(\d+)', s)]


def is_chapter_structured(file_list: list[str]) -> bool:
    """
    書庫内のファイル一覧から、複数の話数フォルダ（またはCoverフォルダ＋話数フォルダ）に
    分かれている構造であるかを判定する。
    """
    raw_paths = [f.replace("\\", "/").strip().strip("/") for f in file_list if f.strip().strip("/")]
    if not raw_paths:
        return False

    # ディレクトリそのもののエントリ（子孫を持つエントリ）を除外し、実際のファイルのみを抽出
    all_set = set(raw_paths)
    files = [p for p in raw_paths if not any(other.startswith(p + "/") for other in all_set)]
    if not files:
        files = raw_paths

    # 各ファイルのパスを構成するディレクトリ部分を取得
    file_dirs = [os.path.dirname(f).strip("/") for f in files if os.path.dirname(f).strip("/")]
    if not file_dirs:
        return False

    # 共通のプレフィックス（最外層フォルダ）があれば除去する
    # 例: 'ahou Shoujo.../cover/01.jpg' -> 'cover/01.jpg'
    first_split = file_dirs[0].split("/")
    top_dir = first_split[0]
    if all(d == top_dir or d.startswith(top_dir + "/") for d in file_dirs):
        stripped_dirs = []
        for d in file_dirs:
            if d == top_dir:
                pass
            elif d.startswith(top_dir + "/"):
                stripped_dirs.append(d[len(top_dir) + 1:])
        file_dirs = stripped_dirs

    if not file_dirs:
        return False

    # 各ファイルが属する直下のフォルダ名を収集
    sub_folders = set(d.split("/")[0] for d in file_dirs if d)

    # 2つ以上のサブフォルダに分かれているか
    if len(sub_folders) >= 2:
        return True

    # 1つのフォルダのみでも、それが cover フォルダで、かつ外側にファイルがある場合
    if len(sub_folders) == 1 and any("cover" in s.lower() for s in sub_folders):
        return True

    return False


def organize_chapters_and_flatten(extracted_dir: str) -> tuple[int, int, int]:
    """
    話数別フォルダ・ファイル名の整理および入れ子の解消を行う。
    1. 最外層の単一ラッパーフォルダがあれば解消
    2. Coverフォルダ・ファイルを最優先で Cover_001.ext ... にリネーム
    3. それ以外のフォルダを正順ソートし、v001_001.ext, v001_002.ext ... にリネーム
    4. 全ファイルをルート直下に並べ、空になったサブフォルダを削除する。

    戻り値:
        (cover_count, chapter_count, total_renamed)
    """
    # 1. 最外層の単一フォルダ入れ子があれば解消
    normalize_folder_structure(extracted_dir)
    
    # 2. Coverファイルと各話フォルダの分類
    cover_files = []
    chapter_dirs = []
    root_non_cover_files = []
    
    entries = sorted(os.listdir(extracted_dir), key=natural_sort_key)
    for item in entries:
        item_path = os.path.join(extracted_dir, item)
        if os.path.isdir(item_path):
            if "cover" in item.lower():
                for root, dirs, files in os.walk(item_path):
                    for f in files:
                        cover_files.append(os.path.join(root, f))
            else:
                chapter_dirs.append(item_path)
        else:
            if "cover" in item.lower():
                cover_files.append(item_path)
            else:
                root_non_cover_files.append(item_path)
                
    # フォルダ名で正順ソート
    chapter_dirs.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    cover_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    root_non_cover_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    
    # 話数フォルダもCoverもない場合は何もしない
    if not chapter_dirs and not cover_files:
        return (0, 0, 0)
        
    # 一時退避（ステージング）ディレクトリを作成して衝突を防止
    staging_dir = tempfile.mkdtemp(prefix="afm_stage_")
    try:
        total_renamed = 0
        cover_count = len(cover_files)
        chapter_count = len(chapter_dirs)
        
        # 1. Coverのリネーム: Cover_001.jpg, Cover_002.jpg ...
        for idx, src in enumerate(cover_files, 1):
            ext = os.path.splitext(src)[1].lower()
            dst_name = f"Cover_{idx:03d}{ext}"
            shutil.copy2(src, os.path.join(staging_dir, dst_name))
            total_renamed += 1
            
        # 2. ルートに直置きされていた非Coverファイル（もしあれば）は v000_001... として扱う
        if root_non_cover_files:
            for idx, src in enumerate(root_non_cover_files, 1):
                ext = os.path.splitext(src)[1].lower()
                dst_name = f"v000_{idx:03d}{ext}"
                shutil.copy2(src, os.path.join(staging_dir, dst_name))
                total_renamed += 1

        # 3. 各話フォルダのリネーム: v001_001.jpg ...
        for ch_idx, ch_dir in enumerate(chapter_dirs, 1):
            ch_files = []
            for root, dirs, files in os.walk(ch_dir):
                for f in files:
                    ch_files.append(os.path.join(root, f))
            ch_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
            
            for f_idx, src in enumerate(ch_files, 1):
                ext = os.path.splitext(src)[1].lower()
                dst_name = f"v{ch_idx:03d}_{f_idx:03d}{ext}"
                shutil.copy2(src, os.path.join(staging_dir, dst_name))
                total_renamed += 1
                
        # 4. extracted_dir 内の既存エントリを全削除し、ステージングしたファイルをルートに移動
        for item in os.listdir(extracted_dir):
            item_path = os.path.join(extracted_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
            else:
                try:
                    os.remove(item_path)
                except OSError:
                    pass
                    
        for f in os.listdir(staging_dir):
            shutil.move(os.path.join(staging_dir, f), os.path.join(extracted_dir, f))
            
        logger.info(f"話数別フォルダ・ファイル名整理完了: Cover {cover_count}件, {chapter_count}話, 計 {total_renamed}ファイル")
        return (cover_count, chapter_count, total_renamed)
        
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)



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
