# 04_lab1_practice.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
# แบบฝึก Lab 1 ขั้นที่ 3: เขียนคำตอบต่อท้ายไฟล์นี้
lots = [
    {"lot_id": "L001", "kg": 500, "sample": {"moisture_pct": 11.8, "defect_ratio": 0.06, "cupping_score": 83}},
    {"lot_id": "L002", "kg": 300, "sample": {"moisture_pct": 13.1, "defect_ratio": 0.18, "cupping_score": 76}},
    {"lot_id": "L003", "kg": 800, "sample": {"moisture_pct": 12.2, "defect_ratio": 0.10, "cupping_score": 80}},
]

# 1) พิมพ์ lot_id ของล็อตที่ความชื้นไม่เกิน 12% และเมล็ดเสียไม่เกิน 8% (ผ่านเกณฑ์โรงคั่วพิเศษ)
# 2) เขียนฟังก์ชัน value(sample) = 130 * (1 - 1.2 * defect_ratio) แล้วพิมพ์มูลค่าต่อ kg ของทุกล็อต
# 3) หามูลค่ารวมของทุกล็อต (มูลค่าต่อ kg x kg) แล้วพิมพ์ทศนิยม 2 ตำแหน่ง
