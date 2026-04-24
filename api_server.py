import json
from pathlib import Path
import xmltodict
from fastapi import FastAPI

app = FastAPI()

DUMPS_ROOT = Path("dumps")

BARCODE_INDEX = {}

# Chains you want to support
CHAINS = ["BAREKET", "TIV_TAAM", "YELLOW"]

# In-memory cache
CACHE = {}

import os

@app.on_event("startup")
def build_index():
    print("🔄 Building barcode index...")

    for folder in DUMPS_ROOT.iterdir():
        if not folder.is_dir():
            continue

        chain_name = folder.name
        products = extract_products(chain_name)

        for p in products:
            barcode = p["barcode"]
            if not barcode:
                continue

            if barcode not in BARCODE_INDEX:
                BARCODE_INDEX[barcode] = []

            BARCODE_INDEX[barcode].append(p)

    print(f"✅ Indexed {len(BARCODE_INDEX)} unique barcodes")

def resolve_chain_folder(chain_input: str) -> str:
    """
    Match user input (any case) to actual folder name.
    """
    for folder in DUMPS_ROOT.iterdir():
        if folder.is_dir() and folder.name.lower() == chain_input.lower():
            return folder.name

    raise ValueError(f"Chain '{chain_input}' not found in dumps")

@app.get("/debug")
def debug_files(chain: str = "BAREKET"):
    chain_folder = DUMPS_ROOT / chain

    return {
        "folder": str(chain_folder),
        "exists": chain_folder.exists(),
        "files": [str(f.name) for f in chain_folder.glob("*.xml")]
    }

# ---------------------------
# FIND ITEMS (ROBUST)
# ---------------------------
def find_items_recursively(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "Item":
                if isinstance(value, list):
                    return value
                elif isinstance(value, dict):
                    return [value]
            else:
                result = find_items_recursively(value)
                if result:
                    return result

    elif isinstance(obj, list):
        for element in obj:
            result = find_items_recursively(element)
            if result:
                return result

    return []


# ---------------------------
# NORMALIZER (UNIVERSAL)
# ---------------------------
def normalize_item(item: dict, chain_name: str) -> dict:
    name = (
        item.get("ItemName")
        or item.get("ItemNm")
        or item.get("ManufacturerItemDescription")
        or ""
    )

    barcode = (
        item.get("ItemCode")
        or item.get("Barcode")
        or ""
    )

    try:
        price = float(item.get("ItemPrice") or item.get("UnitOfMeasurePrice") or 0)
    except:
        price = 0.0

    try:
        quantity = int(float(item.get("Quantity") or 0))
    except:
        quantity = 0

    return {
        "chain": chain_name,
        "barcode": barcode,
        "name": name,
        "price": price,
        "unit": item.get("UnitOfMeasure") or "",
        "quantity": quantity,
        "manufacturer": item.get("ManufacturerName") or "",
        "update_time": item.get("PriceUpdateDate") or "",
        "allow_discount": str(item.get("AllowDiscount", "0")) == "1",
        "is_weighted": str(item.get("bIsWeighted", "0")) == "1",
    }


# ---------------------------
# EXTRACT PRODUCTS
# ---------------------------
def extract_products(chain_name: str):
    chain_folder = DUMPS_ROOT / chain_name

    price_files = list(chain_folder.rglob("*.xml"))

    if not price_files:
        return []

    products = []

    for xml_file in price_files:
        with xml_file.open("rb") as f:
            data = xmltodict.parse(f)

        items = find_items_recursively(data)

        if isinstance(items, dict):
            items = [items]

        for item in items:
            normalized = normalize_item(item, chain_name)
            products.append(normalized)

    return products


# ---------------------------
# CACHE LAYER (FAST)
# ---------------------------
def get_cached_products(chain):
    if chain not in CACHE:
        CACHE[chain] = extract_products(chain)
    return CACHE[chain]


# ---------------------------
# SINGLE CHAIN ENDPOINT
# ---------------------------
@app.get("/products")
def get_products(chain: str):
    real_chain = resolve_chain_folder(chain)
    products = get_cached_products(real_chain)

    return {
        "chain": real_chain,
        "count": len(products),
        "products": products[:500]
    }

# ---------------------------
# BARCODE LOOKUP (🔥 YOUR MAIN USE CASE)
# ---------------------------
@app.get("/product/{barcode}")
def get_product(barcode: str):
    products = BARCODE_INDEX.get(barcode)

    if not products:
        return {
            "error": "Product not found",
            "barcode": barcode
        }

    result = {
        "barcode": barcode,
        "name": products[0]["name"],
        "manufacturer": products[0]["manufacturer"],
        "offers": {}
    }

    for p in products:
        chain = p["chain"]
        current = result["offers"].get(chain)

        if current is None or p["price"] < current["price"]:
            result["offers"][chain] = {
                "chain": chain,
                "price": p["price"]
            }

    result["offers"] = list(result["offers"].values())

    return result

# ---------------------------
# START SERVER
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)