"""
valuation.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
1) ประเมินมูลค่าล็อตจากผลวัดตัวอย่าง  2) อ่านความต้องการของผู้ซื้อ
>>> วันที่ 17 ผู้จัดจะสอนสูตรจริง ให้แทนที่ฟังก์ชัน estimate_value() ด้วยสูตรนั้น <<<
"""
import re

from pydantic import BaseModel, Field, ValidationError


def estimate_value(sample, base_price=130.0):
    """มูลค่าโดยประมาณ (บาท/kg) สูตรสมมติ: ความชื้นเกิน 12.5% หัก 4%/หน่วย, เมล็ดเสียหัก 1.2 เท่า, cupping +1.5%/คะแนน"""
    m, d, c = sample['moisture_pct'], sample['defect_ratio'], sample['cupping_score']
    f_m = 1.0 - 0.04 * max(0.0, m - 12.5) - 0.02 * max(0.0, 9.5 - m)
    f_d = 1.0 - 1.2 * d
    f_c = 1.0 + 0.015 * (min(max(c, 70), 88) - 78)
    return round(base_price * f_m * f_d * f_c, 2)


class Requirement(BaseModel):
    """ความต้องการของผู้ซื้อในรูปตัวเลข (pydantic ตรวจชนิดและช่วงค่าให้)"""
    max_moisture: float = Field(default=14.0, ge=8, le=20)
    max_defect: float = Field(default=1.0, ge=0, le=1)        # สัดส่วน 0–1
    min_cup: float = Field(default=0, ge=0, le=100)
    price_level: str = Field(default='market', pattern='^(premium|market|low)$')
    source: str = 'default'


def parse_requirement_rules(text):
    """อ่านเงื่อนไขด้วย regex (ทางสำรองที่ไม่ต้องใช้ LLM)"""
    out = {}
    m = re.search(r'ความชื้น[^0-9]{0,15}([0-9]+(?:\.[0-9]+)?)\s*%', text)
    if m:
        out['max_moisture'] = float(m.group(1))
    m = re.search(r'(?:เมล็ดเสีย|ข้อบกพร่อง|defect)[^0-9]{0,15}([0-9]+(?:\.[0-9]+)?)\s*%', text, re.I)
    if m:
        out['max_defect'] = float(m.group(1)) / 100
    m = re.search(r'cupping[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)', text, re.I)
    if m:
        out['min_cup'] = float(m.group(1))
    if re.search(r'พรีเมียม|premium|ดีกว่าตลาด', text, re.I):
        out['price_level'] = 'premium'
    elif re.search(r'ต่ำกว่าตลาด|ราคาถูก|เน้นปริมาณ', text):
        out['price_level'] = 'low'
    return out


SYSTEM = ('You extract buyer requirements for green coffee. Reply with ONLY a JSON object with keys: '
          'max_moisture (percent number), max_defect_pct (percent number), min_cup (number, 0 if none), '
          'price_level ("premium", "market" or "low"). Use null when not stated.')


def parse_requirement(text, llm=None):
    """LLM อ่านก่อน -> ตรวจค่า -> ถ้าขาด/ผิด ใช้ regex เติม -> ถ้ายังไม่มี ใช้ค่าเริ่มต้น"""
    rules = parse_requirement_rules(text)
    data, src = {}, 'rules'
    if llm is not None:
        j = llm.chat_json(SYSTEM, text)
        if isinstance(j, dict):
            if j.get('max_moisture') is not None:
                data['max_moisture'] = j['max_moisture']
            if j.get('max_defect_pct') is not None:
                data['max_defect'] = float(j['max_defect_pct']) / 100
            if j.get('min_cup') is not None:
                data['min_cup'] = j['min_cup']
            if j.get('price_level') in ('premium', 'market', 'low'):
                data['price_level'] = j['price_level']
            src = 'llm'
    for k, v in rules.items():
        if k not in data:
            data[k] = v
        elif k != 'price_level' and abs(float(data[k]) - v) > 1e-6:
            data[k] = v                       # ตัวเลขที่ regex อ่านได้ชัดเจน เชื่อ regex มากกว่า LLM เล็ก
            src = 'llm+rules'
    try:
        return Requirement(**data, source=src)
    except ValidationError:
        return Requirement(**rules, source='rules')
