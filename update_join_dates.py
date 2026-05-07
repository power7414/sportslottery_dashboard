import pandas as pd
import sqlite3
from pathlib import Path

data_dir = Path('data')
conn = sqlite3.connect('processed/betting_data.db')
cursor = conn.cursor()

# Get all members with missing join_date
cursor.execute("SELECT backend_id, member_id FROM dim_member WHERE join_date IS NULL OR join_date = '' OR join_date = 'None'")
missing_members = cursor.fetchall()

missing_bids = set(r[0] for r in missing_members if r[0])
missing_mids = set(r[1] for r in missing_members if r[1])

print(f"Missing dates for {len(missing_bids) + len(missing_mids)} identifiers.")

updates_found = {}

for file_path in data_dir.glob('*.xlsx'):
    if file_path.name.startswith('~$'): continue
    print(f"Reading {file_path.name}...")
    try:
        xl = pd.ExcelFile(file_path)
    except Exception as e:
        continue
        
    daily_sheets = [s for s in xl.sheet_names if s.strip().isdigit()]
    for sheet_name in daily_sheets:
        try:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
        except Exception as e:
            continue
            
        for _, row in df.iterrows():
            if pd.isna(row[1]) or pd.isna(row[3]):
                continue
            
            m_id = str(row[1]).strip()
            
            if m_id in missing_bids or m_id in missing_mids:
                if m_id not in updates_found:
                    # Convert join_date
                    if isinstance(row[3], pd.Timestamp) or hasattr(row[3], 'strftime'):
                        try:
                            date_str = row[3].strftime('%Y-%m-%d')
                            updates_found[m_id] = date_str
                        except:
                            pass
                    else:
                        date_str = str(row[3]).strip()[:10]
                        if len(date_str) == 10 and date_str.count('-') == 2:
                            updates_found[m_id] = date_str

print(f"Found {len(updates_found)} join dates!")

# Update DB
for m_id, date_str in updates_found.items():
    cursor.execute("""
        UPDATE dim_member 
        SET join_date = ? 
        WHERE (backend_id = ? OR member_id = ?) AND (join_date IS NULL OR join_date = '' OR join_date = 'None')
    """, (date_str, m_id, m_id))

conn.commit()
conn.close()
print("Done updating!")
