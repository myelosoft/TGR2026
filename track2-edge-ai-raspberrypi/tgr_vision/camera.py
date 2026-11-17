"""
camera.py  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
เปิดกล้อง CSI (Picamera2) หรือ USB (OpenCV) แล้วคืนฟังก์ชัน grab() ที่ให้ภาพแบบ BGR (ใช้กับ OpenCV/YOLO ได้ทันที)

  cam = open_camera('csi', 2304, 1296, lock=True)   # กล้อง CSI ล็อกแสงและ white balance
  cam = open_camera('usb:0', 1920, 1080)            # USB กล้องตัวแรก
  frame = cam.grab(); cam.close()
"""
import time

import cv2


class Camera:
    def __init__(self, grab, close, desc):
        self.grab, self.close, self.desc = grab, close, desc


def open_camera(src='csi', width=2304, height=1296, lock=True, warmup=2.0):
    if src == 'csi':
        from picamera2 import Picamera2           # ติดตั้งด้วย sudo apt install python3-picamera2
        cam = Picamera2()
        cfg = cam.create_still_configuration(main={'size': (width, height), 'format': 'RGB888'})
        cam.configure(cfg)
        cam.start()
        time.sleep(warmup)                          # ให้ auto exposure / auto white balance นิ่งก่อน
        if lock:
            md = cam.capture_metadata()
            cam.set_controls({'AeEnable': False, 'AwbEnable': False,
                              'ExposureTime': md['ExposureTime'],
                              'AnalogueGain': md['AnalogueGain'],
                              'ColourGains': md['ColourGains']})
            time.sleep(0.5)
            print(f"[csi] ล็อกแสง: exposure={md['ExposureTime']} us gain={md['AnalogueGain']:.2f} "
                  f"wb={tuple(round(g, 2) for g in md['ColourGains'])}")
        # Picamera2 รูปแบบ 'RGB888' เรียงไบต์เป็น B,G,R ใช้กับ OpenCV ได้ตรง ๆ
        return Camera(lambda: cam.capture_array('main'), cam.stop, f'CSI {width}x{height}')

    if src.startswith('usb'):
        idx = int(src.split(':')[1]) if ':' in src else 0
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise RuntimeError(f'เปิดกล้อง USB index {idx} ไม่ได้ (ตรวจด้วย v4l2-ctl --list-devices)')
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        t0 = time.time()
        while time.time() - t0 < warmup:            # ทิ้งเฟรมแรก ๆ ระหว่างกล้องปรับแสง
            cap.read()
        if lock:                                    # กล้อง USB บางรุ่นไม่รองรับ จะไม่มีผล
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)   # V4L2: 1 = manual, 3 = auto

        def grab():
            for _ in range(3):                      # ล้างเฟรมค้างใน buffer ให้ได้ภาพล่าสุด
                cap.grab()
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('อ่านภาพจากกล้อง USB ไม่ได้')
            return frame

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return Camera(grab, cap.release, f'USB{idx} {w}x{h}')

    raise ValueError("source กล้องต้องเป็น 'csi' หรือ 'usb' / 'usb:1'")
