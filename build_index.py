import json
from pathlib import Path
import xmltodict

DUMPS_ROOT = Path("dumps")
OUTPUT_FILE = "products_index.json"


def find_items(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "Item":
                return v if isinstance(v, list) else [v]
            res = find_items(v)
            if res:
                return res
    elif isinstance(obj, list):
        for el in obj:
            res = find_items(el)
            if res:
                return res
    return []


def normalize(item, chain):
    return {
        "chain": chain,
        "barcode": item.get("ItemCode") or "",
        "name": item.get("ItemName") or item.get("ItemNm") or "",
        "price": float(item.get("ItemPrice") or 0),
        "manufacturer": item.get("ManufacturerName") or "",
    }


index = {}

for folder in DUMPS_ROOT.iterdir():
    if not folder.is_dir():
        continue

    chain = folder.name
    files = list(folder.rglob("*.xml"))

    for f in files[:2]:  # limit per chain for speed
        with f.open("rb") as file:
            data = xmltodict.parse(file)

        items = find_items(data)

        for item in items:
            product = normalize(item, chain)
            barcode = product["barcode"]

            if not barcode:
                continue

            if barcode not in index:
                index[barcode] = []

            index[barcode].append(product)


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f)

print(f"✅ Built index with {len(index)} barcodes")