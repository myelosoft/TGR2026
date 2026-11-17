// TGR2026 Track 1 Lab Sheet · Lab 5
// ทดสอบ BME280 + AM2315
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AM2315.h>

Adafruit_BME280 bme;
Adafruit_AM2315 am2315(&Wire);
bool bmeOk = false, amOk = false;

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  Wire.setClock(100000);

  bmeOk = bme.begin(0x76, &Wire) || bme.begin(0x77, &Wire);
  Serial.printf("BME280 : %s\n", bmeOk ? "OK" : "NOT FOUND");

  amOk = am2315.begin();
  Serial.printf("AM2315 : %s\n", amOk ? "OK" : "NOT FOUND");
}

void loop() {
  if (bmeOk) {
    Serial.printf("bme_t:%.2f,bme_rh:%.1f,bme_hpa:%.1f\n",
                  bme.readTemperature(), bme.readHumidity(),
                  bme.readPressure() / 100.0F);
  }
  float t, h;
  if (am2315.readTemperatureAndHumidity(&t, &h)) {
    Serial.printf("am_t:%.1f,am_rh:%.1f\n", t, h);
  } else {
    Serial.println("AM2315 read failed");
  }
  delay(2500);   // AM2315 อัปเดตได้ไม่ถี่กว่าทุก 2 วินาที
}
