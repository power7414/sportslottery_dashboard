# AGENT.md — 共同頻率確認文件

## 專案概述
本專案為**運彩投注額結算系統 (Business Intelligence Dashboard)**。
主要為台灣運彩經銷商自動化處理後台匯出的 Excel 報表，整合行銷管道追蹤、會員行為分析、以及內部財務收支，提供即時、互動式的商業洞察。

## 技術選型
- **前端與框架**：Streamlit (1.34+)
- **資料庫**：SQLite
- **圖表庫**：Plotly
- **同步雲端**：Dropbox API (使用 Refresh Token)

## 視覺與 UI 規範 (TailAdmin 深色風格)
- **色碼**：Primary Color `#465fff`, Background `#101828`。
- **圖標**：全面改用 Google Material Icons (例如 `:material/monitoring:`)，避免使用傳統 Emoji。
- **折線圖**：必須使用 `shape='spline'`（平滑）與 `fill='tozeroy'`（漸層面積），且設定 `hovermode="x unified"`。
- **圓餅圖**：關閉 Legend，將資訊改以 `textinfo='percent+label'` 放在圓餅內部，且 `hole=0.5`（呈現甜甜圈圖）。
- **對話框**：薪資試算與新增收支等操作，使用新版 `@st.dialog` 彈窗，保持頁面整潔。

## ⚠️ 核心雷區與業務邏輯
- **`src/calculate_betting_final.py`**：負責 Excel 的清洗與跨月補點回溯邏輯（處理上月最後一天晚間投注被記在下月第一天報表的問題），絕對不可隨意重寫或刪除。
- **休賽期判定**：RFM 分析中，若會員超過 30 天未投注，但目前處於其偏好賽事的休賽季（如 NBA 玩家在 7-9 月），應判定為 `⚪ 沉睡中 (休賽季)` 而非 `🔴 已流失`。
