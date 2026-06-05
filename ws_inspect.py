from dotenv import load_dotenv
import os
import time

from integrate import (
    ConnectToIntegrate,
    IntegrateWebSocket
)

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

ws = IntegrateWebSocket(conn)

def on_connect():
    print("CONNECTED")

def on_login(data):
    print("LOGIN")
    print(data)

def on_tick(data):
    print("\nTICK UPDATE")
    print(data)

def on_depth(data):
    print("\nDEPTH UPDATE")
    print(data)

def on_ack(data):
    print("\nACK")
    print(data)

ws.on_connect = on_connect
ws.on_login = on_login
ws.on_tick_update = on_tick
ws.on_depth_update = on_depth
ws.on_acknowledgement = on_ack

print("Starting websocket...")

ws.connect()

while True:
    time.sleep(1)



