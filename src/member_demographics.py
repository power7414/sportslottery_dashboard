import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path


def render_member_demographics():

    DB_PATH = Path(__file__).parent.parent / "processed" / "betting_data.db"

    if not DB_PATH.exists():
        st.warning("找不到資料庫，請先執行資料同步！")
        st.stop()

    # 顯示跨 rerun 的 Toast 提示
    if "toast_msg" in st.session_state:
        msg, icon = st.session_state.toast_msg
        st.toast(msg, icon=icon if icon else None)
        del st.session_state.toast_msg

    def get_db_connection():
        return sqlite3.connect(DB_PATH, timeout=30)

    @st.cache_data
    def load_and_process_data():
        # Force cache invalidation 2026-05-07
        conn = get_db_connection()
        dim = pd.read_sql("SELECT * FROM dim_member", conn, dtype={'phone': str})

        fact_bets = pd.read_sql("""
            SELECT member_id as bet_member_id, 
                   date,
                   bet_amount
            FROM fact_daily_bets 
        """, conn)
        conn.close()

        # 建立對應字典
        mapping = {}
        for _, row in dim.iterrows():
            b_id = str(row['backend_id']).strip() if pd.notna(row['backend_id']) else ''
            m_id = str(row['member_id']).strip() if pd.notna(row['member_id']) else ''
            c = row['channel'] if pd.notna(row['channel']) and str(row['channel']).strip() != '' else '未分類'
            jd = row['join_date'] if pd.notna(row['join_date']) else None

            if b_id: mapping[b_id] = (c, jd)
            if m_id: mapping[m_id] = (c, jd)

        # --- 處理未標記會員 & 計算摘要 ---
        fact_summary = fact_bets.groupby('bet_member_id').agg(
            first_bet_date=('date', 'min'),
            last_active_date=('date', 'max'),
            total_bet=('bet_amount', 'sum'),
            active_days=('date', 'nunique')
        ).reset_index()

        def resolve_member(m_id, first_bet_date):
            m_id = str(m_id).strip()
            if m_id in mapping:
                c, jd = mapping[m_id]
                final_jd = jd if pd.notna(jd) else first_bet_date
                return pd.Series([c, final_jd, True])
            else:
                return pd.Series(['未標記', first_bet_date, False])

        fact_summary[['channel', 'join_date', 'is_known']] = fact_summary.apply(
            lambda r: resolve_member(r['bet_member_id'], r['first_bet_date']), axis=1
        )

        # 建立統整的新增會員 DataFrame (含未標記)
        unified_members = []

        # 建立一個字典加速查詢已知會員的首投日
        first_bet_dict = dict(zip(fact_summary['bet_member_id'], fact_summary['first_bet_date']))

        # 先加入已知的
        for _, row in dim.iterrows():
            b_id = str(row['backend_id']).strip() if pd.notna(row['backend_id']) else ''
            m_id = str(row['member_id']).strip() if pd.notna(row['member_id']) else ''
            c = row['channel'] if pd.notna(row['channel']) and str(row['channel']).strip() != '' else '未分類'
            jd = row['join_date']
            uid = m_id if m_id else b_id

            # 如果主檔沒有加入日期，嘗試從投注紀錄 (first_bet_date) 中尋找替補
            if pd.isna(jd) or str(jd).strip() in ('', 'None', 'nan'):
                jd = first_bet_dict.get(m_id) or first_bet_dict.get(b_id)

            unified_members.append({'uid': uid, 'channel': c, 'join_date': jd})

        # 再加入未標記的
        unmapped = fact_summary[~fact_summary['is_known']]
        for _, row in unmapped.iterrows():
            unified_members.append({'uid': row['bet_member_id'], 'channel': '未標記', 'join_date': row['first_bet_date']})

        df_unified = pd.DataFrame(unified_members)
        # 修正 Pandas 解析混合日期格式 (2025/5/31 vs 2025-03-09) 會產生 NaT 的問題
        df_unified['join_date'] = pd.to_datetime(df_unified['join_date'].astype(str).str.replace('/', '-'), errors='coerce')
        df_unified = df_unified.dropna(subset=['join_date'])
        df_unified['ym'] = df_unified['join_date'].dt.strftime('%Y-%m')

        # --- 計算每月管道投注額 ---
        fact_bets['ym'] = pd.to_datetime(fact_bets['date']).dt.strftime('%Y-%m')
        fact_bets['channel'] = fact_bets['bet_member_id'].apply(lambda x: mapping.get(str(x).strip(), ('未標記', None))[0])
        monthly_bet_by_channel = fact_bets.groupby(['ym', 'channel'])['bet_amount'].sum().reset_index()

        return dim, df_unified, fact_summary, monthly_bet_by_channel, unmapped

    dim_members, df_unified, fact_summary, monthly_bet_by_channel, df_unmapped = load_and_process_data()

    # ── 1. 管道分析圖表 ────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader(":material/monitoring: 每月新增會員與管道營收分析")
        tab1, tab2 = st.tabs([":material/person_add: 新增會員數量分析", ":material/payments: 管道帶來的投注額分析"])

        # 管道顏色
        COLORS = {
            '米勒叔叔':             '#465fff',
            '盈吉多台灣運彩線上投注站':  '#0ba5ec',
            'NBA_TA':              '#12b76a',
            '盈吉多籃球':            '#f79009',
            '盈吉多棒球':            '#f04438',
            '未標記':             '#94a3b8',
            '未分類':             '#667085',
            '其他':               '#344054',
        }

        with tab1:
            months_list = sorted(df_unified['ym'].unique())[-12:]
            df_chart = df_unified[df_unified['ym'].isin(months_list)]

            st.caption("每個月份新增會員人數，依管道堆疊；未標記包含未同意第三方之會員")

            # 寬格式: ym 為索引，各管道為欄位
            channel_pivot = (
                df_chart
                .groupby(['ym', 'channel'])
                .size()
                .unstack(fill_value=0)
            )

            ch_cols = list(channel_pivot.columns)
            colors  = [COLORS.get(c, '#888888') for c in ch_cols]

            st.bar_chart(
                channel_pivot,
                color=colors,
                stack=True,
                use_container_width=True,
            )

        with tab2:
            st.caption("各管道每月創造之總投注額，可評估行銷 ROI")
            months_bet  = sorted(monthly_bet_by_channel['ym'].unique())[-12:]
            df_bet_chart = monthly_bet_by_channel[monthly_bet_by_channel['ym'].isin(months_bet)]

            bet_pivot = (
                df_bet_chart
                .groupby(['ym', 'channel'])['bet_amount'].sum()
                .unstack(fill_value=0)
            )
            ch_bet_cols = list(bet_pivot.columns)
            bet_colors  = [COLORS.get(c, '#888888') for c in ch_bet_cols]

            st.bar_chart(
                bet_pivot,
                color=bet_colors,
                stack=True,
                use_container_width=True,
            )

    st.divider()

    # ── 2. 新增/編輯會員表單 ───────────────────────────────────────
    with st.container(border=True):
        st.subheader(":material/manage_accounts: 會員名單管理")
        st.caption("有時候 Excel 沒抓到新會員的管道，或者圖表上出現「未標記」，您可以在這裡直接手動新增或補齊。")

        def save_member_callback():
            m_id = st.session_state.get("f_member", "")
            m_name = st.session_state.get("f_name", "")
            m_channel = st.session_state.get("f_channel", "其他")
            m_date = st.session_state.get("f_join_date")
            m_note = st.session_state.get("f_note", "")

            if not m_id:
                st.session_state.toast_msg = ("請輸入「會員代號」", "⚠️")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT backend_id FROM dim_member WHERE backend_id = ? OR member_id = ?", (m_id, m_id))
                exists = cursor.fetchone()
                date_str = m_date.strftime('%Y-%m-%d') if m_date else None

                # 自動生成 backend_id：取名字最後一個字 + 數字代碼的後五碼
                b_id = None
                if m_name and str(m_id).strip().isdigit() and len(m_id) >= 5:
                    b_id = m_name.strip()[-1] + m_id.strip()[-5:]

                if exists:
                    if b_id:
                        cursor.execute("""
                            UPDATE dim_member 
                            SET backend_id=?, name=?, channel=?, join_date=?, phone=? 
                            WHERE backend_id=? OR member_id=?
                        """, (b_id, m_name, m_channel, date_str, m_note, m_id, m_id))
                    else:
                        cursor.execute("""
                            UPDATE dim_member 
                            SET name=?, channel=?, join_date=?, phone=? 
                            WHERE backend_id=? OR member_id=?
                        """, (m_name, m_channel, date_str, m_note, m_id, m_id))
                    st.session_state.toast_msg = ("已成功更新會員資料！", "✅")
                else:
                    cursor.execute("""
                        INSERT INTO dim_member (backend_id, member_id, name, channel, join_date, phone)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (b_id, m_id, m_name, m_channel, date_str, m_note))
                    st.session_state.toast_msg = ("已成功新增會員！", "✅")

                conn.commit()
                conn.close()
                load_and_process_data.clear()

                # 在 Callback 階段清空欄位 (Streamlit 允許在此階段修改 widget state)
                st.session_state.f_member = ""
                st.session_state.f_name = ""
                st.session_state.f_note = ""

            except Exception as e:
                st.session_state.toast_msg = (f"寫入資料庫失敗：{e}", "❌")

        with st.expander("手動新增 / 編輯會員資料", expanded=False):
            for k in ["f_member", "f_name", "f_note"]:
                if k not in st.session_state:
                    st.session_state[k] = ""

            col1, col2 = st.columns(2)
            with col1:
                member_id = st.text_input("會員代號 (必填)", placeholder="請貼上表格中的代號 (如: 851382213 或 林X明12345)", key="f_member")

                # 即時搜尋與提示
                if member_id:
                    m_id_str = str(member_id).strip()
                    dim_match = dim_members[(dim_members['member_id'].astype(str) == m_id_str) | (dim_members['backend_id'].astype(str) == m_id_str)]
                    fact_match = fact_summary[fact_summary['bet_member_id'].astype(str) == m_id_str]

                    if not dim_match.empty:
                        info = dim_match.iloc[0]
                        st.info(f"主檔已存在此會員\n\n管道：`{info['channel']}` | 姓名：`{info.get('name', '')}`")
                    elif not fact_match.empty:
                        f_info = fact_match.iloc[0]
                        st.warning(f"發現未標記的投注紀錄！\n\n首次下注：`{f_info['first_bet_date']}` | 總投注額：`${f_info['total_bet']:,.0f}`")
                    else:
                        st.success("這是一筆全新的會員資料，目前查無任何下注紀錄。")

                name = st.text_input("真實姓名 (選填)", key="f_name")
            with col2:
                existing_channels = set(dim_members['channel'].dropna().unique())
                default_channels = {"盈吉多籃球", "盈吉多棒球", "小凱", "小蝦", "其他"}
                all_channels = sorted(list(existing_channels | default_channels))

                channel = st.selectbox("管道來源", options=all_channels, key="f_channel")
                join_date = st.date_input("加入會員日期", key="f_join_date")
                note = st.text_input("備註 / 電話", placeholder="選填", key="f_note")

            st.button("儲存會員資料", type="primary", on_click=save_member_callback)

    st.markdown("---")

    # ── 3. 會員資料表 ────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader(":material/groups: 會員名單總覽")

        tab_all, tab_unmapped = st.tabs([":material/search: 全庫名單 (可搜尋)", ":material/assignment_late: 待標記之活躍會員 (優先處理)"])

        with tab_all:
            st.caption("提示：您可以直接在下方表格內雙擊修改文字，或是滑到最下方 `+` 新增列、選取後按 `Delete` 刪除。完成後請點擊「儲存表格變更」。")

            col_search, col_save = st.columns([7, 3])
            with col_search:
                search_query = st.text_input("快速搜尋會員", placeholder="請輸入代號、管道、電話等關鍵字...")

            if search_query:
                mask = dim_members.astype(str).apply(lambda col: col.str.contains(search_query, case=False, na=False)).any(axis=1)
                filtered_members = dim_members[mask]
            else:
                filtered_members = dim_members

            edited_members = st.data_editor(
                filtered_members,
                use_container_width=True,
                num_rows="dynamic",
                key="member_editor",
                height=500,
                column_config={
                    "phone": st.column_config.TextColumn(
                        "phone",
                        help="輸入電話號碼，將以純文字儲存，保留開頭的 0"
                    )
                }
            )

            with col_save:
                st.write("") # 排版對齊用
                st.write("")
                if st.button("儲存表格變更", type="primary", use_container_width=True):
                    try:
                        # 為了避免在「搜尋狀態」下覆寫掉沒被搜到的會員，這裡採用智慧合併更新
                        updated_full_df = dim_members.copy()

                        # 1. 更新有被編輯的列
                        updated_full_df.update(edited_members)

                        # 2. 加入在表格最下方全新新增的列
                        new_rows = edited_members[~edited_members.index.isin(dim_members.index)]
                        if not new_rows.empty:
                            updated_full_df = pd.concat([updated_full_df, new_rows])

                        # 3. 刪除在畫面上被刪除的列
                        deleted_indices = set(filtered_members.index) - set(edited_members.index)
                        if deleted_indices:
                            updated_full_df = updated_full_df.drop(index=list(deleted_indices))

                        # 寫入資料庫前，過濾掉因介面編輯產生的 'nan' 字串
                        updated_full_df = updated_full_df.replace({'nan': None, 'None': None, '': None})

                        conn = get_db_connection()
                        updated_full_df.to_sql('dim_member', conn, if_exists='replace', index=False)
                        conn.close()

                        load_and_process_data.clear() # 清除快取
                        st.session_state.toast_msg = ("會員名單已成功覆寫至資料庫！", "✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"儲存表格失敗：{e}")

        with tab_unmapped:
            st.caption("這些是「**有下注紀錄，但尚未歸類管道**」的野生會員。系統以他們的第一筆下注日作為加入日期。請複製代號到上方的表單幫他們建檔。")
            df_u_show = df_unmapped.sort_values('total_bet', ascending=False)
            df_u_show.columns = ['會員代號', '首次下注日 (推測加入日)', '最後活躍日', '歷史總投注額', '活躍天數', '管道', '加入日', '已知']
            df_u_show = df_u_show[['會員代號', '歷史總投注額', '首次下注日 (推測加入日)', '最後活躍日', '活躍天數']]

            st.dataframe(
                df_u_show,
                use_container_width=True,
                column_config={
                    "歷史總投注額": st.column_config.NumberColumn(
                        "歷史總投注額",
                        format="$%d",
                        help="總投注金額"
                    )
                }
            )
