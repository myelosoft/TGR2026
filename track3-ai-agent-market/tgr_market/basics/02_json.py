# 02_json.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
# JSON คือข้อความที่หน้าตาเหมือน dict/list ของ Python ใช้รับส่งข้อมูลกับ API
import json

text = '{"lot_id": "L001", "kg": 500, "sample": {"moisture_pct": 11.8, "defect_ratio": 0.06}}'
data = json.loads(text)                 # ข้อความ JSON -> dict
print(type(data), data["sample"]["defect_ratio"])

offer = {"lot_id": "L001", "buyer_id": "B2", "price_per_kg": 136.4}
print(json.dumps(offer, ensure_ascii=False))   # dict -> ข้อความ JSON

with open("my_offer.json", "w", encoding="utf-8") as f:   # เขียนลงไฟล์
    json.dump(offer, f, ensure_ascii=False, indent=2)
with open("my_offer.json", encoding="utf-8") as f:        # อ่านจากไฟล์
    print("อ่านกลับ:", json.load(f))

# TODO: แปลงข้อความ '[{"id":"B1","capacity_per_round":2},{"id":"B2","capacity_per_round":3}]'
#       เป็น list แล้วหาผลรวม capacity_per_round
