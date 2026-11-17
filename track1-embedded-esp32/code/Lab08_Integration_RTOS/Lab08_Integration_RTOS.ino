// TGR2026 Track 1 Lab Sheet · Lab 8
// Firmware รวมทุกเซ็นเซอร์ด้วย FreeRTOS (2 task, 2 queue, 1 mutex)
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

#include <DHT.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AM2315.h>

// ===================== ตั้งค่า =====================
const char* WIFI_SSID = "TGR_TEAM";
const char* WIFI_PASS = "12345678";
const char* MQTT_HOST = "192.168.1.50";   // IP ของ broker (Pi)
const uint16_t MQTT_PORT = 1883;
const char* TEAM      = "kmitl01";
// ====================================================

WiFiClient net;
PubSubClient mqtt(net);

String deviceId, tData, tStatus, tCmd, tAck, tResult;
uint32_t publishInterval = 5000;   // ms (เปลี่ยนได้ผ่านคำสั่ง)
uint32_t lastPublish = 0, lastReconnect = 0, seq = 0;

// ================= Lab 8: ชนิดข้อมูลกลาง (ต้องอยู่ก่อนฟังก์ชันแรก) =================
// ค่าล่าสุดของเซ็นเซอร์ทุกตัว (task เซ็นเซอร์เขียน, task เครือข่ายอ่าน)
struct Snapshot {
  int   ntcMv = 0;      float ntcC = NAN;
  int   capMv = 0;      float capPct = NAN;
  float dhtC = NAN,  dhtRh = NAN;
  float bmeC = NAN,  bmeRh = NAN, bmeHpa = NAN;
  float amC  = NAN,  amRh  = NAN;
  float mbC  = NAN,  mbRh  = NAN; int mbErr = 1;
  uint32_t updatedAt = 0;
};
Snapshot snap;
SemaphoreHandle_t snapMutex;

// คำสั่งจาก MQTT → task เซ็นเซอร์
struct Command { char cmd[16]; char sampleId[32]; };
QueueHandle_t cmdQueue;

// ผลการวัดเมล็ด → task เครือข่าย
struct BeanResult { char sampleId[32]; float raw, net, sd, mc; bool inRange; };
QueueHandle_t resultQueue;

TaskHandle_t hNet = nullptr, hSensors = nullptr;

// ================= Lab 7: เซลล์วัดเมล็ด =================
// ---------------- เลือกวิธีวัด ----------------
enum Method { RC_TIMING, TOUCH, RESISTIVE };
const Method METHOD = RC_TIMING;

const int PIN_BEAN_SENSE  = 2;    // ADC1 / touch / digital input
const int PIN_BEAN_CHARGE = 11;   // ชาร์จผ่าน R 1M (แบบ A)
const int PIN_PROBE_PWR   = 16;   // จ่ายไฟอิเล็กโทรด (แบบ B)

// ผลการวัดหลายครั้ง (ประกาศ struct ไว้ก่อนฟังก์ชันแรกเสมอ)
struct Stat { float value; float sd; };

// ---------------- อ่านดิบ 1 ครั้ง ----------------
float rcCyclesOnce() {
  pinMode(PIN_BEAN_SENSE, OUTPUT);
  digitalWrite(PIN_BEAN_SENSE, LOW);        // คายประจุ
  digitalWrite(PIN_BEAN_CHARGE, LOW);
  delayMicroseconds(1000);
  pinMode(PIN_BEAN_SENSE, INPUT);
  uint32_t c0 = ESP.getCycleCount();
  digitalWrite(PIN_BEAN_CHARGE, HIGH);      // เริ่มชาร์จ
  while (digitalRead(PIN_BEAN_SENSE) == LOW) {
    if (ESP.getCycleCount() - c0 > 240UL * 20000) break;   // กันค้างที่ 20 ms
  }
  uint32_t dc = ESP.getCycleCount() - c0;
  digitalWrite(PIN_BEAN_CHARGE, LOW);
  return (float)dc;
}

float readOnce() {
  switch (METHOD) {
    case RC_TIMING: return rcCyclesOnce();
    case TOUCH:     return (float)touchRead(PIN_BEAN_SENSE);
    default: {
      digitalWrite(PIN_PROBE_PWR, HIGH);
      delay(20);
      float mv = analogReadMilliVolts(PIN_BEAN_SENSE);
      digitalWrite(PIN_PROBE_PWR, LOW);
      return mv;
    }
  }
}

// ---------------- อ่าน n ครั้ง: ค่ากลางแบบตัดหัวท้าย + ส่วนเบี่ยงเบนมาตรฐาน ----------------

