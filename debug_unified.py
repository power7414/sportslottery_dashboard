import pandas as pd
import sqlite3

conn = sqlite3.connect('processed/betting_data.db')
dim = pd.read_sql("SELECT * FROM dim_member", conn, dtype={'phone': str})
fact_bets = pd.read_sql("SELECT member_id as bet_member_id, date, bet_amount FROM fact_daily_bets", conn)

fact_summary = fact_bets.groupby('bet_member_id').agg(
    first_bet_date=('date', 'min')
).reset_index()

mapping = {}
for _, row in dim.iterrows():
    b_id = str(row['backend_id']).strip() if pd.notna(row['backend_id']) else ''
    m_id = str(row['member_id']).strip() if pd.notna(row['member_id']) else ''
    c = row['channel'] if pd.notna(row['channel']) and str(row['channel']).strip() != '' else '未分類'
    jd = row['join_date']
    if b_id: mapping[b_id] = (c, jd)
    if m_id: mapping[m_id] = (c, jd)

unified_members = []
first_bet_dict = dict(zip(fact_summary['bet_member_id'], fact_summary['first_bet_date']))

for _, row in dim.iterrows():
    b_id = str(row['backend_id']).strip() if pd.notna(row['backend_id']) else ''
    m_id = str(row['member_id']).strip() if pd.notna(row['member_id']) else ''
    c = row['channel'] if pd.notna(row['channel']) and str(row['channel']).strip() != '' else '未分類'
    jd = row['join_date']
    uid = m_id if m_id else b_id
    
    if pd.isna(jd) or str(jd).strip() in ('', 'None', 'nan'):
        jd = first_bet_dict.get(m_id) or first_bet_dict.get(b_id)
        
    unified_members.append({'uid': uid, 'channel': c, 'join_date': jd})

df_unified = pd.DataFrame(unified_members)

df_unified['parsed_date'] = pd.to_datetime(df_unified['join_date'], errors='coerce')
failed = df_unified[df_unified['parsed_date'].isna()]
print("Failed parsing:")
print(failed[['channel', 'join_date']].head(20))
print("Total failed:", len(failed))
