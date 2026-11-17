#!/usr/bin/env python3
"""
benchmark_pi.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
วัดเวลาทำนายของโมเดลหลายตัว/หลายขนาดภาพบน Pi พร้อมอุณหภูมิ CPU
  python benchmark_pi.py --models yolo26n-seg_ncnn_model yolo26n-seg.pt --image test.jpg --runs 20
"""
import argparse, statistics, subprocess, time

import cv2
from ultralytics import YOLO


def soc_temp():
    try:
        return subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return 'n/a'


ap = argparse.ArgumentParser()
ap.add_argument('--models', nargs='+', required=True)
ap.add_argument('--image', required=True)
ap.add_argument('--imgsz', type=int, default=None, help='ใส่เฉพาะโมเดล .pt (NCNN ใช้ขนาดตอน export)')
ap.add_argument('--runs', type=int, default=20)
a = ap.parse_args()

img = cv2.imread(a.image)
print(f'{"model":38s} {"mean ms":>8s} {"median":>8s} {"fps":>6s}  temp')
for m in a.models:
    model = YOLO(m)
    kw = {'verbose': False}
    if a.imgsz and m.endswith('.pt'):
        kw['imgsz'] = a.imgsz
    for _ in range(3):                         # warm-up
        model.predict(img, **kw)
    ts = []
    for _ in range(a.runs):
        t0 = time.perf_counter()
        model.predict(img, **kw)
        ts.append((time.perf_counter() - t0) * 1000)
    mean = statistics.mean(ts)
    print(f'{m:38s} {mean:8.1f} {statistics.median(ts):8.1f} {1000 / mean:6.2f}  {soc_temp()}')
