from integrate import ConnectToIntegrate

conn = ConnectToIntegrate()

for s in conn.symbols:

    txt = str(s).upper()

    if "BANK" in txt:
        print(s)