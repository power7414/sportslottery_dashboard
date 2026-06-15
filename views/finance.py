import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sqlite3
import datetime


DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"
if not DB_PATH.exists():
    st.warning("找不到資料庫，請先執行資料同步！")
    st.stop()

def get_db_connection():
    return sqlite3.connect(DB_PATH, timeout=30)

def load_finance_data():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM fact_finance", conn)
    conn.close()
    
    # 確保日期格式
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

df_finance = load_finance_data()

# =====================================================================
# 資料預處理與 KPI 運算
# =====================================================================
df_valid = df_finance.dropna(subset=['date']).copy()
df_valid['ym'] = df_valid['date'].dt.strftime('%Y-%m')

# 分類計算
initial_capital = df_valid[df_valid['category'] == '初始資金']['amount'].sum()
# 為了計算嚴謹，排除初始資金來算營運淨利
df_ops = df_valid[df_valid['category'] != '初始資金'].copy()

total_revenue = df_ops[df_ops['amount'] > 0]['amount'].sum()
total_expense = abs(df_ops[df_ops['amount'] < 0]['amount'].sum())
net_profit = total_revenue - total_expense
current_cash = initial_capital + net_profit

# =====================================================================
# 介面渲染區
# =====================================================================

st.title(":material/account_balance: 財務紀錄與現金流大盤")
st.caption("追蹤所有營運收入與支出，自動計算現金流與淨利。")
st.divider()

# ── 1. KPI 卡片 (置頂) ─────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader(":material/dashboard: 大盤財務現況")
    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        st.metric(
            label="當前手頭現金",
            value=f"NT$ {current_cash:,.0f}",
            delta="含初始資金",
            delta_color="off",
        )
    with kc2:
        st.metric(
            label="總營運收入",
            value=f"NT$ {total_revenue:,.0f}",
        )
    with kc3:
        st.metric(
            label="總營運支出",
            value=f"NT$ {total_expense:,.0f}",
            delta=f"-NT$ {total_expense:,.0f}",
            delta_color="inverse",
        )
    with kc4:
        st.metric(
            label="營運總淨利",
            value=f"NT$ {net_profit:,.0f}",
            delta=f"{net_profit:+,.0f}",
        )

# ── 2. 財務操作與新增紀錄 (Dialog 彈窗) ──────────────────────────────────────────
@st.dialog("每月常態薪資試算", width="large")
def salary_dialog():
    st.caption("您可以在此表微調當月發放金額，下方會自動計算總額供您填入流水帳。若有常態性的變動（如調薪或新增員工），請點擊下方按鈕儲存。")
    conn = get_db_connection()
    try:
        df_salary_template = pd.read_sql("SELECT employee as 員工, amount as 發放金額 FROM dim_salary_template", conn)
    except:
        df_salary_template = pd.DataFrame(columns=["員工", "發放金額"])
    conn.close()
        
    edited_salary = st.data_editor(
        df_salary_template,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "發放金額": st.column_config.NumberColumn(
                "發放金額 (NT$)",
                format="$%d",
                step=100
            )
        }
    )
    
    total_salary = edited_salary['發放金額'].sum()
    st.info(f"**當月薪資總發放額：NT$ {total_salary:,.0f}**")
    
    if st.button("儲存為新預設名單", use_container_width=True, type="primary"):
        conn = get_db_connection()
        save_df = edited_salary.copy()
        save_df.columns = ['employee', 'amount']
        save_df.to_sql('dim_salary_template', conn, if_exists='replace', index=False)
        conn.close()
        st.success("已成功更新薪資預設名單！")
        st.rerun()

@st.dialog("新增收支紀錄", width="large")
def add_finance_record_dialog():
    with st.form("finance_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            f_date = st.date_input("日期", value=datetime.date.today())
            f_type = st.selectbox("收支類別", ["收入", "支出"])
        with col2:
            existing_cats = df_finance['category'].dropna().unique().tolist()
            existing_cats = [c for c in existing_cats if c.strip() != '']
            f_cat_select = st.selectbox("項目 (快速選擇)", ["- 手動輸入新項目 -"] + existing_cats)
            f_cat_manual = st.text_input("或手動輸入新項目", placeholder="例如：廣告費")
            
        with col3:
            f_amount = st.number_input("金額 (NT$)", value=0, step=100)
            f_note = st.text_input("備註 (選填)", placeholder="例如：買IG粉絲")
            
        submitted = st.form_submit_button("儲存紀錄", type="primary", use_container_width=True)
        
        if submitted:
            final_cat = f_cat_manual if f_cat_manual else (f_cat_select if f_cat_select != "- 手動輸入新項目 -" else "")
            if not final_cat:
                st.error("請輸入或選擇一個「項目」！")
            elif f_amount == 0:
                st.error("金額不能為 0！")
            else:
                if f_type == "支出" and f_amount > 0:
                    final_amount = -float(f_amount)
                else:
                    final_amount = float(f_amount)
                    
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO fact_finance (date, type, category, note, description, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f_date.strftime("%Y-%m-%d"), f_type, final_cat, f_note, "", final_amount))
                conn.commit()
                conn.close()
                st.success("紀錄已成功新增！")
                st.rerun()

with st.container(border=True):
    st.subheader(":material/settings: 財務操作面板")
    st.caption("點擊下方按鈕以展開對應的表單，填寫完成後會自動更新大盤。")
    
    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        if st.button(":material/payments: 每月薪資試算", use_container_width=True):
            salary_dialog()
    with col_btn2:
        if st.button(":material/add_circle: 新增收支紀錄", use_container_width=True, type="primary"):
            add_finance_record_dialog()

