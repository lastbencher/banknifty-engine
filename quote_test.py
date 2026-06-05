from dotenv import load_dotenv
import os

from integrate import ConnectToIntegrate, IntegrateData

load_dotenv()

conn = ConnectToIntegrate()

conn.login(
    api_token=os.getenv("API_TOKEN"),
    api_secret=os.getenv("API_SECRET")
)

data = IntegrateData(conn)

q = data.quotes(
    exchange="NFO",
    trading_symbol="BANKNIFTY26MAY26F"
)

print(q)


