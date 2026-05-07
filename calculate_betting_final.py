#!/usr/bin/env python3
"""最終優化版的月度投注額計算程式"""

import pandas as pd
from pathlib import Path
from typing import Dict
import calendar
from tqdm import tqdm
import time

def extract_betting_from_sheet(df: pd.DataFrame, is_day_one: bool = False) -> Dict:
    """從工作表提取投注資料 - 最簡化版本"""
    result = {
        'current': {'同意人數': 0, '同意投注額': 0, '不同意人數': 0, '不同意投注額': 0},
        'last_month': None
    }

    if is_day_one:
        result['last_month'] = {'同意人數': 0, '同意投注額': 0, '不同意人數': 0, '不同意投注額': 0}

    # 掃描DataFrame尋找投注資料
    for i in range(len(df)):
        for j in range(len(df.columns) - 2):
            cell = df.iloc[i, j]

            if pd.notna(cell) and isinstance(cell, str):
                # 檢查是否為上月區段
                is_last_month = (is_day_one and i < 20 and
                               any('上月' in str(df.iloc[k, :].values) for k in range(max(0, i-5), min(len(df), i+1))))

                if '同意部份個人資料可揭露' in cell or '不同意個人資料揭露' in cell:
                    people = df.iloc[i, j + 1]
                    amount = df.iloc[i, j + 2]

                    if pd.notna(amount) and isinstance(amount, (int, float)) and amount >= 0:
                        target = result['last_month'] if is_last_month else result['current']

                        if '同意部份' in cell:
                            target['同意人數'] = int(people) if pd.notna(people) else 0
                            target['同意投注額'] += float(amount)
                        else:
                            target['不同意人數'] = int(people) if pd.notna(people) else 0
                            target['不同意投注額'] += float(amount)

    return result

def process_excel_file(file_path: Path) -> Dict:
    """處理單一Excel檔案"""
    # 解析檔名
    parts = file_path.name.split('-')
    if len(parts) < 2:
        return None

    year_month = parts[-1].replace('.xlsx', '')
    if len(year_month) != 4:
        return None

    year = "20" + year_month[:2]
    month = year_month[2:]

    # 讀取檔案
    xl = pd.ExcelFile(file_path)
    daily_data = {}
    last_month_data = None

    # 處理每個數字工作表
    for sheet_name in xl.sheet_names:
        if sheet_name.strip().isdigit():
            day = int(sheet_name.strip())
            if 1 <= day <= 31:
                df = pd.read_excel(xl, sheet_name, header=None)
                data = extract_betting_from_sheet(df, is_day_one=(day == 1))

                # 當月資料
                current = data['current']
                if current['同意投注額'] + current['不同意投注額'] > 0:
                    daily_data[day] = current

                # 上月最後一天資料
                if day == 1 and data['last_month']:
                    last_month = data['last_month']
                    if last_month['同意投注額'] + last_month['不同意投注額'] > 0:
                        last_month_data = last_month

    return {
        'year': year,
        'month': month,
        'daily': daily_data,
        'last_month_final': last_month_data
    }

def calculate_monthly_betting(data_dir: str = "data") -> Dict:
    """主要計算函數"""
    data_path = Path(data_dir)
    excel_files = sorted(data_path.glob("*.xlsx"))

    if not excel_files:
        print("⚠️ 在 data 資料夾中找不到 Excel 檔案")
        return {}

    print(f"📁 找到 {len(excel_files)} 個 Excel 檔案")
    all_data = {}

    # 處理每個檔案
    print("📊 開始讀取檔案...")
    for file_path in tqdm(excel_files, desc="讀取", unit="檔", ncols=80):
        result = process_excel_file(file_path)
        if result:
            month_key = f"{result['year']}-{result['month']}"
            all_data[month_key] = result

    # 補充跨月資料
    print("🔄 處理跨月資料...")
    time.sleep(0.1)  # 讓進度條完整顯示

    for month_key in sorted(all_data.keys()):
        year, month = month_key.split('-')

        # 計算下個月的key
        next_month = int(month) + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year = str(int(year) + 1)

        next_key = f"{next_year}-{str(next_month).zfill(2)}"

        # 補充月底資料
        if next_key in all_data and all_data[next_key]['last_month_final']:
            days_in_month = calendar.monthrange(int(year), int(month))[1]
            all_data[month_key]['daily'][days_in_month] = all_data[next_key]['last_month_final']

    return all_data

