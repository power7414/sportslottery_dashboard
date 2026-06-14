import os
import sqlite3
import re
import dropbox
from dropbox.exceptions import AuthError
from dotenv import load_dotenv
from pathlib import Path

# 載入環境變數
load_dotenv()

# 設定本地端資料夾路徑與 Dropbox 目標資料夾
BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "processed" / "betting_data.db"
DROPBOX_TARGET_FOLDER = "/93121074"

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except OSError:
        pass


def get_latest_db_month():
    """去 SQLite 查詢目前最新的資料落在哪個月份 (例如回傳 '2026-04')"""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        cur = conn.cursor()
        cur.execute("SELECT MAX(date) FROM fact_daily_summary")
        max_date = cur.fetchone()[0]
        conn.close()
        if max_date:
            return max_date[:7] # 只取 YYYY-MM
    except:
        pass
    return None

def extract_ym_from_filename(filename: str):
    """從檔名萃取月份，例如 2604 -> '2026-04'"""
    match = re.search(r'-(\d{4})\.xlsx', filename)
    if not match:
        return None
    ym = match.group(1)
    return f"20{ym[:2]}-{ym[2:]}"

def get_dropbox_client():
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    
    if not refresh_token:
        raise ValueError("尚未設定 DROPBOX_REFRESH_TOKEN 環境變數。")
        
    # 建立一個具有自動刷新能力的 Dropbox 客戶端
    return dropbox.Dropbox(
        app_key=app_key,
        app_secret=app_secret,
        oauth2_refresh_token=refresh_token
    )

def sync_dropbox_folder(dbx_folder_path: str = DROPBOX_TARGET_FOLDER):
    """從 Dropbox 下載最新檔案到本地 data/ 目錄，只下載有變動的檔案"""
    dbx = get_dropbox_client()
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    latest_db_month = get_latest_db_month()
    
    try:
        safe_print(f"正在連線至 Dropbox，檢查是否有新資料...")
        if latest_db_month:
            safe_print(f"👉 資料庫目前最新進度：{latest_db_month}，歷史舊檔案將被直接忽略。")
            
        result = dbx.files_list_folder(dbx_folder_path)
        
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.xlsx'):
                file_ym = extract_ym_from_filename(entry.name)
                
                # 🛡️ 核心防護機制：如果這份 Excel 的月份「小於」資料庫的最新月份，連看都不看！
                if latest_db_month and file_ym and file_ym < latest_db_month:
                    continue
                    
                local_file_path = LOCAL_DATA_DIR / entry.name
                
                # 智慧比對：改用「檔案最後修改時間」
                # 如果本地檔案存在，且 Dropbox 上的修改時間沒有比本地檔案的新，就跳過
                if local_file_path.exists():
                    local_mtime = local_file_path.stat().st_mtime
                    # entry.server_modified 是 datetime 物件
                    remote_mtime = entry.server_modified.timestamp()
                    
                    if remote_mtime <= local_mtime:
                        continue
                    
                safe_print(f"發現新資料，正在下載: {entry.name} ... ", end="", flush=True)
                dbx.files_download_to_file(str(local_file_path), entry.path_display)
                
                # 下載後，手動把本地檔案的修改時間，同步成 Dropbox 上的時間，確保下次比對精準
                os.utime(local_file_path, (entry.server_modified.timestamp(), entry.server_modified.timestamp()))
                
                safe_print("完成!")
                downloaded_files.append(local_file_path)
                
        if downloaded_files:
            safe_print(f"✅ 共成功同步了 {len(downloaded_files)} 個新檔案。")
        else:
            safe_print(f"✅ 資料庫已是最新，沒有需要下載的檔案。")
            
        return downloaded_files
                
    except AuthError as e:
        safe_print("❌ 認證失敗！請確認 DROPBOX_ACCESS_TOKEN 是否正確或已過期。")
        raise e
    except Exception as e:
        safe_print(f"❌ 發生錯誤: {e}")
        raise e

if __name__ == "__main__":
    safe_print("=== 開始同步 Dropbox 資料 ===")
    sync_dropbox_folder()
    safe_print("=== 同步結束 ===")
