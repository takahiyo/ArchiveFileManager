import os
import sys
import shutil

# src ディレクトリをパスに追加
sys.path.append(os.path.join(os.getcwd(), "src"))

import config

def test_external_config():
    print("--- External Config Test ---")
    exe_dir = config.get_exe_dir()
    config_path = os.path.join(exe_dir, config.CLEAN_PATTERNS_FILE)
    
    print(f"Exe Dir: {exe_dir}")
    print(f"Config Path: {config_path}")
    
    # 既存のファイルを退避
    backup = None
    if os.path.exists(config_path):
        backup = config_path + ".bak"
        shutil.move(config_path, backup)
        print("Backup existing config.")

    try:
        # 1. 初回ロード（ファイルがない状態）
        patterns = config.load_clean_patterns()
        print(f"Initial patterns: {patterns}")
        if not os.path.exists(config_path):
            print("FAILED: Config file not created on first load.")
            return

        # 2. ファイルを書き換え
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("*.tmp\n")
            f.write("custom_file.txt\n")
        
        # 再読み込み
        reloaded = config.load_clean_patterns()
        print(f"Reloaded patterns: {reloaded}")
        if "*.tmp" not in reloaded or "custom_file.txt" not in reloaded:
            print("FAILED: Reloaded patterns mismatch.")
            return
        
        # 3. 保存機能
        config.save_clean_patterns(["new_pattern.log"])
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"File content after save:\n{content}")
            if "new_pattern.log" not in content:
                print("FAILED: Save failed.")
                return
        
        print("\nSUCCESS: External config logic works correctly.")

    finally:
        # 復元
        if os.path.exists(config_path):
            os.remove(config_path)
        if backup:
            shutil.move(backup, config_path)
            print("Restored backup.")

if __name__ == "__main__":
    test_external_config()
