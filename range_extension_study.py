import pandas as pd

df = pd.read_csv("banknifty_180d.csv")

df["datetime"] = pd.to_datetime(df["datetime"])
df["date"] = df["datetime"].dt.date

results = []

for date, day in df.groupby("date"):

    if len(day) < 100:
        continue

    day = day.sort_values("datetime")

    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()

    after_ib = day.iloc[60:]

    broke_high = (after_ib["high"] > ib_high).any()
    broke_low = (after_ib["low"] < ib_low).any()

    if broke_high and broke_low:
        extension_type = "BOTH"

    elif broke_high:
        extension_type = "HIGH_ONLY"

    elif broke_low:
        extension_type = "LOW_ONLY"

    else:
        extension_type = "NONE"

    results.append({
        "date": date,
        "ib_high": round(ib_high, 2),
        "ib_low": round(ib_low, 2),
        "extension_type": extension_type
    })

research = pd.DataFrame(results)

print()
print("=" * 60)
print("RANGE EXTENSION STUDY")
print("=" * 60)

print()
print("COUNTS")
print(research["extension_type"].value_counts())

print()
print("PERCENTAGES")
print(
    (
        research["extension_type"]
        .value_counts(normalize=True)
        * 100
    ).round(1)
)

research.to_csv(
    "range_extension_research.csv",
    index=False
)

print()
print("Saved range_extension_research.csv")