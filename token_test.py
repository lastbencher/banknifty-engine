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

r = conn.send_request(
    route_prefix="https://data.definedgesecurities.com/sds/history/",
    route="NSE/26009/day/010120200000/010520260000",
    method="GET"
)

rows = list(r["data"])

print("Rows:", len(rows))

if rows:
    print("\nFIRST:")
    print(rows[0])

    print("\nLAST:")
    print(rows[-1])