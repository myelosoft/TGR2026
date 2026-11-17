#!/usr/bin/env python3
"""
predict_pi.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)

รันโมเดล YOLO26 (.pt หรือโฟลเดอร์ NCNN) กับภาพไฟล์ โฟลเดอร์ หรือกล้อง แล้วสรุปผลเป็น JSON
ใช้ได้ทั้ง 3 วัน:
  วันที่ 1  python predict_pi.py --model cls_ncnn_model --source test/          (classification ทั้งภาพ)
            python predict_pi.py --model seg_ncnn_model --source test/          (นับเมล็ดแล้วโหวต = แม่นกว่า)
            python predict_pi.py --model seg_ncnn_model --cls-model cls_ncnn_model --source test/
  วันที่ 2  python predict_pi.py --model seg_ncnn_model --source test/ --save    (วาดกรอบ + mask)
  วันที่ 3  python predict_pi.py --model seg_ncnn_model --source csi --mqtt 192.168.1.50 --team kmitl01 --save
            python predict_pi.py --model seg_ncnn_model --source csi --mqtt 192.168.1.50 --team kmitl01 --listen
              (รอคำสั่ง {"cmd":"capture","lot_id":"A"} ที่ tgr2026/<team>/vision/cmd แล้วตอบที่ .../vision/result)

ผลลัพธ์ (โฟลเดอร์ --out):
  results.jsonl   1 บรรทัดต่อ 1 ภาพ (JSON เดียวกับที่ส่ง MQTT)
  summary.csv     ตารางสรุป ใช้ส่งงาน/ตรวจผลเร็ว
  annotated/      ภาพที่วาดผลแล้ว (เมื่อใส่ --save)
"""
import argparse, csv, glob, json, time
from pathlib import Path

import cv2
from ultralytics import YOLO

IMG_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def iter_source(src, a, cmd_q=None):
    """คืน (ชื่อภาพ, ภาพ BGR, meta) ทีละภาพ จากไฟล์ / โฟลเดอร์ / glob / กล้อง"""
    if src == 'csi' or src.startswith('usb'):
        from camera import open_camera
        w, h = map(int, a.cam_size.split('x'))
        cam = open_camera(src, w, h, lock=not a.no_lock)
        if cmd_q is not None:
            print(f'กล้อง: {cam.desc} | รอคำสั่ง MQTT {{"cmd":"capture","lot_id":"A"}} (Ctrl+C เพื่อหยุด)')
        elif a.interval > 0:
            print(f'กล้อง: {cam.desc} | ถ่ายทุก {a.interval} s (Ctrl+C เพื่อหยุด)')
        else:
            print(f'กล้อง: {cam.desc} | Enter = ถ่าย+ทำนาย, พิมพ์ q แล้ว Enter = ออก')
        try:
            n = 0
            while True:
                meta = {}
                if cmd_q is not None:
                    meta = cmd_q.get()                   # รอจนมีคำสั่งเข้ามา
                elif a.interval > 0:
                    time.sleep(a.interval)
                elif input('> ').strip().lower() == 'q':
                    break
                n += 1
                tag = meta.get('lot_id') or src.replace(':', '')
                yield f'{tag}_{time.strftime("%H%M%S")}_{n:03d}.jpg', cam.grab(), meta
        except KeyboardInterrupt:
            pass
        finally:
            cam.close()
        return
    p = Path(src)
    if p.is_dir():
        files = sorted(f for f in p.rglob('*') if f.suffix.lower() in IMG_EXT)
    elif p.is_file():
        files = [p]
    else:
        files = sorted(Path(f) for f in glob.glob(src))
    if not files:
        raise SystemExit(f'ไม่พบภาพจาก {src}')
    for f in files:
        img = cv2.imread(str(f))
        if img is not None:
            yield f.name, img, {}


