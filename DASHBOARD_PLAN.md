# 運彩投注額結算 - Dashboard 專案架構與開發指南

## 1. 專案目標 (Objective)
將本地端繁雜的 Python Excel 處理腳本，全面升級為基於 SQLite 的 **商業智能儀表板 (BI Dashboard)**，供內部團隊進行即時的業績追蹤、精準行銷、客戶挽回與財務記帳。

## 2. 技術棧選型 (Tech Stack)
*   **前端展示：`Streamlit`**
    *   負責路由 (Multi-page) 與互動式圖表 (結合 Plotly)。
    *   內建 `st.data_editor` 作為輕量化 ERP 表單填寫介面。
*   **核心資料庫：`SQLite`**
    *   完全棄用每次重讀 Excel 的舊模式。所有清洗過的資料皆儲存於 `processed/betting_data.db`。
    *   優點：支援關聯式查詢、支援即時的資料 CRUD（如修改會員管道、新增財務紀錄）。
*   **資料清洗：`Pandas` & `Openpyxl`**
    *   用於解析運彩後台產生的複雜 Excel 表格。
*   **雲端同步：`Dropbox Python SDK`**
    *   用於自動增量下載最新的 Excel 報表。

## 3. 架構邏輯分層 (Architecture)

### Phase 1: 自動增量更新層 (Data Sync & Upsert)
*   **觸發機制**：每次開啟 `app.py` 時，透過 `session_state` 觸發一次 Dropbox 檢查。
*   **處理邏輯 (`src/init_database.py`)**：
    *   採用 **「精準增量更新 (True Incremental Update)」**。
    *   系統只會解析最新下載的單一 Excel 檔案，並透過 `INSERT OR REPLACE` (UPSERT) 將每日投注明細 (`fact_daily_bets`) 與跨月同意/不同意總和 (`fact_daily_summary`) 更新至 SQLite。
    *   這將更新時間從原本的 90 秒壓縮至 5 秒以內。

### Phase 2: 前端展示與商業邏輯層 (Frontend Display)
所有頁面均依賴 `betting_data.db` 進行關聯查詢，嚴禁前端直接讀取原始 Excel。

*   **app.py (首頁 Overview)**
    *   本月/上月/本週業績指標。
    *   6 個月歷史營收堆疊圖。
    *   每月前十名大戶排行榜。
*   **pages/01_整體投注.py (Overall Betting)**
    *   活躍度追蹤：DAU / WAU / MAU 趨勢分析。
    *   熱圖與自訂時間區間查詢。
*   **pages/02_會員資料與管道.py (Member Demographics)**
    *   行銷 ROI 分析：每月新增會員與管道營收堆疊圖。
    *   野生大戶捕捉：將不在主檔的會員標記為 `❓ 未標記`，並允許透過介面直接寫入 `dim_member` 資料庫進行正名。
*   **pages/03_投注行為分析.py (Behavior Analysis)**
    *   基於「現在時間 (Right Now)」往前推 30 天的當前狀態判定。
    *   偵測「需挽回大戶」與「已流失客群」。
    *   動態標籤系統：賽事偏好 (純NBA/雙棲) 與 玩家性格 (高頻鐵粉/衝動型)。
*   **pages/04_財務紀錄.py (Finance Ledger)**
    *   整合性 ERP 模塊，提供表單新增與 `st.data_editor` 互動式直接編輯。
    *   營運淨利計算與收支圖表 (Bar + Line + Pie 組合)。

## 4. 資料庫綱要 (Database Schema)

資料庫位於 `processed/betting_data.db`，核心表單如下：
*   **`fact_daily_bets`**: 個別會員的每日投注明細。
*   **`fact_daily_summary`**: 每日整體的「同意/不同意」總人數與總金額（含跨月結帳紀錄）。
*   **`dim_member`**: 會員主檔，記錄 `backend_id`、`member_id`、`channel`、`join_date` 等。
*   **`fact_finance`**: 財務紀錄表，記錄 `date`、`type`(收入/支出)、`category`、`amount` 等。

## 5. AI Agent 開發準則 (Skills & Guidelines)
後續參與此專案的 AI 助理（Agent）必須遵守以下規則：
1.  **資料庫唯一真理 (Single Source of Truth)**：所有商業運算都必須基於 SQLite 資料庫。嚴禁讀取 `data/` 裡面的 Excel 來進行動態運算。
2.  **效能優先**：所有查詢與資料聚合必須搭配 `@st.cache_data`，以確保使用者切換分頁時的流暢度。若資料庫有更新（如透過表單寫入），需呼叫 `st.cache_data.clear()`。
3.  **UI 規範**：盡量使用 Streamlit 原生的元件 (`st.metric`, `st.dataframe`, `st.data_editor`) 並搭配 Plotly 視覺化。
4.  **檔案增刪**：舊有的 `analysis.py`, `calculate_by_channel.py` 等單次執行腳本已被棄用並刪除，請專注於擴充 `pages/` 模組或優化 SQL 查詢。
