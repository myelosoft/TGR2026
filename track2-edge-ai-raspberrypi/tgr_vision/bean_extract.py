#!/usr/bin/env python3
"""
bean_extract.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)

ตัดเมล็ดกาแฟแต่ละเม็ดออกจากภาพที่ "1 ภาพ = 1 คลาส" และเมล็ดวางไม่ชนกัน (ข้อมูลเทรนวันที่ 1)
แล้วสร้างข้อมูล 4 ชุดโดยไม่ต้อง label เอง:
  out/cls/{train,val}/<class>/*.jpg     ภาพเมล็ดทีละเม็ด สำหรับ YOLO26-cls
  out/seg/images/train/*.jpg + labels    polygon ของทุกเมล็ด สำหรับ YOLO26-seg (ทุกเมล็ดได้คลาสของภาพ)
  out/cutouts/<class>/*.png + manifest   เมล็ดแบบพื้นหลังโปร่งใส สำหรับ synth_piles.py
  out/backgrounds/*.jpg                  พื้นหลังที่ลบเมล็ดออกแล้ว สำหรับ synth_piles.py
  out/debug/*.jpg                        ภาพตรวจสอบ ต้องเปิดดูทุกภาพก่อนเทรน!

โครงสร้างโฟลเดอร์ขาเข้า:  raw/<class_name>/*.jpg   (ชื่อโฟลเดอร์ = ชื่อคลาส)

ตัวอย่าง:
  python bean_extract.py --src data/day1_raw --out data/day1_out
  python bean_extract.py --src data/day1_raw --out data/day1_out --method fastsam   # ถ้า OpenCV ตัดไม่ดี
"""
import argparse, json, random, shutil
from pathlib import Path

import cv2
import numpy as np

IMG_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def list_images(d):
    return sorted(p for p in Path(d).iterdir() if p.suffix.lower() in IMG_EXT)