def classify_crops(cls_model, img, boxes, imgsz):
    """ตัดเมล็ดตามกรอบแล้วจำแนกด้วยโมเดล cls (แบบสองขั้น)"""
    crops = []
    h, w = img.shape[:2]
    for x0, y0, x1, y1 in boxes:
        bw, bh = x1 - x0, y1 - y0
        side = max(bw, bh) * 1.3                 # ขยายกรอบ 15% ต่อด้าน ให้เหมือนตอนเทรน
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        X0, Y0 = int(max(cx - side / 2, 0)), int(max(cy - side / 2, 0))
        X1, Y1 = int(min(cx + side / 2, w)), int(min(cy + side / 2, h))
        crops.append(img[Y0:Y1, X0:X1])
    out = []
    for i in range(0, len(crops), 32):
        for r in cls_model.predict(crops[i:i + 32], imgsz=imgsz, verbose=False):
            out.append((r.names[int(r.probs.top1)], float(r.probs.top1conf)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, help='best.pt หรือโฟลเดอร์ *_ncnn_model')
    ap.add_argument('--source', required=True, help='ไฟล์ / โฟลเดอร์ / "test/*.jpg" / csi / usb:0')
    ap.add_argument('--cls-model', default=None, help='(ไม่บังคับ) โมเดล cls จำแนกเมล็ดที่ seg ตัดมาอีกชั้น')
    ap.add_argument('--imgsz', type=int, default=None, help='ต้องเท่ากับตอน export NCNN (ไม่ใส่ = ใช้ค่าในโมเดล)')
    ap.add_argument('--cls-imgsz', type=int, default=224)
    ap.add_argument('--conf', type=float, default=0.35)
    ap.add_argument('--good', default='good', help='ชื่อคลาสเมล็ดดี (ส่วนที่เหลือนับเป็นเมล็ดเสีย)')
    ap.add_argument('--out', default='runs_pi')
    ap.add_argument('--save', action='store_true', help='บันทึกภาพที่วาดผลแล้ว')
    ap.add_argument('--cam-size', default='2304x1296')
    ap.add_argument('--no-lock', action='store_true', help='ไม่ล็อกแสง/white balance ของกล้อง')
    ap.add_argument('--interval', type=float, default=0, help='>0 = ถ่ายอัตโนมัติทุก N วินาที')
    ap.add_argument('--mqtt', default=None, help='host หรือ host:port ของ broker')
    ap.add_argument('--team', default='kmitl01')
    ap.add_argument('--topic', default=None, help='ค่าเริ่มต้น tgr2026/<team>/vision/result')
    ap.add_argument('--listen', action='store_true', help='รอคำสั่งถ่ายภาพทาง MQTT ที่ tgr2026/<team>/vision/cmd')
    ap.add_argument('--show', action='store_true', help='แสดงภาพผลบนหน้าจอ (ต้องมี desktop)')
    a = ap.parse_args()

    out = Path(a.out)
    (out / 'annotated').mkdir(parents=True, exist_ok=True)
    model = YOLO(a.model)
    cls_model = YOLO(a.cls_model) if a.cls_model else None
    kw = dict(conf=a.conf, verbose=False)
    if a.imgsz:
        kw['imgsz'] = a.imgsz

    client, topic = None, a.topic or f'tgr2026/{a.team}/vision/result'
    cmd_topic, cmd_q = f'tgr2026/{a.team}/vision/cmd', None
    if a.listen and not a.mqtt:
        raise SystemExit('--listen ต้องใช้คู่กับ --mqtt')
    if a.mqtt:
        import paho.mqtt.client as mqtt
        host, port = (a.mqtt.split(':') + ['1883'])[:2]
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'{a.team}-vision')
        client.will_set(f'tgr2026/{a.team}/vision/status', '{"online":false}', qos=1, retain=True)
        if a.listen:
            import queue
            cmd_q = queue.Queue()

            def on_connect(c, userdata, flags, rc, props=None):
                c.subscribe(cmd_topic, qos=1)        # subscribe ใหม่ทุกครั้งที่เชื่อมต่อ (กันหลุดแล้วเงียบ)

            def on_message(c, userdata, msg):
                try:
                    m = json.loads(msg.payload)
                except ValueError:
                    m = {}
                if m.get('cmd') == 'capture':
                    cmd_q.put(m)
            client.on_connect = on_connect
            client.on_message = on_message
        client.connect(host, int(port), keepalive=30)
        client.loop_start()
        client.publish(f'tgr2026/{a.team}/vision/status', '{"online":true}', qos=1, retain=True)
        print(f'MQTT -> {host}:{port}  topic={topic}' + (f'  | ฟังคำสั่งที่ {cmd_topic}' if a.listen else ''))

    rows, jl = [], open(out / 'results.jsonl', 'a', encoding='utf-8')
    for name, img, meta in iter_source(a.source, a, cmd_q):
        t0 = time.perf_counter()
        r = model.predict(img, **kw)[0]
        names = r.names
        rec = {'team': a.team, 'node': 'vision', 'image_id': name, 'ts': int(time.time()),
               'model': Path(a.model).name}
        if meta.get('lot_id'):
            rec['lot_id'] = meta['lot_id']
        if r.probs is not None:                                  # ---- โมเดล classification ทั้งภาพ
            rec['image_label'] = names[int(r.probs.top1)]
            rec['conf'] = round(float(r.probs.top1conf), 3)
            rec['top5'] = {names[int(i)]: round(float(c), 3) for i, c in zip(r.probs.top5, r.probs.top5conf)}
        else:                                                    # ---- โมเดล detect / seg
            labels, confs = [], []
            if r.boxes is not None and len(r.boxes):
                if cls_model:
                    pairs = classify_crops(cls_model, img, r.boxes.xyxy.cpu().numpy(), a.cls_imgsz)
                    labels, confs = [p[0] for p in pairs], [p[1] for p in pairs]
                else:
                    labels = [names[int(c)] for c in r.boxes.cls.tolist()]
                    confs = r.boxes.conf.tolist()
            counts = {n: 0 for n in names.values()}
            for lb in labels:
                counts[lb] = counts.get(lb, 0) + 1
            total = len(labels)
            good = counts.get(a.good, 0)
            rec.update({'counts': counts, 'total': total, 'defect_count': total - good,
                        'defect_ratio': round((total - good) / total, 3) if total else None,
                        'mean_conf': round(sum(confs) / len(confs), 3) if confs else None,
                        'image_label': max(counts, key=counts.get) if total else None})
        rec['infer_ms'] = round((time.perf_counter() - t0) * 1000, 1)

        line = json.dumps(rec, ensure_ascii=False)
        print(line)
        jl.write(line + '\n')
        jl.flush()
        if client:
            client.publish(topic, line, qos=1)
        if a.save or a.source in ('csi',) or a.source.startswith('usb'):
            vis = r.plot(line_width=1, font_size=10, labels=cls_model is None)
            txt = f"{rec.get('image_label')} | n={rec.get('total', '-')} | defect={rec.get('defect_ratio', '-')}"
            cv2.putText(vis, txt, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            cv2.imwrite(str(out / 'annotated' / name), vis)
            if a.show:
                cv2.imshow('TGR2026 vision', cv2.resize(vis, None, fx=0.5, fy=0.5))
                cv2.waitKey(1)
        rows.append(rec)

    jl.close()
    if rows:
        keys = sorted({k for r in rows for k in r.get('counts', {})})
        with open(out / 'summary.csv', 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f)
            wr.writerow(['image_id', 'image_label', 'total', 'defect_ratio', 'infer_ms'] + keys)
            for r in rows:
                wr.writerow([r['image_id'], r.get('image_label'), r.get('total'), r.get('defect_ratio'),
                             r['infer_ms']] + [r.get('counts', {}).get(k, '') for k in keys])
        print(f'\nบันทึก {len(rows)} ภาพ -> {out}/summary.csv, results.jsonl' + (', annotated/' if a.save else ''))
    if client:
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    main()
