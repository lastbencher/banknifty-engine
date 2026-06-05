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

    minutes_outside = 0

    for _, row in day.iloc[break_idx:].iterrows():

        if first_break == "HIGH":

            if row["close"] <= ib_high:
                break

            minutes_outside += 1

        else:

            if row["close"] >= ib_low:
                break

            minutes_outside += 1

    results.append({
        "date": date,
        "first_break": first_break,
        "minutes_outside": minutes_outside
    })

research = pd.DataFrame(results)

print()
print("=" * 60)
print("ACCEPTANCE STUDY")
print("=" * 60)

print()
print("OVERALL")
print(research["minutes_outside"].describe())

print()
print("BY DIRECTION")
print(
    research.groupby("first_break")["minutes_outside"].describe()
)

print()
print("ACCEPTANCE LEVELS")

for mins in [1, 2, 3, 5, 10, 15, 20, 30, 45, 60]:

    pct = (
        research["minutes_outside"] >= mins
    ).mean() * 100

    print(f"{mins:>2} min : {pct:.1f}%")

research.to_csv(
    "acceptance_research.csv",
    index=False
)

print()
print("Saved acceptance_research.csv")