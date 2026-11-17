#!/usr/bin/env python3
"""
synth_piles.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)

สร้าง "กองเมล็ดสังเคราะห์" จาก cutout ที่ได้จาก bean_extract.py
วางเมล็ดซ้อนกันเป็นกองบนพื้นหลังไม้ แล้วเขียน label YOLO-seg ที่หักส่วนที่ถูกบังออกแล้ว
ใช้ลดช่องว่างระหว่าง "ภาพเทรนที่วางเรียง" กับ "ภาพทดสอบที่เป็นกอง"

  --mode single  ภาพละ 1 คลาส (เลียนแบบภาพทดสอบวันที่ 1–2)
  --mode mixed   คละคลาสในภาพเดียว (เลียนแบบภาพทดสอบวันที่ 3)
  --mode both    ครึ่งต่อครึ่ง

ตัวอย่าง:
  python synth_piles.py --ext data/day1_out --out data/synth --n 400 --mode both
ผลลัพธ์: data/synth/images/{train,val}, labels/{train,val} และ data/synth/data.yaml (รวมภาพจริงด้วย)
"""
import argparse, json, math, random, shutil
from pathlib import Path

import cv2
import numpy as np


def rotate_rgba(im, ang, scale):
    h, w = im.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, scale)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos) + 2, int(h * cos + w * sin) + 2
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(im, M, (nw, nh), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))


