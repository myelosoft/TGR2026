# 03_rest_api.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
# คุยกับตลาดจำลองด้วย GET / POST (เปิด python market_sim/server.py ไว้ก่อน)
import requests

BASE = "http://127.0.0.1:8000"
HEAD = {"X-Team-Token": "token-team_a"}       # บอกตลาดว่าเราเป็นทีมไหน

state = requests.get(BASE + "/api/state", timeout=5).json()           # GET = ขอดูข้อมูล
print("รอบ", state["round"], "จาก", state["max_rounds"], "เหลือ", state["seconds_left"], "วินาที")

buyers = requests.get(BASE + "/api/buyers", timeout=5).json()
for b in buyers:
    print(b["id"], b["name"], "-", b["description"][:60], "...")

lots = requests.get(BASE + "/api/lots", headers=HEAD, timeout=5).json()
for l in lots:
    print(l["lot_id"], l["kg"], "kg", l["sample"], l["status"])

# POST = ส่งข้อมูล: เสนอขายล็อตแรกให้ B2 ที่ราคา 130 บาท/kg
body = {"round": state["round"], "offers": [{"lot_id": lots[0]["lot_id"], "buyer_id": "B2", "price_per_kg": 130}]}
r = requests.post(BASE + "/api/offers", json=body, headers=HEAD, timeout=5)
print("สถานะ", r.status_code, r.json())

# TODO 1: รอให้รอบนี้จบ แล้วดูผลด้วย GET /api/results?round=<รอบ> (อย่าลืม headers=HEAD)
# TODO 2: ลองส่งล็อตที่ไม่ใช่ของทีม แล้วอ่านข้อความ error ที่ตลาดตอบกลับมา
