import sqlite3
import pandas as pd

conn = sqlite3.connect('processed/betting_data.db')
df = pd.read_sql('SELECT * FROM dim_member', conn)

def fix_phone(x):
    if pd.isna(x) or str(x).strip() in ('', 'None', 'nan'):
        return None
    s = str(x).strip()
    if s.endswith('.0'):
        s = s[:-2]
    # 如果長度是 9 碼且是 9 開頭，前面補 0 (例如 919913268 -> 0919913268)
    if len(s) == 9 and s.startswith('9'):
        s = '0' + s
    return s

df['phone'] = df['phone'].apply(fix_phone)

cur = conn.cursor()
cur.execute('DROP TABLE dim_member')
cur.execute('''
    CREATE TABLE dim_member (
        backend_id TEXT,
        member_id TEXT,
        name TEXT,
        phone TEXT,
        join_date TEXT,
        channel TEXT
    )
''')
df.to_sql('dim_member', conn, if_exists='append', index=False)
conn.commit()
conn.close()
print("Phones fixed!")
