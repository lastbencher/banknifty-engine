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

for token in [
    "66068",  # May
    "62326",  # Jun
    "61088",  # Jul
]:
    try:

        r = conn.send_request(
            route_prefix="https://data.definedgesecurities.com/sds/history/",
            route=f"NFO/{token}/day/010520260000/260520260000",
            method="GET"
        )

        rows = list(r["data"])

        print(token, "ROWS:", len(rows))

    except Exception as e:
        print(token, "FAILED", e)