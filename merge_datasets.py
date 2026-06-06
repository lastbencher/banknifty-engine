# Superseded by update_pipeline.py (fetch + merge + features + daily cron).
import pandas as pd

print("=" * 70)
print("BUILDING BANKNIFTY MASTER DATASET")
print("=" * 70)

# --------------------------------------------------
# LOAD KAGGLE
# --------------------------------------------------

print("\nLoading Kaggle...")

kg = pd.read_csv("banknifty_10y_clean.csv")

kg["datetime"] = pd.to_datetime(
    kg["datetime"]
)

# remove timezone
if kg["datetime"].dt.tz is not None:
    kg["datetime"] = (
        kg["datetime"]
        .dt.tz_localize(None)
    )

kg = kg[
    ["datetime", "open", "high", "low", "close"]
]

print("Kaggle rows:", len(kg))
print(
    "Range:",
    kg["datetime"].min(),
    "->",
    kg["datetime"].max()
)

# --------------------------------------------------
# LOAD DEFINEDGE
# --------------------------------------------------

print("\nLoading Definedge...")

dd = pd.read_csv("banknifty_180d.csv")

dd["datetime"] = pd.to_datetime(
    dd["datetime"]
)

dd = dd[
    ["datetime", "open", "high", "low", "close"]
]

print("Definedge rows:", len(dd))
print(
    "Range:",
    dd["datetime"].min(),
    "->",
    dd["datetime"].max()
)

# --------------------------------------------------
# COMBINE
# --------------------------------------------------

master = pd.concat(
    [kg, dd],
    ignore_index=True
)

# remove duplicates
master = (
    master
    .sort_values("datetime")
    .drop_duplicates(
        subset=["datetime"],
        keep="last"
    )
)

master = master.reset_index(drop=True)

print("\nAfter merge:", len(master))

print(
    "Master Range:",
    master["datetime"].min(),
    "->",
    master["datetime"].max()
)

# --------------------------------------------------
# SAVE
# --------------------------------------------------

master.to_csv(
    "banknifty_master.csv",
    index=False
)

print("\nSaved:")
print("banknifty_master.csv")

# --------------------------------------------------
# STATS
# --------------------------------------------------

master["date"] = (
    master["datetime"]
    .dt.date
)

print("\nTrading Days:")
print(master["date"].nunique())

print("\nRows:")
print(len(master))

print("\nDone.")