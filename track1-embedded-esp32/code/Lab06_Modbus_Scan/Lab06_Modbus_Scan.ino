// TGR2026 Track 1 Lab Sheet · Lab 6
// สแกนหา baud / address / function code ของเซ็นเซอร์ RS485
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

const int PIN_485_RX = 18;   // ESP32 รับ
const int PIN_485_TX = 17;   // ESP32 ส่ง
HardwareSerial &RS485 = Serial1;

// CRC16 แบบ Modbus (poly 0xA001, ค่าเริ่ม 0xFFFF)
uint16_t modbusCRC(const uint8_t *buf, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= buf[i];
    for (int b = 0; b < 8; b++) {
      if (crc & 0x0001) crc = (crc >> 1) ^ 0xA001;
      else              crc >>= 1;
    }
  }
  return crc;
}

// อ่านรีจิสเตอร์ count ตัว เก็บลง out[]
// คืนค่า: 0 = สำเร็จ, 1 = ไม่ตอบ (timeout), 2 = CRC ผิด,
//         3 = ตอบผิดรูปแบบ, 0x80+code = เซ็นเซอร์ตอบ exception
int modbusRead(uint8_t addr, uint8_t fc, uint16_t reg, uint16_t count, uint16_t *out) {
  if (count == 0 || count > 29) return 3;
  uint8_t req[8] = { addr, fc,
                     (uint8_t)(reg >> 8),   (uint8_t)(reg & 0xFF),
                     (uint8_t)(count >> 8), (uint8_t)(count & 0xFF), 0, 0 };
  uint16_t crc = modbusCRC(req, 6);
  req[6] = crc & 0xFF;      // CRC ส่งไบต์ต่ำก่อน
  req[7] = crc >> 8;

  while (RS485.available()) RS485.read();   // ล้างข้อมูลค้างใน buffer
  RS485.write(req, 8);
  RS485.flush();                            // รอจนส่งครบทุกไบต์

  const size_t expect = 5 + 2 * count;      // addr + fc + n + data + crc(2)
  uint8_t resp[64];
  size_t n = 0;
  uint32_t t0 = millis();
  while (millis() - t0 < 300 && n < expect) {
    if (RS485.available()) resp[n++] = RS485.read();
    if (n >= 5 && (resp[1] & 0x80)) break;  // exception มีแค่ 5 ไบต์
  }

  if (n == 0) return 1;
  if (n < 5)  return 3;
  uint16_t got = resp[n - 2] | (resp[n - 1] << 8);
  if (modbusCRC(resp, n - 2) != got) return 2;
  if (resp[1] & 0x80) return 0x80 | resp[2];
  if (n != expect || resp[0] != addr || resp[1] != fc || resp[2] != 2 * count) return 3;

  for (uint16_t i = 0; i < count; i++) {
    out[i] = (resp[3 + 2 * i] << 8) | resp[4 + 2 * i];   // ไบต์สูงมาก่อน
  }
  return 0;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  const uint32_t bauds[] = {9600, 4800, 19200};
  const uint8_t  fcs[]   = {0x03, 0x04};

  for (uint32_t baud : bauds) {
    RS485.begin(baud, SERIAL_8N1, PIN_485_RX, PIN_485_TX);
    delay(50);
    Serial.printf("--- baud %lu ---\n", (unsigned long)baud);
    for (uint8_t addr = 1; addr <= 10; addr++) {
      for (uint8_t fc : fcs) {
        uint16_t r[2];
        int err = modbusRead(addr, fc, 0x0000, 2, r);
        if (err == 0) {
          Serial.printf("FOUND addr=%u fc=0x%02X  reg0=%u (/10=%.1f)  reg1=%u (/10=%.1f)\n",
                        addr, fc, r[0], (int16_t)r[0] / 10.0, r[1], (int16_t)r[1] / 10.0);
        } else if (err >= 0x80) {
          Serial.printf("addr=%u fc=0x%02X exception %d (มีอุปกรณ์ แต่ไม่รับคำสั่งนี้)\n",
                        addr, fc, err & 0x7F);
        } else if (err == 2) {
          Serial.printf("addr=%u fc=0x%02X CRC ผิด (สัญญาณรบกวนหรือ baud ใกล้เคียง)\n", addr, fc);
        }
        delay(30);   // เว้นช่วงระหว่างเฟรม
      }
    }
    RS485.end();
  }
  Serial.println("scan done");
}

void loop() {}
