# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 書庫クリーン機能のテスト
"""

import os
import sys
import shutil
import tempfile
import fnmatch

# src ディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from archive_content_cleaner import (
    find_matching_files,
    find_long_names,
    shorten_name
)

def test_matching_logic():
    print("Testing pattern matching logic...")
    file_list = [
        "test.txt",
        "sub/folder/test.url",
        "test.url.bak",
        "sub/Thumbs.db",
        "archive.zip",
    ]
    patterns = ["*.url", "Thumbs.db"]
    
    matched = find_matching_files(file_list, patterns)
    expected = ["sub/folder/test.url", "sub/Thumbs.db"]
    
    if set(matched) == set(expected):
        print("  Pattern Match SUCCESS")
        return True
    else:
        print(f"  Pattern Match FAILED: {matched}")
        return False

def test_long_name_logic():
    print("Testing long name logic...")
    long_name_100 = "a" * 100 + ".txt"
    long_dir = "b" * 90
    file_list = [
        "normal.txt",
        long_name_100,
        f"{long_dir}/normal.txt",
    ]
    
    # MAX_NAME_LENGTH = 80 相当のテスト
    long_items = find_long_names(file_list, 80)
    
    if len(long_items) == 2 and long_name_100 in long_items and f"{long_dir}/normal.txt" in long_items:
        print("  Long Name Detection SUCCESS")
    else:
        print(f"  Long Name Detection FAILED: {long_items}")
        return False
        
    # 短縮テスト
    shortened = shorten_name(long_name_100, 80)
    # 拡張子 (.txt = 4 chars) とハッシュ (~xxxxxx = 7 chars) を除いたベース部分
    # 文字列の長さが80を超えることはないか
    base, ext = os.path.splitext(shortened)
    if len(base) <= 80 and ext == ".txt" and "~" in base:
        print(f"  Name Shortening SUCCESS: {shortened}")
    else:
        print(f"  Name Shortening FAILED: {shortened} (length: {len(base)})")
        return False

    return True

if __name__ == "__main__":
    success = True
    if not test_matching_logic(): success = False
    print("-" * 20)
    if not test_long_name_logic(): success = False
    print("-" * 20)
    
    if success:
        print("All tests PASSED (logic check only).")
        sys.exit(0)
    else:
        print("Some tests FAILED.")
        sys.exit(1)
