import pandas as pd

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

github = github[
    github["datetime"].dt.date.astype(str)
    == "2015-03-30"
]

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
    kaggle["datetime"].dt.date.astype(str)
    == "2015-03-30"
]

print("\nGITHUB")
print(github.head(20))

print("\nKAGGLE")
print(
    kaggle[
        ["datetime","open","high","low","close"]
    ].head(20)
)