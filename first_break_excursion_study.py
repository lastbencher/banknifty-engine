import pandas as pd
import numpy as np

print("=" * 70)
print("FIRST BREAK EXCURSION STUDY")
print("=" * 70)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

df = pd.read_csv("banknifty_master.csv")

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime")

df["date"] = df["datetime"].dt.date

# --------------------------------------------------
# ANALYSIS
# --------------------------------------------------

records = []

for date, day in df.groupby("date"):

    day = day.sort_values("datetime")

    if len(day) < 300:
        continue

    ib = day.iloc[:60]

    ib_high = ib["high"].max()
    ib_low = ib["low"].min()

    after_ib = day.iloc[60:]

    first_break = None
    break_index = None

    # ------------------------------------------
    # FIND FIRST BREAK
    # ------------------------------------------

    for idx, row in after_ib.iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break_index = idx
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break_index = idx
            break

    if first_break is None:
        continue

    trade_data = day.loc[break_index:]

    # ------------------------------------------
    # EXCURSION BEFORE OPPOSITE BREAK
    # ------------------------------------------

    opposite_break = False

    if first_break == "HIGH":

        best_move = (
            trade_data["high"].max()
            - ib_high
        )

        opposite_break = (
            trade_data["low"].min()
            < ib_low
        )

    else:

        best_move = (
            ib_low
            - trade_data["low"].min()
        )

        opposite_break = (
            trade_data["high"].max()
            > ib_high
        )

    records.append({
        "date": pd.to_datetime(date),
        "first_break": first_break,
        "best_move": best_move,
        "opposite_break": opposite_break
    })

study = pd.DataFrame(records)

print("\nSessions:", len(study))

# --------------------------------------------------
# OVERALL
# --------------------------------------------------

print("\n")
print("=" * 70)
print("BEST MOVE STATISTICS")
print("=" * 70)

print(
    study["best_move"]
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

# --------------------------------------------------
# SUCCESS RATES
# --------------------------------------------------

print("\n")
print("=" * 70)
print("TARGET HIT RATES")
print("=" * 70)

targets = [
    25,
    50,
    75,
    100,
    150,
    200,
    250,
    300,
    400,
    500
]

for t in targets:

    pct = (
        (study["best_move"] >= t)
        .mean()
        * 100
    )

    print(
        f"{t:>3} pts : {pct:.1f}%"
    )

# --------------------------------------------------
# BY DIRECTION
# --------------------------------------------------

print("\n")
print("=" * 70)
print("BY FIRST BREAK")
print("=" * 70)

print(
    study.groupby("first_break")["best_move"]
    .describe()
    .round(1)
)

# --------------------------------------------------
# OPPOSITE BREAK VS NO OPPOSITE BREAK
# --------------------------------------------------

print("\n")
print("=" * 70)
print("OPPOSITE BREAK IMPACT")
print("=" * 70)

print(
    study.groupby("opposite_break")["best_move"]
    .describe()
    .round(1)
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
print("LAST 3 YEARS")
print("=" * 70)

for t in targets:

    pct = (
        (recent["best_move"] >= t)
        .mean()
        * 100
    )

    print(
        f"{t:>3} pts : {pct:.1f}%"
    )

# --------------------------------------------------
# SAVE
# --------------------------------------------------

study.to_csv(
    "first_break_excursion_research.csv",
    index=False
)

print("\nSaved first_break_excursion_research.csv")

print("\nDONE")