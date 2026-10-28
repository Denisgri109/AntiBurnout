import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL")

async def connect_to_backend():
    while True:
        try:
            print(f"Attempting to connect to {SERVER_URL}...")
            async with websockets.connect(SERVER_URL) as websocket:
                print("Successfully connected!")
                
                while True:
                    await websocket.send("Pi is active")
                    await asyncio.sleep(5)
                    
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server. Reconnecting in 5s...")
        except ConnectionRefusedError:
            print("Server is down. Retrying in 5s...")
        except Exception as e:
            print(f"Network error: {e}. Retrying in 5s...")
            
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_backend())