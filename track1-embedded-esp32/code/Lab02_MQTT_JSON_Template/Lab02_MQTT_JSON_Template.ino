// TGR2026 Track 1 Lab Sheet · Lab 2
// Template WiFi + MQTT + JSON (แก้ส่วนตั้งค่าก่อนอัปโหลด)
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
  Serial.println("Device id: " + deviceId);
}

void loop() {
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
