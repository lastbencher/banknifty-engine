from dotenv import load_dotenv
import os

from integrate import ConnectToIntegrate

load_dotenv()

print("TOKEN:", os.getenv("API_TOKEN"))
print("SECRET EXISTS:", os.getenv("API_SECRET") is not None)

conn = ConnectToIntegrate()

try:
    conn.login(
        api_token=os.getenv("API_TOKEN"),
        api_secret=os.getenv("API_SECRET")
    )

    print("LOGIN OK")

except Exception as e:
    print("LOGIN FAILED:")
    print(repr(e))