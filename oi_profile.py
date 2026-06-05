import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

df["price_change"] = df["close"].diff()
df["oi_change"] = df["oi"].diff()

def classify(row):

    if row["price_change"] > 0 and row["oi_change"] > 0:
        return "Long Build"

    if row["price_change"] < 0 and row["oi_change"] > 0:
        return "Short Build"

    if row["price_change"] > 0 and row["oi_change"] < 0:
        return "Short Cover"

    if row["price_change"] < 0 and row["oi_change"] < 0:
        return "Long Unwind"

    return "Neutral"

df["regime"] = df.apply(classify, axis=1)

print(df["regime"].value_counts())


