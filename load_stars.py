import csv
import gzip

stars = []

with gzip.open("hygdata_v42.csv.gz", "rt", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["mag"] == "":
            continue
        mag = float(row["mag"])
        if mag < 6 and row["ra"] != "" and row["dec"] != "":
            stars.append({
                "name": row["proper"],
                "ra": float(row["ra"]),
                "dec": float(row["dec"]),
                "mag": mag,
            })

print("Stars loaded:", len(stars))
for star in stars[:5]:
    print(star)