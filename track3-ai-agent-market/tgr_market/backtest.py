#!/usr/bin/env python3
"""
backtest.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
จำลองหลายเกมแบบไม่ผ่านเครือข่าย (เร็วมาก) เพื่อเทียบกลยุทธ์ก่อนใช้จริง
  python backtest.py --games 30                      # ใช้ agent/config.json
  python backtest.py --games 30 --set patience=0.25  # ลองเปลี่ยนค่าทีละตัว
คะแนน = รายได้ / มูลค่าจริง (ยิ่งมากยิ่งดี) เทียบกับ starter (สุ่มผู้ซื้อ ขายที่มูลค่าประเมิน) และ bot 3 แบบ
"""
import argparse, json, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path[:0] = [str(HERE / 'market_sim'), str(HERE / 'agent')]
import server                                           # noqa: E402
from server import Market, Offer                        # noqa: E402
from strategy import Strategy                           # noqa: E402
from valuation import parse_requirement, estimate_value  # noqa: E402


def lots_view(M, team):
    return [{'lot_id': l['id'], 'kg': l['kg'], 'sample': l['sample'], 'status': l['status']}
            for l in M.lots.values() if l['owner'] == team]


def play(seed, cfg, rounds, lots):
    M = Market(['agent', 'starter'], 3, lots, rounds, 1e9, seed)
    server.M = M
    buyers = [{'id': b['id'], 'name': b['name'], 'description': b['description'],
               'capacity_per_round': b['capacity']} for b in M.buyers]
    st = Strategy(cfg, buyers, {b['id']: parse_requirement(b['description']) for b in buyers})
    rng = random.Random(seed)
    while not M.finished:
        r = M.round
        if r > 1:
            st.update({'my_offers': [o for o in M.history[r - 2]['offers'] if o['team'] == 'agent']})
        offers, _ = st.decide(lots_view(M, 'agent'), r, M.rounds)
        M.offers['agent'] = [Offer(**o) for o in offers]
        M.offers['starter'] = [Offer(lot_id=l['lot_id'], buyer_id=rng.choice(buyers)['id'],
                                     price_per_kg=estimate_value(l['sample']))
                               for l in lots_view(M, 'starter') if l['status'] == 'unsold']
        M.clear_round()
    return {t: M.score(t)['score'] for t in ['agent', 'starter'] + M.bots}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=30)
    ap.add_argument('--rounds', type=int, default=10)
    ap.add_argument('--lots', type=int, default=6)
    ap.add_argument('--set', nargs='*', default=[], help='เปลี่ยนค่าใน strategy เช่น patience=0.2 step_up=0.05')
    a = ap.parse_args()
    cfg = json.loads((HERE / 'agent' / 'config.json').read_text(encoding='utf-8'))['strategy']
    for kv in a.set:
        k, v = kv.split('=')
        cfg[k] = float(v)
    allres = [play(s, cfg, a.rounds, a.lots) for s in range(a.games)]
    print(f'{a.games} เกม, {a.rounds} รอบ, ล็อตละทีม {a.lots}  ค่าที่เปลี่ยน: {a.set or "-"}')
    for t in allres[0]:
        xs = [r[t] for r in allres]
        print(f'  {t:8s} คะแนนเฉลี่ย {statistics.mean(xs):.4f}  (ต่ำสุด {min(xs):.3f} สูงสุด {max(xs):.3f})')
    wins = sum(r['agent'] == max(r.values()) for r in allres)
    beat = sum(r['agent'] > r['starter'] for r in allres)
    print(f'  agent ได้ที่ 1: {wins}/{a.games} เกม  | ชนะ starter: {beat}/{a.games} เกม')
