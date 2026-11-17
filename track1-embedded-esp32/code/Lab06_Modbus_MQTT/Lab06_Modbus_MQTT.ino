// TGR2026 Track 1 Lab Sheet · Lab 6
// อ่าน SHTC3 Modbus RTU แล้วส่ง MQTT
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

struct MbCache { float tempC = NAN, rhPct = NAN; int err = 1; uint32_t readAt = 0; } mbCache;
uint32_t lastMbRead = 0;

void pollModbus() {
  if (millis() - lastMbRead < 3000) return;
  lastMbRead = millis();
  uint16_t r[2];
  mbCache.err = modbusRead(MB_ADDR, MB_FC, 0x0000, 2, r);
  if (mbCache.err == 0) {
    mbCache.tempC  = (int16_t)r[IDX_TEMP] / 10.0f;   // int16 รองรับค่าติดลบ
    mbCache.rhPct  = r[IDX_RH] / 10.0f;
    mbCache.readAt = millis();
  }
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
  JsonObject m = doc["shtc3_485"].to<JsonObject>();
  m["ok"]  = (mbCache.err == 0);
  m["err"] = mbCache.err;
  if (mbCache.err == 0) {
    m["temp_c"] = mbCache.tempC;
    m["rh_pct"] = mbCache.rhPct;
  }

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
  RS485.begin(MB_BAUD, SERIAL_8N1, PIN_485_RX, PIN_485_TX);
  Serial.println("Device id: " + deviceId);
}

void loop() {
  pollModbus();
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
