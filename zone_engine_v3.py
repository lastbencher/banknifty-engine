import pandas as pd

df = pd.read_csv("banknifty_10d.csv")

df["price_bin"] = (df["close"] / 20).round() * 20

df["price_change"] = df["close"].diff()
df["oi_change"] = df["oi"].diff()

# ------------------
# REGIMES
# ------------------

long_build = df[
    (df["price_change"] > 0)
    & (df["oi_change"] > 0)
]

short_build = df[
    (df["price_change"] < 0)
    & (df["oi_change"] > 0)
]

short_cover = df[
    (df["price_change"] > 0)
    & (df["oi_change"] < 0)
]

long_unwind = df[
    (df["price_change"] < 0)
    & (df["oi_change"] < 0)
]

# ------------------
# AGGREGATE
# ------------------

lb = long_build.groupby("price_bin").size()
sb = short_build.groupby("price_bin").size()
sc = short_cover.groupby("price_bin").size()
lu = long_unwind.groupby("price_bin").size()

# ------------------
# PRINT
# ------------------

print()
print("="*60)
print("LONG BUILD-UP (DEMAND)")
print("="*60)

print(lb.sort_values(ascending=False).head(15))

print()
print("="*60)
print("SHORT BUILD-UP (SUPPLY)")
print("="*60)

print(sb.sort_values(ascending=False).head(15))

print()
print("="*60)
print("SHORT COVERING")
print("="*60)

print(sc.sort_values(ascending=False).head(15))

print()
print("="*60)
print("LONG UNWINDING")
print("="*60)

print(lu.sort_values(ascending=False).head(15))


