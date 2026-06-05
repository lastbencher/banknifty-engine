import pandas as pd

df = pd.read_csv("banknifty.csv")

df["datetime"] = pd.to_datetime(df["datetime"])
df["date"] = df["datetime"].dt.date

results = []

for d in sorted(df["date"].unique()):

    day = df[df["date"] == d]

    # Initial Balance = first 60 minutes
    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()

    ib_range = ib_high - ib_low

    day_high = day["high"].max()
    day_low = day["low"].min()

    day_range = day_high - day_low

    ratio = ib_range / day_range

    results.append({
        "date": d,
        "ib_range": round(ib_range),
        "day_range": round(day_range),
        "ratio": round(ratio, 3)
    })

r = pd.DataFrame(results)

# =====================================
# IB RANGE CLASSIFICATION
# Based on your actual percentiles:
# 25% = 432
# 75% = 548
# =====================================

r["ib_type"] = "NORMAL"

r.loc[r["ib_range"] < 432, "ib_type"] = "NARROW"
r.loc[r["ib_range"] > 548, "ib_type"] = "WIDE"

# =====================================
# EFFICIENCY CLASSIFICATION
# Based on actual percentiles:
# 25% = 0.415
# 75% = 0.767
# =====================================

r["efficiency_type"] = "BALANCED"

r.loc[r["ratio"] < 0.415, "efficiency_type"] = "EXPANSION"
r.loc[r["ratio"] > 0.767, "efficiency_type"] = "ROTATIONAL"

# Save for future studies

r.to_csv("ib_research.csv", index=False)

print("\nSaved ib_research.csv")

print("\n" + "=" * 60)
print("IB RESEARCH STUDY")
print("=" * 60)

print("\nPer Day:\n")
print(r.to_string(index=False))

print("\n" + "=" * 60)

print("\nIB RANGE STATISTICS")

print("\nAverage IB :", round(r["ib_range"].mean()))
print("Median IB  :", round(r["ib_range"].median()))

for p in [10, 25, 50, 75, 90]:
    print(
        f"{p}% :",
        round(r["ib_range"].quantile(p / 100))
    )

print("\n" + "=" * 60)

print("\nEFFICIENCY STATISTICS")

print("\nAverage Ratio :", round(r["ratio"].mean(), 3))
print("Median Ratio  :", round(r["ratio"].median(), 3))

for p in [10, 25, 50, 75, 90]:
    print(
        f"{p}% :",
        round(r["ratio"].quantile(p / 100), 3)
    )

print("\n" + "=" * 60)

print("\nIB TYPE COUNTS")
print(r["ib_type"].value_counts())

print("\nEFFICIENCY TYPE COUNTS")
print(r["efficiency_type"].value_counts())