import streamlit as st
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.member_demographics import render_member_demographics

st.title(":material/group: 會員管道分佈與資料維護")
st.caption("查看各來源管道的會員組成，並對會員名單進行管理與維護。")
st.divider()

render_member_demographics()
