// TGR2026 Track 1 Lab Sheet · Lab 3
// ทดสอบเซ็นเซอร์ analog ผ่าน Serial / Serial Plotter
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

// ---------------- ขา ----------------
const int PIN_NTC       = 4;
const int PIN_SOIL_RES  = 5;
const int PIN_SOIL_CAP  = 6;
const int PIN_SOIL_V2   = 7;
const int PIN_PROBE_PWR = 16;

// ---------------- ค่าคงที่ของวงจร (วัดจริงแล้วแก้) ----------------
const float VCC_MV  = 3300.0;   // แรงดันขา 3V3 ที่วัดได้จริง (mV)
const float R_FIXED = 10000.0;  // ตัวต้านทานคู่กับ NTC (วัดจริงด้วยมัลติมิเตอร์)
const float R0_NTC  = 10000.0;  // ความต้านทาน NTC ที่ 25 °C
const float B_NTC   = 3950.0;   // ค่า Beta (datasheet; ถ้าไม่รู้ใช้ 3950)
const float T0_K    = 298.15;   // 25 °C ในหน่วยเคลวิน

// ---------------- ค่า calibration (ได้จากขั้นที่ 4) ----------------
int RES_DRY_MV = 3200, RES_WET_MV = 1300;
int CAP_DRY_MV = 2500, CAP_WET_MV = 1100;
int V2_DRY_MV  = 2500, V2_WET_MV  = 1100;

// อ่าน n ครั้ง แล้วคืนค่ากลาง (median)
int readMilliVoltsMedian(int pin, int n = 15) {
  int v[31];
  n = constrain(n, 1, 31);
  for (int i = 0; i < n; i++) {
    v[i] = analogReadMilliVolts(pin);
    delayMicroseconds(300);
  }
  for (int i = 1; i < n; i++) {           // insertion sort
    int key = v[i], j = i - 1;
    while (j >= 0 && v[j] > key) { v[j + 1] = v[j]; j--; }
    v[j + 1] = key;
  }
  return v[n / 2];
}

// แปลง mV ของ NTC (NTC อยู่ฝั่ง GND) เป็น °C ด้วยสมการ Beta
float ntcCelsius(int mv) {
  if (mv < 50 || mv > VCC_MV - 50) return NAN;   // สายหลุดหรือช็อต
  float r = R_FIXED * mv / (VCC_MV - mv);
  float invT = 1.0 / T0_K + log(r / R0_NTC) / B_NTC;
  return 1.0 / invT - 273.15;
}

// แปลง mV เป็น % จากจุด calibrate 2 จุด (ใช้ได้ทั้งเซ็นเซอร์ที่ค่าขึ้นหรือลงเมื่อเปียก)
float toPercent(int mv, int dryMv, int wetMv) {
  if (dryMv == wetMv) return NAN;
  float p = 100.0 * (mv - dryMv) / (float)(wetMv - dryMv);
  return constrain(p, 0.0, 100.0);
}

// อ่าน probe resistive โดยเปิดไฟเฉพาะตอนอ่าน
int readResistiveMv() {
  digitalWrite(PIN_PROBE_PWR, HIGH);
  delay(50);                               // รอให้แรงดันนิ่ง
  int mv = readMilliVoltsMedian(PIN_SOIL_RES);
  digitalWrite(PIN_PROBE_PWR, LOW);
  return mv;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_PROBE_PWR, OUTPUT);
  digitalWrite(PIN_PROBE_PWR, LOW);
}

void loop() {
  int ntcMv = readMilliVoltsMedian(PIN_NTC);
  int resMv = readResistiveMv();
  int capMv = readMilliVoltsMedian(PIN_SOIL_CAP);
  int v2Mv  = readMilliVoltsMedian(PIN_SOIL_V2);

  // รูปแบบ name:value คั่นด้วยจุลภาค ใช้กับ Tools → Serial Plotter ได้ทันที
  Serial.printf("ntc_mv:%d,temp_c:%.1f,res_mv:%d,res_pct:%.0f,cap_mv:%d,cap_pct:%.0f,v2_mv:%d\n",
                ntcMv, ntcCelsius(ntcMv),
                resMv, toPercent(resMv, RES_DRY_MV, RES_WET_MV),
                capMv, toPercent(capMv, CAP_DRY_MV, CAP_WET_MV),
                v2Mv);
  delay(1000);
}
