import pandas as pd

FILE = "banknifty_tick_ten.csv"

print("=" * 70)
print("BANK NIFTY 10 YEAR DATASET VALIDATION")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

print("\nLoading CSV...")

df = pd.read_csv(FILE)

print("Rows:", len(df))
print("Columns:", list(df.columns))

# --------------------------------------------------
# DATETIME
# --------------------------------------------------

print("\nParsing datetime...")

df["datetime"] = pd.to_datetime(df["datetime"])

print("\nFIRST 5 ROWS")
print(df.head())

print("\nLAST 5 ROWS")
print(df.tail())

print("\nDATE RANGE")

print("Earliest :", df["datetime"].min())
print("Latest   :", df["datetime"].max())

# --------------------------------------------------
# SORT
# --------------------------------------------------

df = df.sort_values("datetime")

# --------------------------------------------------
# TRADING DAYS
# --------------------------------------------------

df["date"] = df["datetime"].dt.date

days = df["date"].nunique()

print("\nTRADING DAYS:", days)

# --------------------------------------------------
# BARS PER DAY
# --------------------------------------------------

daily_bars = (
    df.groupby("date")
      .size()
      .reset_index(name="bars")
)

print("\n" + "=" * 70)
print("BARS PER DAY")
print("=" * 70)

print(daily_bars["bars"].describe())

print("\nLOW BAR COUNT DAYS (<300)")

low_days = daily_bars[daily_bars["bars"] < 300]

print("Count:", len(low_days))

if len(low_days):
    print(low_days.head(50))

# --------------------------------------------------
# DUPLICATES
# --------------------------------------------------

print("\n" + "=" * 70)
print("DUPLICATES")
print("=" * 70)

dupes = df["datetime"].duplicated().sum()

print("Duplicate timestamps:", dupes)

# --------------------------------------------------
# MISSING VALUES
# --------------------------------------------------

print("\n" + "=" * 70)
print("MISSING VALUES")
print("=" * 70)

print(df.isna().sum())

# --------------------------------------------------
# ZERO VOLUME
# --------------------------------------------------

print("\n" + "=" * 70)
print("ZERO VOLUME")
print("=" * 70)

zero_vol = (df["volume"] == 0).mean() * 100

print(f"Zero volume rows: {zero_vol:.2f}%")

# --------------------------------------------------
# YEARLY COUNTS
# --------------------------------------------------

df["year"] = df["datetime"].dt.year

print("\n" + "=" * 70)
print("ROWS BY YEAR")
print("=" * 70)

print(df.groupby("year").size())

# --------------------------------------------------
# SAMPLE RECENT DAYS
# --------------------------------------------------

print("\n" + "=" * 70)
print("LAST 20 TRADING DAYS")
print("=" * 70)

recent_days = sorted(df["date"].unique())[-20:]

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

print(pd.DataFrame(summary))

# --------------------------------------------------
# SAVE CLEAN VERSION
# --------------------------------------------------

df.to_csv("banknifty_10y_clean.csv", index=False)

print("\nSaved: banknifty_10y_clean.csv")

print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)