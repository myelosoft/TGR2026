"""
strategy.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
ส่วน "คิด" ของ agent: เลือกผู้ซื้อ ตั้งราคา และเรียนรู้จากผลรอบก่อน (ไม่ใช้ LLM คำนวณตัวเลข)

หลักการ
  เก็บ "ช่วงอัตราส่วน ราคา/มูลค่า" ที่ผู้ซื้อแต่ละรายน่าจะยอมจ่าย [lo, hi]
    ขายได้ที่อัตรา x     -> lo ขยับขึ้นเป็น x (และเปิด hi ให้ลองสูงขึ้น)
    แพงเกินที่อัตรา x    -> hi ลดลงเป็น x
    ผู้ซื้อเต็ม          -> hi ลดลงเล็กน้อย (คู่แข่งถูกกว่า)
    ไม่ผ่านเงื่อนไข      -> ไม่เสนอคู่ล็อต–ผู้ซื้อนี้อีก
  ราคาเสนอ = มูลค่า x จุดในช่วง [lo, hi]: รอบแรกใกล้ hi (อดทน) รอบท้ายเลื่อนลงหา lo (ขายให้ได้)
"""
from valuation import estimate_value


class Strategy:
    def __init__(self, cfg, buyers, reqs):
        self.cfg = cfg
        self.buyers = {b['id']: b for b in buyers}
        self.reqs = reqs                                       # buyer_id -> Requirement
        band = cfg['prior_band']                               # ช่วงอัตราส่วน ราคา/มูลค่า ที่คาดว่าผู้ซื้อยอมจ่าย
        self.lo = {bid: band[r.price_level][0] for bid, r in reqs.items()}
        self.hi = {bid: band[r.price_level][1] for bid, r in reqs.items()}
        self.banned = set()                                    # (lot_id, buyer_id) ที่ไม่ผ่านเงื่อนไข
        self.values = {}                                       # lot_id -> มูลค่าประเมิน

    def remember(self, lots):
        """จำมูลค่าประเมินของทุกล็อต (ใช้ตอนรีสตาร์ต เพื่อเรียนรู้จากผลรอบเก่าได้)"""
        for lot in lots:
            self.values[lot['lot_id']] = estimate_value(lot['sample'], self.cfg['base_price'])

    def eligible(self, lot, bid):
        s, r, m = lot['sample'], self.reqs[bid], self.cfg['safety']
        return (s['moisture_pct'] + m['moisture'] <= r.max_moisture and
                s['defect_ratio'] + m['defect'] <= r.max_defect and
                s['cupping_score'] - m['cup'] >= r.min_cup and (lot['lot_id'], bid) not in self.banned)

    def update(self, results):
        """เรียนรู้ช่วงราคาของผู้ซื้อแต่ละรายจากผลรอบที่แล้ว (คล้ายการค้นหาแบบแบ่งครึ่ง)"""
        gap = self.cfg['min_gap']
        for o in results.get('my_offers', []):
            bid, res = o['buyer_id'], o['result']
            v = self.values.get(o['lot_id'])
            if bid not in self.lo or not v:
                continue
            x = o['price_per_kg'] / v                          # อัตราส่วนที่เสนอไป
            if res == 'sold':                                  # ขายได้ = ผู้ซื้อยอมจ่ายอย่างน้อย x
                self.lo[bid] = max(self.lo[bid], x)
                self.hi[bid] = max(self.hi[bid], x + gap)      # อาจตั้งต่ำไป เปิดช่องให้ลองสูงขึ้น
            elif res == 'price_too_high':                      # แพงเกิน = ผู้ซื้อจ่ายไม่ถึง x
                self.hi[bid] = min(self.hi[bid], x)
                self.lo[bid] = min(self.lo[bid], self.hi[bid] - gap)
            elif res == 'buyer_full':                          # มีคู่แข่งที่ถูกกว่า
                self.hi[bid] = max(self.lo[bid] + gap, self.hi[bid] - gap / 2)
            elif res == 'not_eligible':
                self.banned.add((o['lot_id'], bid))

    def ask_ratio(self, bid, round_no, max_rounds):
        """รอบแรก ๆ ตั้งใกล้ขอบบน (อดทนรอราคาดี) ใกล้จบค่อยเลื่อนลงหาขอบล่าง"""
        c = self.cfg
        left = max_rounds - round_no                           # รอบที่เหลือหลังรอบนี้
        if left == 0:
            return max(self.lo[bid] * c['last_round_factor'], c['floor'])
        frac = left / max_rounds
        aggr = c['aggr_end'] + (c['aggr_start'] - c['aggr_end']) * frac
        return max(self.lo[bid] + (self.hi[bid] - self.lo[bid]) * aggr, c['floor'])

    def decide(self, lots, round_no, max_rounds):
        c = self.cfg
        used = {bid: 0 for bid in self.buyers}
        offers, notes = [], []
        unsold = [l for l in lots if l['status'] == 'unsold']
        for lot in unsold:
            self.values[lot['lot_id']] = estimate_value(lot['sample'], c['base_price'])
        for lot in sorted(unsold, key=lambda l: -self.values[l['lot_id']] * l['kg']):   # ล็อตมูลค่ามากเลือกก่อน
            v = self.values[lot['lot_id']]
            options = [(self.ask_ratio(bid, round_no, max_rounds), bid) for bid in self.buyers
                       if self.eligible(lot, bid) and used[bid] < self.buyers[bid]['capacity_per_round']]
            if not options:
                notes.append({'lot_id': lot['lot_id'], 'value': v, 'decision': 'no eligible buyer'})
                continue
            ratio, bid = max(options)
            used[bid] += 1
            price = round(v * ratio, 2)
            offers.append({'lot_id': lot['lot_id'], 'buyer_id': bid, 'price_per_kg': price})
            notes.append({'lot_id': lot['lot_id'], 'value': v, 'buyer_id': bid, 'ratio': round(ratio, 3),
                          'price_per_kg': price, 'band': [round(self.lo[bid], 3), round(self.hi[bid], 3)]})
        return offers, notes
