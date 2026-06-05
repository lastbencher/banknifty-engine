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
        exchange="NSE",
        trading_symbol="BANKNIFTY1-EQ",
        timeframe="day",
        start=datetime(2020, 1, 1),
        end=datetime.now()
    )
)

print("Rows:", len(candles))

if candles:
    print("FIRST:", candles[0])
    print("LAST :", candles[-1])