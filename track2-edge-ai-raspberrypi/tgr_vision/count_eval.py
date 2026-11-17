#!/usr/bin/env python3
"""
count_eval.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
เทียบ "จำนวนเมล็ดต่อคลาส" ที่โมเดลนับได้ (results.jsonl จาก predict_pi.py) กับ label จริง (YOLO txt)
เพราะโจทย์ต้องการจำนวนและสัดส่วนเมล็ดเสีย ไม่ใช่แค่ mAP
  python count_eval.py --pred runs_B/results.jsonl --labels data/day2_yolo/labels/val --yaml data/day2_yolo/data.yaml
"""
import argparse, json, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--pred', required=True)
ap.add_argument('--labels', required=True, help='โฟลเดอร์ label YOLO (.txt) ของภาพชุดเดียวกัน')
ap.add_argument('--yaml', required=True, help='data.yaml ที่มี names')
ap.add_argument('--good', default='good')
a = ap.parse_args()

names = {}
for ln in Path(a.yaml).read_text(encoding='utf-8').splitlines():
    m = re.match(r'\s+(\d+):\s*(\S+)', ln)
    if m:
        names[int(m.group(1))] = m.group(2)
cls = [names[k] for k in sorted(names)]

preds = {}
for ln in Path(a.pred).read_text(encoding='utf-8').splitlines():
    r = json.loads(ln)
    preds[Path(r['image_id']).stem] = r
err = {c: [] for c in cls}
rows = []
for lf in sorted(Path(a.labels).glob('*.txt')):
    if lf.stem not in preds:
        continue
    gt = {c: 0 for c in cls}
    for ln in lf.read_text().splitlines():
        if ln.strip():
            gt[names[int(ln.split()[0])]] += 1
    pc = preds[lf.stem].get('counts', {})
    for c in cls:
        err[c].append(abs(pc.get(c, 0) - gt[c]))
    tot_gt, tot_p = sum(gt.values()), sum(pc.get(c, 0) for c in cls)
    dr_gt = (tot_gt - gt.get(a.good, 0)) / tot_gt if tot_gt else 0
    dr_p = (tot_p - pc.get(a.good, 0)) / tot_p if tot_p else 0
    rows.append((lf.stem, tot_gt, tot_p, dr_gt, dr_p))

if not rows:
    raise SystemExit('ไม่พบภาพที่ตรงกันระหว่าง pred กับ labels (ชื่อไฟล์ต้องตรงกัน)')
print(f'{"image":28s} {"gt":>5s} {"pred":>5s} {"defect_gt":>10s} {"defect_pred":>12s}')
for s, g, p, dg, dp in rows:
    print(f'{s:28s} {g:5d} {p:5d} {dg:10.3f} {dp:12.3f}')
print('\nค่าเฉลี่ยความคลาดเคลื่อนของจำนวน (MAE) ต่อคลาส ต่อภาพ:')
for c in cls:
    print(f'  {c:14s} {sum(err[c]) / len(err[c]):6.2f} เมล็ด')
print(f'ความคลาดเคลื่อนเฉลี่ยของสัดส่วนเมล็ดเสีย: {sum(abs(dp - dg) for *_, dg, dp in rows) / len(rows):.3f}')
