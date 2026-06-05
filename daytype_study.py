import pandas as pd

df = pd.read_csv("ib_research.csv")

day_types = {
    "2026-05-13": "Normal Day",
    "2026-05-14": "Normal Variation",
    "2026-05-15": "Normal Day",
    "2026-05-18": "Normal Variation",
    "2026-05-19": "Normal Day",
    "2026-05-20": "Trend Day",
    "2026-05-21": "Normal Variation",
    "2026-05-22": "Normal Day",
}

df["day_type"] = df["date"].map(day_types)

print("\nDATASET")
print(df)

print("\n" + "=" * 60)
print("IB TYPE vs DAY TYPE")
print("=" * 60)

table = pd.crosstab(
    df["ib_type"],
    df["day_type"]
)

print(table)

print("\n" + "=" * 60)
print("ROW PERCENTAGES")
print("=" * 60)

pct = table.div(table.sum(axis=1), axis=0) * 100

print(pct.round(1))