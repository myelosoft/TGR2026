# คำสั่ง terminal ทั้งหมดในชุดฝึก (คัดลอกทีละบรรทัด)

# ===== Lab 0 ติดตั้ง Mosquitto =====
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo nano /etc/mosquitto/conf.d/tgr.conf

# ===== Lab 0 เปิด Mosquitto =====
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
hostname -I        # จด IP ของ Pi ไว้ เช่น 192.168.1.50

# ===== Lab 0 ทดสอบ broker =====
# หน้าต่าง 1: รับทุก topic ที่ขึ้นต้นด้วย tgr2026/
mosquitto_sub -h 192.168.1.50 -t "tgr2026/#" -v

# หน้าต่าง 2: ส่งข้อความทดสอบ
mosquitto_pub -h 192.168.1.50 -t "tgr2026/test" -m '{"hello":"world"}'

# ===== Lab 0 EMQX ผ่าน Docker =====
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER      # ออกจากระบบแล้วเข้าใหม่ 1 ครั้ง

# ถ้า Mosquitto เปิดอยู่ ต้องปิดก่อน เพราะใช้พอร์ต 1883 เหมือนกัน
sudo systemctl stop mosquitto
sudo systemctl disable mosquitto

docker run -d --name emqx --restart unless-stopped \
  -p 1883:1883 -p 8083:8083 -p 18083:18083 \
  emqx/emqx:5.8

docker ps            # ต้องเห็น emqx สถานะ Up

# ===== Lab 2 ส่งคำสั่งทดสอบ =====
mosquitto_pub -h 192.168.1.50 -t "tgr2026/kmitl01/esp32s3-a1b2c3/cmd" -m '{"cmd":"interval","ms":2000}'
mosquitto_pub -h 192.168.1.50 -t "tgr2026/kmitl01/esp32s3-a1b2c3/cmd" -m '{"cmd":"led","value":1}'
mosquitto_pub -h 192.168.1.50 -t "tgr2026/kmitl01/esp32s3-a1b2c3/cmd" -m 'not json'

# ===== Lab 2 ติดตั้ง paho-mqtt =====
pip install paho-mqtt

# ===== Lab 7 สั่ง tare / measure =====
mosquitto_pub -h 192.168.1.50 -t "tgr2026/kmitl01/esp32s3-a1b2c3/cmd" -m '{"cmd":"tare"}'
mosquitto_pub -h 192.168.1.50 -t "tgr2026/kmitl01/esp32s3-a1b2c3/cmd" -m '{"cmd":"measure","sample_id":"lot-A"}'
