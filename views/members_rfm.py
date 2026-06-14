import streamlit as st
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.member_rfm_analysis import render_behavior_analysis

st.title(":material/monitoring: RFM 留存與流失分析")
st.caption("透過 RFM 模型了解會員健康度，識別高風險流失會員並擬定再行銷策略。")
st.divider()

render_behavior_analysis()
