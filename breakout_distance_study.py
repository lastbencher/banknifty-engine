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

    for idx, row in day.iloc[60:].iterrows():

        if row["high"] > ib_high:
            first_break = "HIGH"
            break

        if row["low"] < ib_low:
            first_break = "LOW"
            break

    if first_break is None:
        continue

    after_break = day.iloc[idx:]

    if first_break == "HIGH":

        max_extension = (
            after_break["high"].max()
            - ib_high
        )

    else:

        max_extension = (
            ib_low
            - after_break["low"].min()
        )

    results.append({
        "date": date,
        "first_break": first_break,
        "max_extension": round(max_extension, 2)
    })

research = pd.DataFrame(results)

print()
print("=" * 60)
print("BREAKOUT DISTANCE STUDY")
print("=" * 60)

print()
print("OVERALL")
print(
    research["max_extension"]
    .describe()
)

print()
print("BY DIRECTION")

print(
    research.groupby("first_break")
    ["max_extension"]
    .describe()
)

print()
print("SUCCESS RATES")

for distance in [25, 50, 75, 100, 150, 200]:

    pct = (
        research["max_extension"] >= distance
    ).mean() * 100

    print(
        f"{distance:>3} pts : {pct:.1f}%"
    )