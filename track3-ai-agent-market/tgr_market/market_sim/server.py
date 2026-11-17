#!/usr/bin/env python3
"""
market_sim/server.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
ตลาดกาแฟจำลองสำหรับซ้อม (เดาจากสไลด์ Pre-Camp ไม่ใช่ตลาดจริงของผู้จัด)

เริ่มเซิร์ฟเวอร์:
  python market_sim/server.py --teams team_a,team_b --rounds 10 --round-seconds 30 --seed 1
แล้วเปิด http://127.0.0.1:8000 (ขายด้วยมือ) และ http://127.0.0.1:8000/docs (ดู API ทั้งหมด)

กติกาย่อ:
  - ทุกทีม (รวม bot) มีล็อตกาแฟ ทีมเห็นแค่ "ผลวัดตัวอย่าง" ซึ่งมีความคลาดเคลื่อน มูลค่าจริงถูกซ่อนไว้
  - แต่ละรอบ ส่งข้อเสนอแบบปิดซอง: 1 ล็อตเสนอได้ 1 ผู้ซื้อต่อรอบ พร้อมราคาต่อ kg
  - ผู้ซื้อแต่ละรายมีเงื่อนไข (เขียนเป็นข้อความ) และรับได้จำกัดล็อตต่อรอบ
    จะรับข้อเสนอที่ผ่านเงื่อนไข และราคาไม่เกินราคาที่ตัวเองยอมจ่าย โดยเลือกข้อเสนอที่คุ้มที่สุดก่อน
  - จบเกม ล็อตที่ขายไม่ออกถูกขายทิ้งให้พ่อค้าคนกลางที่ 60% ของมูลค่าจริง
  - คะแนน = รายได้รวม / มูลค่าจริงรวม (มากกว่า 1 ได้ ถ้าขายให้ผู้ซื้อที่ให้ราคาพรีเมียม)
"""
import argparse, asyncio, json, random, time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

BASE_PRICE = 130.0           # บาท/kg (สมมติ)
SALVAGE = 0.60               # ขายทิ้งตอนจบเกม = 60% ของมูลค่าจริง

BUYER_TYPES = [
    # id, ชื่อ, คำบรรยาย (ข้อความ), เงื่อนไขจริง, ตัวคูณราคาที่ยอมจ่าย, ความไวต่อคุณภาพ, จำนวนล็อตต่อรอบ
    ('B1', 'Specialty Roaster ชุมพร',
     'โรงคั่วกาแฟพิเศษ รับเฉพาะล็อตที่ความชื้นไม่เกิน 12% เมล็ดเสียไม่เกิน 8% และคะแนน cupping 82 ขึ้นไป '
     'ยินดีจ่ายราคาพรีเมียมสำหรับของดีจริง รับได้รอบละไม่เกิน 2 ล็อต',
     {'max_moisture': 12.0, 'max_defect': 0.08, 'min_cup': 82}, 1.25, 1.0, 2),
    ('B2', 'Commercial Roaster กรุงเทพ',
     'โรงคั่วเชิงพาณิชย์ ต้องการความชื้นไม่เกิน 13% เมล็ดเสียไม่เกิน 20% ไม่กำหนดคะแนน cupping '
     'ราคากลางตลาด รับได้รอบละ 3 ล็อต',
     {'max_moisture': 13.0, 'max_defect': 0.20, 'min_cup': 0}, 1.05, 0.8, 3),
    ('B3', 'โรงงานกาแฟสำเร็จรูป',
     'โรงงานกาแฟสำเร็จรูป รับของได้แทบทุกเกรด ความชื้นไม่เกิน 14% เมล็ดเสียไม่เกิน 35% '
     'เน้นปริมาณ ให้ราคาต่ำกว่าตลาดเล็กน้อย รับได้รอบละ 5 ล็อต',
     {'max_moisture': 14.0, 'max_defect': 0.35, 'min_cup': 0}, 0.92, 0.4, 5),
    ('B4', 'ผู้ส่งออกเมล็ดกาแฟ',
     'ผู้ส่งออก ต้องการความชื้นไม่เกิน 12.5% เมล็ดเสียไม่เกิน 12% คะแนน cupping 78 ขึ้นไป '
     'ให้ราคาดีกว่าตลาดในประเทศ รับได้รอบละ 3 ล็อต',
     {'max_moisture': 12.5, 'max_defect': 0.12, 'min_cup': 78}, 1.12, 0.9, 3),
]


