TGR2026 Track 2 · Edge AI ด้วย YOLO26 บน Raspberry Pi 5
ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE

แตกไฟล์ไว้ที่ ~/tgr_vision ทั้งบนโน้ตบุ๊ก (Ubuntu) และบน Raspberry Pi

ติดตั้ง
  โน้ตบุ๊ก : bash setup_laptop.sh      (รอบแรกติดตั้งไดรเวอร์ NVIDIA -> รีบูต -> รันซ้ำ)
  Pi       : bash setup_pi.sh

ไฟล์
  train_yolo26.ipynb  ขั้นตอนเทรนทั้งหมดใน Jupyter (kernel: Python (tgr))
  bean_extract.py     ตัดเมล็ดอัตโนมัติจากภาพ 1 คลาสต่อภาพ -> crop (cls), polygon (seg), cutout
  synth_piles.py      สร้างกองเมล็ดสังเคราะห์พร้อม label YOLO-seg ที่หักส่วนที่ถูกบัง
  convert_labels.py   แปลง JSON ของ X-AnyLabeling/LabelMe เป็น YOLO (seg/det)
  count_eval.py       วัดความคลาดเคลื่อนของการนับเมล็ดต่อคลาสและสัดส่วนเมล็ดเสีย
  camera.py           เปิดกล้อง CSI (Picamera2) / USB (OpenCV) พร้อมล็อกแสงและ white balance
  capture.py          ถ่ายภาพเก็บ dataset
  predict_pi.py       ทำนาย -> นับต่อคลาส -> JSON -> MQTT (โฟลเดอร์ภาพ / กล้อง / รอคำสั่ง MQTT)
  benchmark_pi.py     วัดความเร็วโมเดลบน Pi

สถานะการทดสอบ (12 พ.ย. 2569)
  ทดสอบรันจริงแล้ว: bean_extract.py, synth_piles.py, convert_labels.py, count_eval.py (กับภาพจำลอง)
  ตรวจ syntax แล้วแต่ยังไม่ได้รันกับ ultralytics/กล้องจริง: predict_pi.py, camera.py, capture.py,
  benchmark_pi.py, notebook และ setup scripts  -> ต้องทดสอบบนเครื่องจริงตาม Lab 3-4 ก่อนใช้แข่ง
  examples/           ไฟล์ตัวอย่าง: day2_mix.yaml, day3_mix.yaml, tgr-vision.service, gpio_button.py
