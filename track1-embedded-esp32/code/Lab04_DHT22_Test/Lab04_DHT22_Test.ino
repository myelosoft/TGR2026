// TGR2026 Track 1 Lab Sheet · Lab 4
// ทดสอบ DHT22
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <DHT.h>

const int PIN_DHT = 15;
DHT dht(PIN_DHT, DHT22);

void setup() {
  Serial.begin(115200);
  dht.begin();
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();   // °C
  if (isnan(h) || isnan(t)) {
    Serial.println("DHT22 read failed");
  } else {
    Serial.printf("temp_c:%.1f,rh_pct:%.1f\n", t, h);
  }
  delay(2500);   // ห้ามต่ำกว่า 2000 ms
}
