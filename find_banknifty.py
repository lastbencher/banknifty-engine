from integrate import ConnectToIntegrate

conn = ConnectToIntegrate()

for s in conn.symbols:
    if (
        s.get("symbol") == "BANKNIFTY"
        and s.get("instrument_type") == "FUTIDX"
    ):
        print(s)




