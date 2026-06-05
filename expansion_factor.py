import pandas as pd

df = pd.read_csv("ib_research.csv")

df["expansion_factor"] = (
    df["day_range"] / df["ib_range"]
)

print("\nOVERALL")
print(df["expansion_factor"].describe().round(2))

print("\nBY IB TYPE")

print(
    df.groupby("ib_type")["expansion_factor"]
      .agg(["count", "mean", "median"])
      .round(2)
)