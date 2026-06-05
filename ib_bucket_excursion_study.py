import pandas as pd
import numpy as np

print("=" * 70)
print("IB BUCKET EXCURSION STUDY")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

df = pd.read_csv("banknifty_master.csv")

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime")

df["date"] = df["datetime"].dt.date

# --------------------------------------------------
# BUILD DAILY RECORDS
# --------------------------------------------------

records = []

for date, day in df.groupby("date"):

    day = day.sort_values("datetime")

    if len(day) < 300:
        continue

    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()

    ib_range = ib_high - ib_low

    after_ib = day.iloc[60:]

    first_break = None
    break_idx = None

    for idx, row in after_ib.iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break_idx = idx
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break_idx = idx
            break

    if first_break is None:
        continue

    trade_data = day.loc[break_idx:]

    breakout_price = (
        (ib_high + ib_low) / 2
    )

    if first_break == "HIGH":

        excursion_points = (
            trade_data["high"].max()
            - ib_high
        )

        opposite_break = (
            trade_data["low"].min()
            < ib_low
        )

    else:

        excursion_points = (
            ib_low
            - trade_data["low"].min()
        )

        opposite_break = (
            trade_data["high"].max()
            > ib_high
        )

    excursion_pct = (
        excursion_points
        / breakout_price
        * 100
    )

    excursion_ib = (
        excursion_points
        / ib_range
        if ib_range > 0
        else np.nan
    )

    records.append({
        "date": pd.to_datetime(date),
        "ib_range": ib_range,
        "first_break": first_break,
        "excursion_points": excursion_points,
        "excursion_pct": excursion_pct,
        "excursion_ib": excursion_ib,
        "opposite_break": opposite_break
    })

study = pd.DataFrame(records)

print("\nSessions:", len(study))

# --------------------------------------------------
# IB BUCKETS
# --------------------------------------------------

q25 = study["ib_range"].quantile(.25)
q75 = study["ib_range"].quantile(.75)

print("\nIB BUCKETS")
print("NARROW <=", round(q25, 1))
print("WIDE   >=", round(q75, 1))

def classify_ib(x):

    if x <= q25:
        return "NARROW"

    if x >= q75:
        return "WIDE"

    return "NORMAL"

study["ib_bucket"] = (
    study["ib_range"]
    .apply(classify_ib)
)

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

for bucket in [
    "NARROW",
    "NORMAL",
    "WIDE"
]:

    data = study[
        study["ib_bucket"] == bucket
    ]

    print("\n")
    print("=" * 70)
    print(bucket)
    print("=" * 70)

    print("\nSessions:", len(data))

    print("\nIB RANGE")

    print(
        data["ib_range"]
        .describe()
        .round(1)
    )

    print("\nEXCURSION POINTS")

    print(
        data["excursion_points"]
        .describe(
            percentiles=[
                .25,
                .50,
                .75,
                .90
            ]
        )
        .round(1)
    )

    print("\nEXCURSION %")

    print(
        data["excursion_pct"]
        .describe(
            percentiles=[
                .25,
                .50,
                .75,
                .90
            ]
        )
        .round(3)
    )

    print("\nEXCURSION x IB")

    print(
        data["excursion_ib"]
        .describe(
            percentiles=[
                .25,
                .50,
                .75,
                .90
            ]
        )
        .round(2)
    )

    print("\nOPPOSITE BREAK RATE")

    print(
        round(
            data["opposite_break"]
            .mean() * 100,
            1
        ),
        "%"
    )

    print("\nPOINT TARGETS")

    for pts in [
        25,
        50,
        75,
        100,
        150,
        200
    ]:

        pct = (
            (
                data["excursion_points"]
                >= pts
            )
            .mean()
            * 100
        )

        print(
            f"{pts:>3} pts : {pct:.1f}%"
        )

# --------------------------------------------------
# RECENT REGIME
# --------------------------------------------------

latest = study["date"].max()

recent = study[
    study["date"]
    >= latest - pd.DateOffset(years=3)
]

print("\n")
print("=" * 70)
print("LAST 3 YEARS ONLY")
print("=" * 70)

print(
    recent.groupby("ib_bucket")[
        [
            "excursion_points",
            "excursion_pct",
            "excursion_ib"
        ]
    ]
    .median()
    .round(2)
)

# --------------------------------------------------
# SAVE
# --------------------------------------------------

study.to_csv(
    "ib_bucket_excursion_research.csv",
    index=False
)

print("\nSaved ib_bucket_excursion_research.csv")

print("\nDONE")