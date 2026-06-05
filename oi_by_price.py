import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

df["oi_change"] = df["oi"].diff()

df["price_bin"] = (
    (df["close"] / 20).round() * 20
)

result = (
    df.groupby("price_bin")["oi_change"]
      .sum()
      .sort_values(ascending=False)
)

print(result.head(20))


