# -*- coding: utf-8 -*-
"""
ArchiveFileManager - ロジックテスト
GUI を介さずに、圧縮・解凍・補正などのロジックが動作するか確認します。
"""

import os
import sys
import shutil
import tempfile

# src ディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from config import validate_environment
from extension_fixer import detect_real_format
from folder_normalizer import normalize_folder_structure

def test_environment():
    print("Testing environment...")
    errors = validate_environment()
    if errors:
        print("Error: Environment validation failed!")
        for err in errors:
            print(f"  - {err}")
        return False
    print("Environment OK.")
    return True

def test_folder_normalizer():
    print("Testing folder normalizer...")
    temp_dir = tempfile.mkdtemp()
    try:
        # 入れ子構造を作成: temp_dir/A/B/file.txt
        nest1 = os.path.join(temp_dir, "A")
        os.makedirs(nest1)
        nest2 = os.path.join(nest1, "B")
        os.makedirs(nest2)
        
        with open(os.path.join(nest2, "file.txt"), "w") as f:
            f.write("test")
            
        print(f"  Created nested structure in {temp_dir}")
        
        # 処理実行
        count = normalize_folder_structure(temp_dir)
        print(f"  Fixed {count} levels.")
        
        # 結果確認
        if os.path.isfile(os.path.join(temp_dir, "file.txt")):
            print("  Normalization SUCCESS: file.txt moved to root.")
            return True
        else:
            print("  Normalization FAILED: file.txt not found in root.")
            return False
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    success = True
    if not test_environment(): success = False
    print("-" * 20)
    if not test_folder_normalizer(): success = False
    print("-" * 20)
    
    if success:
        print("All tests PASSED (logic check only).")
        sys.exit(0)
    else:
        print("Some tests FAILED.")
        sys.exit(1)