def make_background(bgs, W, H):
    bg = cv2.imread(str(random.choice(bgs)))
    bh, bw = bg.shape[:2]
    s = max(W / bw, H / bh) * random.uniform(1.0, 1.3)
    bg = cv2.resize(bg, None, fx=s, fy=s)
    y = random.randint(0, bg.shape[0] - H)
    x = random.randint(0, bg.shape[1] - W)
    bg = bg[y:y + H, x:x + W]
    if random.random() < 0.5:
        bg = cv2.flip(bg, 1)
    return bg, s   # อัตราย่อของพื้นหลัง ใช้ย่อเมล็ดให้เข้าสัดส่วนเดียวกัน


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ext', required=True, help='โฟลเดอร์ผลลัพธ์ของ bean_extract.py')
    ap.add_argument('--out', required=True)
    ap.add_argument('--bg-dir', default=None, help='ภาพพื้นหลังเปล่า (ถ้ามี) แทนพื้นหลังที่ inpaint')
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--val-frac', type=float, default=0.15)
    ap.add_argument('--mode', choices=['single', 'mixed', 'both'], default='both')
    ap.add_argument('--beans', default='40,120', help='จำนวนเมล็ดต่อภาพ ต่ำสุด,สูงสุด')
    ap.add_argument('--size', default='1280,960', help='ขนาดภาพผลลัพธ์ W,H')
    ap.add_argument('--min-visible', type=float, default=0.3, help='ส่วนที่มองเห็นขั้นต่ำจึงจะติด label')
    ap.add_argument('--good-ratio', type=float, default=0.6, help='สัดส่วนเมล็ด good ในโหมด mixed')
    ap.add_argument('--bean-scale', type=float, default=1.0, help='ปรับขนาดเมล็ดเพิ่ม/ลด (ใช้เมื่อพื้นหลังมาจากกล้องอื่น)')
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    random.seed(a.seed)
    np.random.seed(a.seed)

    ext, out = Path(a.ext), Path(a.out)
    classes = json.loads((ext / 'classes.json').read_text())
    manifest = json.loads((ext / 'cutouts' / 'manifest.json').read_text())
    by_cls = {c: [m for m in manifest if m['cls'] == c] for c in classes}
    by_cls = {c: v for c, v in by_cls.items() if v}
    bgs = sorted(Path(a.bg_dir or ext / 'backgrounds').glob('*.jpg'))
    if not bgs:
        raise SystemExit('ไม่พบภาพพื้นหลัง')
    W, H = map(int, a.size.split(','))
    nmin, nmax = map(int, a.beans.split(','))
    good = next((c for c in classes if 'good' in c.lower()), None)

    shutil.rmtree(out, ignore_errors=True)
    for s in ['train', 'val']:
        (out / 'images' / s).mkdir(parents=True)
        (out / 'labels' / s).mkdir(parents=True)

    cache = {}
    stats = {c: 0 for c in classes}
    for i in range(a.n):
        split = 'val' if i < int(a.n * a.val_frac) else 'train'
        canvas, bg_scale = make_background(bgs, W, H)
        canvas = canvas.astype(np.float32)
        inst = np.zeros((H, W), np.int32)            # แผนที่ว่าแต่ละพิกเซลเป็นของเมล็ดไหน
        mode = a.mode if a.mode != 'both' else random.choice(['single', 'mixed'])
        main_cls = random.choice(list(by_cls))
        n = random.randint(nmin, nmax)
        # จุดศูนย์กลางกอง 1–3 กอง
        centers = [(random.uniform(.3, .7) * W, random.uniform(.3, .7) * H) for _ in range(random.randint(1, 3))]
        spread = random.uniform(0.12, 0.22)
        placed = []                                     # (cls_id, เต็ม mask area)
        for k in range(n):
            if mode == 'single':
                c = main_cls
            elif good in by_cls and random.random() < a.good_ratio:
                c = good
            else:
                c = random.choice([x for x in by_cls if x != good] or list(by_cls))
            m = random.choice(by_cls[c])
            if m['path'] not in cache:
                cache[m['path']] = cv2.imread(str(ext / m['path']), cv2.IMREAD_UNCHANGED)
            cut = cache[m['path']]
            # เมล็ดกับพื้นหลังมาจากภาพความละเอียดเดียวกัน จึงย่อด้วยอัตราเดียวกับพื้นหลัง (bg_scale)
            scale = bg_scale * a.bean_scale * random.uniform(0.85, 1.15)
            rot = rotate_rgba(cut, random.uniform(0, 360), scale)
            if random.random() < 0.5:
                rot = cv2.flip(rot, 1)
            rh, rw = rot.shape[:2]
            cx, cy = random.choice(centers)
            x = int(np.clip(np.random.normal(cx, spread * W), 0, W - 1) - rw / 2)
            y = int(np.clip(np.random.normal(cy, spread * H), 0, H - 1) - rh / 2)
            x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + rw, W), min(y + rh, H)
            if x1 - x0 < rw * 0.6 or y1 - y0 < rh * 0.6:
                continue                                 # หลุดขอบภาพมากเกินไป
            patch = rot[y0 - y:y1 - y, x0 - x:x1 - x]
            alpha = patch[..., 3:4].astype(np.float32) / 255.0
            # เงาใต้เมล็ด ให้ดูเป็นกองจริงมากขึ้น
            sh = cv2.GaussianBlur(alpha[..., 0], (0, 0), 3)[..., None] * 0.35
            sx0, sy0 = min(x0 + 3, W - 1), min(y0 + 3, H - 1)
            sx1, sy1 = min(x1 + 3, W), min(y1 + 3, H)
            canvas[sy0:sy1, sx0:sx1] *= (1 - sh[:sy1 - sy0, :sx1 - sx0])
            roi = canvas[y0:y1, x0:x1]
            roi[:] = roi * (1 - alpha) + patch[..., :3].astype(np.float32) * alpha
            idx = len(placed) + 1
            inst[y0:y1, x0:x1][alpha[..., 0] > 0.5] = idx
            placed.append((classes.index(c), int((alpha[..., 0] > 0.5).sum())))

        img = np.clip(canvas, 0, 255).astype(np.uint8)
        # ปรับแสง/สีเล็กน้อยทั้งภาพ
        img = cv2.convertScaleAbs(img, alpha=random.uniform(0.9, 1.1), beta=random.uniform(-12, 12))
        lines = []
        for idx, (cid, full) in enumerate(placed, start=1):
            vis = (inst == idx).astype(np.uint8)
            area = int(vis.sum())
            if full == 0 or area < a.min_visible * full or area < 30:
                continue
            cnts, _ = cv2.findContours(vis, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            c = max(cnts, key=cv2.contourArea)
            p = cv2.approxPolyDP(c, 0.003 * cv2.arcLength(c, True), True).reshape(-1, 2).astype(np.float32)
            if len(p) < 3:
                continue
            p[:, 0] /= W
            p[:, 1] /= H
            lines.append(f'{cid} ' + ' '.join(f'{v:.5f}' for v in p.reshape(-1)))
            stats[classes[cid]] += 1
        name = f'synth_{i:05d}'
        cv2.imwrite(str(out / 'images' / split / f'{name}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (out / 'labels' / split / f'{name}.txt').write_text('\n'.join(lines) + '\n')
        if (i + 1) % 50 == 0:
            print(f'  {i + 1}/{a.n}')

    real = (ext / 'seg' / 'images' / 'train').resolve()
    yaml = [f'path: {out.resolve()}', 'train:', f'  - {(out / "images/train").resolve()}', f'  - {real}',
            f'val: {(out / "images/val").resolve()}', f'nc: {len(classes)}', 'names:']
    yaml += [f'  {i}: {c}' for i, c in enumerate(classes)]
    (out / 'data.yaml').write_text('\n'.join(yaml) + '\n')
    print('จำนวน instance ต่อคลาส:', json.dumps(stats, ensure_ascii=False))
    print(f'data.yaml -> {out / "data.yaml"} (train = synth + ภาพจริง, val = synth)')


if __name__ == '__main__':
    main()
