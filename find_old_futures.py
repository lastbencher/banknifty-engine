from dotenv import load_dotenv
import os

from integrate import ConnectToIntegrate

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

print("LOGIN OK")

count = 0

for s in conn.symbols:

    if (
        s["segment"] == "NFO"
        and s["symbol"] == "BANKNIFTY"
        and s["instrument_type"] == "FUTIDX"
    ):
        print(s)
        count += 1

print("\nTOTAL:", count)