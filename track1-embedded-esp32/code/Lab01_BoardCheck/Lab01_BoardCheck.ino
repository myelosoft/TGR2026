// TGR2026 Track 1 Lab Sheet · Lab 1
// ตรวจ Flash / PSRAM / MAC
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.printf("Chip   : %s rev %d\n", ESP.getChipModel(), ESP.getChipRevision());
  Serial.printf("CPU    : %d cores @ %d MHz\n", ESP.getChipCores(), ESP.getCpuFreqMHz());
  Serial.printf("Flash  : %u MB\n", (unsigned)(ESP.getFlashChipSize() / (1024 * 1024)));
  Serial.printf("PSRAM  : %u bytes\n", (unsigned)ESP.getPsramSize());
  WiFi.mode(WIFI_STA);
  Serial.print("MAC    : ");
  Serial.println(WiFi.macAddress());   // จดไว้ ใช้เป็น device id
}

void loop() {}
