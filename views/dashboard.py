import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# (同步邏輯已移至主路由 app.py)

# ── 排行榜 rank-row 保留最小 CSS（純視覺，無原生元件可替代）─────────
st.markdown("""
<style>
.rank-row {
    display: flex; align-items: center;
    background: rgba(255,255,255,0.03); 
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 0.75rem; padding: 0.65rem 1rem; margin-bottom: 0.45rem;
}
.rank-num { width: 32px; font-weight: 800; font-size: 1rem; }
.rank-num.gold   { color: #f79009; }
.rank-num.silver { color: #98a2b3; }
.rank-num.bronze { color: #dc6803; }
.rank-num.other  { color: #667085; }
.rank-id  { flex: 1; font-size: 0.9rem; color: #e2e8f0; }
.rank-amt { font-size: 0.95rem; font-weight: 700; color: #465fff; }
</style>
""", unsafe_allow_html=True)

# ── 資料庫連線 ────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"

@st.cache_data(ttl=300)
def load_bets():
    """個別會員每日投注明細"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    df = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df

@st.cache_data(ttl=300)
def load_summary():
    """每日彙整（同意 + 不同意第三人）"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    df = pd.read_sql("SELECT * FROM fact_daily_summary", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df

df_bets    = load_bets()
df_summary = load_summary()

# ── 計算指標 ──────────────────────────────────────────────────────
# 動態取得資料庫中最新的日期當作「今天」，這樣跨月才不會抓不到資料
latest_date = df_summary['date'].max()
if pd.isna(latest_date):
    latest_date = datetime.now()

cur_ym   = latest_date.strftime("%Y-%m")
prev_ym  = (latest_date.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
week_start = latest_date - timedelta(days=latest_date.weekday())

# 本月 / 上月 / 本週 ── 用 fact_daily_summary 計算總額
df_summary['total_amount'] = df_summary['agreed_amount'] + df_summary['disagreed_amount']
df_summary['total_people'] = df_summary['agreed_people'] + df_summary['disagreed_people']
df_summary['ym']           = df_summary['date'].dt.strftime("%Y-%m")

this_month_summary = df_summary[df_summary['ym'] == cur_ym]
prev_month_summary = df_summary[df_summary['ym'] == prev_ym]
this_week_summary  = df_summary[df_summary['date'] >= pd.Timestamp(week_start.date())]

this_month_total = this_month_summary['total_amount'].sum()
prev_month_total = prev_month_summary['total_amount'].sum()
this_week_total  = this_week_summary['total_amount'].sum()

mom_delta = ((this_month_total - prev_month_total) / prev_month_total * 100
             if prev_month_total > 0 else None)

# 本月新增會員（用個別明細表）
df_bets['ym']  = df_bets['date'].dt.strftime("%Y-%m")
cur_members    = set(df_bets[df_bets['ym'] == cur_ym]['member_id'])
prev_members   = set(df_bets[df_bets['ym'] == prev_ym]['member_id'])
new_members    = len(cur_members - prev_members)

# 過去 6 個月：堆疊用資料
monthly = (df_summary.groupby('ym')
           .agg(agreed=('agreed_amount','sum'),
                disagreed=('disagreed_amount','sum'),
                total_members=('total_people','last'))   # 用月底的總會員數
           .reset_index()
           .sort_values('ym')
           .tail(6))

# 過去 6 個月：活躍會員數（有實際下注的人數）
member_monthly = (df_bets.groupby('ym')['member_id']
                  .nunique().reset_index()
                  .rename(columns={'member_id':'active_members'}))
monthly = monthly.merge(member_monthly, on='ym', how='left')


# 本月排行榜前 10
top10 = (df_bets[df_bets['ym'] == cur_ym]
         .groupby('member_id')['bet_amount'].sum()
         .reset_index()
         .sort_values('bet_amount', ascending=False)
         .head(10))

# ── 渲染頁面 ──────────────────────────────────────────────────────
st.title(":material/dashboard: 運彩投注額 Dashboard")
st.caption(f"資料更新至 {latest_date.strftime('%Y/%m/%d')}（系統當前月份：{cur_ym}）")
st.divider()

# ── KPI 卡片 (native st.metric) ────────────────────────────────────────────
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta_str = f"{mom_delta:+.1f}% vs 上月" if mom_delta is not None else None
        st.metric(
            label="本月總投注額",
            value=f"NT$ {this_month_total:,.0f}",
            delta=delta_str,
        )
    with c2:
        st.metric(
            label="本週總投注額",
            value=f"NT$ {this_week_total:,.0f}",
            delta=f"本週（{week_start.strftime('%m/%d')} 起）",
            delta_color="off",
        )
    with c3:
        st.metric(
            label="本月新增會員數",
            value=f"{new_members} 人",
            delta="本月首次出現的會員",
            delta_color="off",
        )
    with c4:
        cur_active = monthly[monthly['ym'] == cur_ym]['active_members'].values
        cur_active_val = int(cur_active[0]) if len(cur_active) > 0 else 0
        prev_ym_val = monthly['ym'].iloc[-2] if len(monthly) >= 2 else None
        prev_active = monthly[monthly['ym'] == prev_ym_val]['active_members'].values if prev_ym_val else []
        prev_active_val = int(prev_active[0]) if len(prev_active) > 0 else None
        active_delta = f"{cur_active_val - prev_active_val:+d} vs 上月" if prev_active_val is not None else None
        st.metric(
            label="本月活躍會員數",
            value=f"{cur_active_val} 人",
            delta=active_delta,
        )


# ── 圖表 ──────────────────────────────────────────────────────────
with st.container(border=True):
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":material/bar_chart: 過去 6 個月總投注額")
        st.caption("同意 ＋ 不同意第三人 合計")
        monthly['total'] = monthly['agreed'] + monthly['disagreed']
        chart1_df = monthly.set_index('ym')[['total']]
        chart1_df.columns = ['總投注額']
        st.bar_chart(
            chart1_df,
            color=['#465fff'],
            use_container_width=True,
        )

    with col_right:
        st.subheader(":material/groups: 過去 6 個月會員數")
        st.caption("同意會員 ＋ 不同意第三人（堆疊）")
        # agreed/disagreed_people 是累計快照値，取月底最後一筆
        people_monthly = (
            df_summary[df_summary['ym'].isin(monthly['ym'])]
            .groupby('ym')
            .agg(
                agreed_people   =('agreed_people',    'last'),
                disagreed_people=('disagreed_people', 'last'),
            )
            .reset_index()
        )
        people_chart = (
            monthly[['ym']]
            .merge(people_monthly, on='ym', how='left')
            .set_index('ym')[['agreed_people', 'disagreed_people']]
        )
        people_chart.columns = ['同意會員', '不同意第三人']
        st.bar_chart(
            people_chart,
            color=['#465fff', '#0ba5ec'],
            stack=True,
            use_container_width=True,
        )


# ── 排行榜 ────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader(":material/leaderboard: 本月投注排行榜（前 10 名）")

    rank_cols = st.columns(2)
    for i, (_, row) in enumerate(top10.iterrows()):
        rank    = i + 1
        col_idx = i % 2
        if   rank == 1: num_cls, label = "gold",   "1"
        elif rank == 2: num_cls, label = "silver", "2"
        elif rank == 3: num_cls, label = "bronze", "3"
        else:           num_cls, label = "other",  str(rank)

        with rank_cols[col_idx]:
            st.markdown(f"""
            <div class="rank-row">
                <div class="rank-num {num_cls}">{label}</div>
                <div class="rank-id">{row['member_id']}</div>
                <div class="rank-amt">NT$ {row['bet_amount']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
