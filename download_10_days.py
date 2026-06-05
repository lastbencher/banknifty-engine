from dotenv import load_dotenv
import os

from datetime import datetime, timedelta
import pandas as pd

from integrate import ConnectToIntegrate, IntegrateData

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

data = IntegrateData(conn)

all_data = []

for days_back in range(1, 11):

    day = datetime.now() - timedelta(days=days_back)

    start = datetime(
        day.year,
        day.month,
        day.day,
        9,
        15
    )

    end = datetime(
        day.year,
        day.month,
        day.day,
        15,
        30
    )

    try:

        candles = list(
            data.historical_data(
                exchange="NFO",
                trading_symbol="BANKNIFTY",
                timeframe="minute",
                start=start,
                end=end
            )
        )

        print(day.date(), "Rows:", len(candles))

        all_data.extend(candles)

    except Exception as e:
        print(day.date(), "ERROR:", e)

df = pd.DataFrame(all_data)

df = df.sort_values("datetime")

df.to_csv("banknifty_10d.csv", index=False)

print("\nTotal Rows:", len(df))
print("Saved banknifty_10d.csv")