def true_value(lot):
    """มูลค่าจริงต่อ kg (ซ่อนจากผู้เล่น) จากคุณสมบัติจริงของล็อต"""
    m, d, c = lot['moisture'], lot['defect'], lot['cup']
    f_m = 1.0 - 0.04 * max(0.0, m - 12.5) - 0.02 * max(0.0, 9.5 - m)
    f_d = 1.0 - 1.2 * d
    f_c = 0.85 + 0.015 * (min(max(c, 70), 88) - 78) + 0.15
    return round(BASE_PRICE * f_m * f_d * f_c, 2)


def eligible(req, lot):
    return lot['moisture'] <= req['max_moisture'] and lot['defect'] <= req['max_defect'] and lot['cup'] >= req['min_cup']


class Offer(BaseModel):
    lot_id: str
    buyer_id: str
    price_per_kg: float = Field(gt=0)


class OfferBatch(BaseModel):
    round: int
    offers: list[Offer]


class Market:
    def __init__(self, teams, n_bots, lots_per_team, rounds, round_seconds, seed):
        self.rng = random.Random(seed)
        self.rounds, self.round_seconds = rounds, round_seconds
        self.teams = {t: f'token-{t}' for t in teams}
        self.bots = [f'bot_{i + 1}' for i in range(n_bots)]
        self.round = 1
        self.finished = False
        self.deadline = time.time() + round_seconds
        self.lots = {}
        self.offers = {}            # team -> list[Offer] ของรอบปัจจุบัน
        self.history = []           # ผลทุกรอบ
        self.buyers = [{'id': b[0], 'name': b[1], 'description': b[2], 'req': b[3], 'mult': b[4],
                        'sens': b[5], 'capacity': b[6]} for b in BUYER_TYPES]
        k = 0
        for owner in list(self.teams) + self.bots:
            for _ in range(lots_per_team):
                k += 1
                lot = {'moisture': round(self.rng.uniform(10.0, 13.8), 2),
                       'defect': round(self.rng.betavariate(2, 9), 3),
                       'cup': round(self.rng.uniform(74, 86), 1)}
                lot.update({'id': f'L{k:03d}', 'owner': owner, 'kg': self.rng.choice([200, 300, 500, 800, 1000]),
                            'value': true_value(lot), 'status': 'unsold', 'sold_to': None, 'price': None,
                            'sample': {'moisture_pct': round(lot['moisture'] + self.rng.gauss(0, 0.3), 1),
                                       'defect_ratio': round(min(max(lot['defect'] + self.rng.gauss(0, 0.02), 0), 1), 3),
                                       'cupping_score': round(lot['cup'] + self.rng.gauss(0, 1.0), 1)}})
                self.lots[lot['id']] = lot

    # ---------- buyers ----------
    def reserve(self, buyer, lot):
        """ราคาสูงสุดที่ผู้ซื้อยอมจ่ายต่อ kg (ซ่อน) แกว่ง ±8% ทุกรอบ"""
        q = lot['value'] / BASE_PRICE
        wtp = BASE_PRICE * buyer['mult'] * (1 - buyer['sens'] + buyer['sens'] * q)
        return wtp * self.rng.uniform(0.92, 1.08)

    # ---------- bots ----------
    def bot_offers(self, bot):
        out = []
        style = int(bot.split('_')[1]) % 3
        for lot in self.lots.values():
            if lot['owner'] != bot or lot['status'] != 'unsold':
                continue
            est = true_value({'moisture': lot['sample']['moisture_pct'], 'defect': lot['sample']['defect_ratio'],
                              'cup': lot['sample']['cupping_score']})
            ok = [b for b in self.buyers if eligible(b['req'], {'moisture': lot['sample']['moisture_pct'],
                  'defect': lot['sample']['defect_ratio'], 'cup': lot['sample']['cupping_score']})]
            if not ok:
                continue
            if style == 0:      # ตั้งราคาสูงคงที่ ขายให้ผู้ซื้อที่จ่ายดีที่สุด
                b = max(ok, key=lambda x: x['mult'])
                price = est * 1.15
            elif style == 1:    # ขายถูก ขายให้โรงงาน
                b = min(ok, key=lambda x: x['mult'])
                price = est * 0.92
            else:               # สุ่ม
                b = self.rng.choice(ok)
                price = est * self.rng.uniform(0.95, 1.2)
            out.append(Offer(lot_id=lot['id'], buyer_id=b['id'], price_per_kg=round(price, 2)))
        return out

    # ---------- clearing ----------
    def clear_round(self):
        for bot in self.bots:
            self.offers[bot] = self.bot_offers(bot)
        result = {'round': self.round, 'offers': [], 'market': {}}
        for buyer in self.buyers:
            cands = []
            for team, offs in self.offers.items():
                for o in offs:
                    lot = self.lots.get(o.lot_id)
                    if o.buyer_id != buyer['id'] or not lot or lot['owner'] != team or lot['status'] != 'unsold':
                        continue
                    ok = eligible(buyer['req'], lot)
                    r = self.reserve(buyer, lot)
                    cands.append((team, o, lot, ok, r))
            accepted = sorted([c for c in cands if c[3] and c[1].price_per_kg <= c[4]],
                              key=lambda c: c[1].price_per_kg / c[4])[:buyer['capacity']]
            acc_ids = {c[1].lot_id for c in accepted}
            prices = []
            for team, o, lot, ok, r in cands:
                won = o.lot_id in acc_ids
                reason = 'sold' if won else ('not_eligible' if not ok else ('price_too_high' if o.price_per_kg > r
                                                                             else 'buyer_full'))
                if won:
                    lot.update(status='sold', sold_to=buyer['id'], price=o.price_per_kg)
                    prices.append(o.price_per_kg)
                result['offers'].append({'team': team, 'lot_id': o.lot_id, 'buyer_id': buyer['id'],
                                         'price_per_kg': o.price_per_kg, 'result': reason})
            result['market'][buyer['id']] = {'offers_received': len(cands), 'bought': len(prices),
                                            'min_price': min(prices) if prices else None,
                                            'max_price': max(prices) if prices else None}
        self.history.append(result)
        self.offers = {}
        if self.round >= self.rounds:
            self.finished = True
            for lot in self.lots.values():
                if lot['status'] == 'unsold':
                    lot.update(status='salvage', price=round(lot['value'] * SALVAGE, 2))
        else:
            self.round += 1
            self.deadline = time.time() + self.round_seconds

    def score(self, team):
        mine = [l for l in self.lots.values() if l['owner'] == team]
        val = sum(l['value'] * l['kg'] for l in mine)
        rev = sum((l['price'] or 0) * l['kg'] for l in mine if l['status'] in ('sold', 'salvage'))
        return {'team': team, 'revenue': round(rev), 'true_value': round(val) if self.finished else None,
                'score': round(rev / val, 4) if self.finished else None,
                'sold': sum(l['status'] == 'sold' for l in mine), 'lots': len(mine)}


