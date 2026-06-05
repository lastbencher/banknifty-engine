import pandas as pd

print("=" * 70)
print("DEFINEDGE vs KAGGLE COMPARISON")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

print("\nLoading files...")

kg = pd.read_csv("banknifty_10y_clean.csv")
dd = pd.read_csv("banknifty_180d.csv")

# --------------------------------------------------
# DATETIME
# --------------------------------------------------

kg["datetime"] = pd.to_datetime(kg["datetime"])
dd["datetime"] = pd.to_datetime(dd["datetime"])

# remove timezone from kaggle so both match
if kg["datetime"].dt.tz is not None:
    kg["datetime"] = kg["datetime"].dt.tz_localize(None)

kg["date"] = kg["datetime"].dt.date
dd["date"] = dd["datetime"].dt.date

print("\nKAGGLE RANGE")
print(kg["date"].min(), "->", kg["date"].max())

print("\nDEFINEDGE RANGE")
print(dd["date"].min(), "->", dd["date"].max())

# --------------------------------------------------
# OVERLAP
# --------------------------------------------------

common_dates = sorted(
    set(kg["date"]).intersection(
        set(dd["date"])
    )
)

print("\nOVERLAPPING DAYS:", len(common_dates))

if len(common_dates) == 0:
    print("\nNO OVERLAPPING DATES FOUND")
    quit()

# --------------------------------------------------
# DAILY COMPARISON
# --------------------------------------------------

results = []

for d in common_dates:

    kg_day = kg[kg["date"] == d]
    dd_day = dd[dd["date"] == d]

    if len(kg_day) == 0 or len(dd_day) == 0:
        continue

    kg_open = kg_day.iloc[0]["open"]
    kg_high = kg_day["high"].max()
    kg_low = kg_day["low"].min()
    kg_close = kg_day.iloc[-1]["close"]

    dd_open = dd_day.iloc[0]["open"]
    dd_high = dd_day["high"].max()
    dd_low = dd_day["low"].min()
    dd_close = dd_day.iloc[-1]["close"]

    results.append({
        "date": d,

        "open_diff":
            abs(kg_open - dd_open),

        "high_diff":
            abs(kg_high - dd_high),

        "low_diff":
            abs(kg_low - dd_low),

        "close_diff":
            abs(kg_close - dd_close)
    })

comparison = pd.DataFrame(results)

print("\n" + "=" * 70)
print("DIFFERENCE STATISTICS")
print("=" * 70)

for col in [
    "open_diff",
    "high_diff",
    "low_diff",
    "close_diff"
]:

    print(f"\n{col.upper()}")

    print(
        comparison[col]
        .describe()
        .round(2)
    )

# --------------------------------------------------
# WORST DAYS
# --------------------------------------------------

comparison["total_diff"] = (
    comparison["open_diff"]
    + comparison["high_diff"]
    + comparison["low_diff"]
    + comparison["close_diff"]
)

print("\n" + "=" * 70)
print("WORST 20 DAYS")
print("=" * 70)

print(
    comparison
    .sort_values(
        "total_diff",
        ascending=False
    )
    .head(20)
)

comparison.to_csv(
    "definedge_vs_kaggle.csv",
    index=False
)

print("\nSaved definedge_vs_kaggle.csv")

print("\nDONE")