import subprocess
import os
import zipfile

def test_unrar_x():
    unrar_exe = r"C:\Program Files\WinRAR\UnRAR.exe"
    test_zip = os.path.abspath("test_x.zip")
    with zipfile.ZipFile(test_zip, "w") as z:
        z.writestr("test.txt", "content")
    
    dest_base = os.path.abspath("test_dest")
    
    cases = [
        {"name": "NoSlash", "dest": dest_base},
        {"name": "WithSlash", "dest": dest_base + os.sep},
        {"name": "Basic", "cmd": [unrar_exe, "x", "-y", test_zip, dest_base + os.sep]},
    ]
    
    for case in cases:
        if os.path.exists(dest_base):
            import shutil
            shutil.rmtree(dest_base, ignore_errors=True)
        os.makedirs(dest_base, exist_ok=True)
        
        cmd = case.get("cmd")
        if not cmd:
            cmd = [unrar_exe, "x", "-o+", "-y", test_zip, case["dest"]]
            
        print(f"\nCase: {case['name']}")
        print(f"Cmd: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Ret: {res.returncode}")
        print(f"Stdout: {res.stdout.strip()[:100]}")
        print(f"Stderr: {res.stderr.strip()}")
        
    if os.path.exists(test_zip): os.remove(test_zip)
    if os.path.exists(dest_base):
        import shutil
        shutil.rmtree(dest_base, ignore_errors=True)

if __name__ == "__main__":
    test_unrar_x()
