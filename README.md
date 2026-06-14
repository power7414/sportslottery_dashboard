# 運彩投注額結算系統 (Business Intelligence Dashboard)

這是一個為台灣運彩經銷商量身打造的**商業智能分析儀表板 (BI Dashboard)**。
系統能自動化處理運彩後台匯出的龐大 Excel 數據，並整合行銷管道追蹤、會員行為分析、以及內部財務收支，提供即時、互動式的商業洞察。

## 🌟 核心功能

1. **極速自動同步**
   - 透過 Dropbox API 進行真正的「精準增量更新」。
   - 新檔案下載後，透過 SQLite 的 UPSERT 機制，只需 5 秒即可完成資料庫更新。
2. **多維度商業分析**
   - **首頁 & 01_整體投注**：即時掌握 DAU (日活躍)、WAU、MAU 及營收走勢。
   - **02_會員資料與管道**：評估行銷管道 (如盈吉多籃球、小凱等) 帶來的實際業績 (ROI)，並抓出「未標記」的野生大戶。
   - **03_投注行為分析**：偵測流失客群、判定玩家性格 (高頻鐵粉、衝動型)，並透過賽事月份自動貼標 (純NBA / 雙棲玩家)。
   - **04_財務紀錄**：內建類似 Excel 的互動式編輯表單，收支紀錄直接寫入資料庫，自動結算營運淨利與現金流。

## 🛠️ 安裝與啟動

### 1. 系統環境需求
- Python 3.10+
- `.env` 檔案配置 (請參考 `.env.example`，需填寫 Dropbox Token 等資訊)

### 2. 建立並啟動虛擬環境（建議）

```bash
# 建立虛擬環境（只需執行一次）
python3 -m venv venv

# 啟動虛擬環境（每次開發前執行）
source venv/bin/activate
```

> ⚠️ macOS / Linux 請用 `source venv/bin/activate`；Windows 請用 `venv\Scripts\activate`。
>
> 啟動成功後，terminal 提示符前面會出現 `(venv)` 字樣。若要離開環境，執行 `deactivate`。

### 3. 安裝相依套件
```bash
pip install streamlit pandas plotly dropbox openpyxl
```

### 3. 啟動 Dashboard
```bash
python3 -m streamlit run app.py
```
> ⚠️ 請勿使用 `python3 streamlit run app.py`（錯誤）或單獨的 `streamlit run app.py`（若 streamlit 不在 PATH 中會失敗）。
>
> 系統啟動時，會自動檢查 Dropbox 雲端是否有新的 Excel 報表，若有將會自動執行增量更新。

## 📂 資料夾結構說明

*   `app.py`：Dashboard 首頁與入口點。
*   `pages/`：儀表板的核心四個分析模組。
*   `src/`：後端邏輯層，包含 `dropbox_sync.py` 與 `init_database.py` (增量更新引擎)。
*   `processed/`：存放系統核心的 SQLite 資料庫 `betting_data.db`。
*   `data/` & `member/`：原始 Excel 與 CSV 檔案備份。

> **💡 開發架構與進階資訊：**
> 請參閱 [DEVELOPER_GUIDE.md](file:///Users/pkwu/Documents/運彩投注額結算/DEVELOPER_GUIDE.md) 以了解更詳細的模組設計、AI 開發準則與資料庫架構。

## 🤖 AI 協同開發規範

本專案引進以下三核心文件以引導 AI 進行精準開發：
*   [AGENT.md](file:///Users/pkwu/Documents/運彩投注額結算/AGENT.md)：共同頻率確認文件，記錄本專案的架構共識、UI 風格、核心雷區與業務邏輯。
*   [PROGRESS.md](file:///Users/pkwu/Documents/運彩投注額結算/PROGRESS.md)：專案開發里程碑，追蹤已驗證之功能與未來規劃。
*   [TODO.md](file:///Users/pkwu/Documents/運彩投注額結算/TODO.md)：當前開發目標與具體執行清單。