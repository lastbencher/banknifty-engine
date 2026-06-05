from dotenv import load_dotenv
import os

from datetime import datetime

from integrate import (
    ConnectToIntegrate,
    IntegrateData
)

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

print("LOGIN OK")

data = IntegrateData(conn)

tests = [
    ("30d", datetime(2026,4,1)),
    ("90d", datetime(2026,2,1)),
    ("180d", datetime(2025,11,1)),
    ("270d", datetime(2025,8,1)),
    ("365d", datetime(2025,5,1)),
    ("730d", datetime(2024,5,1)),
]

for label, start_date in tests:

    try:

        candles = list(
            data.historical_data(
                exchange="NSE",
                trading_symbol="Nifty Bank",
                timeframe="minute",
                start=start_date,
                end=datetime.now()
            )
        )

        print(
            f"{label:>5} -> {len(candles)} rows"
        )

    except Exception as e:

        print(
            f"{label:>5} -> FAILED -> {e}"
        )