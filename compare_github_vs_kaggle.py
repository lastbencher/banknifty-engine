import pandas as pd

print("=" * 70)
print("GITHUB vs KAGGLE VALIDATION")
print("=" * 70)

# --------------------------------------------------
# LOAD GITHUB
# --------------------------------------------------

github = pd.read_csv(
    "nifty-banknifty-intraday-data/2015/MAR/BANKNIFTY.txt",
    header=None,
    names=[
        "symbol",
        "date",
        "time",
        "open",
        "high",
        "low",
        "close"
    ]
)

github["datetime"] = pd.to_datetime(
    github["date"].astype(str)
    + " "
    + github["time"]
)

# IMPORTANT:
# GitHub appears to timestamp bars
# one minute later than Kaggle.
# Shift back by 1 minute.

github["datetime"] = (
    github["datetime"]
    - pd.Timedelta(minutes=1)
)

github = github[
    ["datetime", "open", "high", "low", "close"]
]

print("\nGITHUB ROWS:", len(github))

# --------------------------------------------------
# LOAD KAGGLE
# --------------------------------------------------

kaggle = pd.read_csv(
    "banknifty_10y_clean.csv"
)

kaggle["datetime"] = pd.to_datetime(
    kaggle["datetime"]
)

if kaggle["datetime"].dt.tz is not None:
    kaggle["datetime"] = (
        kaggle["datetime"]
        .dt.tz_localize(None)
    )

kaggle = kaggle[
    (kaggle["datetime"] >= "2015-03-01")
    &
    (kaggle["datetime"] < "2015-04-01")
]

print("KAGGLE ROWS:", len(kaggle))

# --------------------------------------------------
# MERGE
# --------------------------------------------------

merged = github.merge(
    kaggle,
    on="datetime",
    suffixes=("_gh", "_kg")
)

print("\nMATCHED ROWS:", len(merged))

if len(merged) == 0:
    print("NO MATCHES FOUND")
    quit()

# --------------------------------------------------
# DIFFS
# --------------------------------------------------

for col in ["open", "high", "low", "close"]:

    merged[f"{col}_diff"] = (
        merged[f"{col}_gh"]
        - merged[f"{col}_kg"]
    ).abs()

print("\n" + "=" * 70)
print("DIFFERENCE STATISTICS")
print("=" * 70)

for col in ["open", "high", "low", "close"]:

    diff_col = f"{col}_diff"

    print(f"\n{diff_col.upper()}")

    print(
        merged[diff_col]
        .describe()
        .round(4)
    )

# --------------------------------------------------
# TOTAL DIFF
# --------------------------------------------------

merged["total_diff"] = (
    merged["open_diff"]
    + merged["high_diff"]
    + merged["low_diff"]
    + merged["close_diff"]
)

print("\n" + "=" * 70)
print("TOTAL DIFFERENCE")
print("=" * 70)

print(
    merged["total_diff"]
    .describe()
    .round(4)
)

# --------------------------------------------------
# WORST 20 BARS
# --------------------------------------------------

print("\n" + "=" * 70)
print("WORST 20 BARS")
print("=" * 70)

print(
    merged[
        [
            "datetime",
            "open_diff",
            "high_diff",
            "low_diff",
            "close_diff",
            "total_diff"
        ]
    ]
    .sort_values(
        "total_diff",
        ascending=False
    )
    .head(20)
)

# --------------------------------------------------
# SAVE
# --------------------------------------------------

merged.to_csv(
    "github_vs_kaggle_results.csv",
    index=False
)

print("\nSaved github_vs_kaggle_results.csv")

print("\nDONE")