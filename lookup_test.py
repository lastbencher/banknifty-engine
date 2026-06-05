from integrate import ConnectToIntegrate

conn = ConnectToIntegrate()

exchange = "NSE"
trading_symbol = "Nifty Bank"

token = next(
    (
        i["token"]
        for i in conn.symbols
        if i["segment"] == exchange
        and i["trading_symbol"] == trading_symbol
    ),
    None,
)

print("TOKEN =", token)