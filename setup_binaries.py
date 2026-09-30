import os
import sys
import urllib.request
import zipfile
import json
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")

def ensure_binaries():
    os.makedirs(BIN_DIR, exist_ok=True)
    scrcpy_dir = os.path.join(BIN_DIR, "scrcpy")
    adb_path = os.path.join(scrcpy_dir, "adb.exe")

    if os.path.exists(adb_path):
        print("[+] ADB and Scrcpy binaries are ready.")
        return True

    print("[*] Downloading Scrcpy & ADB portable package for Windows...")
    try:
        url = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            release = json.loads(resp.read().decode('utf-8'))
            zip_asset = None
            for asset in release.get('assets', []):
                name = asset.get('name', '')
                if 'win64' in name and name.endswith('.zip'):
                    zip_asset = asset
                    break
            
            if zip_asset:
                download_url = zip_asset['browser_download_url']
                print(f"[*] Downloading {zip_asset['name']} from {download_url}...")
                zip_path = os.path.join(BIN_DIR, "scrcpy_temp.zip")
                urllib.request.urlretrieve(download_url, zip_path)
                
                temp_extract = os.path.join(BIN_DIR, "temp_extract")
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(temp_extract)
                os.remove(zip_path)
                
                extracted_sub = os.listdir(temp_extract)
                if extracted_sub:
                    src_folder = os.path.join(temp_extract, extracted_sub[0])
                    os.makedirs(scrcpy_dir, exist_ok=True)
                    for item in os.listdir(src_folder):
                        s = os.path.join(src_folder, item)
                        d = os.path.join(scrcpy_dir, item)
                        if os.path.exists(d):
                            if os.path.isdir(d):
                                shutil.rmtree(d)
                            else:
                                os.remove(d)
                        shutil.move(s, d)
                    shutil.rmtree(temp_extract)
                print("[+] Scrcpy & ADB installed successfully!")
                return True
    except Exception as e:
        print(f"[-] Auto-download failed: {e}")
        return False

if __name__ == "__main__":
    ensure_binaries()