# ── 3. 視覺化圖表 ────────────────────────────────────────────────────
CHART_BG   = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(255,255,255,0.07)"
FONT_COLOR = "#7b809a"

with st.container(border=True):
    st.subheader(":material/trending_up: 財務趨勢與分佈")

    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("#### 月度現金流走勢")
        # 按月統計
        monthly_rev = df_ops[df_ops['amount'] > 0].groupby('ym')['amount'].sum().reset_index(name='收入')
        monthly_exp = df_ops[df_ops['amount'] < 0].groupby('ym')['amount'].sum().abs().reset_index(name='支出')
        monthly_df = pd.merge(monthly_rev, monthly_exp, on='ym', how='outer').fillna(0).sort_values('ym')
        monthly_df['淨利'] = monthly_df['收入'] - monthly_df['支出']
        
        fig1 = go.Figure()
        # 長條圖設定微圓角與精緻顏色
        fig1.add_trace(go.Bar(x=monthly_df['ym'], y=monthly_df['收入'], name='總收入', marker_color='#12b76a', marker=dict(line=dict(width=0), opacity=0.9)))
        fig1.add_trace(go.Bar(x=monthly_df['ym'], y=monthly_df['支出'], name='總支出', marker_color='#f04438', marker=dict(line=dict(width=0), opacity=0.9)))
        
        # 淨利折線圖升級：平滑曲線 (spline) 與半透明漸層
        fig1.add_trace(go.Scatter(
            x=monthly_df['ym'], y=monthly_df['淨利'], name='淨利', 
            line=dict(color='#0ba5ec', width=4, shape='spline'), 
            mode='lines+markers',
            marker=dict(size=8, symbol='circle', line=dict(width=2, color='#101828')),
            fill='tozeroy', fillcolor='rgba(11,165,236,0.1)'
        ))
        
        fig1.update_layout(
            barmode='group', 
            hovermode="x unified", 
            paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG, 
            margin=dict(t=20, b=20),
            legend=dict(font=dict(color=FONT_COLOR), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
            xaxis=dict(tickfont=dict(color=FONT_COLOR), showgrid=False, zeroline=False),
            yaxis=dict(tickfont=dict(color=FONT_COLOR), gridcolor=GRID_COLOR, zeroline=True, zerolinecolor=GRID_COLOR),
            font=dict(family="Outfit")
        )
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.markdown("#### 收支佔比分析")
        tab_rev, tab_exp = st.tabs([":material/arrow_circle_up: 收入來源佔比", ":material/arrow_circle_down: 支出去向佔比"])
        
        with tab_rev:
            rev_pie = df_ops[df_ops['amount'] > 0].groupby('category')['amount'].sum().reset_index()
            fig_r = px.pie(rev_pie, values='amount', names='category', hole=0.5, color_discrete_sequence=['#465fff', '#0ba5ec', '#12b76a', '#f79009', '#7b93ff'])
            fig_r.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#101828', width=2)))
            fig_r.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor=CHART_BG, font=dict(family="Outfit", color=FONT_COLOR), showlegend=False)
            st.plotly_chart(fig_r, use_container_width=True)
            
        with tab_exp:
            exp_pie = df_ops[df_ops['amount'] < 0].copy()
            exp_pie['amount'] = exp_pie['amount'].abs()
            exp_pie = exp_pie.groupby('category')['amount'].sum().reset_index()
            fig_e = px.pie(exp_pie, values='amount', names='category', hole=0.5, color_discrete_sequence=['#f04438', '#f79009', '#12b76a', '#0ba5ec', '#94a3b8'])
            fig_e.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#101828', width=2)))
            fig_e.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor=CHART_BG, font=dict(family="Outfit", color=FONT_COLOR), showlegend=False)
            st.plotly_chart(fig_e, use_container_width=True)

# ── 4. 流水帳表格 (支援直接編輯/新增/刪除) ────────────────────────────────────────────────
with st.container(border=True):
    st.subheader(":material/table_chart: 互動式流水帳總表")
    st.caption("操作提示：您可以直接在下方表格內雙擊修改文字、滑到最下方點擊 `+` 新增一筆紀錄，或是點選最左側的方塊後按下 `Delete` 鍵刪除整列。完成後點擊右下角的儲存按鈕。")

    df_display = df_finance.copy()
    df_display['date'] = df_display['date'].dt.strftime('%Y-%m-%d')
    df_display = df_display[['date', 'type', 'category', 'amount', 'note', 'description']].sort_values('date', ascending=False)

    # 將欄位名稱改為中文以方便編輯
    df_display.columns = ['日期', '類型', '項目', '金額', '備註', '說明']

    # 使用 data_editor (捨棄 pandas style 以保留點擊標頭排序的功能)
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="dynamic",
        height=500,
        key="finance_editor",
        column_config={
            "金額": st.column_config.NumberColumn(
                "金額",
                format="%d",
                step=100
            )
        }
    )

    # 提供儲存與匯出按鈕
    col_btn1, col_btn2, col_btn3 = st.columns([6, 2, 2])
    with col_btn2:
        csv_data = edited_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="匯出 CSV 備份",
            data=csv_data,
            file_name=f"finance_ledger_{datetime.date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_btn3:
        if st.button("儲存表格所有變更", type="primary", use_container_width=True):
            # 將欄位名稱改回英文對應資料庫
            edited_df.columns = ['date', 'type', 'category', 'amount', 'note', 'description']
            
            # 確保金額是數字格式
            edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0)
            
            # 寫回 SQLite
            conn = get_db_connection()
            edited_df.to_sql('fact_finance', conn, if_exists='replace', index=False)
            conn.close()
            
            st.success("所有變更已成功覆寫至資料庫！")
            st.rerun()