Stat measureRaw(int n = 32) {
  float x[64];
  n = constrain(n, 4, 64);
  for (int i = 0; i < n; i++) { x[i] = readOnce(); delay(3); }
  for (int i = 1; i < n; i++) {               // sort
    float k = x[i]; int j = i - 1;
    while (j >= 0 && x[j] > k) { x[j + 1] = x[j]; j--; }
    x[j + 1] = k;
  }
  int a = n / 4, b = n - n / 4;               // ตัด 25% หัวและท้าย
  float s = 0, s2 = 0;
  for (int i = a; i < b; i++) { s += x[i]; s2 += x[i] * x[i]; }
  int m = b - a;
  float mean = s / m;
  float var  = s2 / m - mean * mean;
  return { mean, var > 0 ? sqrtf(var) : 0 };
}

// ---------------- ตาราง calibration: ค่าดิบ (หักค่าภาชนะเปล่าแล้ว) → ความชื้น % ----------------
// เรียงค่าดิบจากน้อยไปมาก ค่าตัวอย่างนี้สมมติ ต้องแทนด้วยผลจากขั้นที่ 5
struct CalPoint { float raw; float mc; };
CalPoint CAL[] = { {1000, 8.0}, {1600, 10.0}, {2300, 12.0}, {3100, 14.0}, {4000, 16.0} };
const int NCAL = sizeof(CAL) / sizeof(CAL[0]);
float emptyBaseline = 0;   // ค่าภาชนะเปล่า วัดด้วยคำสั่ง {"cmd":"tare"}

float rawToMoisture(float raw, bool &inRange) {
  inRange = (raw >= CAL[0].raw && raw <= CAL[NCAL - 1].raw);
  if (raw <= CAL[0].raw) return CAL[0].mc;          // ไม่เดาค่านอกตาราง
  if (raw >= CAL[NCAL - 1].raw) return CAL[NCAL - 1].mc;
  for (int i = 1; i < NCAL; i++) {
    if (raw <= CAL[i].raw) {
      float f = (raw - CAL[i - 1].raw) / (CAL[i].raw - CAL[i - 1].raw);
      return CAL[i - 1].mc + f * (CAL[i].mc - CAL[i - 1].mc);
    }
  }
  return NAN;
}


// ---------- WiFi ----------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWiFi OK  IP=%s  RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

// ---------- ตั้งชื่ออุปกรณ์และ topic จาก MAC (ไม่ซ้ำกันแน่นอน) ----------
void makeTopics() {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char id[24];
  snprintf(id, sizeof(id), "esp32s3-%02x%02x%02x", mac[3], mac[4], mac[5]);
  deviceId = id;
  String base = String("tgr2026/") + TEAM + "/" + deviceId;
  tData   = base + "/data";
  tStatus = base + "/status";
  tCmd    = base + "/cmd";
  tAck    = base + "/ack";
  tResult = base + "/result";
}

// ================= Lab 3: analog =================
// ---------------- ขา ----------------
const int PIN_NTC       = 4;
const int PIN_SOIL_RES  = 5;
const int PIN_SOIL_CAP  = 6;
const int PIN_SOIL_V2   = 7;

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

// ================= Lab 6: Modbus RTU =================
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

const uint32_t MB_BAUD = 9600;   // จากผลสแกน
const uint8_t  MB_ADDR = 1;
const uint8_t  MB_FC   = 0x03;
const int      IDX_TEMP = 0;     // รีจิสเตอร์ไหนคืออุณหภูมิ (0 หรือ 1)
const int      IDX_RH   = 1;

// ---------------- วัตถุของเซ็นเซอร์ ----------------
const int PIN_DHT = 15;
DHT dht(PIN_DHT, DHT22);
Adafruit_BME280 bme;
Adafruit_AM2315 am2315(&Wire);
bool bmeOk = false;

// ---------- เชื่อม MQTT พร้อมฝาก LWT ----------
bool mqttConnect() {
  Serial.printf("MQTT connecting %s:%u ... ", MQTT_HOST, MQTT_PORT);
  bool ok = mqtt.connect(deviceId.c_str(),          // client id ต้องไม่ซ้ำกับใคร
                         nullptr, nullptr,          // ไม่มี user/pass
                         tStatus.c_str(), 1, true,  // LWT topic, QoS 1, retain
                         "{\"online\":false}");
  if (ok) {
    Serial.println("OK");
    mqtt.publish(tStatus.c_str(), "{\"online\":true}", true);   // retain
    mqtt.subscribe(tCmd.c_str());
  } else {
    Serial.printf("FAIL rc=%d\n", mqtt.state());
  }
  return ok;
}


