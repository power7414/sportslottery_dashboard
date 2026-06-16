i４mport sqlite3
import pandas as pd
from pathlib import Path
import sys
import re

BASE_DIR      = Path(__file__).resolve().parent.parent
DATA_DIR      = BASE_DIR / 'data'
PROCESSED_DIR = BASE_DIR / 'processed'
DB_PATH       = PROCESSED_DIR / 'betting_data.db'

from src.calculate_betting_final import calculate_monthly_betting

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except OSError:
        pass


# ────────────────────────────────────────────────────────────────
# 工具函式
# ────────────────────────────────────────────────────────────────
def safe_float(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(str(value).replace(',', '').replace('$', '').strip() or 0)
    except:
        return 0.0


def extract_year_month(filename: str):
    match = re.search(r'-(\d{4})\.xlsx', filename)
    if not match:
        return None, None
    ym = match.group(1)
    return "20" + ym[:2], ym[2:]


# ────────────────────────────────────────────────────────────────
# 初始化資料庫 & 建表
# ────────────────────────────────────────────────────────────────
def init_database() -> sqlite3.Connection:
    PROCESSED_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    cur  = conn.cursor()

    # 表一：個別會員每日投注明細
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fact_daily_bets (
            date       TEXT,
            member_id  TEXT,
            bet_amount REAL,
            PRIMARY KEY (date, member_id)
        )
    ''')

    # 表二：每日彙整（來自已驗證的 calculate_betting_final 邏輯）
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fact_daily_summary (
            date              TEXT PRIMARY KEY,
            agreed_amount     REAL,
            agreed_people     INTEGER,
            disagreed_amount  REAL,
            disagreed_people  INTEGER
        )
    ''')

    conn.commit()
    return conn


# ────────────────────────────────────────────────────────────────
# 寫入個別會員明細（fact_daily_bets）
# ────────────────────────────────────────────────────────────────
def insert_member_bets(file_path: Path, conn: sqlite3.Connection):
    year, month = extract_year_month(file_path.name)
    if not year:
        return

    xl           = pd.ExcelFile(file_path)
    daily_sheets = [s for s in xl.sheet_names if s.strip().isdigit()]
    records      = []

    for sheet_name in daily_sheets:
        day      = int(sheet_name.strip())
        date_str = f"{year}-{month}-{day:02d}"
        df       = pd.read_excel(xl, sheet_name=sheet_name, header=None)

        for _, row in df.iterrows():
            if pd.isna(row[1]):
                continue
            member_id = str(row[1]).strip()
            if not member_id or member_id in ['nan', '會員代號', '']:
                continue
            amount = safe_float(row[2])
            if amount > 0:
                records.append((date_str, member_id, amount))

    cur = conn.cursor()
    cur.execute(f"DELETE FROM fact_daily_bets WHERE date LIKE '{year}-{month}-%'")
    cur.executemany(
        "INSERT OR REPLACE INTO fact_daily_bets (date, member_id, bet_amount) VALUES (?,?,?)",
        records,
    )
    conn.commit()
    safe_print(f"  ✅ {file_path.name} → 會員明細 {len(records)} 筆")


# ────────────────────────────────────────────────────────────────
# 寫入每日彙整（fact_daily_summary）
# ── 完全沿用 calculate_betting_final 的跨月補充邏輯，確保數字正確 ──
# ────────────────────────────────────────────────────────────────
def build_daily_summary(conn: sqlite3.Connection):
    safe_print("\n🔄 使用 calculate_betting_final 邏輯重建每日彙整表...")

    # 呼叫已驗證的計算邏輯（含跨月補充）
    all_data = calculate_monthly_betting(str(DATA_DIR))

    records = []
    for month_key, data in all_data.items():
        year, month = month_key.split('-')
        for day, d in data['daily'].items():
            date_str = f"{year}-{month}-{day:02d}"
            records.append((
                date_str,
                d['同意投注額'],
                d['同意人數'],
                d['不同意投注額'],
                d['不同意人數'],
            ))

    cur = conn.cursor()
    cur.execute("DELETE FROM fact_daily_summary")
    cur.executemany(
        """INSERT OR REPLACE INTO fact_daily_summary
           (date, agreed_amount, agreed_people, disagreed_amount, disagreed_people)
           VALUES (?,?,?,?,?)""",
        records,
    )
    conn.commit()
    safe_print(f"  ✅ 共寫入 {len(records)} 天的彙整資料\n")


def update_specific_files(file_paths: list):
    """只針對有變動的檔案進行精準增量更新"""
    if not file_paths:
        return
        
    safe_print(f"\n🔄 發現 {len(file_paths)} 個新檔案，開始極速增量更新...")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    
    for fp in file_paths:
        fp_path = Path(fp)
        # 1. 增量更新個人明細
        insert_member_bets(fp_path, conn)
        
    # 2. 重新執行全域的每日彙整重建，確保「跨月補點」數據完全正確
    build_daily_summary(conn)
    
    conn.close()
    safe_print("✅ 增量更新完成！\n")


# ────────────────────────────────────────────────────────────────
# 主程式
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import glob

    safe_print("=== 🚀 開始建立 / 更新資料庫 ===\n")

    conn = init_database()
    
    # 僅清空並重新建立投注相關資料表，防止誤刪其他（如財務、會員主檔）資料表
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS fact_daily_bets;")
    cur.execute("DROP TABLE IF EXISTS fact_daily_summary;")
    conn.commit()
    
    # 重新建立投注相關資料表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fact_daily_bets (
            date       TEXT,
            member_id  TEXT,
            bet_amount REAL,
            PRIMARY KEY (date, member_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fact_daily_summary (
            date              TEXT PRIMARY KEY,
            agreed_amount     REAL,
            agreed_people     INTEGER,
            disagreed_amount  REAL,
            disagreed_people  INTEGER
        )
    ''')
    conn.commit()

    # Step 1：寫入個別會員明細
    safe_print("📋 Step 1：寫入個別會員投注明細")
    for fp in sorted(glob.glob(str(DATA_DIR / '*.xlsx'))):
        safe_print(f"  📄 {Path(fp).name}")
        insert_member_bets(Path(fp), conn)

    # Step 2：用已驗證邏輯寫入每日彙整（含跨月補充，數字與原邏輯一致）
    safe_print("\n📊 Step 2：重建每日彙整表（同意 + 不同意第三人）")
    build_daily_summary(conn)

    conn.close()
    safe_print(f"=== ✅ 完成！資料庫位於：{DB_PATH} ===")
