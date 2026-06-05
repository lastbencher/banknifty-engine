from dotenv import load_dotenv
import os

from datetime import datetime, timedelta

from integrate import (
    ConnectToIntegrate,
    IntegrateData
)

import pandas as pd

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

data = IntegrateData(conn)

# Last 90 days
start = datetime.now() - timedelta(days=180)
end = datetime.now()

candles = list(
    data.historical_data(
        exchange="NSE",
        trading_symbol="Nifty Bank",
        timeframe="minute",
        start=start,
        end=end
    )
)

df = pd.DataFrame(candles)

print(df.head())

print("\nRows:", len(df))

if len(df) > 0:
    print("\nFIRST:")
    print(df.iloc[0])

    print("\nLAST:")
    print(df.iloc[-1])

df.to_csv("banknifty.csv", index=False)

print("\nSaved to banknifty.csv")