import time
import random
import urllib.request
import urllib.parse

API_URL = "http://localhost:8000/api/sensor_log"

print("Starting AntiBurnout Sensor Simulation...")
print("Press Ctrl+C to stop.\n")

session_id = 1

while True:
    # 1 = sitting down, 0 = chair empty
    pressure = random.choice([0, 1, 1, 1])
    
    # 1 = motion detected, 0 = still
    motion = random.choice([0, 1])

    params = urllib.parse.urlencode({
        "session_id": session_id,
        "pressure_detected": pressure,
        "motion_detected": motion
    })

    url = f"{API_URL}?{params}"
    req = urllib.request.Request(url, method="POST")

    try:
        with urllib.request.urlopen(req) as response:
            print(f"[LOG] Sent -> Pressure: {pressure}, Motion: {motion} | Server Response: {response.status}")
    except Exception as e:
        print(f"[ERROR] Failed to send reading: {e}")

    time.sleep(5)