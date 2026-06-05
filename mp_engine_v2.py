import pandas as pd

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






for d, val in virgin_vals:
    print(d, "->", val)
print()
print("="*70)
print("SINGLE PRINTS")
print("="*70)

for d in sorted(df["date"].unique()):

    day = df[df["date"] == d]

    day["tpo"] = (
        pd.to_datetime(day["datetime"])
        .dt.floor("30min")
    )

    counts = (
        day.groupby("price_bin")["tpo"]
        .nunique()
    )

    sp = counts[counts == 1]

    if len(sp):



        print()
        print(d)

        for level in sp.index:
            print("  ", level)


