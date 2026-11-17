"""
dashboard.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
หน้าจอเฝ้า agent ระหว่างแข่ง อ่านจาก logs/ ที่ agent.py เขียนไว้
  streamlit run dashboard.py      (เปิดเบราว์เซอร์ที่ http://localhost:8501 แล้วกด "รีเฟรช")
"""
import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

HERE = Path(__file__).parent
LOG = HERE / 'logs'
cfg = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))

st.set_page_config(page_title='TGR2026 Agent Monitor', layout='wide')
st.title('TGR2026 Track 3 · Agent Monitor')
st.caption('ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE · สำหรับเตรียมตัวก่อนไปแข่งขัน')
st.button('รีเฟรช')

col = st.columns(4)
try:
    s = requests.get(cfg['base_url'] + '/api/state', timeout=3).json()
    col[0].metric('รอบ', f"{s['round']}/{s['max_rounds']}")
    col[1].metric('เวลาที่เหลือ (s)', s['seconds_left'])
except Exception as e:
    col[0].warning(f'ต่อตลาดไม่ได้: {e}')

offers_p = LOG / 'offers.csv'
if offers_p.exists():
    df = pd.read_csv(offers_p)
    sold = df[df['result'] == 'sold']
    col[2].metric('ข้อเสนอทั้งหมด', len(df))
    col[3].metric('ขายได้', f'{len(sold)} ({len(sold) / max(len(df), 1):.0%})')
    left, right = st.columns(2)
    left.subheader('ผลต่อรอบ')
    left.bar_chart(df.groupby(['round', 'result']).size().unstack(fill_value=0))
    right.subheader('ผลต่อผู้ซื้อ')
    right.bar_chart(df.groupby(['buyer_id', 'result']).size().unstack(fill_value=0))
    st.subheader('ข้อเสนอล่าสุด')
    st.dataframe(df.tail(20).iloc[::-1], width='stretch')
else:
    st.info('ยังไม่มี logs/offers.csv (รัน agent.py ก่อน)')

dec_p = LOG / 'decisions.jsonl'
if dec_p.exists():
    recs = [json.loads(l) for l in dec_p.read_text(encoding='utf-8').splitlines() if l.strip()]
    last = [r for r in recs if r.get('event') == 'decide']
    if last:
        st.subheader(f"การตัดสินใจรอบล่าสุด (รอบ {last[-1]['round']})  · LLM เรียก {last[-1]['llm_calls']} "
                     f"ครั้ง ล้มเหลว {last[-1]['llm_fails']} ครั้ง")
        st.dataframe(pd.DataFrame(last[-1]['notes']), width='stretch')
try:
    st.subheader('ตารางคะแนน')
    st.dataframe(pd.DataFrame(requests.get(cfg['base_url'] + '/api/leaderboard', timeout=3).json()),
                 width='stretch')
except Exception:
    pass
