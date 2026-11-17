#!/usr/bin/env python3
"""
agent.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
วงจร ดู -> คิด -> ทำ จนจบเกม  ใช้:  python agent.py   (อ่านค่าจาก config.json)

กันพัง: ทุกรอบครอบด้วย try/except, agent ไม่หยุดเพราะ error ครั้งเดียว
แก้ค่าระหว่างแข่ง: แก้ config.json แล้วบันทึก agent จะโหลดค่ากลยุทธ์ใหม่เองในรอบถัดไป
log: logs/decisions.jsonl (ทุกการตัดสินใจ), logs/offers.csv (ผลทุกข้อเสนอ) ใช้กับ dashboard.py
"""
import csv, json, os, time
from pathlib import Path

from llm_client import LLM
from market_api import MarketAPI
from strategy import Strategy
from valuation import parse_requirement

HERE = Path(__file__).parent
CFG = HERE / 'config.json'
LOG = HERE / 'logs'


def load_cfg():
    return json.loads(CFG.read_text(encoding='utf-8'))


def log_json(name, rec):
    with open(LOG / name, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def log_offers(rows):
    p = LOG / 'offers.csv'
    new = not p.exists()
    with open(p, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['round', 'lot_id', 'buyer_id', 'price_per_kg', 'result'])
        for r in rows:
            w.writerow([r['round'], r['lot_id'], r['buyer_id'], r['price_per_kg'], r['result']])


def main():
    LOG.mkdir(exist_ok=True)
    cfg = load_cfg()
    mtime = os.path.getmtime(CFG)
    api = MarketAPI(cfg['base_url'], cfg['token'])
    llm = LLM(cfg['llm'])

    print('อ่านความต้องการของผู้ซื้อ...')
    buyers = api.buyers()
    reqs = {}
    for b in buyers:
        reqs[b['id']] = parse_requirement(b['description'], llm)
        print(f"  {b['id']}: {reqs[b['id']]}")
    strat = Strategy(cfg['strategy'], buyers, reqs)
    log_json('decisions.jsonl', {'event': 'buyers', 'reqs': {k: v.model_dump() for k, v in reqs.items()}})

    done_round, learned_round, rnd = 0, 0, 0
    while True:
        try:
            if os.path.getmtime(CFG) != mtime:                      # แก้ config ระหว่างแข่ง
                mtime = os.path.getmtime(CFG)
                try:
                    strat.cfg = load_cfg()['strategy']
                    print('  [config] โหลดค่ากลยุทธ์ใหม่แล้ว')
                except (json.JSONDecodeError, KeyError) as e:
                    print('  [config] ไฟล์ผิดรูป ใช้ค่าเดิมต่อ:', e)
            st = api.state()
            rnd = st['round']
            # เรียนรู้จากรอบที่ผลออกแล้ว
            last_done = st['max_rounds'] if st['finished'] else rnd - 1
            if learned_round < last_done:
                strat.remember(api.lots())                      # มีมูลค่าของทุกล็อตก่อนเรียนรู้ (สำคัญตอนรีสตาร์ต)
            while learned_round < last_done:
                learned_round += 1
                res = api.results(learned_round)
                strat.update(res)
                log_offers([{**o, 'round': learned_round} for o in res['my_offers']])
                sold = sum(o['result'] == 'sold' for o in res['my_offers'])
                band = {k: f'{strat.lo[k]:.2f}-{strat.hi[k]:.2f}' for k in strat.lo}
                print(f"รอบ {learned_round}: ขายได้ {sold}/{len(res['my_offers'])}  ช่วงราคา/มูลค่า={band}")
            if st['finished']:
                lb = api.leaderboard()
                print('\nจบเกม ตารางคะแนน:')
                for r in lb:
                    print(f"  {r['team']:10s} score={r['score']}  ขายได้ {r['sold']}/{r['lots']}")
                log_json('decisions.jsonl', {'event': 'final', 'leaderboard': lb})
                break
            if rnd != done_round:                                   # รอบใหม่ ยังไม่ได้ส่ง
                lots = api.lots()
                offers, notes = strat.decide(lots, rnd, st['max_rounds'])
                if offers:
                    api.submit(rnd, offers)
                done_round = rnd
                log_json('decisions.jsonl', {'event': 'decide', 'round': rnd, 'notes': notes,
                                             'llm_calls': llm.calls, 'llm_fails': llm.fails})
                print(f'รอบ {rnd}: ส่ง {len(offers)} ข้อเสนอ')
        except ValueError as e:                                     # คำขอผิด (เช่น ส่งผิดรอบ) ข้ามรอบนี้
            print('  [ผิดพลาด]', e)
            done_round = rnd
        except Exception as e:                                      # เครือข่าย/อื่น ๆ รอแล้วลองใหม่
            print('  [ขัดข้อง]', type(e).__name__, e)
            time.sleep(2)
        time.sleep(cfg.get('poll_seconds', 1.0))


if __name__ == '__main__':
    main()