def bean_mask_opencv(img, close_k=7):
    """แยกเมล็ดออกจากพื้นหลังด้วยระยะห่างสีจากพื้นหลังในปริภูมิ LAB"""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = img.shape[:2]
    b = max(4, int(0.04 * min(h, w)))                       # แถบขอบภาพ ใช้ประมาณสีพื้นหลัง
    border = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3),
                             lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = lab - bg
    d[..., 0] *= 0.6                                         # ลดน้ำหนักความสว่าง (ลายไม้) ลงเล็กน้อย
    dist = np.sqrt((d ** 2).sum(-1))
    dist = cv2.GaussianBlur(dist, (0, 0), 2)
    dist8 = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, m = cv2.threshold(dist8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    # เติมรูภายในเมล็ด (ร่องกลางเมล็ดมักถูกตัดเป็นรู)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(m)
    cv2.drawContours(filled, cnts, -1, 255, -1)
    return filled


def bean_masks_fastsam(img, model):
    """ใช้ FastSAM แบ่งทุกวัตถุในภาพ (ต้องติดตั้ง ultralytics)"""
    r = model(img, retina_masks=True, imgsz=1024, conf=0.4, iou=0.9, verbose=False)[0]
    out = np.zeros(img.shape[:2], np.uint8)
    if r.masks is None:
        return out
    for mk in r.masks.data.cpu().numpy():
        mk = cv2.resize(mk, (img.shape[1], img.shape[0])) > 0.5
        out[mk] = 255
    return out


def split_instances(mask, min_frac, max_frac):
    """หา contour ของแต่ละเมล็ด กรองด้วยขนาดเทียบกับค่ากลาง"""
    h, w = mask.shape
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    areas = np.array([cv2.contourArea(c) for c in cnts]) if cnts else np.array([])
    keep = [c for c, a in zip(cnts, areas) if min_frac * h * w <= a <= max_frac * h * w]
    if not keep:
        return []
    med = np.median([cv2.contourArea(c) for c in keep])
    # ตัดชิ้นที่เล็กหรือใหญ่ผิดปกติ (เศษ หรือเมล็ดติดกันหลายเม็ด)
    return [c for c in keep if 0.25 * med <= cv2.contourArea(c) <= 2.5 * med]


def contour_to_poly(c, w, h):
    eps = 0.003 * cv2.arcLength(c, True)
    p = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float32)
    if len(p) < 3:
        return None
    p[:, 0] /= w
    p[:, 1] /= h
    return np.clip(p, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='โฟลเดอร์ raw/<class>/*.jpg')
    ap.add_argument('--out', required=True)
    ap.add_argument('--method', choices=['opencv', 'fastsam'], default='opencv')
    ap.add_argument('--max-side', type=int, default=2000, help='ย่อภาพก่อนประมวลผล (px ด้านยาว)')
    ap.add_argument('--min-area', type=float, default=0.0003, help='พื้นที่เมล็ดต่ำสุด (สัดส่วนของภาพ)')
    ap.add_argument('--max-area', type=float, default=0.05, help='พื้นที่เมล็ดสูงสุด (สัดส่วนของภาพ)')
    ap.add_argument('--pad', type=float, default=0.15, help='ขยายกรอบ crop รอบเมล็ด')
    ap.add_argument('--val', type=float, default=0.2, help='สัดส่วน crop ที่แยกไว้ validate (cls)')
    ap.add_argument('--classes', default=None,
                    help='ไฟล์รายชื่อคลาส 1 ชื่อต่อบรรทัด ตามลำดับของผู้จัด (ไม่ใส่ = เรียงตามตัวอักษร)')
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed)

    src, out = Path(a.src), Path(a.out)
    if a.classes:
        classes = [c.strip() for c in Path(a.classes).read_text(encoding='utf-8').splitlines() if c.strip()]
    else:
        classes = sorted(p.name for p in src.iterdir() if p.is_dir())
    if not classes:
        raise SystemExit(f'ไม่พบโฟลเดอร์คลาสใน {src} (ต้องเป็น {src}/<class>/*.jpg)')
    print('classes:', classes)
    for sub in ['cls', 'seg', 'cutouts', 'backgrounds', 'debug']:
        shutil.rmtree(out / sub, ignore_errors=True)
    (out / 'seg/images/train').mkdir(parents=True)
    (out / 'seg/labels/train').mkdir(parents=True)
    (out / 'backgrounds').mkdir(parents=True)
    (out / 'debug').mkdir(parents=True)

    fastsam = None
    if a.method == 'fastsam':
        from ultralytics import FastSAM
        fastsam = FastSAM('FastSAM-s.pt')

    manifest, summary = [], {}
    for ci, cname in enumerate(classes):
        n_bean = 0
        if not (src / cname).is_dir():
            print(f'  (ไม่มีโฟลเดอร์ {cname} ข้ามไป แต่ยังคงลำดับคลาสไว้)')
            summary[cname] = 0
            continue
        for ip in list_images(src / cname):
            img = cv2.imread(str(ip))
            if img is None:
                print('  อ่านไม่ได้:', ip)
                continue
            s = a.max_side / max(img.shape[:2])
            if s < 1:
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            h, w = img.shape[:2]
            mask = bean_masks_fastsam(img, fastsam) if fastsam else bean_mask_opencv(img)
            cnts = split_instances(mask, a.min_area, a.max_area)
            stem = f'{cname}__{ip.stem}'
            dbg = img.copy()
            lines, beans_mask = [], np.zeros((h, w), np.uint8)
            for k, c in enumerate(cnts):
                poly = contour_to_poly(c, w, h)
                if poly is None:
                    continue
                lines.append(f'{ci} ' + ' '.join(f'{v:.5f}' for v in poly.reshape(-1)))
                one = np.zeros((h, w), np.uint8)
                cv2.drawContours(one, [c], -1, 255, -1)
                beans_mask |= one
                x, y, bw, bh = cv2.boundingRect(c)
                side = int(max(bw, bh) * (1 + 2 * a.pad))
                cx, cy = x + bw // 2, y + bh // 2
                x0, y0 = max(cx - side // 2, 0), max(cy - side // 2, 0)
                x1, y1 = min(x0 + side, w), min(y0 + side, h)
                split = 'val' if random.random() < a.val else 'train'
                cdir = out / 'cls' / split / cname
                cdir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(cdir / f'{stem}_{k:03d}.jpg'), img[y0:y1, x0:x1])
                # cutout แบบโปร่งใสสำหรับสร้างกองสังเคราะห์
                rgba = cv2.cvtColor(img[y:y + bh, x:x + bw], cv2.COLOR_BGR2BGRA)
                rgba[..., 3] = cv2.GaussianBlur(one[y:y + bh, x:x + bw], (3, 3), 0)
                udir = out / 'cutouts' / cname
                udir.mkdir(parents=True, exist_ok=True)
                up = udir / f'{stem}_{k:03d}.png'
                cv2.imwrite(str(up), rgba)
                manifest.append({'path': str(up.relative_to(out)), 'cls': cname, 'src_w': w})
                cv2.drawContours(dbg, [c], -1, (0, 255, 0), 2)
                cv2.putText(dbg, str(k), (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                n_bean += 1
            cv2.imwrite(str(out / 'seg/images/train' / f'{stem}.jpg'), img)
            (out / 'seg/labels/train' / f'{stem}.txt').write_text('\n'.join(lines) + '\n')
            # พื้นหลังไม่มีเมล็ด (inpaint ทับตำแหน่งเมล็ด)
            hole = cv2.dilate(beans_mask, np.ones((15, 15), np.uint8))
            cv2.imwrite(str(out / 'backgrounds' / f'{stem}.jpg'), cv2.inpaint(img, hole, 9, cv2.INPAINT_TELEA))
            cv2.putText(dbg, f'{cname}: {len(lines)} beans', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.imwrite(str(out / 'debug' / f'{stem}.jpg'), dbg)
            print(f'  {ip.name:30s} -> {len(lines):4d} beans')
        summary[cname] = n_bean

    (out / 'cutouts' / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False))
    (out / 'classes.json').write_text(json.dumps(classes, ensure_ascii=False))
    yaml = [f'path: {out.resolve()}/seg', 'train: images/train', 'val: images/train', f'nc: {len(classes)}', 'names:']
    yaml += [f'  {i}: {c}' for i, c in enumerate(classes)]
    (out / 'seg' / 'data.yaml').write_text('\n'.join(yaml) + '\n')
    print('\nจำนวนเมล็ดต่อคลาส:', json.dumps(summary, ensure_ascii=False))
    print(f'เปิดดูภาพตรวจสอบใน {out}/debug ทุกภาพ ถ้ากรอบเขียวไม่ครบหรือเกิน ให้ปรับ --min-area/--max-area หรือใช้ --method fastsam')


if __name__ == '__main__':
    main()
