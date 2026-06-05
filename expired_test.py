from dotenv import load_dotenv
import os

from datetime import datetime

from integrate import ConnectToIntegrate, IntegrateData

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

data = IntegrateData(conn)

candles = list(
    data.historical_data(
        exchange="NFO",
        trading_symbol="BANKNIFTY30JAN20F",
        timeframe="day",
        start=datetime(2020, 1, 1),
        end=datetime(2020, 1, 31)
    )
)

print("Rows:", len(candles))

if candles:
    print(candles[0])
    print(candles[-1])