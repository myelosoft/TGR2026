#!/usr/bin/env python3
"""
convert_labels.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
แปลง label แบบ JSON ของ X-AnyLabeling / LabelMe (ไฟล์ .json คู่กับภาพ) เป็นรูปแบบ YOLO
  python convert_labels.py --src data/day2_labeled --out data/day2_yolo --task seg --val 0.2
  --task seg  ใช้ polygon (rectangle จะถูกแปลงเป็น polygon 4 จุด)
  --task det  ใช้กรอบสี่เหลี่ยม (polygon จะถูกแปลงเป็นกรอบที่ครอบ)
ถ้าผู้จัดให้ label แบบ COCO (.json ไฟล์เดียว) ให้ใช้:
  from ultralytics.data.converter import convert_coco
  convert_coco('annotations_dir', use_segments=True)
"""
import argparse, json, random, shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True, help='โฟลเดอร์ที่มีภาพและ .json คู่กัน')
ap.add_argument('--out', required=True)
ap.add_argument('--task', choices=['seg', 'det'], default='seg')
ap.add_argument('--classes', default=None, help='ไฟล์ข้อความ 1 คลาสต่อบรรทัด (ไม่ใส่ = เรียงตามตัวอักษร)')
ap.add_argument('--val', type=float, default=0.2)
ap.add_argument('--seed', type=int, default=0)
a = ap.parse_args()
random.seed(a.seed)

src, out = Path(a.src), Path(a.out)
jsons = sorted(src.rglob('*.json'))
if not jsons:
    raise SystemExit('ไม่พบไฟล์ .json')
data = [(j, json.loads(j.read_text(encoding='utf-8'))) for j in jsons]
if a.classes:
    classes = [c.strip() for c in Path(a.classes).read_text(encoding='utf-8').splitlines() if c.strip()]
else:
    classes = sorted({s['label'] for _, d in data for s in d.get('shapes', [])})
print('classes:', classes)
shutil.rmtree(out, ignore_errors=True)
for s in ['train', 'val']:
    (out / 'images' / s).mkdir(parents=True)
    (out / 'labels' / s).mkdir(parents=True)

random.shuffle(data)
nval = max(1, int(len(data) * a.val)) if len(data) > 1 else 0
counts = {c: 0 for c in classes}
for i, (j, d) in enumerate(data):
    split = 'val' if i < nval else 'train'
    img = j.parent / Path(d.get('imagePath', j.stem + '.jpg')).name
    if not img.exists():
        cand = [p for p in j.parent.glob(j.stem + '.*') if p.suffix.lower() != '.json']
        if not cand:
            print('  ไม่พบภาพของ', j.name)
            continue
        img = cand[0]
    W, H = d['imageWidth'], d['imageHeight']
    lines = []
    for s in d.get('shapes', []):
        if s['label'] not in classes:
            continue
        pts = s['points']
        if s.get('shape_type') == 'rectangle' and len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        if len(pts) < 3:
            continue
        cid = classes.index(s['label'])
        xs = [min(max(p[0] / W, 0), 1) for p in pts]
        ys = [min(max(p[1] / H, 0), 1) for p in pts]
        if a.task == 'det':
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            lines.append(f'{cid} {(x0 + x1) / 2:.6f} {(y0 + y1) / 2:.6f} {x1 - x0:.6f} {y1 - y0:.6f}')
        else:
            lines.append(f'{cid} ' + ' '.join(f'{x:.6f} {y:.6f}' for x, y in zip(xs, ys)))
        counts[s['label']] += 1
    shutil.copy(img, out / 'images' / split / img.name)
    (out / 'labels' / split / (img.stem + '.txt')).write_text('\n'.join(lines) + '\n')

yaml = [f'path: {out.resolve()}', 'train: images/train', 'val: images/val', f'nc: {len(classes)}', 'names:']
yaml += [f'  {i}: {c}' for i, c in enumerate(classes)]
(out / 'data.yaml').write_text('\n'.join(yaml) + '\n')
print('instance ต่อคลาส:', counts)
print('data.yaml ->', out / 'data.yaml')
