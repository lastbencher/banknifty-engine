import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

df["datetime"] = pd.to_datetime(df["datetime"])
df["date"] = df["datetime"].dt.date

results = []

for day in sorted(df["date"].unique()):

    d = df[df["date"] == day].copy()

    d["price_bin"] = (
        (d["close"] / 20).round() * 20
    )

    vp = (
        d.groupby("price_bin")["volume"]
        .sum()
        .sort_values(ascending=False)
    )

    poc = vp.index[0]

    total_volume = vp.sum()

    value_area_target = total_volume * 0.70

    running = vp.iloc[0]
    included = [poc]

    remaining = vp.drop(poc)

    for price, vol in remaining.items():

        included.append(price)

        running += vol

        if running >= value_area_target:
            break

    vah = max(included)
    val = min(included)

    results.append(
        {
            "date": day,
            "POC": poc,
            "VAH": vah,
            "VAL": val,
        }
    )

result = pd.DataFrame(results)

print("\nDAILY PROFILE\n")
print(result)

print("\nPOC MIGRATION\n")

for i in range(1, len(result)):

    prev = result.iloc[i - 1]["POC"]
    curr = result.iloc[i]["POC"]

    if curr > prev:
        direction = "UP"
    elif curr < prev:
        direction = "DOWN"
    else:
        direction = "FLAT"

    print(
        result.iloc[i]["date"],
        prev,
        "->",
        curr,
        direction
    )


