# 運彩投注額結算系統 - 開發者與架構指南 (Developer Guide)

這份文件記錄了本專案的核心架構、隱藏的業務邏輯（Domain Knowledge），以及特殊套件的處理方式。**任何新加入的工程師或 AI Agent 在修改此專案前，請務必先閱讀本文件**，以避免踩坑或誤刪核心邏輯。

---

## 1. 系統資料流與 Dropbox 同步機制
本系統的資料並非直接透過 API 取得原始數據，而是依賴「Dropbox 同步 Excel 報表 ➡️ 轉換 ➡️ 寫入 SQLite」的 Pipeline。

*   **觸發機制**：
    在 `app.py` 的起始處，系統會透過 `st.session_state.has_synced` 判斷是否為本次 Session 首次開啟。如果是，則會在背景自動呼叫 `sync_dropbox_folder()` 進行同步。我們**沒有**在畫面上放置手動同步按鈕，採全自動背景偵測。
*   **Dropbox 下載邏輯 (`src/dropbox_sync.py`)**：
    *   使用 `DROPBOX_REFRESH_TOKEN` 來確保長期的 API 存取權限。
    *   **智慧比對**：程式會先去 SQLite 查詢當前最新的資料月份（例如 `2026-04`）。若 Dropbox 上的 Excel 檔名小於這個月份，直接略過。若大於等於，則會比對「雲端最後修改時間」與「本地檔案最後修改時間」，有更新才會下載，達到極速增量的效果。

## 2. ⚠️ 核心雷區：Excel 資料清洗解析 (`src/calculate_betting_final.py`)
這是一個**絕對不能被刪除或大幅改寫**的核心模組，因為原始的運彩結算 Excel 報表格式非常混亂且不規則，具有以下特殊業務邏輯：

1.  **「同意」與「不同意」的差異**：
    報表區分了「同意第三人」與「不同意第三人」的投注額。在整體營收與分潤計算上，必須嚴格拆分這兩個數字，這也是為什麼 `fact_daily_summary` 表格會將其分為 `agreed_amount` 與 `disagreed_amount`。
2.  **跨月補點的「幽靈數據」問題**：
    因為系統結算時間差的關係，有時候「上個月最後一天」的晚間投注，會被記載到「下個月第一天」的 Excel 報表中。`calculate_betting_final.py` 裡面有專門針對這個情況的跨月回朔邏輯，確保每個月份的最終結算金額一毛不差。
3.  **依賴關係**：
    當 Dropbox 載下新 Excel 後，`src/init_database.py` 會自動 `import` 這個解析器來將死板的 Excel 轉換成關聯式資料庫可讀的形式，然後用 `UPSERT` 寫進 `.db` 檔案中。

## 3. 會員狀態與流失標籤 (RFM 模型)
在 `src/member_rfm_analysis.py` 中，我們定義了嚴謹的會員分級與流失防護網：
*   **賽季偏好**：透過解析會員過去下注的月份，自動貼上「純 MLB」、「純 NBA」或「雙棲」標籤。
*   **流失 vs. 沉睡**：一般來說超過 30 天未下注會被判定為「🔴 已流失」。但系統會去檢查他是不是單一賽事玩家（例如：現在是 MLB 賽季，但他身上有純 NBA 標籤），如果是的話，會被寬容判定為「⚪ 沉睡中 (休賽季)」，這對精準行銷非常重要。
*   **Colab 探索腳本**：根目錄下有一支 `rfm_analysis.ipynb`，內部包含了等價的邏輯，專門提供給分析師在不啟動網站的情況下，手動用 Jupyter Notebook 匯出特定名單（如「需挽回的前 VIP 客戶」）使用。

## 4. UI 視覺規範與套件特性
專案的視覺高度對齊 TailAdmin 深色主題，請嚴格遵守以下前端規範：

*   **字體與配色**：已在 `.streamlit/config.toml` 中寫死全域配置（Primary Color: `#465fff`, Background: `#101828`）。圖表與 UI 元件請盡量沿用這些色碼。
*   **Material Symbols**：全站放棄使用傳統的 Emoji（表格內的狀態燈號除外），全面改用 Google Material Icons。語法為 `st.markdown(":material/account_balance: 標題")`。
*   **進階圖表 (`st.plotly_chart`)**：
    *   專案**不使用** `st.line_chart` 或 `st.bar_chart`。
    *   為了呈現企業級儀表板質感，我們全面使用 Plotly (`plotly.graph_objects` & `plotly.express`)。
    *   **折線圖必備參數**：請設定 `shape='spline'` 讓折線平滑，並加上 `fill='tozeroy'` 創造漸層面積感。同時務必設定 `hovermode="x unified"`。
    *   **圓餅圖必備參數**：關閉 Legend (`showlegend=False`)，將資訊改以 `textinfo='percent+label'` 放在圓餅內部，且 `hole` 應設定為 `0.5` 呈現甜甜圈圖外觀。
*   **互動表單**：所有如「薪資試算」、「新增收支」等原本佔用版面的大表單，皆已升級為 Streamlit 1.34+ 提供的 `@st.dialog` 彈出式對話框，藉此保持頁面版面的整潔。
*   **排行榜特例**：`views/dashboard.py` 中保留了全站唯一一段 `unsafe_allow_html=True` 的手刻 CSS，這是為了渲染具有金銀銅牌特殊視覺的「本月投注排行榜」，請勿將其替換為原生元件。
