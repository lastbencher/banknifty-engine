import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

# 20 point bins for BankNifty
df["price_bin"] = (df["close"] / 20).round() * 20

vp = (
    df.groupby("price_bin")["volume"]
    .sum()
    .sort_values(ascending=False)
)

print("\nTOP 30 VOLUME NODES\n")
print(vp.head(30))

print("\nCOMPOSITE POC")
print(vp.index[0])




