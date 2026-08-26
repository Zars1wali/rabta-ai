import openpyxl
from collections import Counter

excel_path = r"C:\Users\waliz\Downloads\Haider Arms Data.xlsx"
wb = openpyxl.load_workbook(excel_path, data_only=True)
sheet = wb["Sheet1"]
rows = list(sheet.iter_rows(values_only=True))

header = rows[3][:8]
print("Header:", header)

products = []
for idx, r in enumerate(rows[4:]):
    name = r[0]
    category = r[1]
    brand = r[2]
    origin = r[3]
    caliber = r[4]
    capacity = r[5]
    action = r[6]
    price = r[7]

    if name and str(name).strip() and not str(name).startswith("HAIDER"):
        try:
            p_val = float(price) if price is not None else 0.0
        except Exception:
            p_val = 0.0

        products.append({
            "name": str(name).strip(),
            "category": str(category).strip() if category else "General",
            "brand": str(brand).strip() if brand else "",
            "origin": str(origin).strip() if origin else "",
            "caliber": str(caliber).strip() if caliber else "",
            "capacity": str(capacity).strip() if capacity else "",
            "action": str(action).strip() if action else "",
            "price": p_val,
        })

print(f"Total Valid Products: {len(products)}")
print("\nCategory Distribution:")
for cat, count in Counter([p["category"] for p in products]).items():
    print(f"  - {cat}: {count} items")

print("\nTop Brands:")
for brand, count in Counter([p["brand"] for p in products]).most_common(12):
    print(f"  - {brand}: {count} items")

print("\nSample 5 Products:")
for p in products[:5]:
    print(f"  * {p['name']} | {p['category']} | {p['brand']} ({p['origin']}) | {p['caliber']} | PKR {p['price']:,.0f}")
