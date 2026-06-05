from dotenv import load_dotenv
import os

from integrate import ConnectToIntegrate, IntegrateData

load_dotenv()

print("TOKEN:", os.getenv("API_TOKEN") is not None)
print("SECRET:", os.getenv("API_SECRET") is not None)

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

print("LOGIN SUCCESS")


