import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.title("✨ TailAdmin 設計展示 (Demo)")
st.caption("此頁面展示所有計畫引入的原生 Streamlit 元件與 Plotly 圖表效果，確認後再套用至各分頁。")
st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 1：st.badge — 狀態標籤
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("① st.badge — 狀態標籤")
    st.caption("用途：取代手刻的 `<span class='pill'>` HTML，用於會員狀態、頁面標題旁的分類標籤。")

    # 使用場景 A：會員狀態
    st.markdown("**會員狀態標籤 (Members Page)**")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.badge("VIP 高價值", color="green", icon=":material/star:")
    with col2:
        st.badge("流失預警", color="red", icon=":material/warning:")
    with col3:
        st.badge("穩定活躍", color="blue", icon=":material/check_circle:")
    with col4:
        st.badge("新會員", color="violet", icon=":material/new_releases:")
    with col5:
        st.badge("沉睡中", color="gray", icon=":material/bedtime:")

    st.markdown("---")

    # 使用場景 B：在 Markdown 中內嵌 badge（表格行內用）
    st.markdown("**在文字行內嵌入（`st.markdown` 內嵌格式）**")
    st.markdown(
        "會員 #88512 | 本月投注額 NT$ 125,000 | "
        ":green-badge[VIP 高價值] &nbsp; "
        ":blue-badge[穩定活躍] &nbsp; "
        ":orange-badge[待聯繫]"
    )

    st.markdown("---")

    # 使用場景 C：頁面標題旁
    st.markdown("**頁面標題旁搭配 badge**")
    title_col, badge_col = st.columns([6, 2])
    with title_col:
        st.subheader("會員數據與行為分析")
    with badge_col:
        st.write("")
        st.badge(f"共 248 位活躍會員", color="primary", icon=":material/group:")

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 2：st.metric — KPI 卡片（已套用）
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("② st.metric — KPI 卡片 ✅ 已套用")
    st.caption("已替換至 dashboard.py、betting_analysis.py、finance.py。`delta` 自動套用 `config.toml` 的主題色。")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("本月總投注額", "NT$ 2,450,000", "+8.3% vs 上月")
    with m2:
        st.metric("活躍會員數", "248 人", "+12 人", delta_color="normal")
    with m3:
        st.metric("總支出", "NT$ 85,000", "-NT$ 85,000", delta_color="inverse")
    with m4:
        st.metric("本週投注額", "NT$ 620,000", "本週（05/05 起）", delta_color="off")

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 3：st.pills — 切換按鈕（已套用）
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("③ st.pills — 時間粒度切換 ✅ 已套用")
    st.caption("已替換至 betting_analysis.py 的圖表時間切換。比 `st.radio` 更像按鈕群組，膠囊樣式。")

    c1, c2 = st.columns([3, 1])
    with c2:
        granularity = st.pills("顯示粒度", ["日", "週", "月"], default="日", label_visibility="collapsed")
    with c1:
        st.caption(f"目前選擇：**{granularity}** 為單位顯示圖表")

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 4：@st.dialog — 彈出式對話框（待套用至 finance.py）
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("④ @st.dialog — 彈出對話框（待套用）")
    st.caption("用途：取代 finance.py 的 `st.expander` 表單。點擊後在頁面中央彈出，填完後自動關閉。")

    @st.dialog("新增收支紀錄", width="large")
    def add_finance_dialog():
        st.caption("填寫以下欄位後按下儲存，資料將自動寫入資料庫。")
        col1, col2 = st.columns(2)
        with col1:
            import datetime
            st.date_input("日期", value=datetime.date.today())
            st.selectbox("收支類別", ["收入", "支出"])
        with col2:
            st.selectbox("項目", ["廣告費", "薪資", "平台費", "會員收入"])
            st.number_input("金額 (NT$)", value=0, step=100)
        st.text_input("備註", placeholder="選填")
        if st.button("儲存紀錄", type="primary", use_container_width=True):
            st.success("已成功新增！")
            st.rerun()

    if st.button("➕ 新增收支紀錄（點擊看 Dialog 效果）", type="primary"):
        add_finance_dialog()

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 5：column_config.ProgressColumn — 表格進度條
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("⑤ column_config.ProgressColumn — 投注額進度條")
    st.caption("用途：在會員清單或排行榜 dataframe 中，將投注額欄位轉為視覺化進度條。")

    df_demo = pd.DataFrame({
        "會員 ID": ["#885512", "#762341", "#934821", "#123456", "#789012"],
        "本月投注額": [125000, 98000, 72000, 45000, 31000],
        "佔比 (%)": [28.5, 22.3, 16.4, 10.3, 7.1],
        "狀態": ["VIP 高價值", "穩定活躍", "穩定活躍", "待觀察", "待觀察"],
    })

    st.dataframe(
        df_demo,
        use_container_width=True,
        column_config={
            "本月投注額": st.column_config.ProgressColumn(
                "本月投注額",
                help="相對於最高投注額的比例",
                format="NT$ %d",
                min_value=0,
                max_value=125000,
            ),
            "佔比 (%)": st.column_config.NumberColumn(
                "佔比",
                format="%.1f%%",
            ),
        },
        hide_index=True,
    )

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 6：st.popover — 彈出選單（待確認）
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("⑥ st.popover — 彈出選單（待確認）")
    st.caption("用途：圖表右上角的「更多設定」或「篩選」按鈕，點擊後展開一個小浮動選單。")

    chart_col, btn_col = st.columns([5, 1])
    with btn_col:
        with st.popover("⚙️ 設定", use_container_width=True):
            st.markdown("**圖表設定**")
            st.checkbox("顯示平均線", value=True)
            st.checkbox("顯示數據標籤", value=False)
            st.selectbox("Y 軸單位", ["元 (NT$)", "萬元"])
    with chart_col:
        st.caption("← 點擊右側「設定」按鈕試試 popover 效果")

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 7：Plotly 圖表效果展示
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("⑦ Plotly 圖表效果（計畫套用至各頁面）")

    np.random.seed(42)
    dates = pd.date_range("2026-04-01", "2026-04-30")
    vals1 = (np.random.normal(300, 40, len(dates)).cumsum() + 5000)
    vals2 = (np.random.normal(150, 20, len(dates)).cumsum() + 2500)
    labels = [d.strftime("%m/%d") for d in dates]

    CHART_STYLE = dict(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit", color="#94a3b8"),
        margin=dict(t=40, b=10, l=0, r=0),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#101828", bordercolor="#344054", font_size=13, font_family="Outfit"),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.05,
                    xanchor="center", x=0.5, font=dict(color="#94a3b8")),
    )
    XAXIS = dict(zeroline=False, showline=False, showgrid=False, tickfont=dict(color="#94a3b8", size=11))
    YAXIS = dict(zeroline=False, showline=False, gridcolor="#1d2939", griddash="dash",
                 tickfont=dict(color="#94a3b8", size=11))

    tab1, tab2 = st.tabs(["平滑漸層面積圖", "堆疊長條 + Spike"])

    with tab1:
        fig = go.Figure()
        for alpha in [0.22, 0.10, 0.04]:
            fig.add_trace(go.Scatter(x=labels, y=vals1, mode="none",
                fill="tozeroy", fillcolor=f"rgba(70,95,255,{alpha})",
                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=labels, y=vals1, name="同意會員",
            mode="lines", line=dict(width=3, color="#465fff", shape="spline", smoothing=1.3),
            fill="tozeroy", fillcolor="rgba(70,95,255,0.02)",
            hovertemplate="NT$ %{y:,.0f}",
        ))
        for alpha in [0.15, 0.07, 0.02]:
            fig.add_trace(go.Scatter(x=labels, y=vals2, mode="none",
                fill="tozeroy", fillcolor=f"rgba(11,165,236,{alpha})",
                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=labels, y=vals2, name="不同意第三人",
            mode="lines", line=dict(width=2, color="#0ba5ec", shape="spline", smoothing=1.3),
            fill="tozeroy", fillcolor="rgba(11,165,236,0.01)",
            hovertemplate="NT$ %{y:,.0f}",
        ))
        fig.update_layout(**CHART_STYLE, height=300)
        fig.update_xaxes(**XAXIS)
        fig.update_yaxes(**YAXIS)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
        agreed    = [1200, 1500, 1100, 1800, 2100, 1950]
        disagreed = [400, 500, 380, 620, 700, 650]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=months, y=agreed, name="同意會員", marker_color="#465fff",
                              hovertemplate="<b>%{x}</b><br>同意：NT$ %{y:,}<extra></extra>"))
        fig2.add_trace(go.Bar(x=months, y=disagreed, name="不同意第三人", marker_color="#0ba5ec",
                              hovertemplate="<b>%{x}</b><br>不同意：NT$ %{y:,}<extra></extra>"))
        fig2.update_layout(**CHART_STYLE, barmode="stack", height=300, bargap=0.35)
        fig2.update_xaxes(**XAXIS, showspikes=True, spikecolor="#465fff",
                          spikethickness=1, spikedash="dot", spikemode="across")
        fig2.update_yaxes(**YAXIS)
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 8：st.bar_chart / st.line_chart — 原生圖表 vs Plotly 對比
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("⑧ 原生圖表 vs Plotly 對比")
    st.caption("左欄用 `st.bar_chart` / `st.line_chart`（一行搞定），右欄用 Plotly（完整控制）。把滑鼠移到圖表上觀察 tooltip 差異。")

    # 共用假資料
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    agreed    = [1200, 1500, 1100, 1800, 2100, 1950]
    disagreed = [400,  500,  380,  620,  700,  650]

    chart_df = pd.DataFrame({
        "同意會員": agreed,
        "不同意第三人": disagreed,
    }, index=months)

    # ── 長條圖對比 ────────────────────────────────────────────
    st.markdown("##### 📊 長條圖")
    bc1, bc2 = st.columns(2)

    with bc1:
        st.markdown("**`st.bar_chart` 原生** — 一行程式碼")
        st.caption("✅ Tooltip 自動套用 `config.toml` 主題色  ✅ 自動加圖例  ❌ 無法控制 tooltip 格式")
        st.bar_chart(
            chart_df,
            color=["#465fff", "#0ba5ec"],
            stack=True,
        )

    with bc2:
        st.markdown("**`st.plotly_chart` Plotly** — 完整控制")
        st.caption("✅ 自訂 tooltip 樣式  ✅ 數字格式  ❌ 需要 15+ 行設定")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=months, y=agreed, name="同意會員", marker_color="#465fff",
                                 hovertemplate="<b>%{x}</b><br>同意：NT$ %{y:,}<extra></extra>"))
        fig_bar.add_trace(go.Bar(x=months, y=disagreed, name="不同意第三人", marker_color="#0ba5ec",
                                 hovertemplate="<b>%{x}</b><br>不同意：NT$ %{y:,}<extra></extra>"))
        fig_bar.update_layout(
            barmode="stack", hovermode="x unified",
            hoverlabel=dict(bgcolor="#101828", bordercolor="#344054", font_size=13, font_family="Outfit"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=0, r=0), height=300, bargap=0.35,
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02,
                        xanchor="center", x=0.5, font=dict(color="#94a3b8")),
            font=dict(family="Outfit", color="#94a3b8"),
        )
        fig_bar.update_xaxes(zeroline=False, showline=False, showgrid=False, tickfont=dict(color="#94a3b8", size=11))
        fig_bar.update_yaxes(zeroline=False, showline=False, gridcolor="#1d2939", griddash="dash",
                              tickfont=dict(color="#94a3b8", size=11))
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── 折線圖對比 ────────────────────────────────────────────
    st.markdown("##### 📈 折線圖")
    lc1, lc2 = st.columns(2)

    np.random.seed(42)
    dates = pd.date_range("2026-04-01", "2026-04-30")
    vals1 = (np.random.normal(300, 40, len(dates)).cumsum() + 5000)
    vals2 = (np.random.normal(150, 20, len(dates)).cumsum() + 2500)
    labels = [d.strftime("%m/%d") for d in dates]

    line_df = pd.DataFrame({
        "同意會員": vals1,
        "不同意第三人": vals2,
    }, index=labels)

    with lc1:
        st.markdown("**`st.line_chart` 原生** — 一行程式碼")
        st.caption("✅ 自動對齊主題色  ✅ Tooltip 原生樣式  ❌ 無漸層、無平滑曲線")
        st.line_chart(
            line_df,
            color=["#465fff", "#0ba5ec"],
        )

    with lc2:
        st.markdown("**`st.plotly_chart` Plotly** — 平滑 + 漸層")
        st.caption("✅ `spline` 平滑曲線  ✅ 漸層面積  ✅ 自訂 tooltip  ❌ 需要更多程式碼")
        fig_line = go.Figure()
        for alpha in [0.22, 0.10, 0.04]:
            fig_line.add_trace(go.Scatter(x=labels, y=vals1, mode="none",
                fill="tozeroy", fillcolor=f"rgba(70,95,255,{alpha})",
                showlegend=False, hoverinfo="skip"))
        fig_line.add_trace(go.Scatter(
            x=labels, y=vals1, name="同意會員",
            mode="lines", line=dict(width=3, color="#465fff", shape="spline", smoothing=1.3),
            fill="tozeroy", fillcolor="rgba(70,95,255,0.02)",
            hovertemplate="NT$ %{y:,.0f}",
        ))
        fig_line.add_trace(go.Scatter(
            x=labels, y=vals2, name="不同意第三人",
            mode="lines", line=dict(width=2, color="#0ba5ec", shape="spline", smoothing=1.3),
            hovertemplate="NT$ %{y:,.0f}",
        ))
        fig_line.update_layout(
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#101828", bordercolor="#344054", font_size=13, font_family="Outfit"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=0, r=0), height=300,
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02,
                        xanchor="center", x=0.5, font=dict(color="#94a3b8")),
            font=dict(family="Outfit", color="#94a3b8"),
        )
        fig_line.update_xaxes(zeroline=False, showline=False, showgrid=False, tickfont=dict(color="#94a3b8", size=11))
        fig_line.update_yaxes(zeroline=False, showline=False, gridcolor="#1d2939", griddash="dash",
                               tickfont=dict(color="#94a3b8", size=11))
        st.plotly_chart(fig_line, use_container_width=True)

    # ── 結論比較表 ────────────────────────────────────────────
    st.markdown("##### 📋 選擇建議")
    st.dataframe(
        pd.DataFrame({
            "功能": ["程式碼行數", "Tooltip 自訂", "顏色控制", "漸層面積", "平滑曲線", "Spike 十字準線", "數字格式化", "與主題整合"],
            "st.bar/line_chart": ["✅ 1 行", "❌ 無法自訂", "✅ 傳 color 參數", "❌ 不支援", "❌ 不支援", "❌ 不支援", "❌ 自動格式", "✅ 自動套用 config.toml"],
            "st.plotly_chart": ["❌ 15-30 行", "✅ 完整控制", "✅ 完整控制", "✅ 支援", "✅ spline", "✅ showspikes", "✅ 自訂 format", "⚠️ 需手動對齊色票"],
        }),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ════════════════════════════════════════════════════════════
# 區塊 9：平均線用「常數欄位」在原生圖表實現
# ════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("⑨ 平均線 → 作為獨立數列呈現")
    st.caption("把平均值重複填入每一行，`st.line_chart` 就會畫出一條水平參考線，不需要 Plotly。")

    np.random.seed(7)
    dates9 = pd.date_range("2026-04-01", "2026-04-30")
    active = np.random.randint(15, 80, len(dates9))
    avg_val = int(active.mean())

    df9 = pd.DataFrame({
        "活躍人數": active,
        f"平均 ({avg_val} 人)": avg_val,   # 常數欄位 → 水平線
    }, index=[d.strftime("%m/%d") for d in dates9])

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**`st.line_chart` + 平均欄位**")
        st.caption(f"灰色的「平均 ({avg_val} 人)」欄位在每個日期都是同一個數值，所以呈現為一條水平線。")
        st.line_chart(
            df9,
            color=["#465fff", "#94a3b8"],   # 藍色=活躍人數, 灰色=平均線
        )

    with col_b:
        st.markdown("**資料結構（前 5 行）**")
        st.caption("只要把平均值填滿整欄，圖表就自動畫出參考線，邏輯非常簡單：")
        st.dataframe(df9.head(5), use_container_width=True)
        st.code(f"""# 實作方式（3 行搞定）
avg = int(df["active_users"].mean())   # = {avg_val}
df["平均 ({avg_val} 人)"] = avg        # 常數欄位
st.line_chart(df[["活躍人數", "平均 ({avg_val} 人)"]])""", language="python")

    st.markdown("---")
    st.markdown("**長條圖也能用同樣方法加趨勢折線（混合圖）？**")
    st.caption("⚠️ `st.bar_chart` 不支援混合圖（bar + line），平均線在長條圖上只能用 Plotly 或省略。但折線圖完全可行！")
