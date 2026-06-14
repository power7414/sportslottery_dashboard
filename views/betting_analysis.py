import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"

if not DB_PATH.exists():
    st.warning("找不到資料庫，請先回到首頁等待自動同步完成！")
    st.stop()

@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    df_bets    = pd.read_sql("SELECT date, member_id, bet_amount FROM fact_daily_bets", conn)
    df_summary = pd.read_sql("SELECT * FROM fact_daily_summary", conn)
    conn.close()
    df_bets["date"]    = pd.to_datetime(df_bets["date"])
    df_summary["date"] = pd.to_datetime(df_summary["date"])
    return df_bets, df_summary

df_bets, df_summary = load_data()
latest_date = df_summary["date"].max()
min_date    = df_summary["date"].min()

# ── 頁面標題 ─────────────────────────────────────────────────────
st.title(":material/monitoring: 整體投注概覽")
st.caption("切換顯示單位與時間區間，觀察活躍人數增長趨勢與整體營收狀態。")
st.divider()

# ── KPI 佔位符（最頂端，資料處理後填入）─────────────────────────
kpi_placeholder = st.empty()

st.divider()

# ── 圖表卡片（篩選控件 + 圖表 同在一個 container）───────────────
chart_container = st.container(border=True)

# 第一次進入 container：放篩選控件
with chart_container:
    hcol1, hcol2, hcol3 = st.columns([3, 1, 4])
    with hcol1:
        st.subheader(":material/show_chart: 趨勢圖表")
    with hcol2:
        granularity = st.pills(
            "granularity", ["日", "週", "月"],
            default="日", label_visibility="collapsed"
        )
        if granularity is None:
            granularity = "日"
    with hcol3:
        period_opts = ["過去 7 天", "過去 14 天", "過去 1 個月",
                       "過去 3 個月", "過去 6 個月", "過去 1 年"]
        selected_period = st.pills(
            "period", period_opts,
            default=None, label_visibility="collapsed"
        )

# ── 計算起迄日期 ──────────────────────────────────────────────────
if selected_period is None:
    start_date   = min_date
    period_label = "全部資料"
else:
    days_map = {
        "過去 7 天": 6, "過去 14 天": 13, "過去 1 個月": 29,
        "過去 3 個月": 89, "過去 6 個月": 179, "過去 1 年": 364,
    }
    start_date   = latest_date - pd.Timedelta(days=days_map[selected_period])
    period_label = selected_period

end_date = latest_date

# ── 篩選資料 ─────────────────────────────────────────────────────
mask_bets    = (df_bets["date"]    >= start_date) & (df_bets["date"]    <= end_date)
mask_summary = (df_summary["date"] >= start_date) & (df_summary["date"] <= end_date)

df_bets_f    = df_bets[mask_bets].copy()
df_summary_f = df_summary[mask_summary].copy()

if df_summary_f.empty:
    with chart_container:
        st.warning("此區間內無投注紀錄，請選擇其他期間。")
    st.stop()

# ── 時間粒度標籤 ──────────────────────────────────────────────────
if granularity == "日":
    df_bets_f["g_date"]    = df_bets_f["date"].dt.strftime("%Y-%m-%d")
    df_summary_f["g_date"] = df_summary_f["date"].dt.strftime("%Y-%m-%d")
elif granularity == "週":
    df_bets_f["g_date"]    = df_bets_f["date"].dt.to_period("W").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
    df_summary_f["g_date"] = df_summary_f["date"].dt.to_period("W").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
else:
    df_bets_f["g_date"]    = df_bets_f["date"].dt.strftime("%Y-%m")
    df_summary_f["g_date"] = df_summary_f["date"].dt.strftime("%Y-%m")

# ── 聚合趨勢資料 ──────────────────────────────────────────────────
trend = df_summary_f.groupby("g_date").agg(
    agreed   =("agreed_amount",    "sum"),
    disagreed=("disagreed_amount", "sum"),
).reset_index()
trend["total"] = trend["agreed"] + trend["disagreed"]

active = df_bets_f.groupby("g_date")["member_id"].nunique().reset_index()
active.columns = ["g_date", "active_users"]
trend = trend.merge(active, on="g_date", how="left")

# ── KPI 運算 ─────────────────────────────────────────────────────
total_amount         = df_summary_f["agreed_amount"].sum() + df_summary_f["disagreed_amount"].sum()
total_unique_members = df_bets_f["member_id"].nunique()
active_days          = df_bets_f["date"].nunique()
avg_daily_amount     = total_amount / active_days if active_days > 0 else 0
avg_per_member       = total_amount / total_unique_members if total_unique_members > 0 else 0
avg_users            = trend["active_users"].mean()

# ── 填入 KPI 佔位符 ───────────────────────────────────────────────
with kpi_placeholder.container():
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("區間總投注額",    f"NT$ {total_amount/10000:,.1f} 萬",
                      delta="含同意 + 不同意第三人", delta_color="off")
        with k2:
            st.metric("平均日投注額",    f"NT$ {avg_daily_amount/10000:,.1f} 萬",
                      delta=f"共 {active_days} 個有效交易日", delta_color="off")
        with k3:
            st.metric("不重複活躍會員", f"{total_unique_members:,} 人",
                      delta="區間內有下注紀錄", delta_color="off")
        with k4:
            st.metric("人均投注額",      f"NT$ {avg_per_member/10000:,.1f} 萬",
                      delta="每位會員平均", delta_color="off")

# 第二次進入同一個 chart_container：放圖表
with chart_container:
    st.caption(f"期間：{period_label}　{start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}　｜　單位：{granularity}")
    tab1, tab2 = st.tabs([":material/group: 活躍人數趨勢", ":material/payments: 投注額趨勢"])

    with tab1:
        avg_label = f"平均 ({avg_users:.1f} 人)"
        dau_df = trend.set_index("g_date")[["active_users"]].copy()
        dau_df.columns = ["活躍人數"]
        dau_df[avg_label] = round(avg_users, 1)
        st.line_chart(dau_df, color=["#38bdf8", "#94a3b8"], use_container_width=True)

    with tab2:
        amt_df = trend.set_index("g_date")[["agreed", "disagreed"]].copy()
        amt_df.columns = ["同意會員", "不同意第三人"]
        st.bar_chart(amt_df, color=["#465fff", "#0ba5ec"], stack=True, use_container_width=True)

# ── 區間活躍會員清單 ──────────────────────────────────────────────
with st.container(border=True):
    st.subheader(":material/list_alt: 區間活躍會員清單")
    st.caption("以下是篩選區間內的會員名單。點擊欄位標題可排序，找出區間內的重注大戶。")

    member_stats = df_bets_f.groupby("member_id").agg(
        total_bet      =("bet_amount", "sum"),
        active_days    =("date",       "nunique"),
        avg_bet_per_day=("bet_amount", "mean"),
    ).reset_index().sort_values("total_bet", ascending=False)
    member_stats.columns = ["會員代號", "區間總投注額", "區間內活躍天數", "平均每日投注額"]

    max_bet = member_stats["區間總投注額"].max() if not member_stats.empty else 100000

    st.dataframe(
        member_stats,
        use_container_width=True,
        height=320,
        column_config={
            "區間總投注額": st.column_config.ProgressColumn(
                "區間總投注額",
                format="NT$ %d",
                min_value=0,
                max_value=float(max_bet),
            ),
            "平均每日投注額": st.column_config.NumberColumn("平均每日投注額", format="NT$ %d"),
        }
    )
