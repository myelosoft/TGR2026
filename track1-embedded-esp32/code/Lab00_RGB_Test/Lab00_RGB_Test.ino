// TGR2026 Track 1 Lab Sheet · Lab 0
// ทดสอบอัปโหลดโปรแกรมและ Serial Monitor
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

void setup() {
  Serial.begin(115200);
}

void loop() {
  rgbLedWrite(RGB_BUILTIN, 0, 40, 0);   // เขียวอ่อน
  Serial.println("LED ON");
  delay(500);
  rgbLedWrite(RGB_BUILTIN, 0, 0, 0);    // ดับ
  Serial.println("LED OFF");
  delay(500);
}
