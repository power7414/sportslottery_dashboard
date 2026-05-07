import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sqlite3
import numpy as np

st.set_page_config(page_title="會員健康與行為大廳", page_icon="", layout="wide")

DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"
if not DB_PATH.exists():
    st.warning("找不到資料庫，請先執行資料同步！")
    st.stop()

@st.cache_data
def load_all_data():
    conn = sqlite3.connect(DB_PATH)
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
    if has_nba and has_mlb: return " 雙棲"
    elif has_mlb: return " 純 MLB"
    elif has_nba: return " 純 NBA"
    return " 未知"

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
        status = " 活躍中"
        if m_last30_bet >= 40000: value = " VIP"
        elif m_last30_bet >= 12000: value = " 主力"
        else: value = " 一般"
    else:
        is_sleeping = False
        if (current_month_num in mlb_months and 'NBA' in season_tag) or \
           (current_month_num in nba_months and 'MLB' in season_tag):
            is_sleeping = True
            
        if is_sleeping:
            status = " 沉睡中 (休賽季)"
        else:
            status = " 已流失"
            
        if max_bet >= 40000: value = " 前 VIP"
        elif max_bet >= 12000: value = " 前主力"
        else: value = " 前一般"

    # 頻率
    days_per_month = row['total_active_days'] / row['total_months']
    if days_per_month >= 12: freq_tag = " 高頻玩家"
    elif days_per_month <= 4: freq_tag = " 偶發玩家"
    else: freq_tag = " 穩健玩家"
    
    # 波動度
    std = row['std_daily_bet'] if pd.notna(row['std_daily_bet']) else 0
    if std > 20000: vol_tag = " 衝動大戶 (高波動)"
    elif std < 5000: vol_tag = " 規律下注 (低波動)"
    else: vol_tag = " 一般波動"
    
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
# 介面渲染區 (UI Rendering)
# =====================================================================

st.title(" 會員當前健康度與行為大廳")

# ── 區塊一：戰情 KPI (最上方) ──
st.markdown(f"###  戰情中心：當前健康度 (資料更新至: {latest_date.strftime('%Y/%m/%d')})")
st.markdown("以「現在這一刻」往前推算 30 天，精準掌握現在誰該救、誰該放著休眠。")

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric(" 過去 30 天活躍人數", len(member_stats[member_stats['當前狀態'] == ' 活躍中']))
kc2.metric(" 當前 VIP 人數 (>4萬)", len(member_stats[member_stats['近期/歷史價值'] == ' VIP']))
kc3.metric(" 需挽回大戶 (前VIP/主力已流失)", len(member_stats[(member_stats['當前狀態'] == ' 已流失') & (member_stats['近期/歷史價值'].isin([' 前 VIP', ' 前主力']))]))
kc4.metric(" 正常休賽季沉睡人數", len(member_stats[member_stats['當前狀態'] == ' 沉睡中 (休賽季)']))

st.markdown("---")

# ── 區塊二：歷史趨勢圖 ──
st.markdown("###  月度健康與價值趨勢 (歷史軌跡)")
col_t1, col_t2 = st.columns(2)

with col_t1:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df_trend['ym_str'], y=df_trend['活躍人數'], name='每月活躍人數', line=dict(color='#34d399', width=3)))
    fig1.add_trace(go.Scatter(x=df_trend['ym_str'], y=df_trend['沉睡人數'], name='休賽季沉睡 (無害)', line=dict(color='#60a5fa', width=2, dash='dash')))
    fig1.add_trace(go.Scatter(x=df_trend['ym_str'], y=df_trend['累積流失'], name='累積流失警報', line=dict(color='#f87171', width=2)))
    fig1.update_layout(
        title="活躍、流失與沉睡走勢圖", 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
        hovermode="x unified", margin=dict(b=0)
    )
    fig1.update_xaxes(showgrid=False)
    fig1.update_yaxes(gridcolor="#334155")
    st.plotly_chart(fig1, use_container_width=True)

with col_t2:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df_trend['ym_str'], y=df_trend['VIP大戶'], name='VIP大戶 (>4萬)', marker_color='#a78bfa'))
    fig2.add_trace(go.Bar(x=df_trend['ym_str'], y=df_trend['主力客'], name='主力客 (>1.2萬)', marker_color='#fbbf24'))
    fig2.add_trace(go.Bar(x=df_trend['ym_str'], y=df_trend['一般客'], name='一般玩家', marker_color='#94a3b8'))
    fig2.update_layout(
        title="每月客群價值堆疊圖", barmode='stack', 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
        hovermode="x unified", margin=dict(b=0)
    )
    fig2.update_xaxes(showgrid=False)
    fig2.update_yaxes(gridcolor="#334155")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── 區塊三：資料表顯示 ──
st.markdown("###  智能標籤會員清單")

display_cols = ['member_id', '當前狀態', '近期/歷史價值', '賽事偏好', '下注頻率', '下注波動度', '近30天總投注', 'historical_total_bet', '距今天數', 'last_date']
df_display = member_stats[display_cols].rename(columns={'member_id':'會員代號', 'last_date':'最後下注日', 'historical_total_bet': '歷史總投注'}).sort_values('近30天總投注', ascending=False)
df_display['最後下注日'] = df_display['最後下注日'].dt.strftime('%Y-%m-%d')

filter_status = st.radio(" 快速篩選名單", ["顯示全部", " 活躍中", " 需挽回大戶 (前VIP/主力)", " 所有已流失", " 沉睡中 (可略過)"], horizontal=True)

df_filtered = df_display.copy()
if filter_status == " 活躍中":
    df_filtered = df_display[df_display['當前狀態'] == ' 活躍中']
elif filter_status == " 所有已流失":
    df_filtered = df_display[df_display['當前狀態'] == ' 已流失']
elif filter_status == " 需挽回大戶 (前VIP/主力)":
    df_filtered = df_display[(df_display['當前狀態'] == ' 已流失') & (df_display['近期/歷史價值'].isin([' 前 VIP', ' 前主力']))]
elif filter_status == " 沉睡中 (可略過)":
    df_filtered = df_display[df_display['當前狀態'] == ' 沉睡中 (休賽季)']

st.dataframe(
    df_filtered,
    use_container_width=True,
    height=600,
    column_config={
        "近30天總投注": st.column_config.NumberColumn(
            "近30天總投注",
            format="$%d"
        ),
        "歷史總投注": st.column_config.NumberColumn(
            "歷史總投注",
            format="$%d"
        )
    }
)
