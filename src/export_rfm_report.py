import sqlite3
import pandas as pd
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'processed' / 'betting_data.db'
OUTPUT_PATH = BASE_DIR / 'reports' / 'rfm_raw_data_for_review.xlsx'

def generate_rfm_report():
    if not DB_PATH.exists():
        print("資料庫不存在，請先執行 init_database.py")
        return
        
    print("正在從資料庫讀取投注明細...")
    conn = sqlite3.connect(DB_PATH)
    
    # 讀取全部明細
    df = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])
    
    # 取得資料庫中最新的一天，作為計算 Recency 的基準點 (Today)
    latest_date = df['date'].max()
    print(f"資料庫最新日期為: {latest_date.strftime('%Y-%m-%d')}")
    
    # 開始計算每個會員的 RFM 指標
    print("正在計算 RFM 指標與行為數據...")
    rfm = df.groupby('member_id').agg(
        # R: 距今最後一次下注有幾天 (Recency)
        last_bet_date=('date', 'max'),
        # F: 總共下注了幾「天」 (Frequency)
        active_days=('date', 'nunique'),
        # M: 累積下注總額 (Monetary)
        total_bet_amount=('bet_amount', 'sum'),
        # 客單價：平均每日下注額
        avg_daily_bet=('bet_amount', 'mean'),
        # 波動度：每日下注額的標準差 (如果只有一天會是 NaN，補 0)
        bet_volatility=('bet_amount', 'std'),
        # 總共活躍過幾個「月」
        active_months=('date', lambda x: x.dt.to_period('M').nunique())
    ).reset_index()
    
    # 計算 Recency 天數
    rfm['days_since_last_bet'] = (latest_date - rfm['last_bet_date']).dt.days
    
    # 填補 NaN
    rfm['bet_volatility'] = rfm['bet_volatility'].fillna(0)
    
    # 重新排列欄位，方便閱讀
    rfm = rfm[[
        'member_id',
        'total_bet_amount',       # M
        'days_since_last_bet',    # R
        'active_days',            # F
        'active_months',
        'avg_daily_bet',          # 客單價
        'bet_volatility',         # 波動度
        'last_bet_date'
    ]]
    
    # 按照總投注額排序，方便您看出大戶的樣貌
    rfm = rfm.sort_values('total_bet_amount', ascending=False)
    
    # 輸出成 Excel
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    rfm.to_excel(OUTPUT_PATH, index=False)
    print(f"\n✅ 報告已成功產出：{OUTPUT_PATH}")
    print("\n💡 您可以打開這個 Excel 檔，觀察大戶跟流失客在:")
    print("   1. days_since_last_bet (超過幾天沒下注算流失？)")
    print("   2. active_days (每個月下注幾天算活躍？)")
    print("   3. total_bet_amount (累積多少錢算是 VIP？)")
    print("   的分佈狀況，我們再來制定標籤標準！")

if __name__ == "__main__":
    generate_rfm_report()
