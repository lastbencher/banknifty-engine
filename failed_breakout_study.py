import pandas as pd

df = pd.read_csv("banknifty_180d.csv")

df["datetime"] = pd.to_datetime(df["datetime"])
df["date"] = df["datetime"].dt.date

results = []

for date, day in df.groupby("date"):

    if len(day) < 100:
        continue

    day = day.sort_values("datetime").reset_index(drop=True)

    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()
    ib_mid = (ib_high + ib_low) / 2

    first_break = None
    break_idx = None

    for idx, row in day.iloc[60:].iterrows():

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

    after = day.iloc[break_idx:]

    returned_inside = False
    crossed_mid = False
    broke_opposite = False

    if first_break == "HIGH":

        returned_inside = (
            after["low"] < ib_high
        ).any()

        crossed_mid = (
            after["low"] < ib_mid
        ).any()

        broke_opposite = (
            after["low"] < ib_low
        ).any()

    else:

        returned_inside = (
            after["high"] > ib_low
        ).any()

        crossed_mid = (
            after["high"] > ib_mid
        ).any()

        broke_opposite = (
            after["high"] > ib_high
        ).any()

    results.append({
        "date": date,
        "first_break": first_break,
        "returned_inside": returned_inside,
        "crossed_mid": crossed_mid,
        "broke_opposite": broke_opposite
    })

research = pd.DataFrame(results)

print()
print("=" * 60)
print("FAILED BREAKOUT STUDY")
print("=" * 60)

print()
print("RETURNED INSIDE IB")

print(
    (
        research["returned_inside"]
        .mean()
        * 100
    ).round(1),
    "%"
)

print()
print("CROSSED IB MID")

print(
    (
        research["crossed_mid"]
        .mean()
        * 100
    ).round(1),
    "%"
)

print()
print("BROKE OPPOSITE SIDE")

print(
    (
        research["broke_opposite"]
        .mean()
        * 100
    ).round(1),
    "%"
)

print()
print("BY DIRECTION")

summary = research.groupby(
    "first_break"
)[[
    "returned_inside",
    "crossed_mid",
    "broke_opposite"
]].mean() * 100

print(summary.round(1))