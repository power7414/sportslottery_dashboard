# TODO.md — 當前目標執行步驟

## Phase 1: 專案基礎文件補齊
- [x] 建立專案核心文件 `AGENT.md`
- [x] 建立專案里程碑文件 `PROGRESS.md`
- [x] 建立當前執行清單 `TODO.md`
- [x] 更新修正 `README.md` 的錯誤連結與補充說明

## Phase 2: 後續系統健全度與優化
- [ ] 為 `betting_data.db` 的 `fact_daily_bets` (member_id, date) 與 `fact_daily_summary` (date) 建立 Index 以優化大數據載入效能
- [ ] 在 `views/finance.py` 的財務流水帳與 `views/members_crm.py` 的名單中加入「匯出 CSV」功能
