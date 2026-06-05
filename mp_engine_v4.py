import pandas as pd
import math
from datetime import datetime

df = pd.read_csv("banknifty_10d.csv")

df["date"] = pd.to_datetime(df["datetime"]).dt.date
df["price_bin"] = (df["close"] / 20).round() * 20

profiles = []

# -----------------------
# DAILY PROFILE
# -----------------------
for d in sorted(df["date"].unique()):

    day = df[df["date"] == d].copy()

    vp = (
        day.groupby("price_bin")["volume"]
        .sum()
        .sort_values(ascending=False)
    )

    poc = vp.index[0]

    total_vol = vp.sum()
    target = total_vol * 0.70

    included = {poc}
    running = vp.loc[poc]

    remaining = vp.drop(poc)

    while running < target and len(remaining):

        nxt = remaining.idxmax()

        included.add(nxt)
        running += remaining.loc[nxt]

        remaining = remaining.drop(nxt)

    vah = max(included)
    val = min(included)

    day_high = day["high"].max()
    day_low = day["low"].min()

    profiles.append({
        "date": d,
        "POC": poc,
        "VAH": vah,
        "VAL": val,
        "HIGH": day_high,
        "LOW": day_low,
    })

profile_df = pd.DataFrame(profiles)

# -----------------------
# VIRGIN POCS
# -----------------------

virgin_pocs = []

virgin_vahs = []
virgin_vals = []
for i in range(len(profile_df) - 1):

    poc = profile_df.iloc[i]["POC"]

    future = df[
        df["date"] > profile_df.iloc[i]["date"]
    ]

    touched = (
        (future["low"] <= poc)
        &
        (future["high"] >= poc)
    ).any()

    if not touched:
        virgin_pocs.append(
            (
                profile_df.iloc[i]["date"],
                poc
            )
        )
    vah = profile_df.iloc[i]["VAH"]

    touched_vah = (
        (future["low"] <= vah)
        &
        (future["high"] >= vah)
    ).any()

    if not touched_vah:
        virgin_vahs.append(
            (
                profile_df.iloc[i]["date"],
                vah
            )
        )

    val = profile_df.iloc[i]["VAL"]

    touched_val = (
        (future["low"] <= val)
        &
        (future["high"] >= val)
    ).any()

    if not touched_val:
        virgin_vals.append(
            (
                profile_df.iloc[i]["date"],
                val
            )
        )
# -----------------------
# POOR HIGH / LOW
# -----------------------

def poor_high(day):

    h = day["high"].max()

    touches = (
        abs(day["high"] - h) < 5
    ).sum()

    return touches >= 2

def poor_low(day):

    l = day["low"].min()

    touches = (
        abs(day["low"] - l) < 5
    ).sum()

    return touches >= 2


# -----------------------
# DAY TYPE
# -----------------------

day_types = []

for d in sorted(df["date"].unique()):

    day = df[df["date"] == d]

    first_hour = day.head(60)

    ib_high = first_hour["high"].max()
    ib_low = first_hour["low"].min()

    ib_range = ib_high - ib_low

    day_range = (
        day["high"].max()
        - day["low"].min()
    )

    ratio = (
        day_range / ib_range
        if ib_range > 0
        else 0
    )

    if ratio > 3:
        dtype = "Trend Day"
    elif ratio > 2:
        dtype = "Normal Variation"
    else:
        dtype = "Normal Day"

    day_types.append(
        (d, dtype)
    )

# -----------------------
# REPORT
# -----------------------

print()
print("REPORT GENERATED:",
      datetime.now().strftime("%d.%m.%Y | %H:%M"))

print("\n" + "="*70)
print("DAILY MARKET PROFILE")
print("="*70)

