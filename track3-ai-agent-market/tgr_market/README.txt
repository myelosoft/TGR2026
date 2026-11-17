TGR2026 Track 3 · AI Agent ขายกาแฟใน Next-Gen Market (ชุดฝึก)
ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE
สำหรับเตรียมตัวก่อนไปแข่งขัน ไม่ใช่เนื้อหาโจทย์จริงจากผู้จัด (ตลาด สูตร และ API เป็นการคาดเดา)

ติดตั้ง:   python -m venv venv  ->  เปิด venv  ->  pip install -r requirements.txt

basics/                 แบบฝึก Python, JSON, REST API สำหรับผู้เริ่มต้น (04_lab1_practice.py = แบบฝึก Lab 1)
market_sim/server.py    ตลาดจำลอง (หน้าเว็บขายด้วยมือ http://127.0.0.1:8000, เอกสาร API /docs)
agent/config.json       ค่าทั้งหมดของ agent (แก้ระหว่างแข่งได้)
agent/market_api.py     ส่วนเดียวที่คุยกับตลาด (วันที่ 17 แก้ไฟล์นี้ให้ตรงกับ API จริง)
agent/llm_client.py     เรียก LLM แบบ OpenAI-compatible (Ollama หรือของผู้จัด)
agent/valuation.py      ประเมินมูลค่าล็อต + อ่านความต้องการผู้ซื้อ (LLM + regex สำรอง)
agent/strategy.py       เลือกผู้ซื้อ ตั้งราคา เรียนรู้ช่วงราคาของผู้ซื้อ
agent/agent.py          ลูปหลัก ดู-คิด-ทำ + log
agent/starter_agent.py  agent ตั้งต้นแบบสุ่ม (เส้นฐาน)
agent/dashboard.py      หน้าจอเฝ้า agent (streamlit run dashboard.py)
backtest.py             จำลองหลายสิบเกมเพื่อเทียบกลยุทธ์

สถานะการทดสอบ (12 พ.ย. 2569): ตลาดจำลอง, agent (รวมการรีสตาร์ตกลางเกม), starter, backtest, dashboard และ basics รันจริงแล้ว
LLM ทดสอบกับเซิร์ฟเวอร์จำลองแบบ OpenAI-compatible ยังไม่ได้ทดสอบกับ Ollama จริงและ LLM ของผู้จัด
