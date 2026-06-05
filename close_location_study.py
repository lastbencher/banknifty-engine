import pandas as pd

print("=" * 70)
print("CLOSE LOCATION STUDY")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

df = pd.read_csv("banknifty_master.csv")

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime")

df["date"] = df["datetime"].dt.date

# --------------------------------------------------
# BUILD DAILY DATA
# --------------------------------------------------

records = []

for date, day in df.groupby("date"):

    day = day.sort_values("datetime")

    if len(day) < 300:
        continue

    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()

    close = day.iloc[-1]["close"]

    if close > ib_high:
        location = "ABOVE_IB"

    elif close < ib_low:
        location = "BELOW_IB"

    else:
        location = "INSIDE_IB"

    day_high = day["high"].max()
    day_low = day["low"].min()

    first_break = None

    after_ib = day.iloc[60:]

    for _, row in after_ib.iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break

    opposite_break = False

    if first_break == "HIGH":
        opposite_break = (
            after_ib["low"].min() < ib_low
        )

    elif first_break == "LOW":
        opposite_break = (
            after_ib["high"].max() > ib_high
        )

    records.append({
        "date": pd.to_datetime(date),
        "location": location,
        "first_break": first_break,
        "opposite_break": opposite_break,
        "ib_range": ib_high - ib_low,
        "day_range": day_high - day_low
    })

daily = pd.DataFrame(records)

latest = daily["date"].max()

windows = {
    "FULL_HISTORY":
        daily,

    "LAST_3_YEARS":
        daily[
            daily["date"]
            >= latest
            - pd.DateOffset(years=3)
        ],

    "LAST_1_YEAR":
        daily[
            daily["date"]
            >= latest
            - pd.DateOffset(years=1)
        ]
}

# --------------------------------------------------
# REPORT
# --------------------------------------------------

for name, data in windows.items():

    print("\n")
    print("=" * 70)
    print(name)
    print("=" * 70)

    print("\nSessions:", len(data))

    print("\nCLOSE LOCATION")

    print(
        (
            data["location"]
            .value_counts(normalize=True)
            * 100
        )
        .round(1)
    )

    print("\nFIRST BREAK -> CLOSE LOCATION")

    table = pd.crosstab(
        data["first_break"],
        data["location"],
        normalize="index"
    ) * 100

    print(table.round(1))

    print("\nOPPOSITE BREAK DAYS")

    opp = data[
        data["opposite_break"]
    ]

    if len(opp):

        print(
            (
                opp["location"]
                .value_counts(normalize=True)
                * 100
            )
            .round(1)
        )

print("\n")
print("=" * 70)
print("STUDY COMPLETE")
print("=" * 70)