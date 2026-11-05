import asyncio
import json
import os
import websockets
from dotenv import load_dotenv
from gpiozero import MotionSensor, MCP3008, Buzzer, LED

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "ws://10.13.213.14:8000/ws/pi")
PRESSURE_THRESHOLD = float(os.getenv("PRESSURE_THRESHOLD", "0.35"))
PI_SECRET_KEY = os.getenv("PI_SECRET_KEY")

pir = MotionSensor(23)
pressure = MCP3008(0)
buzzer = Buzzer(24, active_high=False)
led = LED(25)


async def send_readings(websocket):
    while True:
        raw_val = pressure.value
        data = {
            "pir_connected": True,
            "pressure_connected": True,
            "motion_detected": int(pir.is_active),
            "pressure_detected": int(raw_val >= PRESSURE_THRESHOLD),
            "pressure_raw": round(raw_val, 3),
        }
        await websocket.send(json.dumps(data))
        await asyncio.sleep(1)


async def receive_commands(websocket):
    async for message in websocket:
        try:
            cmd = json.loads(message)
            device = cmd.get("device")
            action = cmd.get("action")

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
                    await asyncio.sleep(0.3)
                    buzzer.off()
        except Exception as e:
            print(f"Command error: {e}")


async def main():
    while True:
        try:
            print(f"Connecting to {SERVER_URL}...")
            # Send the secret key securely in the HTTP headers during the handshake
            async with websockets.connect(SERVER_URL, additional_headers={"X-Pi-Secret": PI_SECRET_KEY}) as ws:
                print("Successfully connected to AntiBurnout backend!")
                await asyncio.gather(send_readings(ws), receive_commands(ws))
        except Exception as e:
            print(f"Connection failed ({e}). Retrying in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping sensors...")
    finally:
        led.off()
        buzzer.off()
