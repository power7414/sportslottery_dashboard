import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sqlite3
import datetime

st.set_page_config(page_title="財務紀錄與現金流", page_icon="", layout="wide")

DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"
if not DB_PATH.exists():
    st.warning("找不到資料庫，請先執行資料同步！")
    st.stop()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

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

st.title(" 財務紀錄與現金流大盤")

# ── 1. KPI 卡片 (置頂) ─────────────────────────────────────────────────────
st.markdown("###  大盤財務現況")
kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric(" 當前手頭現金 (含初始資金)", f"NT$ {current_cash:,.0f}")
kc2.metric(" 總營運收入", f"NT$ {total_revenue:,.0f}")
kc3.metric(" 總營運支出", f"NT$ {total_expense:,.0f}")
kc4.metric(" 營運總淨利", f"NT$ {net_profit:,.0f}", delta=f"{net_profit:,.0f}")

st.markdown("---")

# ── 1.5 每月常態薪資試算 ──────────────────────────────────────────────────
st.markdown("###  每月薪資試算表")
with st.expander(" 點擊展開薪資試算", expanded=False):
    st.markdown(" 您可以在此表微調當月發放金額，下方會自動計算總額供您填入流水帳。若有常態性的變動（如調薪或新增員工），請點擊右方按鈕儲存。")
    
    # 讀取資料庫預設名單
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
    
    col_s1, col_s2 = st.columns([7, 3])
    with col_s1:
        total_salary = edited_salary['發放金額'].sum()
        st.info(f"** 當月薪資總發放額：NT$ {total_salary:,.0f}**")
    with col_s2:
        if st.button(" 儲存為新預設名單", use_container_width=True):
            conn = get_db_connection()
            save_df = edited_salary.copy()
            save_df.columns = ['employee', 'amount']
            save_df.to_sql('dim_salary_template', conn, if_exists='replace', index=False)
            conn.close()
            st.success(" 已成功更新薪資預設名單！")
            st.rerun()

st.markdown("---")

# ── 2. 新增收支表單 ──────────────────────────────────────────────────
st.markdown("###  新增收支紀錄")
with st.expander(" 點擊展開新增紀錄表單", expanded=False):
    with st.form("finance_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            f_date = st.date_input("日期", value=datetime.date.today())
            f_type = st.selectbox("收支類別", ["收入", "支出"])
        with col2:
            # 抓取歷史項目供選擇，並允許自己輸入
            existing_cats = df_finance['category'].dropna().unique().tolist()
            existing_cats = [c for c in existing_cats if c.strip() != '']
            f_cat_select = st.selectbox("項目 (快速選擇)", ["- 手動輸入新項目 -"] + existing_cats)
            f_cat_manual = st.text_input("或手動輸入新項目", placeholder="例如：廣告費")
            
        with col3:
            f_amount = st.number_input("金額 (NT$)", value=0, step=100)
            f_note = st.text_input("備註 (選填)", placeholder="例如：買IG粉絲")
            
        submitted = st.form_submit_button(" 儲存紀錄")
        
        if submitted:
            final_cat = f_cat_manual if f_cat_manual else (f_cat_select if f_cat_select != "- 手動輸入新項目 -" else "")
            if not final_cat:
                st.error(" 請輸入或選擇一個「項目」！")
            elif f_amount == 0:
                st.error(" 金額不能為 0！")
            else:
                # 寫入資料庫 (如果選擇支出，且輸入正數，則自動轉負；若輸入負數則保留原意)
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
                st.success(" 紀錄已成功新增！")
                st.rerun()

st.markdown("---")

# ── 3. 視覺化圖表 ────────────────────────────────────────────────────
st.markdown("###  財務趨勢與分佈")

c1, c2 = st.columns([3, 2])

with c1:
    st.markdown("#### 月度現金流走勢")
    # 按月統計
    monthly_rev = df_ops[df_ops['amount'] > 0].groupby('ym')['amount'].sum().reset_index(name='收入')
    monthly_exp = df_ops[df_ops['amount'] < 0].groupby('ym')['amount'].sum().abs().reset_index(name='支出')
    monthly_df = pd.merge(monthly_rev, monthly_exp, on='ym', how='outer').fillna(0).sort_values('ym')
    monthly_df['淨利'] = monthly_df['收入'] - monthly_df['支出']
    
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=monthly_df['ym'], y=monthly_df['收入'], name='總收入', marker_color='#34d399'))
    fig1.add_trace(go.Bar(x=monthly_df['ym'], y=monthly_df['支出'], name='總支出', marker_color='#f87171'))
    fig1.add_trace(go.Scatter(x=monthly_df['ym'], y=monthly_df['淨利'], name='淨利', line=dict(color='#fbbf24', width=3), mode='lines+markers'))
    
    fig1.update_layout(barmode='group', hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20))
    fig1.update_yaxes(gridcolor="#334155")
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    st.markdown("#### 收支佔比分析")
    tab_rev, tab_exp = st.tabs([" 收入來源佔比", " 支出去向佔比"])
    
    with tab_rev:
        rev_pie = df_ops[df_ops['amount'] > 0].groupby('category')['amount'].sum().reset_index()
        fig_r = px.pie(rev_pie, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        fig_r.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_r, use_container_width=True)
        
    with tab_exp:
        exp_pie = df_ops[df_ops['amount'] < 0].copy()
        exp_pie['amount'] = exp_pie['amount'].abs()
        exp_pie = exp_pie.groupby('category')['amount'].sum().reset_index()
        fig_e = px.pie(exp_pie, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_e.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_e, use_container_width=True)

st.markdown("---")

# ── 4. 流水帳表格 (支援直接編輯/新增/刪除) ────────────────────────────────────────────────
st.markdown("###  互動式流水帳總表")
st.markdown(" **操作提示**：您可以直接在下方表格內雙擊修改文字、滑到最下方點擊 `+` 新增一筆紀錄，或是點選最左側的方塊後按下 `Delete` 鍵刪除整列。完成後點擊右下角的儲存按鈕。")

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

# 提供儲存按鈕
col_btn1, col_btn2 = st.columns([8, 2])
with col_btn2:
    if st.button(" 儲存表格所有變更", type="primary", use_container_width=True):
        # 將欄位名稱改回英文對應資料庫
        edited_df.columns = ['date', 'type', 'category', 'amount', 'note', 'description']
        
        # 確保金額是數字格式
        edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0)
        
        # 寫回 SQLite
        conn = get_db_connection()
        edited_df.to_sql('fact_finance', conn, if_exists='replace', index=False)
        conn.close()
        
        st.success(" 所有變更已成功覆寫至資料庫！")
        st.rerun()
