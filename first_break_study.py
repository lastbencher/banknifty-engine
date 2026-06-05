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

    first_break = None

    for _, row in day.iloc[60:].iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break

    if first_break is None:
        continue

    after_break = day[
        day["datetime"] > row["datetime"]
    ]

    opposite_break = False

    if first_break == "HIGH":
        opposite_break = (
            after_break["low"] < ib_low
        ).any()

    if first_break == "LOW":
        opposite_break = (
            after_break["high"] > ib_high
        ).any()

    results.append({
        "date": date,
        "first_break": first_break,
        "opposite_break": opposite_break
    })

research = pd.DataFrame(results)

print()
print("=" * 60)
print("FIRST BREAK STUDY")
print("=" * 60)

print()
print("FIRST BREAK COUNTS")
print(
    research["first_break"]
    .value_counts()
)

print()
print("OPPOSITE BREAK RATE")

summary = (
    research
    .groupby("first_break")
    ["opposite_break"]
    .mean()
    * 100
)

print(summary.round(1))