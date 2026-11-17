#!/usr/bin/env python3
"""
capture.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
ถ่ายภาพเก็บ dataset จากกล้อง CSI หรือ USB ลงโฟลเดอร์ data/raw/<label>/
  python capture.py --source csi --label good          # Enter = ถ่าย 1 ภาพ, q = ออก
  python capture.py --source usb:0 --label broken --size 1920x1080
  python capture.py --source csi --test                # ถ่ายภาพเดียวไว้ตรวจกล้อง/โฟกัส แล้วจบ
"""
import argparse, time
from pathlib import Path

import cv2
from camera import open_camera

ap = argparse.ArgumentParser()
ap.add_argument('--source', default='csi', help='csi / usb:0')
ap.add_argument('--label', default='unlabeled', help='ชื่อคลาส = ชื่อโฟลเดอร์ปลายทาง')
ap.add_argument('--out', default='data/raw')
ap.add_argument('--size', default='2304x1296')
ap.add_argument('--no-lock', action='store_true')
ap.add_argument('--test', action='store_true')
a = ap.parse_args()

w, h = map(int, a.size.split('x'))
cam = open_camera(a.source, w, h, lock=not a.no_lock)
print('เปิดกล้อง:', cam.desc)
if a.test:
    img = cam.grab()
    cv2.imwrite('camera_test.jpg', img)
    sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    print(f'บันทึก camera_test.jpg  ขนาด {img.shape[1]}x{img.shape[0]}  ความคม (Laplacian var) = {sharp:.0f}')
    print('ค่าความคมยิ่งสูงยิ่งชัด ให้ปรับโฟกัส/ระยะจนค่าสูงสุด แล้วจดไว้เป็นมาตรฐาน')
    cam.close()
    raise SystemExit

d = Path(a.out) / a.label
d.mkdir(parents=True, exist_ok=True)
n = len(list(d.glob('*.jpg')))
print(f'บันทึกลง {d}  (มีอยู่แล้ว {n} ภาพ)  Enter = ถ่าย, q = ออก')
try:
    while input('> ').strip().lower() != 'q':
        img = cam.grab()
        p = d / f'{a.label}_{time.strftime("%Y%m%d_%H%M%S")}.jpg'
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        n += 1
        print(f'  [{n}] {p.name}')
finally:
    cam.close()