app = FastAPI(title='TGR2026 Practice Coffee Market', version='1.0')
M: Market = None
LOCK = asyncio.Lock()


def team_of(token):
    for t, tok in M.teams.items():
        if tok == token:
            return t
    raise HTTPException(401, 'token ไม่ถูกต้อง (ใช้ header X-Team-Token)')


@app.get('/api/state')
def state():
    return {'round': M.round, 'max_rounds': M.rounds, 'finished': M.finished,
            'seconds_left': max(0, round(M.deadline - time.time(), 1)),
            'submitted': sorted(t for t in M.offers if t in M.teams)}


@app.get('/api/buyers')
def buyers():
    return [{'id': b['id'], 'name': b['name'], 'description': b['description'], 'capacity_per_round': b['capacity']}
            for b in M.buyers]


@app.get('/api/lots')
def lots(x_team_token: str = Header(...)):
    t = team_of(x_team_token)
    return [{'lot_id': l['id'], 'kg': l['kg'], 'sample': l['sample'], 'status': l['status'],
             'sold_to': l['sold_to'], 'price_per_kg': l['price']} for l in M.lots.values() if l['owner'] == t]


@app.post('/api/offers')
async def offers(batch: OfferBatch, x_team_token: str = Header(...)):
    t = team_of(x_team_token)
    async with LOCK:
        if M.finished:
            raise HTTPException(409, 'เกมจบแล้ว')
        if batch.round != M.round:
            raise HTTPException(409, f'ตอนนี้เป็นรอบ {M.round} ไม่ใช่รอบ {batch.round}')
        seen, clean = set(), []
        for o in batch.offers:
            lot = M.lots.get(o.lot_id)
            if not lot or lot['owner'] != t:
                raise HTTPException(400, f'{o.lot_id} ไม่ใช่ล็อตของทีม')
            if lot['status'] != 'unsold':
                raise HTTPException(400, f'{o.lot_id} ขายไปแล้ว')
            if o.lot_id in seen:
                raise HTTPException(400, f'{o.lot_id} เสนอได้ครั้งเดียวต่อรอบ')
            if o.buyer_id not in {b['id'] for b in M.buyers}:
                raise HTTPException(400, f'ไม่มีผู้ซื้อ {o.buyer_id}')
            seen.add(o.lot_id)
            clean.append(o)
        M.offers[t] = clean                               # ส่งซ้ำในรอบเดียวกัน = แทนที่ของเดิม
        if set(M.offers) >= set(M.teams):                 # ทุกทีมส่งแล้ว ปิดรอบทันที
            M.clear_round()
    return {'ok': True, 'round': batch.round, 'accepted_offers': len(clean)}


