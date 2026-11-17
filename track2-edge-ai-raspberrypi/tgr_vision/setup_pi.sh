#!/bin/bash
# setup_pi.sh  (TGR2026 Track 2 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran)
# ติดตั้ง YOLO26 + กล้อง + MQTT บน Raspberry Pi 5 (Raspberry Pi OS 64-bit)   ใช้: bash setup_pi.sh
set -e
echo "== 1/4 อัปเดตระบบ =="
sudo apt update
sudo apt full-upgrade -y
echo "== 2/4 แพ็กเกจระบบ: กล้อง, venv, เครื่องมือ =="
sudo apt install -y python3-venv python3-pip python3-picamera2 rpicam-apps v4l-utils \
                    mosquitto-clients git htop tmux
echo "== 3/4 สร้าง virtual environment (เห็น picamera2 ของระบบด้วย) =="
python3 -m venv --system-site-packages ~/tgr-venv
source ~/tgr-venv/bin/activate
pip install -U pip
pip install ultralytics ncnn paho-mqtt
grep -q "tgr-venv" ~/.bashrc || echo 'source ~/tgr-venv/bin/activate' >> ~/.bashrc
echo "== 4/4 ตรวจสอบ =="
python - << 'PY'
import ultralytics, ncnn, cv2
print('ultralytics', ultralytics.__version__, '| ncnn', ncnn.__version__, '| opencv', cv2.__version__)
try:
    import picamera2; print('picamera2 OK')
except Exception as e:
    print('picamera2 ERROR:', e)
ultralytics.checks()
PY
rpicam-hello --list-cameras || true
echo "เสร็จแล้ว: เปิด terminal ใหม่ จะเข้า venv ให้อัตโนมัติ"
