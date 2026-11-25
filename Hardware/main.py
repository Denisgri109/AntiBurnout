import json
import os
import time
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from gpiozero import MotionSensor, MCP3008, Buzzer, LED

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
PRESSURE_THRESHOLD = float(os.getenv("PRESSURE_THRESHOLD", "0.35"))

SENSOR_TOPIC = "antiburnout/sensors/data"
CONTROL_TOPIC = "antiburnout/actuators/control/+"

pir = MotionSensor(23)
pressure = MCP3008(0)
buzzer = Buzzer(24, active_high=False)
led = LED(25)


def read_sensors():
    raw_val = pressure.value
    return {
        "pir_connected": True,
        "pressure_connected": True,
        "motion_detected": int(pir.is_active),
        "pressure_detected": int(raw_val >= PRESSURE_THRESHOLD),
        "pressure_raw": round(raw_val, 3),
    }


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Successfully connected to AntiBurnout MQTT broker!")
        client.subscribe(CONTROL_TOPIC)
    else:
        print(f"Connection failed ({reason_code}). Retrying...")


def on_message(client, userdata, msg):
    device = msg.topic.split("/")[-1]
    try:
        action = json.loads(msg.payload).get("action")
    except (ValueError, AttributeError) as e:
        print(f"Command error: {e}")
        return

    if device == "led":
        if action == "blink":
            led.blink(on_time=0.3, off_time=0.3, n=5)
        elif action == "on":
            led.on()
        elif action == "off":
            led.off()

    elif device == "buzzer":
        if action == "beep":
            buzzer.on()
            time.sleep(0.3)
            buzzer.off()


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    
    client.connect_async(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    try:
        while True:
            client.publish(SENSOR_TOPIC, json.dumps(read_sensors()))
            time.sleep(1)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopping sensors...")
    finally:
        led.off()
        buzzer.off()