for row in profiles:

    d = row["date"]

    day = df[df["date"] == d]

    ph = poor_high(day)
    pl = poor_low(day)

    dtype = next(
        x[1]
        for x in day_types
        if x[0] == d
    )

    print()
    print(f"DATE : {d}")
    print(f"POC  : {row['POC']}")
    print(f"VAH  : {row['VAH']}")
    print(f"VAL  : {row['VAL']}")
    print(f"TYPE : {dtype}")
    print(f"POOR HIGH : {ph}")
    print(f"POOR LOW  : {pl}")

print()
print("="*70)
print("VIRGIN POCS")
print("="*70)

for d, poc in virgin_pocs:

    print(d, "->", poc)
print()
print("="*70)
print("VIRGIN VAHS")
print("="*70)

for d, vah in virgin_vahs:
    print(d, "->", vah)

print()
print("="*70)
print("VIRGIN VALS")
print("="*70)


for d, val in virgin_vals:
    print(d, "->", val)
print()
print("="*70)
print("SINGLE PRINTS")
print("="*70)

for d in sorted(df["date"].unique()):

    day = df[df["date"] == d].copy()

    day["tpo"] = (
        pd.to_datetime(day["datetime"])
        .dt.floor("30min")
    )

    tpo_map = {}

    for tpo, bracket in day.groupby("tpo"):



        low_bin = math.floor(bracket["low"].min() / 20) * 20
        high_bin = math.ceil(bracket["high"].max() / 20) * 20

        for p in range(
            int(low_bin),
            int(high_bin) + 20,
            20
        ):
            tpo_map.setdefault(
                p,
                set()
            ).add(tpo)

    poc = (
        day.groupby("price_bin")["volume"]
        .sum()
        .idxmax()
    )

    single_prints = [
        p
        for p, tpos in tpo_map.items()
        if len(tpos) == 1
        and abs(p - poc) > 40
    ]


    if single_prints:

        print()
        print(d)

        start = single_prints[0]
        prev = single_prints[0]

        zones = []

        for p in single_prints[1:]:

            if p == prev + 20:
                prev = p
            else:
                zones.append((start, prev))
                start = p
                prev = p

        zones.append((start, prev))

        for a, b in zones:

            width = b - a

            if width <= 120:

                if a == b:
                    print("  ", a)
                else:
                    print(f"   {a} -> {b}")

            else:

                mid = round(((a + b) / 2) / 20) * 20

                print()
                print(f"   TAIL: {a} -> {b}")
                print(f"   LEVELS: {a} / {mid} / {b}")



print()
print("="*70)
print("INSTITUTIONAL MAP")
print("="*70)
print()
print("SUPPLY")
print("-"*30)

print("54560")
print("54400 - 54500")

print()
print("SELLING TAIL")
print("-"*30)

print("54060 - 54200")
print("Levels: 54060 / 54120 / 54200")

print()
print("BALANCE")
print("-"*30)

print("54080 - 54180")
print()
print("FAIR VALUE")
print("-"*30)
print("54160")

print()
print("BUYING TAIL")
print("-"*30)

print("53600 - 53920")
print("Levels: 53600 / 53760 / 53920")

print()
print("DEMAND")
print("-"*30)

print("53720 - 53800")

print()
print("MAGNETS")
print("-"*30)

print("53560")
print("52960")
print()
print("="*70)
print("NEXT SESSION BIAS")
print("="*70)

print()

print("ABOVE 54180")
print("Bullish -> 54400 - 54560")

print()

print("BELOW 53720")
print("Bearish -> 53560 -> 52960")

print()

print("BETWEEN 53720 AND 54180")
print("Balance / Rotation")
print()
print("="*70)
print("TRADE PLAN")
print("="*70)

print()

print("LONG SETUP")
print("-"*30)
print("Acceptance above 54180")
print("Target 1 -> 54400")
print("Target 2 -> 54500")
print("Target 3 -> 54560")

print()

print("SHORT SETUP")
print("-"*30)
print("Acceptance below 53720")
print("Target 1 -> 53560")
print("Target 2 -> 52960")

print()

print("NO TRADE")
print("-"*30)
print("Inside 53720 - 54180")
print("Expect rotation / chop")