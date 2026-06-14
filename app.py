import streamlit as st
import sys
from pathlib import Path

# 將 src 加入路徑以便引入同步模組
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))
from src.sync_manager import start_background_sync, SyncManager

# ── 頁面設定與導覽列 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="運彩投注額 Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 智慧背景自動同步 ────────────────────────────────────────────────────────
if 'has_synced' not in st.session_state:
    st.session_state.has_synced = True
    start_background_sync()

# 檢測背景同步狀態，進行熱加載
if SyncManager.has_new_data:
    st.cache_data.clear()
    SyncManager.has_new_data = False
    st.toast(f"🎉 發現 {SyncManager.new_files_count} 個新檔案，已自動於背景更新資料庫！")
    st.rerun()

if SyncManager.error_msg:
    st.sidebar.error(f"同步失敗: {SyncManager.error_msg}")
    SyncManager.error_msg = None

# ── 顯示同步狀態 (於 Sidebar 頂部) ──────────────────────────────────────────
if SyncManager.is_running:
    st.sidebar.info("🔄 背景資料同步中...")
else:
    st.sidebar.caption("☁️ 雲端同步已完成")



# ── 建立自訂導覽列 (Sidenav) ───────────────────────────────────────────
# 將所有的畫面模組註冊進 st.navigation
pages = [
    st.Page("views/dashboard.py", title="首頁", icon=":material/home:"),
    st.Page("views/betting_analysis.py", title="投注額趨勢分析", icon=":material/monitoring:"),
    st.Page("views/members_crm.py", title="會員管道與資料維護", icon=":material/groups:"),
    st.Page("views/members_rfm.py", title="會員狀態與流失分析", icon=":material/health_and_safety:"),
    st.Page("views/finance.py", title="財務紀錄", icon=":material/account_balance:"),
    st.Page("views/demo_tailadmin.py", title="設計展示 (Demo)", icon=":material/palette:"),
]

pg = st.navigation(pages)
pg.run()
