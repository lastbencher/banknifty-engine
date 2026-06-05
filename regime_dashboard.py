import pandas as pd
import numpy as np

print("=" * 70)
print("BANKNIFTY REGIME DASHBOARD")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

df = pd.read_csv("banknifty_master.csv")

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime")

df["date"] = df["datetime"].dt.date

print("\nRows:", len(df))
print("Trading Days:", df["date"].nunique())

# --------------------------------------------------
# BUILD DAILY STATS
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

    day_high = day["high"].max()
    day_low = day["low"].min()

    day_range = day_high - day_low

    expansion_factor = (
        day_range / ib_range
        if ib_range > 0
        else np.nan
    )

    # ----------------------------------------
    # FIRST BREAK
    # ----------------------------------------

    first_break = None

    after_ib = day.iloc[60:]

    for _, row in after_ib.iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break

    # ----------------------------------------
    # OPPOSITE BREAK
    # ----------------------------------------

    opposite_break = False

    if first_break == "HIGH":
        opposite_break = (
            after_ib["low"].min() < ib_low
        )

    elif first_break == "LOW":
        opposite_break = (
            after_ib["high"].max() > ib_high
        )

    # ----------------------------------------
    # ACCEPTANCE
    # consecutive bars outside IB
    # ----------------------------------------

    max_outside = 0
    current = 0

    for _, row in after_ib.iterrows():

        outside = (
            row["high"] > ib_high
            or
            row["low"] < ib_low
        )

        if outside:
            current += 1
            max_outside = max(
                max_outside,
                current
            )
        else:
            current = 0

    # ----------------------------------------
    # TREND DAY
    # ----------------------------------------

    trend_day = (
        expansion_factor >= 2.0
    )

    records.append({
        "date": pd.to_datetime(date),
        "ib_range": ib_range,
        "day_range": day_range,
        "expansion_factor": expansion_factor,
        "first_break": first_break,
        "opposite_break": opposite_break,
        "acceptance": max_outside,
        "trend_day": trend_day
    })

daily = pd.DataFrame(records)

print("\nDaily Sessions:", len(daily))

# --------------------------------------------------
# WINDOWS
# --------------------------------------------------

latest_date = daily["date"].max()

windows = {
    "FULL_HISTORY":
        daily,

    "LAST_3_YEARS":
        daily[
            daily["date"]
            >= latest_date
            - pd.DateOffset(years=3)
        ],

    "LAST_1_YEAR":
        daily[
            daily["date"]
            >= latest_date
            - pd.DateOffset(years=1)
        ]
}

# --------------------------------------------------
# REPORT FUNCTION
# --------------------------------------------------

def report(name, data):

    print("\n")
    print("=" * 70)
    print(name)
    print("=" * 70)

    print("\nSessions:", len(data))

    print("\nIB RANGE")

    print(
        data["ib_range"]
        .describe(
            percentiles=[
                .10,
                .25,
                .50,
                .75,
                .90
            ]
        )
        .round(1)
    )

    print("\nEXPANSION FACTOR")

    print(
        data["expansion_factor"]
        .describe(
            percentiles=[
                .10,
                .25,
                .50,
                .75,
                .90
            ]
        )
        .round(2)
    )

    print("\nFIRST BREAK")

    print(
        (
            data["first_break"]
            .value_counts(
                normalize=True
            )
            * 100
        )
        .round(1)
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

    print("\nTREND DAY RATE")

    print(
        round(
            data["trend_day"]
            .mean() * 100,
            1
        ),
        "%"
    )

    print("\nACCEPTANCE")

    for mins in [
        1,
        3,
        5,
        10,
        15,
        30,
        60
    ]:

        pct = (
            (
                data["acceptance"]
                >= mins
            )
            .mean()
            * 100
        )

        print(
            f"{mins:>2} min : {pct:.1f}%"
        )

# --------------------------------------------------
# RUN
# --------------------------------------------------

for name, data in windows.items():

    report(name, data)

print("\n")
print("=" * 70)
print("REGIME ANALYSIS COMPLETE")
print("=" * 70)