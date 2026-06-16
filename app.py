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
def get_user_email():
    # 1. 嘗試從 st.user 取得 (Streamlit 1.37.0+)
    try:
        if hasattr(st, "user") and st.user:
            if hasattr(st.user, "email") and st.user.email:
                return st.user.email
            if hasattr(st.user, "get"):
                val = st.user.get("email")
                if val: return val
    except:
        pass

    # 2. 嘗試從 st.experimental_user 取得 (舊版 Streamlit)
    try:
        if hasattr(st, "experimental_user") and st.experimental_user:
            if hasattr(st.experimental_user, "email") and st.experimental_user.email:
                return st.experimental_user.email
            if hasattr(st.experimental_user, "get"):
                val = st.experimental_user.get("email")
                if val: return val
    except:
        pass

    # 3. 嘗試從 HTTP 標頭取得 (Streamlit Cloud 自動帶入的身份標頭)
    try:
        headers = st.context.headers
        if headers:
            email = headers.get("X-Streamlit-User")
            if email:
                return email
    except:
        pass

    return None

user_email = get_user_email()

# 偵測是否在雲端運行
import os
is_cloud = "STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION" in os.environ or os.path.exists("/mount/src")
is_local = not is_cloud

# 定義管理員 Email 清單 (您其他的信箱以及夥伴信箱)
ADMIN_EMAILS = [
    "enoch41228@gmail.com",
    "schumichu0925@gmail.com",
    "charliem713ac@gmail.com",
    "power7414@gmail.com"  # 確保您的 Google 信箱也在此
]

# 權限判定：
# 本地端 (is_local) 預設為 Admin 方便開發
# 雲端 (is_cloud) 則檢查登入 Email 是否在管理員清單內，不在或未登入則限制為 Viewer 權限
is_admin = is_local or (user_email and user_email in ADMIN_EMAILS)

if not is_admin:
    # 僅限首頁 (Viewer 權限，例如 b10703023@gmail.com 或未登入的雲端訪客)
    pages = [
        st.Page("views/dashboard.py", title="首頁", icon=":material/home:"),
    ]
else:
    # 管理員權限
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
