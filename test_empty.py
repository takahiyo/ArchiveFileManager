# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 空フォルダロジックテスト
"""

import os
import sys
import shutil
import tempfile
import time

# src ディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from empty_folder_scanner import scan_empty_folders, delete_folders

def test_empty_folder_scanner():
    print("Testing empty folder scanner...")
    temp_dir = tempfile.mkdtemp()
    try:
        # 構造作成:
        # temp_dir/
        #   ├── empty1/       (空)
        #   ├── not_empty/
        #   │   └── file.txt
        #   └── deep/
        #       └── empty2/   (空)
        
        os.makedirs(os.path.join(temp_dir, "empty1"))
        os.makedirs(os.path.join(temp_dir, "not_empty"))
        with open(os.path.join(temp_dir, "not_empty", "file.txt"), "w") as f:
            f.write("test")
        os.makedirs(os.path.join(temp_dir, "deep", "empty2"))
        
        # タイムスタンプ更新のために少し待つ
        time.sleep(0.1)
        
        # 検索テスト
        results = scan_empty_folders(temp_dir)
        print(f"  Found {len(results)} empty folders.")
        
        folder_names = [x["name"] for x in results]
        if "empty1" in folder_names and "empty2" in folder_names and "not_empty" not in folder_names:
            print("  Scan SUCCESS: Correct folders identified.")
        else:
            print(f"  Scan FAILED: Unexpected results: {folder_names}")
            return False

        # 削除テスト
        targets = [x["path"] for x in results]
        del_results = delete_folders(targets)
        
        success_count = sum(1 for r in del_results if r["success"])
        if success_count == 2:
            print("  Delete SUCCESS: All targets deleted.")
        else:
            print(f"  Delete FAILED: Deleted {success_count} folders.")
            return False
            
        # 残存確認
        if os.path.exists(os.path.join(temp_dir, "empty1")):
            print("  Delete FAILED: empty1 still exists.")
            return False
            
        return True

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    if test_empty_folder_scanner():
        print("All tests PASSED.")
        sys.exit(0)
    else:
        print("Tests FAILED.")
        sys.exit(1)