// ================= Lab 8: RTOS =================
void taskSensors(void *pv) {
  uint32_t lastFast = 0, lastSlow = 0;
  for (;;) {
    // (1) คำสั่งวัดเมล็ด มาก่อนเสมอ (รอ 0 ms ถ้าไม่มีคำสั่ง)
    Command c;
    if (xQueueReceive(cmdQueue, &c, 0) == pdTRUE) {
      if (strcmp(c.cmd, "tare") == 0) {
        emptyBaseline = measureRaw(32).value;
      } else if (strcmp(c.cmd, "measure") == 0) {
        Stat st = measureRaw(32);
        BeanResult r;
        strlcpy(r.sampleId, c.sampleId, sizeof(r.sampleId));
        r.raw = st.value;
        r.sd  = st.sd;
        r.net = st.value - emptyBaseline;
        r.mc  = rawToMoisture(r.net, r.inRange);
        xQueueSend(resultQueue, &r, 0);
      }
    }

    // (2) analog ทุก 1 s
    if (millis() - lastFast >= 1000) {
      lastFast = millis();
      int ntcMv = readMilliVoltsMedian(PIN_NTC);
      int capMv = readMilliVoltsMedian(PIN_SOIL_CAP);
      xSemaphoreTake(snapMutex, portMAX_DELAY);       // ถือ mutex แค่ช่วงคัดลอก
      snap.ntcMv = ntcMv;  snap.ntcC = ntcCelsius(ntcMv);
      snap.capMv = capMv;  snap.capPct = toPercent(capMv, CAP_DRY_MV, CAP_WET_MV);
      snap.updatedAt = millis();
      xSemaphoreGive(snapMutex);
    }

    // (3) เซ็นเซอร์ช้า ทุก 3 s
    if (millis() - lastSlow >= 3000) {
      lastSlow = millis();
      float dh = dht.readHumidity(), dt = dht.readTemperature();
      float bt = NAN, bh = NAN, bp = NAN;
      if (bmeOk) { bt = bme.readTemperature(); bh = bme.readHumidity(); bp = bme.readPressure() / 100.0f; }
      float at = NAN, ah = NAN;
      if (!am2315.readTemperatureAndHumidity(&at, &ah)) { at = NAN; ah = NAN; }
      uint16_t r[2];
      int err = modbusRead(MB_ADDR, MB_FC, 0x0000, 2, r);

      xSemaphoreTake(snapMutex, portMAX_DELAY);
      snap.dhtC = dt;  snap.dhtRh = dh;
      snap.bmeC = bt;  snap.bmeRh = bh;  snap.bmeHpa = bp;
      snap.amC  = at;  snap.amRh  = ah;
      snap.mbErr = err;
      if (err == 0) { snap.mbC = (int16_t)r[IDX_TEMP] / 10.0f; snap.mbRh = r[IDX_RH] / 10.0f; }
      else          { snap.mbC = NAN; snap.mbRh = NAN; }
      xSemaphoreGive(snapMutex);
    }

    vTaskDelay(pdMS_TO_TICKS(20));   // คืน CPU ให้ task อื่น
  }
}

// ใส่ตัวเลขลง JSON หรือ null ถ้าเป็น NaN
void putNum(JsonObject o, const char *key, float v, int dp = 1) {
  if (isnan(v)) { o[key] = nullptr; return; }
  float p = powf(10, dp);
  o[key] = roundf(v * p) / p;
}

void onMessage(char *topic, byte *payload, unsigned int len) {
  JsonDocument in, ack;
  if (deserializeJson(in, payload, len)) {
    ack["ok"] = false; ack["error"] = "bad json";
  } else {
    const char *cmd = in["cmd"] | "";
    ack["cmd"] = cmd;
    if (strcmp(cmd, "measure") == 0 || strcmp(cmd, "tare") == 0) {
      Command c = {};
      strlcpy(c.cmd, cmd, sizeof(c.cmd));
      strlcpy(c.sampleId, in["sample_id"] | "unknown", sizeof(c.sampleId));
      bool queued = xQueueSend(cmdQueue, &c, 0) == pdTRUE;   // queue เต็ม = ปฏิเสธ
      ack["ok"] = queued;
      if (!queued) ack["error"] = "busy";
    } else if (strcmp(cmd, "interval") == 0) {
      uint32_t ms = in["ms"] | 5000;
      publishInterval = (ms < 500) ? 500 : ms;
      ack["ok"] = true;
    } else if (strcmp(cmd, "ping") == 0) {
      ack["ok"] = true;
      ack["uptime_ms"] = millis();
    } else {
      ack["ok"] = false; ack["error"] = "unknown cmd";
    }
  }
  char buf[256];
  size_t n = serializeJson(ack, buf, sizeof(buf));
  mqtt.publish(tAck.c_str(), (const uint8_t *)buf, n, false);
}

