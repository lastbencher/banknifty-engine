from integrate import ConnectToIntegrate

conn = ConnectToIntegrate()

for s in conn.symbols:

    if s.get("symbol") == "BANKNIFTY":
        print(
            s.get("trading_symbol"),
            "|",
            s.get("instrument_type"),
            "|",
            s.get("expiry")
        )