// TGR2026 Track 1 Lab Sheet · Lab 7
// เซ็นเซอร์ความชื้นเมล็ดกาแฟ: สั่ง tare / measure ผ่าน MQTT
// ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran
// บอร์ด: ESP32S3 Dev Module, Flash 16MB, PSRAM: OPI PSRAM

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ===================== ตั้งค่า =====================
const char* WIFI_SSID = "TGR_TEAM";
const char* WIFI_PASS = "12345678";
const char* MQTT_HOST = "192.168.1.50";   // IP ของ broker (Pi)
const uint16_t MQTT_PORT = 1883;
const char* TEAM      = "kmitl01";
// ====================================================

WiFiClient net;
PubSubClient mqtt(net);

String deviceId, tData, tStatus, tCmd, tAck;
uint32_t publishInterval = 5000;   // ms (เปลี่ยนได้ผ่านคำสั่ง)
uint32_t lastPublish = 0, lastReconnect = 0, seq = 0;

// >>> Lab 3–7: วางขา ค่าคงที่ struct และฟังก์ชันของเซ็นเซอร์ไว้ตรงนี้ (ก่อนฟังก์ชันแรกของไฟล์) <<<
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

String tResult;                 // ใน makeTopics(): tResult = base + "/result";
volatile bool measureRequested = false;
volatile bool tareRequested = false;
char sampleId[32] = "";

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

// ---------- รับคำสั่งจาก broker ----------
void onMessage(char* topic, byte* payload, unsigned int len) {
  Serial.printf("<< %s : %.*s\n", topic, len, (char*)payload);

  JsonDocument cmdDoc, ack;
  DeserializationError err = deserializeJson(cmdDoc, payload, len);
  if (err) {
    ack["ok"] = false;
    ack["error"] = err.c_str();
  } else {
    const char* cmd = cmdDoc["cmd"] | "";   // ถ้าไม่มีฟิลด์ cmd ใช้ ""
    ack["cmd"] = cmd;
    if (strcmp(cmd, "interval") == 0) {
      uint32_t ms = cmdDoc["ms"] | 5000;
      publishInterval = (ms < 500) ? 500 : ms;   // กันค่าต่ำเกินไป
      ack["ok"] = true;
      ack["interval_ms"] = publishInterval;
    } else if (strcmp(cmd, "led") == 0) {
      int v = cmdDoc["value"] | 0;
      rgbLedWrite(RGB_BUILTIN, 0, v ? 40 : 0, 0);
      ack["ok"] = true;
      ack["led"] = v;
    } else if (strcmp(cmd, "ping") == 0) {
      ack["ok"] = true;
      ack["uptime_ms"] = millis();
    } else if (strcmp(cmd, "measure") == 0) {
      strlcpy(sampleId, cmdDoc["sample_id"] | "unknown", sizeof(sampleId));
      measureRequested = true;
      ack["ok"] = true;
    } else if (strcmp(cmd, "tare") == 0) {
      tareRequested = true;
      ack["ok"] = true;
    } else {
      ack["ok"] = false;
      ack["error"] = "unknown cmd";
    }
  }
  char buf[256];
  size_t n = serializeJson(ack, buf, sizeof(buf));
  mqtt.publish(tAck.c_str(), (const uint8_t*)buf, n, false);
}

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

// ---------- สร้างและส่ง JSON ----------
void publishData() {
  JsonDocument doc;
  doc["team"]   = TEAM;
  doc["device"] = deviceId;
  doc["seq"]    = ++seq;
  time_t now = time(nullptr);
  doc["ts"]     = (now > 1700000000) ? (uint32_t)now : 0;   // 0 = ยังไม่ได้เวลาจาก NTP
  doc["uptime_ms"] = millis();
  doc["rssi_dbm"]  = WiFi.RSSI();
  doc["heap_free"] = ESP.getFreeHeap();
  // >>> Lab ถัดไปเติมค่าเซ็นเซอร์ตรงนี้ เช่น doc["temp_c"] = t; <<<

  char buf[768];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  bool ok = mqtt.publish(tData.c_str(), (const uint8_t*)buf, n, false);
  Serial.printf(">> %s %s%s\n", tData.c_str(), buf, ok ? "" : "  (FAILED)");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  connectWiFi();
  makeTopics();
  configTime(0, 0, "pool.ntp.org", "time.google.com");   // เวลา UTC (ต้องมีอินเทอร์เน็ต)
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(1024);   // สำคัญ! ค่าเริ่มต้น 256 byte ส่ง JSON ยาวไม่ได้
  mqtt.setKeepAlive(15);
  pinMode(PIN_BEAN_CHARGE, OUTPUT);
  digitalWrite(PIN_BEAN_CHARGE, LOW);
  pinMode(PIN_PROBE_PWR, OUTPUT);
  digitalWrite(PIN_PROBE_PWR, LOW);
  Serial.println("Device id: " + deviceId);
}

void loop() {
  if (tareRequested) {
    tareRequested = false;
    emptyBaseline = measureRaw(32).value;
    Serial.printf("tare baseline = %.1f\n", emptyBaseline);
  }
  if (measureRequested && mqtt.connected()) {
    measureRequested = false;
    Stat st = measureRaw(32);
    float net = st.value - emptyBaseline;
    bool inRange;
    float mc = rawToMoisture(net, inRange);

    JsonDocument r;
    r["team"]      = TEAM;
    r["device"]    = deviceId;
    r["sample_id"] = sampleId;
    r["ts"]        = (uint32_t)time(nullptr);
    r["method"]    = (METHOD == RC_TIMING) ? "cap_rc" : (METHOD == TOUCH) ? "cap_touch" : "resistive";
    r["raw"]       = roundf(st.value);
    r["raw_net"]   = roundf(net);
    r["raw_sd"]    = roundf(st.sd * 10) / 10.0f;
    r["moisture_pct"] = roundf(mc * 10) / 10.0f;
    r["in_range"]  = inRange;
    r["ok"]        = inRange && st.sd < 0.05f * st.value;   // แกว่งเกิน 5% ถือว่าไม่น่าเชื่อถือ
    char buf[512];
    size_t n = serializeJson(r, buf, sizeof(buf));
    mqtt.publish(tResult.c_str(), (const uint8_t*)buf, n, false);
    Serial.println(buf);
  }
  if (!mqtt.connected()) {
    if (millis() - lastReconnect > 3000) {   // ลองใหม่ทุก 3 s โดยไม่ค้าง loop
      lastReconnect = millis();
      mqttConnect();
    }
  } else {
    mqtt.loop();   // ต้องเรียกบ่อย ๆ เพื่อรับข้อความและรักษา keepalive
  }

  if (mqtt.connected() && millis() - lastPublish >= publishInterval) {
    lastPublish = millis();
    publishData();
  }
}