void publishSnapshot() {
  Snapshot s;
  xSemaphoreTake(snapMutex, portMAX_DELAY);
  s = snap;                          // คัดลอกทั้งก้อนแล้วปล่อย mutex ทันที
  xSemaphoreGive(snapMutex);

  JsonDocument doc;
  doc["team"] = TEAM;  doc["device"] = deviceId;
  doc["seq"] = ++seq;  doc["ts"] = (uint32_t)time(nullptr);
  doc["age_ms"] = millis() - s.updatedAt;
  JsonObject o;
  o = doc["ntc"].to<JsonObject>();      o["raw_mv"] = s.ntcMv; putNum(o, "temp_c", s.ntcC);
  o = doc["soil_cap"].to<JsonObject>(); o["raw_mv"] = s.capMv; putNum(o, "pct", s.capPct, 0);
  o = doc["dht22"].to<JsonObject>();    putNum(o, "temp_c", s.dhtC);  putNum(o, "rh_pct", s.dhtRh);
  o = doc["bme280"].to<JsonObject>();   putNum(o, "temp_c", s.bmeC);  putNum(o, "rh_pct", s.bmeRh);
                                        putNum(o, "pressure_hpa", s.bmeHpa);
  o = doc["am2315"].to<JsonObject>();   putNum(o, "temp_c", s.amC);   putNum(o, "rh_pct", s.amRh);
  o = doc["shtc3_485"].to<JsonObject>(); o["err"] = s.mbErr;
                                        putNum(o, "temp_c", s.mbC);   putNum(o, "rh_pct", s.mbRh);
  char buf[1024];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(tData.c_str(), (const uint8_t *)buf, n, false);
}

void publishResult(const BeanResult &r) {
  JsonDocument doc;
  doc["team"] = TEAM;  doc["device"] = deviceId;
  doc["sample_id"] = r.sampleId;
  doc["ts"] = (uint32_t)time(nullptr);
  doc["raw"] = roundf(r.raw);  doc["raw_net"] = roundf(r.net);
  doc["raw_sd"] = roundf(r.sd * 10) / 10.0f;
  doc["moisture_pct"] = roundf(r.mc * 10) / 10.0f;
  doc["in_range"] = r.inRange;
  doc["ok"] = r.inRange && r.sd < 0.05f * r.raw;
  char buf[512];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(tResult.c_str(), (const uint8_t *)buf, n, false);
}

void setLed(uint8_t r, uint8_t g, uint8_t b) {   // เปลี่ยนสีเฉพาะเมื่อสถานะเปลี่ยน
  static uint32_t last = 0xFFFFFFFF;
  uint32_t now = (r << 16) | (g << 8) | b;
  if (now != last) { rgbLedWrite(RGB_BUILTIN, r, g, b); last = now; }
}

void taskNet(void *pv) {
  uint32_t lastPub = 0, lastTry = 0;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      setLed(40, 0, 0);                         // แดง: ไม่มี WiFi (ระบบต่อใหม่เอง)
    } else if (!mqtt.connected()) {
      setLed(40, 20, 0);                        // ส้ม: ไม่มี broker
      if (millis() - lastTry > 3000) { lastTry = millis(); mqttConnect(); }
    } else {
      setLed(0, 30, 0);                         // เขียว: พร้อม
      mqtt.loop();
      if (millis() - lastPub >= publishInterval) { lastPub = millis(); publishSnapshot(); }
      BeanResult r;
      while (xQueueReceive(resultQueue, &r, 0) == pdTRUE) publishResult(r);
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_PROBE_PWR, OUTPUT);    digitalWrite(PIN_PROBE_PWR, LOW);
  pinMode(PIN_BEAN_CHARGE, OUTPUT);  digitalWrite(PIN_BEAN_CHARGE, LOW);

  Wire.begin(8, 9);
  Wire.setClock(100000);
  bmeOk = bme.begin(0x76, &Wire) || bme.begin(0x77, &Wire);
  am2315.begin();
  dht.begin();
  RS485.begin(MB_BAUD, SERIAL_8N1, PIN_485_RX, PIN_485_TX);

  snapMutex   = xSemaphoreCreateMutex();
  cmdQueue    = xQueueCreate(4, sizeof(Command));
  resultQueue = xQueueCreate(4, sizeof(BeanResult));

  WiFi.setAutoReconnect(true);
  connectWiFi();
  makeTopics();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(1536);
  mqtt.setKeepAlive(15);

  //                       ฟังก์ชัน      ชื่อ       stack  param  priority handle     core
  xTaskCreatePinnedToCore(taskNet,     "net",     8192, nullptr, 2, &hNet,     0);
  xTaskCreatePinnedToCore(taskSensors, "sensors", 8192, nullptr, 1, &hSensors, 1);
}

void loop() {
  // loop() เหลือหน้าที่รายงานสุขภาพระบบทุก 10 s
  Serial.printf("heap=%u  stack_free net=%u sensors=%u\n",
                (unsigned)ESP.getFreeHeap(),
                (unsigned)uxTaskGetStackHighWaterMark(hNet),
                (unsigned)uxTaskGetStackHighWaterMark(hSensors));
  vTaskDelay(pdMS_TO_TICKS(10000));
}
