#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依照管道來源計算每月投注額
根據 member 資料夾中的 CSV 檔案，將會員分類到不同管道，並計算各管道的月度投注額
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Tuple
import calendar
from tqdm import tqdm
import time


def load_member_channel_mapping(member_dir: str = "member") -> Tuple[Dict[str, str], Dict[str, int]]:
    """
    載入會員管道對應表

    Args:
        member_dir: 會員資料所在目錄

    Returns:
        (會員對應字典, 各管道會員數統計)
        會員對應字典格式: {'後台資料': '管道來源'}
    """
    member_path = Path(member_dir)

    if not member_path.exists():
        print(f"❌ 錯誤：找不到資料夾 {member_dir}")
        return {}, {}

    csv_files = list(member_path.glob('*.csv'))

    if not csv_files:
        print(f"❌ 錯誤：{member_dir} 中沒有找到 CSV 檔案")
        return {}, {}

    member_channel_map = {}
    channel_member_count = {}

    print("=" * 80)
    print("📋 載入會員管道資料")
    print("=" * 80)

    for csv_file in csv_files:
        # 提取管道名稱
        filename = csv_file.name
        channel_name = filename.replace('.csv', '').replace(' - 會員資料表', '').replace(' 推薦', '').strip()

        print(f"\n處理: {filename}")
        print(f"  管道名稱: {channel_name}")

        try:
            # 嘗試不同編碼讀取
            df = None
            for encoding in ['utf-8', 'utf-8-sig', 'big5', 'cp950', 'latin1']:
                try:
                    df = pd.read_csv(csv_file, encoding=encoding)
                    break
                except (UnicodeDecodeError, Exception):
                    continue

            if df is None:
                print(f"  ⚠️ 無法讀取檔案")
                continue

            # 檢查是否有「後台資料」欄位
            if '後台資料' not in df.columns:
                print(f"  ⚠️ 找不到「後台資料」欄位，跳過此檔案")
                continue

            # 建立對應關係（只處理有後台資料的會員）
            valid_members = df[df['後台資料'].notna()]['後台資料'].astype(str).str.strip()
            member_count = 0

            for member_id in valid_members:
                if member_id and member_id != 'nan':
                    # 如果會員已存在，記錄重複
                    if member_id in member_channel_map:
                        print(f"  ⚠️ 重複會員: {member_id} (原屬 {member_channel_map[member_id]}，現在也在 {channel_name})")
                    else:
                        member_channel_map[member_id] = channel_name
                        member_count += 1

            channel_member_count[channel_name] = member_count
            print(f"  ✅ 載入 {member_count} 位會員")

        except Exception as e:
            print(f"  ❌ 錯誤：{str(e)}")
            continue

    print("\n" + "=" * 80)
    print("📊 管道會員統計:")
    for channel, count in sorted(channel_member_count.items()):
        print(f"  {channel}: {count} 位會員")
    print(f"  總計: {len(member_channel_map)} 位會員")
    print("=" * 80)

    return member_channel_map, channel_member_count


def process_excel_file_by_channel(file_path: Path, member_channel_map: Dict[str, str]) -> Dict:
    """
    處理單一 Excel 檔案，並依管道分類投注額

    Args:
        file_path: Excel 檔案路徑
        member_channel_map: 會員管道對應字典

    Returns:
        包含各管道投注額的字典
    """
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
    try:
        xl = pd.ExcelFile(file_path, engine='openpyxl')
    except Exception as e:
        print(f"⚠️ 無法讀取 {file_path.name}: {str(e)}")
        return None

    # 初始化各管道的每日投注額
    channel_daily_data = {}

    # 處理每個數字工作表（每一天）
    for sheet_name in xl.sheet_names:
        if sheet_name.strip().isdigit():
            day = int(sheet_name.strip())
            if 1 <= day <= 31:
                df = pd.read_excel(xl, sheet_name, header=None)

                # 掃描該日的投注資料
                for i in range(len(df)):
                    # 欄位 [1] 是後台資料，欄位 [2] 是投注額
                    member_id = df.iloc[i, 1] if len(df.columns) > 1 else None
                    bet_amount = df.iloc[i, 2] if len(df.columns) > 2 else None

                    # 檢查資料有效性
                    if pd.notna(member_id) and pd.notna(bet_amount):
                        member_id = str(member_id).strip()

                        # 確認投注額是數字
                        try:
                            bet_amount = float(bet_amount)
                            if bet_amount <= 0:
                                continue
                        except (ValueError, TypeError):
                            continue

                        # 查詢該會員屬於哪個管道
                        channel = member_channel_map.get(member_id, "未分類")

                        # 初始化管道資料結構
                        if channel not in channel_daily_data:
                            channel_daily_data[channel] = {}

                        if day not in channel_daily_data[channel]:
                            channel_daily_data[channel][day] = 0

                        # 累加投注額
                        channel_daily_data[channel][day] += bet_amount

    return {
        'year': year,
        'month': month,
        'channel_daily': channel_daily_data
    }


