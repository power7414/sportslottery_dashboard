import streamlit as st
import pandas as pd
from pathlib import Path
import sqlite3
import numpy as np

def render_behavior_analysis():

    DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"
    if not DB_PATH.exists():
        st.warning("找不到資料庫，請先執行資料同步！")
        st.stop()

    @st.cache_data
    def load_all_data():
        conn = sqlite3.connect(DB_PATH, timeout=30)
        df = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
        conn.close()
        df['date'] = pd.to_datetime(df['date'])
        return df

    df_raw = load_all_data()
    latest_date = df_raw['date'].max()

    # =====================================================================
    # 核心計算區 (Data Processing)
    # =====================================================================

    # ── 1. 基礎標籤與運算 (全域) ──
    df_raw['month_num'] = df_raw['date'].dt.month
    nba_months = [10, 11, 12, 1, 2, 3, 4, 5, 6]
    mlb_months = [7, 8, 9]

    seasonality = df_raw.groupby('member_id')['month_num'].apply(set).reset_index()
    def get_season_tag(months_set):
        has_nba = any(m in nba_months for m in months_set)
        has_mlb = any(m in mlb_months for m in months_set)
        if has_nba and has_mlb: return "雙棲"
        elif has_mlb: return "純 MLB"
        elif has_nba: return "純 NBA"
        return "未知"

    seasonality['賽事偏好'] = seasonality['month_num'].apply(get_season_tag)
    season_dict = dict(zip(seasonality['member_id'], seasonality['賽事偏好']))

    # ── 2. 當前狀態與性格計算 (Right Now!) ──
    df_raw['ym'] = df_raw['date'].dt.to_period('M')
    monthly_stats = df_raw.groupby(['ym', 'member_id'])['bet_amount'].sum().reset_index()

    t_30 = latest_date - pd.Timedelta(days=30)
    df_last30 = df_raw[df_raw['date'] > t_30]
    last30_bet = df_last30.groupby('member_id')['bet_amount'].sum().to_dict()

    member_stats = df_raw.groupby('member_id').agg(
        last_date=('date', 'max'),
        total_active_days=('date', 'nunique'),
        std_daily_bet=('bet_amount', 'std'),
        total_months=('ym', 'nunique'),
        historical_total_bet=('bet_amount', 'sum')
    ).reset_index()

    max_monthly = monthly_stats.groupby('member_id')['bet_amount'].max().to_dict()
    current_month_num = latest_date.month

    def get_current_profile(row):
        m_id = row['member_id']
        days_since = (latest_date - row['last_date']).days
        m_last30_bet = last30_bet.get(m_id, 0)
        max_bet = max_monthly.get(m_id, 0)
        season_tag = season_dict.get(m_id, "")

        # 當前狀態
        if days_since <= 30:
            status = "🟢 活躍中"
            if m_last30_bet >= 40000: value = "⭐ VIP"
            elif m_last30_bet >= 12000: value = "🔥 主力"
            else: value = "👤 一般"
        else:
            is_sleeping = False
            if (current_month_num in mlb_months and 'NBA' in season_tag) or \
               (current_month_num in nba_months and 'MLB' in season_tag):
                is_sleeping = True

            if is_sleeping:
                status = "⚪ 沉睡中 (休賽季)"
            else:
                status = "🔴 已流失"

            if max_bet >= 40000: value = "⭐ 前 VIP"
            elif max_bet >= 12000: value = "🔥 前主力"
            else: value = "👤 前一般"

        # 頻率
        days_per_month = row['total_active_days'] / row['total_months']
        if days_per_month >= 12: freq_tag = "高頻玩家"
        elif days_per_month <= 4: freq_tag = "偶發玩家"
        else: freq_tag = "穩健玩家"

        # 波動度
        std = row['std_daily_bet'] if pd.notna(row['std_daily_bet']) else 0
        if std > 20000: vol_tag = "衝動大戶 (高波動)"
        elif std < 5000: vol_tag = "規律下注 (低波動)"
        else: vol_tag = "一般波動"

        return pd.Series([status, value, freq_tag, vol_tag, m_last30_bet, days_since])

    member_stats[['當前狀態', '近期/歷史價值', '下注頻率', '下注波動度', '近30天總投注', '距今天數']] = member_stats.apply(get_current_profile, axis=1)
    member_stats['賽事偏好'] = member_stats['member_id'].map(season_dict)

    # ── 3. 歷史月度趨勢運算 (圖表用) ──
    first_month_dict = df_raw.groupby('member_id')['ym'].min().to_dict()
    all_yms = pd.period_range(df_raw['ym'].min(), df_raw['ym'].max(), freq='M')
    trend_data = []

    for ym in all_yms:
        m_num = ym.month
        eligible = [m for m, fm in first_month_dict.items() if fm <= ym]

        curr_m_data = monthly_stats[monthly_stats['ym'] == ym]
        curr_active = set(curr_m_data['member_id'])

        vip_c = len(curr_m_data[curr_m_data['bet_amount'] >= 40000])
        main_c = len(curr_m_data[(curr_m_data['bet_amount'] >= 12000) & (curr_m_data['bet_amount'] < 40000)])
        general_c = len(curr_active) - vip_c - main_c

        sleep_c = 0
        churn_c = 0
        for m in eligible:
            if m not in curr_active:
                tag = season_dict.get(m, '')
                if (m_num in mlb_months and 'NBA' in tag) or (m_num in nba_months and 'MLB' in tag):
                    sleep_c += 1
                else:
                    churn_c += 1

        trend_data.append({
            'ym_str': str(ym),
            '活躍人數': len(curr_active),
            '沉睡人數': sleep_c,
            '累積流失': churn_c,
            'VIP大戶': vip_c,
            '主力客': main_c,
            '一般客': general_c
        })
    
    df_trend = pd.DataFrame(trend_data)

    # =====================================================================
    # UI 呈現區 (Streamlit UI)
    # =====================================================================

    st.divider()

    # ── 區塊一：當前狀態 KPI ──
    with st.container(border=True):
        st.markdown("##### 🚀 :material/health_and_safety: 戰情中心：當前健康度")
        st.caption("自動追蹤 30 天內的活躍與流失趨勢，精準掌握誰該救、誰該放。")

        kc1, kc2, kc3, kc4 = st.columns(4)
        active_count = len(member_stats[member_stats['當前狀態'] == '活躍中'])
        vip_count    = len(member_stats[member_stats['近期/歷史價值'] == 'VIP'])
        churn_count  = len(member_stats[(member_stats['當前狀態'] == '已流失') & (member_stats['近期/歷史價值'].isin(['前 VIP', '前主力']))])
        sleep_count  = len(member_stats[member_stats['當前狀態'] == '沉睡中 (休賽季)'])

        with kc1:
            st.metric("30天活躍人數", f"{active_count} 人", help="過去 30 天內有投注紀錄的會員")
        with kc2:
            st.metric("當前 VIP 人數", f"{vip_count} 人", help="30天內投注 > 4 萬者")
        with kc3:
            st.metric("高價值流失中", f"{churn_count} 人", delta="需儘速挽回", delta_color="inverse")
        with kc4:
            st.metric("休眠期會員", f"{sleep_count} 人", help="對應目前的非主流賽季")

    st.write("")

    # ── 區塊二：歷史趨勢圖 ──
    with st.container(border=True):
        st.subheader(":material/trending_up: 月度健康與價值趨勢（歷史軌跡）")
        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.caption("活躍、流失與沉睡走勢圖")
            trend_line = df_trend.set_index('ym_str')[['活躍人數', '沉睡人數', '累積流失']]
            st.line_chart(
                trend_line,
                color=['#12b76a', '#0ba5ec', '#f04438'],
                use_container_width=True,
            )

        with col_t2:
            st.caption("每月客群價值堆疊圖")
            trend_bar = df_trend.set_index('ym_str')[['VIP大戶', '主力客', '一般客']]
            st.bar_chart(
                trend_bar,
                color=['#465fff', '#f79009', '#667085'],
                stack=True,
                use_container_width=True,
            )

    # ── 區塊三：資料表顯示 ──
    with st.container(border=True):
        st.subheader(":material/view_list: 智能標籤會員清單")
        
        display_cols = ['member_id', '當前狀態', '近期/歷史價值', '賽事偏好', '下注頻率', '下注波動度', '近30天總投注', 'historical_total_bet', '距今天數', 'last_date']
        df_display = member_stats[display_cols].rename(columns={'member_id':'會員代號', 'last_date':'最後下注日', 'historical_total_bet': '歷史總投注'}).sort_values('近30天總投注', ascending=False)
        
        # 快速篩選 Pills (取代原本的 Radio 與 Legend)
        filter_status = st.pills(
            "快速篩選名單", 
            ["顯示全部", "🟢 活躍中", "👑 需挽回大戶 (前VIP/主力)", "🔴 已流失", "🌙 沉睡中 (休賽季)"], 
            default="顯示全部"
        )

        df_filtered = df_display.copy()
        if filter_status == "🟢 活躍中":
            df_filtered = df_display[df_display['當前狀態'] == '活躍中']
        elif filter_status == "🔴 已流失":
            df_filtered = df_display[df_display['當前狀態'] == '已流失']
        elif filter_status == "👑 需挽回大戶 (前VIP/主力)":
            df_filtered = df_display[(df_display['當前狀態'] == '已流失') & (df_display['近期/歷史價值'].isin(['前 VIP', '前主力']))]
        elif filter_status == "🌙 沉睡中 (休賽季)":
            df_filtered = df_display[df_display['當前狀態'] == '沉睡中 (休賽季)']

        # 計算佔比基準
        total_30d = df_display['近30天總投注'].sum() or 1
        total_hist = df_display['歷史總投注'].sum() or 1

        st.dataframe(
            df_filtered,
            use_container_width=True,
            height=600,
            column_config={
                "會員代號": st.column_config.TextColumn("會員代號", width="medium"),
                "當前狀態": st.column_config.TextColumn("狀態"),
                "近期/歷史價值": st.column_config.TextColumn("價值分群"),
                "近30天總投注": st.column_config.ProgressColumn(
                    "30天業績佔比",
                    help=f"該會員在全體 30 天總投注額 (NT$ {total_30d:,.0f}) 中的貢獻比例",
                    format="NT$ %d",
                    min_value=0,
                    max_value=total_30d,
                ),
                "歷史總投注": st.column_config.ProgressColumn(
                    "歷史業績佔比",
                    help=f"該會員在全體歷史總投注額 (NT$ {total_hist:,.0f}) 中的貢獻比例",
                    format="NT$ %d",
                    min_value=0,
                    max_value=total_hist,
                ),
                "最後下注日": st.column_config.DateColumn("最後下注日"),
                "距今天數": st.column_config.NumberColumn("停牌天數", format="%d 天"),
            },
            hide_index=True
        )
