import threading
import glob
from pathlib import Path
from src.dropbox_sync import sync_dropbox_folder, get_latest_db_month, extract_ym_from_filename
from src.init_database import update_specific_files

class SyncManager:
    lock = threading.Lock()
    is_running = False
    has_new_data = False
    error_msg = None
    new_files_count = 0

def start_background_sync():
    """啟動背景同步線程 (跨 Session 安全，同一時間只會有一個 Thread 在跑)"""
    with SyncManager.lock:
        if SyncManager.is_running:
            return
        SyncManager.is_running = True
        SyncManager.error_msg = None
        SyncManager.has_new_data = False
        SyncManager.new_files_count = 0

    def task():
        try:
            # 1. 同步 Dropbox 雲端新檔案
            new_files = sync_dropbox_folder()
            if new_files is None:
                new_files = []
            
            new_files_resolved = [str(Path(f).resolve()) for f in new_files]
            
            # 2. 智慧掃描本地：找出未導入或最新月份的本地 Excel
            latest_db_month = get_latest_db_month()
            
            BASE_DIR = Path(__file__).resolve().parent.parent
            LOCAL_DATA_DIR = BASE_DIR / "data"
            local_files = glob.glob(str(LOCAL_DATA_DIR / "*.xlsx"))
            
            for lf in local_files:
                lf_path = Path(lf)
                file_ym = extract_ym_from_filename(lf_path.name)
                
                # 如果資料庫無資料，或本地檔案的月份大於等於資料庫中最新月份
                if not latest_db_month or (file_ym and file_ym >= latest_db_month):
                    lf_resolved = str(lf_path.resolve())
                    if lf_resolved not in new_files_resolved:
                        new_files.append(str(lf_path))
                        new_files_resolved.append(lf_resolved)
            
            if new_files:
                update_specific_files(new_files)
                SyncManager.new_files_count = len(new_files)
                SyncManager.has_new_data = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            SyncManager.error_msg = str(e)
        finally:
            with SyncManager.lock:
                SyncManager.is_running = False

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
