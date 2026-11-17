# 01_python_basics.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
# รันด้วย: python basics/01_python_basics.py   แล้วทำแบบฝึกที่มีคำว่า TODO

# 1) ตัวแปรและชนิดข้อมูล
team = "team_a"            # str ข้อความ
round_no = 3               # int จำนวนเต็ม
price = 135.5              # float ทศนิยม
sold = False               # bool จริง/เท็จ
print("ทีม", team, "รอบ", round_no, "ราคา", price, "ขายได้?", sold)

# 2) list = รายการเรียงลำดับ
lots = ["L001", "L002", "L003"]
print("ล็อตแรก:", lots[0], "จำนวนล็อต:", len(lots))
lots.append("L004")

# 3) dict = กล่องเก็บค่าคู่ ชื่อ -> ค่า (หน้าตาเหมือน JSON)
lot = {"lot_id": "L001", "kg": 500, "sample": {"moisture_pct": 11.8, "defect_ratio": 0.06, "cupping_score": 83}}
print("ความชื้น:", lot["sample"]["moisture_pct"])

# 4) if / else
if lot["sample"]["moisture_pct"] <= 12:
    print("ผ่านเกณฑ์ความชื้นของโรงคั่วพิเศษ")
else:
    print("ความชื้นสูงเกิน")

# 5) for loop
for lot_id in lots:
    print("กำลังดูล็อต", lot_id)

# 6) ฟังก์ชัน
def value_per_kg(moisture, defect, base=130):
    """มูลค่าต่อ kg แบบง่าย"""
    v = base * (1 - 1.2 * defect)
    if moisture > 12.5:
        v = v * (1 - 0.04 * (moisture - 12.5))
    return round(v, 2)

print("มูลค่า:", value_per_kg(11.8, 0.06), "บาท/kg")

# TODO 1: เขียนฟังก์ชัน total_value(kg, price_per_kg) คืนค่ารวม แล้ว print ค่าของล็อต 500 kg ที่ 140 บาท/kg
# TODO 2: สร้าง list ของ dict 3 ล็อต (มี lot_id, kg) แล้วใช้ for หาน้ำหนักรวม
# TODO 3: ใช้ if เลือกพิมพ์เฉพาะล็อตที่ kg >= 500
