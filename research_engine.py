import pandas as pd

df = pd.read_csv("banknifty.csv")

df["range"] = df["high"] - df["low"]

print()
print("=" * 50)
print("BANK NIFTY RANGE STUDY")
print("=" * 50)

print()

print("Sessions :", len(df))

print()
print("Average Range :", round(df["range"].mean()))
print("Median Range  :", round(df["range"].median()))

print()

for p in [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95]:
    print(
        f"{p}% Percentile :",
        round(df["range"].quantile(p / 100))
    )

print()

narrow = df["range"] <= df["range"].quantile(0.25)
wide = df["range"] >= df["range"].quantile(0.75)

print("Narrow Days :", narrow.sum())
print("Wide Days   :", wide.sum())

print()

print("Suggested Thresholds")
print("--------------------")
print(
    "NARROW <",
    round(df["range"].quantile(0.25))
)
print(
    "NORMAL",
    round(df["range"].quantile(0.25)),
    "-",
    round(df["range"].quantile(0.75))
)
print(
    "WIDE >",
    round(df["range"].quantile(0.75))
)