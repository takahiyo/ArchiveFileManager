import os
import zipfile
import logging
import sys

# src をパスに追加
sys.path.append(os.path.join(os.getcwd(), 'src'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
from archive_content_cleaner import list_archive_contents, ScanResult, process_single_archive

def test_process():
    test_zip = "test_many_files.zip"
    # 30個のファイルを作成（リストファイル方式を誘発）
    with zipfile.ZipFile(test_zip, "w") as z:
        for i in range(30):
            z.writestr(f"ad_file_{i:02d}.txt", "dummy content")
        z.writestr("keep_me.txt", "essential data")
    
    print(f"Created {test_zip} with 30 deletable files.")
    
    scan_res = ScanResult(test_zip)
    scan_res.matched_files = [f"ad_file_{i:02d}.txt" for i in range(30)]
    
    print("Executing process_single_archive (Direct delete flow)...")
    # do_nesting=False, do_shorten=False で高速削除フローをテスト
    res = process_single_archive(scan_res, do_nesting=False, do_shorten=False)
    
    print(f"Result Success: {res.success}")
    print(f"Result Message: {res.message}")
    print(f"Deleted Count: {res.deleted_count}")
    
    # 内容確認
    if res.success:
        with zipfile.ZipFile(test_zip, 'r') as z:
            remain = z.namelist()
            print(f"Remaining files: {len(remain)}")
            if "keep_me.txt" in remain and len(remain) == 1:
                print("Verification SUCCESS: All matched files deleted correctly via list file.")
            else:
                print(f"Verification FAILED: Remaining files = {remain}")
    
    if os.path.exists(test_zip): os.remove(test_zip)

if __name__ == "__main__":
    test_process()
