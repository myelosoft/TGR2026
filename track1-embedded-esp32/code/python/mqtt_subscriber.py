import json
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
    except json.JSONDecodeError:
        print("bad json:", msg.payload)
        return
    print(msg.topic, data.get("seq"), data)

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.on_message = on_message
c.connect("192.168.1.50", 1883)
c.subscribe("tgr2026/+/+/data")
c.loop_forever()
