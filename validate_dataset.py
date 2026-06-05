import pandas as pd

FILE = "banknifty_tick_ten.csv"

print("=" * 60)
print("BANK NIFTY DATASET VALIDATION")
print("=" * 60)

df = pd.read_csv(FILE)

print("\nROWS:", len(df))
print("COLUMNS:", list(df.columns))

# --------------------------------------------------
# DATETIME
# --------------------------------------------------

df["datetime"] = pd.to_datetime(df["datetime"])

print("\nFIRST BAR")
print(df.iloc[0])

print("\nLAST BAR")
print(df.iloc[-1])

print("\nDATE RANGE")
print(df["datetime"].min())
print(df["datetime"].max())

# --------------------------------------------------
# DAILY BAR COUNTS
# --------------------------------------------------

df["date"] = df["datetime"].dt.date

daily_counts = (
    df.groupby("date")
    .size()
    .reset_index(name="bars")
)

print("\n" + "=" * 60)
print("BARS PER DAY")
print("=" * 60)

print(daily_counts["bars"].describe())

print("\nDAYS WITH <300 BARS")

bad_days = daily_counts[
    daily_counts["bars"] < 300
]

print(bad_days)

# --------------------------------------------------
# RECENT 30 DAYS
# --------------------------------------------------

print("\n" + "=" * 60)
print("LAST 30 TRADING DAYS")
print("=" * 60)

recent_days = (
    sorted(df["date"].unique())[-30:]
)

summary = []

for d in recent_days:

    day = df[df["date"] == d]

    summary.append({
        "date": d,
        "bars": len(day),
        "high": round(day["high"].max(), 2),
        "low": round(day["low"].min(), 2),
        "close": round(day.iloc[-1]["close"], 2)
    })

recent = pd.DataFrame(summary)

print(recent)

# --------------------------------------------------
# DUPLICATES
# --------------------------------------------------

dupes = df["datetime"].duplicated().sum()

print("\nDUPLICATE TIMESTAMPS:", dupes)

# --------------------------------------------------
# MISSING VALUES
# --------------------------------------------------

print("\nMISSING VALUES")

print(df.isna().sum())

print("\nVALIDATION COMPLETE")