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
        trading_symbol="BANKNIFTY26MAY26F",
        timeframe="minute",
        start=datetime(2026, 5, 22, 9, 15),
        end=datetime(2026, 5, 22, 15, 30)
    )
)

print("Rows:", len(candles))
print(candles[0])
print(candles[-1])


