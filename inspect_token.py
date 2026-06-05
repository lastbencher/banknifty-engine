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

try:

    r = conn._req_sess.get(
        "https://data.definedgesecurities.com/sds/history/NFO/66068/day/010520260000/260520260000"
    )

    print("STATUS:", r.status_code)
    print("HEADERS:", r.headers)
    print("TEXT:")
    print(r.text[:1000])

except Exception as e:
    print(e)