def calculate_monthly_betting_by_channel(data_dir: str = "data", member_dir: str = "member") -> Dict:
    """
    主要計算函數：依管道來源計算每月投注額

    Args:
        data_dir: 投注資料目錄
        member_dir: 會員資料目錄

    Returns:
        各月份各管道的投注額統計
    """
    # 載入會員管道對應表
    member_channel_map, channel_member_count = load_member_channel_mapping(member_dir)

    if not member_channel_map:
        print("⚠️ 無法載入會員管道資料")
        return {}

    # 讀取投注資料
    data_path = Path(data_dir)
    excel_files = sorted(data_path.glob("*.xlsx"))

    if not excel_files:
        print(f"⚠️ 在 {data_dir} 資料夾中找不到 Excel 檔案")
        return {}

    print(f"\n📁 找到 {len(excel_files)} 個 Excel 檔案")
    all_data = {}

    # 處理每個檔案
    print("📊 開始讀取投注資料...")
    for file_path in tqdm(excel_files, desc="讀取", unit="檔", ncols=80):
        result = process_excel_file_by_channel(file_path, member_channel_map)
        if result:
            month_key = f"{result['year']}-{result['month']}"
            all_data[month_key] = result

    return all_data


def generate_report(all_data: Dict) -> None:
    """
    生成並列印報告

    Args:
        all_data: 各月份各管道的投注額統計
    """
    print("\n" + "=" * 80)
    print("📈 各管道每月投注額統計報告")
    print("=" * 80)

    # 收集所有出現過的管道
    all_channels = set()
    for month_data in all_data.values():
        all_channels.update(month_data['channel_daily'].keys())

    all_channels = sorted(all_channels)

    # 總計統計
    grand_total_by_channel = {channel: 0 for channel in all_channels}
    grand_total = 0

    for month_key in sorted(all_data.keys()):
        data = all_data[month_key]
        channel_daily = data['channel_daily']

        year, month = month_key.split('-')

        print(f"\n【{year}年{month}月】")
        print("-" * 80)

        month_total = 0
        channel_totals = {}

        # 計算各管道月總計
        for channel in all_channels:
            if channel in channel_daily:
                daily_amounts = channel_daily[channel].values()
                channel_total = sum(daily_amounts)
                channel_totals[channel] = channel_total
                month_total += channel_total
            else:
                channel_totals[channel] = 0

        # 顯示各管道投注額
        for channel in all_channels:
            amount = channel_totals[channel]
            percentage = (amount / month_total * 100) if month_total > 0 else 0
            print(f"  {channel:30s}: NT$ {amount:>12,.0f}  ({percentage:>5.1f}%)")
            grand_total_by_channel[channel] += amount

        print("-" * 80)
        print(f"  {'月總計':30s}: NT$ {month_total:>12,.0f}")
        grand_total += month_total

    # 總計摘要
    print("\n" + "=" * 80)
    print("📊 所有月份總計:")
    print("=" * 80)

    for channel in all_channels:
        amount = grand_total_by_channel[channel]
        percentage = (amount / grand_total * 100) if grand_total > 0 else 0
        print(f"  {channel:30s}: NT$ {amount:>12,.0f}  ({percentage:>5.1f}%)")

    print("=" * 80)
    print(f"  {'總計':30s}: NT$ {grand_total:>12,.0f}")
    print("=" * 80)


def export_to_excel(all_data: Dict, filename: str = "channel_betting_summary.xlsx") -> None:
    """
    匯出到 Excel

    Args:
        all_data: 各月份各管道的投注額統計
        filename: 輸出檔案名稱
    """
    print(f"\n💾 匯出結果到 {filename}...")

    # 收集所有管道
    all_channels = set()
    for month_data in all_data.values():
        all_channels.update(month_data['channel_daily'].keys())

    all_channels = sorted(all_channels)

    # 準備摘要資料
    summary_rows = []

    for month_key in sorted(all_data.keys()):
        data = all_data[month_key]
        channel_daily = data['channel_daily']

        row = {'年月': month_key}
        month_total = 0

        # 計算各管道月總計
        for channel in all_channels:
            if channel in channel_daily:
                channel_total = sum(channel_daily[channel].values())
                row[channel] = channel_total
                month_total += channel_total
            else:
                row[channel] = 0

        row['月總計'] = month_total
        summary_rows.append(row)

    # 寫入 Excel
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # 月份摘要表
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_excel(writer, sheet_name='月份摘要', index=False)

        # 每月明細（各管道每日投注額）
        for month_key in sorted(all_data.keys()):
            data = all_data[month_key]
            channel_daily = data['channel_daily']

            # 收集該月所有天數
            all_days = set()
            for daily_data in channel_daily.values():
                all_days.update(daily_data.keys())

            all_days = sorted(all_days)

            # 建立明細表
            detail_rows = []
            for day in all_days:
                row = {'日': day}
                for channel in all_channels:
                    if channel in channel_daily and day in channel_daily[channel]:
                        row[channel] = channel_daily[channel][day]
                    else:
                        row[channel] = 0

                row['日總計'] = sum(row[ch] for ch in all_channels if ch in row)
                detail_rows.append(row)

            # 工作表名稱（使用年月後4碼）
            sheet_name = month_key.replace('-', '')[-4:]
            df_detail = pd.DataFrame(detail_rows)
            df_detail.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"✅ 完成！結果已匯出至: {filename}")


def main():
    """主程式"""
    print("🚀 啟動運彩投注額結算系統（依管道來源）")
    start_time = time.time()

    # 計算所有資料
    all_data = calculate_monthly_betting_by_channel("data", "member")

    if not all_data:
        print("❌ 沒有找到有效的資料")
        return

    # 生成報告
    generate_report(all_data)

    # 匯出 Excel
    export_to_excel(all_data)

    elapsed = time.time() - start_time
    print(f"\n⏱️ 總處理時間: {elapsed:.1f} 秒")


if __name__ == "__main__":
    main()
