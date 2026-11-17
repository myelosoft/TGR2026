// TGR2026 Track 1 Lab Sheet · Lab 5
// I2C Scanner (SDA=GPIO8, SCL=GPIO9)
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);          // SDA, SCL
  Wire.setClock(100000);     // 100 kHz ปลอดภัยที่สุดสำหรับสายยาว
}

void loop() {
  Serial.println("Scanning I2C...");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found 0x%02X\n", addr);
      found++;
    }
  }
  Serial.printf("%d device(s)\n\n", found);
  delay(3000);
}
