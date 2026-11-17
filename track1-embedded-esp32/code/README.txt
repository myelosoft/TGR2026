TGR2026 Track 1 Lab Sheet - ไฟล์โค้ดประกอบ
ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran

วิธีใช้
1. แตกไฟล์ zip แล้วเปิดโฟลเดอร์ของ Lab ที่ต้องการด้วย Arduino IDE (File > Open > LabXX_.../LabXX_....ino)
2. Tools > Board: ESP32S3 Dev Module, Flash Size: 16MB, PSRAM: OPI PSRAM,
   Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS)
3. แก้ส่วน "ตั้งค่า" (WIFI_SSID, WIFI_PASS, MQTT_HOST, TEAM) ก่อนอัปโหลดทุกครั้ง

สถานะการตรวจสอบ (12 พ.ย. 2569)
คอมไพล์ผ่านทั้ง 13 sketch กับ esp32 core 3.3.12, PubSubClient 2.8, ArduinoJson 7.4.2,
DHT sensor library 1.4.7, Adafruit BME280 2.3.0, Adafruit AM2315 2.2.3, Adafruit BusIO 1.17.4, Adafruit Unified Sensor 1.1.15
ยังต้องทดสอบกับฮาร์ดแวร์จริงตามเช็คพอยต์ในเอกสาร

รายการไฟล์
Lab00_RGB_Test             ทดสอบอัปโหลด
Lab01_BoardCheck           ตรวจ Flash / PSRAM / MAC
Lab02_MQTT_JSON_Template   แม่แบบ WiFi + MQTT + JSON (ฐานของทุก Lab)
Lab03_Analog_Test          ทดสอบเซ็นเซอร์ analog ผ่าน Serial Plotter
Lab03_Analog_MQTT          Lab 3 แบบส่ง MQTT (ประกอบแล้ว)
Lab04_DHT22_Test / _MQTT   DHT22
Lab05_I2C_Scanner          I2C scanner
Lab05_I2C_Test             BME280 + AM2315
Lab06_Modbus_Scan          สแกนหา baud / address / function code
Lab06_Modbus_MQTT          อ่าน SHTC3 Modbus แล้วส่ง MQTT
Lab07_BeanMoisture_MQTT    เซลล์วัดความชื้นเมล็ด สั่ง tare / measure ผ่าน MQTT
Lab08_Integration_RTOS     firmware รวมทุกเซ็นเซอร์ด้วย FreeRTOS
python/                    ตัวรับ MQTT และสคริปต์ calibration
commands.sh                คำสั่ง terminal ทั้งหมด
mosquitto_tgr.conf         ไฟล์ตั้งค่า Mosquitto
