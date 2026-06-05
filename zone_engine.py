import pandas as pd

# =========================
# LOAD DATA
# =========================

df = pd.read_csv("banknifty_10d.csv")

df["price_bin"] = (df["close"] / 20).round() * 20
df["oi_change"] = df["oi"].diff()

# =========================
# VOLUME PROFILE
# =========================

volume_profile = (
    df.groupby("price_bin")["volume"]
      .sum()
      .sort_values(ascending=False)
)

# =========================
# OI PROFILE
# =========================

oi_profile = (
    df.groupby("price_bin")["oi_change"]
      .sum()
      .sort_values(ascending=False)
)

# =========================
# COMPOSITE POC
# =========================

composite_poc = volume_profile.index[0]

# =========================
# BUILD SCORES
# =========================

zones = []

for price in volume_profile.head(30).index:

    volume_score = (
        volume_profile.loc[price]
        / volume_profile.max()
    ) * 60

    oi_score = 0

    if price in oi_profile.index:
        oi_score = max(
            0,
            oi_profile.loc[price]
            / oi_profile.max()
        ) * 40

    total_score = round(volume_score + oi_score, 2)

    zones.append(
        {
            "price": price,
            "score": total_score,
            "volume": volume_profile.loc[price],
            "oi": oi_profile.get(price, 0)
        }
    )

zones = sorted(
    zones,
    key=lambda x: x["score"],
    reverse=True
)

# =========================
# OUTPUT
# =========================

print("\n")
print("=" * 50)
print("BANKNIFTY ZONE ENGINE")
print("=" * 50)

print("\nComposite POC:", composite_poc)

print("\nTOP ZONES\n")

for z in zones[:10]:

    print(
        f"Price: {z['price']:.0f} | "
        f"Score: {z['score']:.1f} | "
        f"Vol: {int(z['volume'])} | "
        f"OIΔ: {int(z['oi'])}"
    )

print("\n" + "=" * 50)