def generate_report(all_data: Dict) -> None:
    """生成並列印報告"""
    print("\n" + "=" * 80)
    print("📈 每月投注額統計報告")
    print("=" * 80)

    total_all = total_agreed = total_disagreed = 0
    warnings = []

    for month_key in sorted(all_data.keys()):
        data = all_data[month_key]
        daily = data['daily']

        if not daily:
            continue

        # 計算統計數據
        agreed_total = sum(d['同意投注額'] for d in daily.values())
        disagreed_total = sum(d['不同意投注額'] for d in daily.values())
        month_total = agreed_total + disagreed_total

        first_day = min(daily.keys())
        last_day = max(daily.keys())
        start_people = daily[first_day]['同意人數'] + daily[first_day]['不同意人數']
        end_people = daily[last_day]['同意人數'] + daily[last_day]['不同意人數']

        year, month = month_key.split('-')

        # 🔍 除錯邏輯：檢查該月天數是否完整
        expected_days = calendar.monthrange(int(year), int(month))[1]
        actual_days = len(daily)
        is_incomplete = actual_days < expected_days

        # 檢查是否為當前月份（可能還在進行中）
        from datetime import datetime
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        is_current_month = (int(year) == current_year and int(month) == current_month)

        # 如果不是當前月份且天數不足，記錄警告
        if is_incomplete and not is_current_month:
            warnings.append({
                'month': f"{year}年{month}月",
                'expected': expected_days,
                'actual': actual_days,
                'missing': expected_days - actual_days
            })

        print(f"\n【{year}年{month}月】")
        print(f"  📅 有資料天數: {actual_days}天", end="")

        # 顯示天數狀態
        if is_incomplete:
            if is_current_month:
                print(f" (進行中，預期{expected_days}天)")
            else:
                print(f" ⚠️ (不完整！預期{expected_days}天，缺少{expected_days - actual_days}天)")
        else:
            print(f" ✅ (完整，共{expected_days}天)")

        print(f"  👥 月底會員: {end_people}人 (成長 {end_people - start_people:+d}人)")
        print(f"     ✅ 同意: {daily[last_day]['同意人數']}人")
        print(f"     ❌ 不同意: {daily[last_day]['不同意人數']}人")
        print(f"  💰 同意投注額: NT$ {agreed_total:,.0f}")
        print(f"  💰 不同意投注額: NT$ {disagreed_total:,.0f}")
        print(f"  💵 月總計: NT$ {month_total:,.0f}")

        total_all += month_total
        total_agreed += agreed_total
        total_disagreed += disagreed_total

    print("\n" + "-" * 80)
    print("📊 總計摘要:")
    print(f"  ✅ 同意會員總投注額: NT$ {total_agreed:,.0f}")
    print(f"  ❌ 不同意會員總投注額: NT$ {total_disagreed:,.0f}")
    print(f"  💎 所有月份總計: NT$ {total_all:,.0f}")

    # 顯示資料完整性警告
    if warnings:
        print("\n" + "⚠️" * 20 + " 資料完整性警告 " + "⚠️" * 20)
        print("發現以下月份的資料不完整：")
        for warning in warnings:
            print(f"  🔍 {warning['month']}: 預期{warning['expected']}天，實際{warning['actual']}天，缺少{warning['missing']}天")
        print("建議檢查這些月份的 Excel 檔案是否有遺失的日期工作表。")
        print("⚠️" * 60)
    else:
        print("\n✅ 所有月份資料完整性檢查通過！")

    print("=" * 80)

def export_to_excel(all_data: Dict, filename: str = "monthly_betting_summary.xlsx") -> None:
    """匯出到Excel"""
    print(f"\n💾 匯出結果到 {filename}...")

    # 準備摘要資料
    summary_rows = []
    for month_key in sorted(all_data.keys()):
        data = all_data[month_key]
        daily = data['daily']

        if not daily:
            continue

        agreed_total = sum(d['同意投注額'] for d in daily.values())
        disagreed_total = sum(d['不同意投注額'] for d in daily.values())

        first_day = min(daily.keys())
        last_day = max(daily.keys())
        start_people = daily[first_day]['同意人數'] + daily[first_day]['不同意人數']
        end_people = daily[last_day]['同意人數'] + daily[last_day]['不同意人數']

        # 檢查資料完整性
        year, month = month_key.split('-')
        expected_days = calendar.monthrange(int(year), int(month))[1]
        actual_days = len(daily)

        # 檢查是否為當前月份
        from datetime import datetime
        current_date = datetime.now()
        is_current_month = (int(year) == current_date.year and int(month) == current_date.month)

        # 判斷完整性狀態
        if actual_days == expected_days:
            completeness = "完整"
        elif is_current_month:
            completeness = "進行中"
        else:
            completeness = f"不完整(缺{expected_days - actual_days}天)"

        summary_rows.append({
            '年月': month_key,
            '有資料天數': actual_days,
            '預期天數': expected_days,
            '資料完整性': completeness,
            '月底會員人數': end_people,
            '月底同意人數': daily[last_day]['同意人數'],
            '月底不同意人數': daily[last_day]['不同意人數'],
            '該月會員成長數': end_people - start_people,
            '同意總投注額': agreed_total,
            '不同意總投注額': disagreed_total,
            '月投注總額': agreed_total + disagreed_total
        })

    # 寫入Excel
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # 摘要表
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name='月份摘要', index=False)

        # 每月明細
        for month_key in sorted(all_data.keys()):
            data = all_data[month_key]
            daily = data['daily']

            if not daily:
                continue

            daily_rows = []
            for day in sorted(daily.keys()):
                d = daily[day]
                daily_rows.append({
                    '日': day,
                    '同意人數': d['同意人數'],
                    '同意投注額': d['同意投注額'],
                    '不同意人數': d['不同意人數'],
                    '不同意投注額': d['不同意投注額'],
                    '日總投注額': d['同意投注額'] + d['不同意投注額']
                })

            sheet_name = month_key.replace('-', '')[-4:]
            pd.DataFrame(daily_rows).to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"✅ 完成！結果已匯出至: {filename}")

def main():
    """主程式"""
    print("🚀 啟動運彩投注額結算系統")
    start_time = time.time()

    # 計算所有資料
    all_data = calculate_monthly_betting("data")

    if not all_data:
        print("❌ 沒有找到有效的資料")
        return

    # 生成報告
    generate_report(all_data)

    # 匯出Excel
    export_to_excel(all_data)

    elapsed = time.time() - start_time
    print(f"\n⏱️ 總處理時間: {elapsed:.1f} 秒")

if __name__ == "__main__":
    main()