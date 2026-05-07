import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="整體投注", page_icon="", layout="wide")

DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"

if not DB_PATH.exists():
    st.warning("找不到資料庫，請先回到首頁等待自動同步完成！")
    st.stop()

@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    # 讀取個別會員每日投注明細 (用於計算獨立人數)
    df_bets = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
    # 讀取每日彙整明細 (用於計算含不同意的精準投注額)
    df_summary = pd.read_sql("SELECT * FROM fact_daily_summary", conn)
    conn.close()
    
    df_bets['date'] = pd.to_datetime(df_bets['date'])
    df_summary['date'] = pd.to_datetime(df_summary['date'])
    return df_bets, df_summary

df_bets, df_summary = load_data()

st.title(" 整體投注概覽 (Overall Betting)")
st.markdown("在此頁面您可以自由切換時間區間與顯示維度 (日/週/月)，觀察活躍人數的增長趨勢與整體營收狀態。")

# 宣告 KPI 容器，先佔位在畫面最上方
kpi_container = st.container()
st.markdown("---")

# ── 頂部篩選器 ──────────────────────────────────────────────────
latest_date = df_summary['date'].max()
min_date = df_summary['date'].min()

months_list = sorted(df_summary['date'].dt.strftime('%Y-%m').unique(), reverse=True)
quick_options = [
    "自訂區間 (日曆)", 
    "過去 7 天", 
    "過去 14 天", 
    "過去 1 個月",
    "過去 3 個月",
    "過去 6 個月",
    "過去 1 年"
] + [f"{m} (整月)" for m in months_list]

# 使用 columns 將篩選器並列顯示在上方
f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 2])

with f_col1:
    selected_quick = st.selectbox("快速選擇區間", quick_options, index=1)

with f_col2:
    if selected_quick == "自訂區間 (日曆)":
        default_start = latest_date.replace(day=1)
        date_range = st.date_input(
            "自訂開始與結束日期",
            value=(default_start, latest_date),
            min_value=min_date,
            max_value=latest_date
        )
        if len(date_range) != 2:
            st.warning("請選擇完整的開始與結束日期。")
            st.stop()
        start_date, end_date = date_range
    else:
        st.write("") # 排版佔位用
        if selected_quick == "過去 7 天":
            start_date = latest_date - pd.Timedelta(days=6)
        elif selected_quick == "過去 14 天":
            start_date = latest_date - pd.Timedelta(days=13)
        elif selected_quick == "過去 1 個月":
            start_date = latest_date - pd.Timedelta(days=29)
        elif selected_quick == "過去 3 個月":
            start_date = latest_date - pd.Timedelta(days=89)
        elif selected_quick == "過去 6 個月":
            start_date = latest_date - pd.Timedelta(days=179)
        elif selected_quick == "過去 1 年":
            start_date = latest_date - pd.Timedelta(days=364)
        else:
            ym = selected_quick.split(" ")[0]
            start_date = pd.to_datetime(f"{ym}-01")
            end_date = start_date + pd.offsets.MonthEnd(1)
            if end_date > latest_date:
                end_date = latest_date
        if selected_quick != "自訂區間 (日曆)" and "整月" not in selected_quick:
            end_date = latest_date

with f_col3:
    st.write("") # 讓 radio 稍微對齊下移
    granularity = st.radio("圖表顯示單位", ["日", "週", "月"], horizontal=True)

start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

st.caption(f"目前篩選範圍: {start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}")
st.markdown("---")

# 篩選資料
mask_bets = (df_bets['date'] >= start_date) & (df_bets['date'] <= end_date)
mask_summary = (df_summary['date'] >= start_date) & (df_summary['date'] <= end_date)

df_bets_filtered = df_bets[mask_bets].copy()
df_summary_filtered = df_summary[mask_summary].copy()

if df_summary_filtered.empty:
    st.warning("此區間內無投注紀錄，請選擇其他日期區間。")
    st.stop()

# ── KPI 運算 ──────────────────────────────────────────────────
total_amount = df_summary_filtered['agreed_amount'].sum() + df_summary_filtered['disagreed_amount'].sum()
total_unique_members = df_bets_filtered['member_id'].nunique()

# 根據選擇的顯示單位 (Granularity) 計算時間標籤
if granularity == "日":
    df_bets_filtered['g_date'] = df_bets_filtered['date'].dt.strftime('%Y-%m-%d')
    df_summary_filtered['g_date'] = df_summary_filtered['date'].dt.strftime('%Y-%m-%d')
    x_label = "日期"
