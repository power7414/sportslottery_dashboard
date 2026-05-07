import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 將 src 加入路徑以便引入同步模組
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))
from src.dropbox_sync import sync_dropbox_folder
from src.init_database import update_specific_files

# ── 頁面設定 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="運彩投注額 Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 智慧自動同步 (每次開啟瀏覽器分頁只執行一次) ──────────────────────
if 'has_synced' not in st.session_state:
    st.session_state.has_synced = True
    with st.spinner(" 正在檢查 Dropbox 是否有最新資料..."):
        try:
            # 1. 去 Dropbox 檢查，只下載大小改變的檔案
            new_files = sync_dropbox_folder()
            
            if new_files:
                st.toast(f" 發現 {len(new_files)} 個新檔案，正在更新資料庫...", icon="")
                # 2. 只有在抓到新檔案時，才去更新資料庫
                update_specific_files(new_files)
                # 3. 清除快取，讓下方讀取到最新資料
                st.cache_data.clear()
                st.toast(" 資料庫已是最新！", icon="")
        except Exception as e:
            st.error(f"同步失敗: {e}")

# ── 自訂 CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #f0f0f0;
}
.hero-title {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(90deg, #a78bfa, #60a5fa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.hero-subtitle { color: #94a3b8; font-size: 0.9rem; margin-top: 0.2rem; }
hr { border-color: #334155; margin: 1.5rem 0; }

.kpi-card {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    text-align: center;
}
.kpi-label {
    color: #94a3b8; font-size: 0.82rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
}
.kpi-value { font-size: 2rem; font-weight: 800; color: #f1f5f9; margin: 0.3rem 0; line-height: 1.1; }
.kpi-delta-pos { color: #34d399; font-size: 0.85rem; font-weight: 600; }
.kpi-delta-neg { color: #f87171; font-size: 0.85rem; font-weight: 600; }
.kpi-delta-neu { color: #94a3b8; font-size: 0.85rem; font-weight: 600; }

.section-title {
    font-size: 1rem; font-weight: 700; color: #cbd5e1;
    margin-bottom: 0.8rem; padding-left: 0.5rem;
    border-left: 3px solid #7c3aed;
}

/* 圖例色塊 */
.legend-dot-agreed    { display:inline-block;width:10px;height:10px;border-radius:50%;background:#a78bfa;margin-right:5px; }
.legend-dot-disagreed { display:inline-block;width:10px;height:10px;border-radius:50%;background:#38bdf8;margin-right:5px; }

.rank-row {
    display: flex; align-items: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 0.65rem 1rem; margin-bottom: 0.45rem;
}
.rank-num { width: 32px; font-weight: 800; font-size: 1rem; }
.rank-num.gold   { color: #fbbf24; }
.rank-num.silver { color: #94a3b8; }
.rank-num.bronze { color: #cd7c50; }
.rank-num.other  { color: #64748b; }
.rank-id  { flex: 1; font-size: 0.9rem; color: #e2e8f0; }
.rank-amt { font-size: 0.95rem; font-weight: 700; color: #a78bfa; }
</style>
""", unsafe_allow_html=True)

# ── 資料庫連線 ────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "processed" / "betting_data.db"

@st.cache_data(ttl=300)
def load_bets():
    """個別會員每日投注明細"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df

@st.cache_data(ttl=300)
def load_summary():
    """每日彙整（同意 + 不同意第三人）"""
    conn = sqlite3.connect(DB_PATH)
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
st.markdown('<p class="hero-title"> 運彩投注額 Dashboard</p>', unsafe_allow_html=True)
st.markdown(f'<p class="hero-subtitle">資料更新至 {latest_date.strftime("%Y/%m/%d")}（系統當前月份：{cur_ym}）</p>', unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ── KPI 卡片 ──────────────────────────────────────────────────────
def delta_html(value):
    if value is None:
        return '<span class="kpi-delta-neu">— 無上月資料</span>'
    cls   = "kpi-delta-pos" if value >= 0 else "kpi-delta-neg"
    arrow = "▲" if value >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {abs(value):.1f}% vs 上月</span>'

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">本月總投注額</div>
        <div class="kpi-value">NT$ {this_month_total:,.0f}</div>
        {delta_html(mom_delta)}
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">本週總投注額</div>
        <div class="kpi-value">NT$ {this_week_total:,.0f}</div>
        <span class="kpi-delta-neu">本週（{week_start.strftime("%m/%d")} 起）</span>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">本月新增會員數</div>
        <div class="kpi-value">{new_members} 人</div>
        <span class="kpi-delta-neu">本月首次出現的會員</span>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── 圖表 ──────────────────────────────────────────────────────────
CHART_BG   = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(255,255,255,0.07)"
FONT_COLOR = "#94a3b8"

col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<div class="section-title">過去 6 個月投注額（同意 ＋ 不同意第三人）</div>', unsafe_allow_html=True)
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        name="同意會員",
        x=monthly['ym'], y=monthly['agreed'],
        marker_color="#7c3aed",
        hovertemplate="<b>%{x}</b><br>同意：NT$ %{y:,.0f}<extra></extra>",
    ))
    fig1.add_trace(go.Bar(
        name="不同意第三人",
        x=monthly['ym'], y=monthly['disagreed'],
        marker_color="#38bdf8",
        hovertemplate="<b>%{x}</b><br>不同意第三人：NT$ %{y:,.0f}<extra></extra>",
    ))
    # 在每組最上方標示總計
    totals = monthly['agreed'] + monthly['disagreed']
    fig1.add_trace(go.Scatter(
        x=monthly['ym'], y=totals,
        mode='text',
        text=[f"共 {v/10000:.0f}萬" for v in totals],
        textposition="top center",
        textfont=dict(color="#cbd5e1", size=11),
        showlegend=False,
    ))
    fig1.update_layout(
        barmode='stack',
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        margin=dict(t=30, b=10, l=10, r=10), height=290,
        legend=dict(font=dict(color=FONT_COLOR), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(tickfont=dict(color=FONT_COLOR), showgrid=False),
        yaxis=dict(tickfont=dict(color=FONT_COLOR), gridcolor=GRID_COLOR,
                   tickformat=",.0f"),
        font=dict(family="Inter"),
    )
    st.plotly_chart(fig1, use_container_width=True)

with col_right:
    st.markdown('<div class="section-title">過去 6 個月會員數分佈（總數 vs 活躍）</div>', unsafe_allow_html=True)
    fig2 = go.Figure()
    
    # 總會員數 (深色)
    fig2.add_trace(go.Bar(
        name="總會員數",
        x=monthly['ym'], y=monthly['total_members'],
        marker_color="#1e293b",
        text=monthly['total_members'],
        textposition="outside",
        textfont=dict(color="#cbd5e1", size=11),
        hovertemplate="<b>%{x}</b><br>總會員數：%{y} 人<extra></extra>",
    ))
    
    # 活躍會員數 (亮色)
    fig2.add_trace(go.Bar(
        name="活躍會員數",
        x=monthly['ym'], y=monthly['active_members'],
        marker_color="#38bdf8",
        text=monthly['active_members'],
        textposition="outside",
        textfont=dict(color="#38bdf8", size=11),
        hovertemplate="<b>%{x}</b><br>活躍會員數：%{y} 人<extra></extra>",
    ))
    
    fig2.update_layout(
        barmode='group', # 並排顯示
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        margin=dict(t=30, b=10, l=10, r=10), height=290,
        legend=dict(font=dict(color=FONT_COLOR), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickfont=dict(color=FONT_COLOR), showgrid=False),
        yaxis=dict(tickfont=dict(color=FONT_COLOR), gridcolor=GRID_COLOR),
        font=dict(family="Inter"),
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── 排行榜 ────────────────────────────────────────────────────────
st.markdown('<div class="section-title"> 本月投注排行榜（前10名，同意會員）</div>', unsafe_allow_html=True)

rank_cols = st.columns(2)
for i, (_, row) in enumerate(top10.iterrows()):
    rank    = i + 1
    col_idx = i % 2
    if   rank == 1: num_cls, icon = "gold",   ""
    elif rank == 2: num_cls, icon = "silver", ""
    elif rank == 3: num_cls, icon = "bronze", ""
    else:           num_cls, icon = "other",  str(rank)

    with rank_cols[col_idx]:
        st.markdown(f"""
        <div class="rank-row">
            <div class="rank-num {num_cls}">{icon}</div>
            <div class="rank-id">{row['member_id']}</div>
            <div class="rank-amt">NT$ {row['bet_amount']:,.0f}</div>
        </div>""", unsafe_allow_html=True)
