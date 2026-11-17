#!/usr/bin/env python3
"""
starter_agent.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
agent ตั้งต้นแบบง่ายที่สุด (คล้าย starter ที่ผู้จัดจะแจก): ทุกรอบเสนอขายทุกล็อตให้ผู้ซื้อแบบสุ่ม
ที่ราคา = มูลค่าประเมิน ไม่ดูเงื่อนไข ไม่เรียนรู้ ใช้เป็นเส้นฐานเทียบกับ agent.py
  python starter_agent.py --team team_b --token token-team_b
"""
import argparse, random, time

from market_api import MarketAPI
from valuation import estimate_value

ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://127.0.0.1:8000')
ap.add_argument('--team', default='team_b')
ap.add_argument('--token', default='token-team_b')
a = ap.parse_args()

api = MarketAPI(a.url, a.token)
buyers = [b['id'] for b in api.buyers()]
done = 0
while True:
    st = api.state()                                   # ดู
    if st['finished']:
        for r in api.leaderboard():
            print(r)
        break
    if st['round'] != done:
        offers = []
        for lot in api.lots():                         # คิด
            if lot['status'] == 'unsold':
                offers.append({'lot_id': lot['lot_id'], 'buyer_id': random.choice(buyers),
                               'price_per_kg': estimate_value(lot['sample'])})
        if offers:
            api.submit(st['round'], offers)            # ทำ
        print(f"รอบ {st['round']}: ส่ง {len(offers)} ข้อเสนอ")
        done = st['round']
    time.sleep(1)