elif granularity == "週":
    df_bets_filtered['g_date'] = df_bets_filtered['date'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d (週一)'))
    df_summary_filtered['g_date'] = df_summary_filtered['date'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d (週一)'))
    x_label = "週起始日"
else:
    df_bets_filtered['g_date'] = df_bets_filtered['date'].dt.strftime('%Y-%m')
    df_summary_filtered['g_date'] = df_summary_filtered['date'].dt.strftime('%Y-%m')
    x_label = "月份"

# 計算圖表用的數據：總額 (含同意與不同意)
trend_amt = df_summary_filtered.groupby('g_date').agg(
    agreed=('agreed_amount', 'sum'),
    disagreed=('disagreed_amount', 'sum')
).reset_index()
trend_amt['total_amount'] = trend_amt['agreed'] + trend_amt['disagreed']

# 計算圖表用的數據：該單位的獨立活躍人數
trend_dau = df_bets_filtered.groupby('g_date').agg(
    active_users=('member_id', 'nunique')
).reset_index()

trend_stats = pd.merge(trend_amt, trend_dau, on='g_date', how='outer').fillna(0)
trend_stats = trend_stats.sort_values('g_date')

avg_users = trend_stats['active_users'].mean()
avg_amount = trend_stats['total_amount'].mean()

# ── 顯示 KPI 卡片 (寫入最上方的 container) ──────────────────────────────────
with kpi_container:
    st.markdown("### 核心指標 (KPIs)")
    col1, col2, col3 = st.columns(3)
    col1.metric("區間總投注額", f"${total_amount:,.0f}")
    col2.metric("區間總活躍人數", f"{total_unique_members:,} 人")
    col3.metric(f"平均每{granularity}活躍人數", f"{avg_users:.0f} 人")

# ── 趨勢圖表 ──────────────────────────────────────────────────
st.markdown("###  趨勢分析")

tab1, tab2 = st.tabs([f" 活躍人數趨勢 (每{granularity})", f" 投注總額堆疊圖 (每{granularity})"])

with tab1:
    fig_dau = px.line(
        trend_stats, x='g_date', y='active_users', 
        markers=True,
        labels={'g_date': x_label, 'active_users': '活躍人數'},
        color_discrete_sequence=['#38bdf8']
    )
    fig_dau.update_layout(
        yaxis_title="獨立活躍人數", 
        xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20)
    )
    fig_dau.update_xaxes(showgrid=False, type='category') 
    fig_dau.update_yaxes(gridcolor="#334155")
    fig_dau.add_hline(y=avg_users, line_dash="dash", line_color="#94a3b8", annotation_text=f"平均: {avg_users:.1f}人")
    st.plotly_chart(fig_dau, use_container_width=True)

with tab2:
    import plotly.graph_objects as go
    fig_amt = go.Figure()
    
    # 加入同意會員的長條
    fig_amt.add_trace(go.Bar(
        name="一般會員 (同意)",
        x=trend_stats['g_date'], 
        y=trend_stats['agreed'],
        marker_color="#38bdf8",
        hovertemplate="<b>%{x}</b><br>同意投注額：$%{y:,.0f}<extra></extra>"
    ))
    
    # 加入不同意會員的長條
    fig_amt.add_trace(go.Bar(
        name="不同意第三人",
        x=trend_stats['g_date'], 
        y=trend_stats['disagreed'],
        marker_color="#1e293b",
        hovertemplate="<b>%{x}</b><br>不同意投注額：$%{y:,.0f}<extra></extra>"
    ))

    fig_amt.update_layout(
        barmode='stack', # 堆疊模式
        yaxis_title="投注總額 ($)", 
        xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20),
        legend=dict(font=dict(color="white"), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_amt.update_xaxes(showgrid=False, type='category') 
    fig_amt.update_yaxes(gridcolor="#334155")
    fig_amt.add_hline(y=avg_amount, line_dash="dash", line_color="#94a3b8", annotation_text=f"平均: ${avg_amount:,.0f}")
    st.plotly_chart(fig_amt, use_container_width=True)

st.markdown("---")

# ── 區間清單 ──────────────────────────────────────────────────
st.markdown("###  區間活躍會員清單")
st.markdown("以下是篩選區間內的「一般會員」名單。您可以點擊標題排序，找出區間內的重注大戶。")

member_stats = df_bets_filtered.groupby('member_id').agg(
    total_bet=('bet_amount', 'sum'),
    active_days=('date', 'nunique'),
    avg_bet_per_day=('bet_amount', 'mean')
).reset_index().sort_values('total_bet', ascending=False)

member_stats.columns = ['會員代號', '區間總投注額', '區間內活躍天數', '平均每日投注額']

st.dataframe(
    member_stats,
    use_container_width=True,
    height=300,
    column_config={
        "區間總投注額": st.column_config.NumberColumn(
            "區間總投注額",
            format="$%d"
        ),
        "平均每日投注額": st.column_config.NumberColumn(
            "平均每日投注額",
            format="$%d"
        )
    }
)
