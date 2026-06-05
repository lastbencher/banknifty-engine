import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

# -------------------
# PREP
# -------------------

df["price_bin"] = (df["close"] / 20).round() * 20

df["price_change"] = df["close"].diff()
df["oi_change"] = df["oi"].diff()

# -------------------
# VOLUME PROFILE
# -------------------

volume_profile = (
    df.groupby("price_bin")["volume"]
      .sum()
)

# -------------------
# OI PROFILE
# -------------------

oi_profile = (
    df.groupby("price_bin")["oi_change"]
      .sum()
)

# -------------------
# LONG BUILD
# -------------------

long_build = (
    df[
        (df["price_change"] > 0)
        & (df["oi_change"] > 0)
    ]
    .groupby("price_bin")
    .size()
)

# -------------------
# SHORT COVER
# -------------------

short_cover = (
    df[
        (df["price_change"] > 0)
        & (df["oi_change"] < 0)
    ]
    .groupby("price_bin")
    .size()
)

# -------------------
# SCORE
# -------------------

zones = []

max_vol = volume_profile.max()

max_oi = max(
    1,
    oi_profile[oi_profile > 0].max()
)

max_lb = max(
    1,
    long_build.max()
)

max_sc = max(
    1,
    short_cover.max()
)

all_bins = sorted(df["price_bin"].unique())

for price in all_bins:

    vol_score = (
        volume_profile.get(price, 0)
        / max_vol
    ) * 40

    oi_score = max(
        0,
        oi_profile.get(price, 0)
    ) / max_oi * 30

    lb_score = (
        long_build.get(price, 0)
        / max_lb
    ) * 15

    sc_score = (
        short_cover.get(price, 0)
        / max_sc
    ) * 15

    total = round(
        vol_score
        + oi_score
        + lb_score
        + sc_score,
        2
    )

    zones.append({
        "price": price,
        "score": total,
        "volume": volume_profile.get(price, 0),
        "oi": oi_profile.get(price, 0),
        "lb": long_build.get(price, 0),
        "sc": short_cover.get(price, 0),
    })

zones = sorted(
    zones,
    key=lambda x: x["score"],
    reverse=True
)

# -------------------
# OUTPUT
# -------------------

print()
print("=" * 70)
print("BANKNIFTY ZONE ENGINE V2")
print("=" * 70)

for z in zones[:15]:

    print(
        f"{z['price']:8.0f} | "
        f"Score={z['score']:6.1f} | "
        f"OI={int(z['oi']):8d} | "
        f"LB={int(z['lb']):3d} | "
        f"SC={int(z['sc']):3d}"
    )

print("=" * 70)


