import pandas as pd

df = pd.read_csv("ib_research.csv")

corr = df["ib_range"].corr(df["day_range"])

print("\nCorrelation:", round(corr, 3))

print("\nAverage Day Range by IB Type\n")

print(
    df.groupby("ib_type")["day_range"]
      .agg(["count", "mean", "median"])
      .round(1)
)