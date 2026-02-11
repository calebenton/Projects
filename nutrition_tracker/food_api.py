import requests

USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
USDA_API_KEY = "DEMO_KEY"  # Free demo key — works for personal use

OFF_BASE_URL = "https://world.openfoodfacts.org/api/v0/product"


def search_usda(query, page_size=15):
    """Search the USDA FoodData Central database."""
    try:
        resp = requests.get(
            f"{USDA_BASE_URL}/foods/search",
            params={
                "api_key": USDA_API_KEY,
                "query": query,
                "pageSize": page_size,
                "dataType": ["Survey (FNDDS)", "SR Legacy", "Branded"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for food in data.get("foods", []):
            nutrients = {n["nutrientName"]: n.get("value", 0) for n in food.get("foodNutrients", [])}
            results.append({
                "name": food.get("description", "Unknown"),
                "brand": food.get("brandName") or food.get("brandOwner", ""),
                "fdc_id": food.get("fdcId"),
                "serving_size": food.get("servingSize") or 100,
                "serving_unit": food.get("servingSizeUnit") or "g",
                "calories": nutrients.get("Energy", 0),
                "protein": nutrients.get("Protein", 0),
                "carbs": nutrients.get("Carbohydrate, by difference", 0),
                "fat": nutrients.get("Total lipid (fat)", 0),
                "fiber": nutrients.get("Fiber, total dietary", 0),
                "sugar": nutrients.get("Total Sugars", nutrients.get("Sugars, total including NLEA", 0)),
                "sodium": nutrients.get("Sodium, Na", 0),
                "source": "usda",
            })
        return results
    except Exception as e:
        return []


def lookup_barcode(barcode):
    """Look up a food product by barcode using Open Food Facts."""
    try:
        resp = requests.get(
            f"{OFF_BASE_URL}/{barcode}.json",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 1:
            return None
        product = data["product"]
        nutr = product.get("nutriments", {})
        return {
            "name": product.get("product_name", "Unknown"),
            "brand": product.get("brands", ""),
            "serving_size": float(product.get("serving_quantity", 100) or 100),
            "serving_unit": product.get("serving_quantity_unit", "g") or "g",
            "calories": nutr.get("energy-kcal_serving") or nutr.get("energy-kcal_100g", 0),
            "protein": nutr.get("proteins_serving") or nutr.get("proteins_100g", 0),
            "carbs": nutr.get("carbohydrates_serving") or nutr.get("carbohydrates_100g", 0),
            "fat": nutr.get("fat_serving") or nutr.get("fat_100g", 0),
            "fiber": nutr.get("fiber_serving") or nutr.get("fiber_100g", 0),
            "sugar": nutr.get("sugars_serving") or nutr.get("sugars_100g", 0),
            "sodium": nutr.get("sodium_serving") or nutr.get("sodium_100g", 0) * 1000,
            "barcode": barcode,
            "source": "openfoodfacts",
        }
    except Exception:
        return None