@app.get('/api/results')
def results(round: int, x_team_token: str = Header(...)):
    t = team_of(x_team_token)
    if round < 1 or round > len(M.history):
        raise HTTPException(404, 'ยังไม่มีผลของรอบนี้')
    h = M.history[round - 1]
    return {'round': round, 'my_offers': [o for o in h['offers'] if o['team'] == t], 'market': h['market']}


@app.get('/api/leaderboard')
def leaderboard():
    rows = [M.score(t) for t in list(M.teams) + M.bots]
    return sorted(rows, key=lambda r: -(r['score'] or r['revenue']))


@app.post('/admin/next')
async def admin_next():
    async with LOCK:
        if not M.finished:
            M.clear_round()
    return state()


@app.get('/', response_class=HTMLResponse)
def page():
    return (Path(__file__).parent / 'manual.html').read_text(encoding='utf-8')


async def ticker():
    while True:
        await asyncio.sleep(0.5)
        if not M.finished and time.time() >= M.deadline:
            async with LOCK:
                if not M.finished and time.time() >= M.deadline:
                    M.clear_round()


@app.on_event('startup')
async def start_ticker():
    asyncio.create_task(ticker())


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--teams', default='team_a', help='รายชื่อทีมคั่นด้วยจุลภาค (token = token-<ทีม>)')
    ap.add_argument('--bots', type=int, default=3)
    ap.add_argument('--lots', type=int, default=6, help='จำนวนล็อตต่อทีม')
    ap.add_argument('--rounds', type=int, default=10)
    ap.add_argument('--round-seconds', type=float, default=30)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8000)
    a = ap.parse_args()
    M = Market(a.teams.split(','), a.bots, a.lots, a.rounds, a.round_seconds, a.seed)
    print('ทีมและ token:', json.dumps(M.teams, ensure_ascii=False))
    uvicorn.run(app, host=a.host, port=a.port, log_level='warning')
