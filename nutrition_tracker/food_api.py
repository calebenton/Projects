import os
import requests

USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
# Get a free key at https://fdc.nal.usda.gov/api-key-signup — DEMO_KEY has strict rate limits
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")

OFF_BASE_URL = "https://world.openfoodfacts.org/api/v0/product"

KJ_TO_KCAL = 1 / 4.184


def _extract_calories(food_nutrients):
    """Extract calories (kcal) from USDA nutrient list, handling kJ vs kcal."""
    kcal = None
    kj = None
    for n in food_nutrients:
        name = n.get("nutrientName", "")
        unit = n.get("unitName", "").upper()
        value = n.get("value", 0)
        if name == "Energy":
            if unit == "KCAL":
                kcal = value
            elif unit == "KJ":
                kj = value
    if kcal is not None:
        return kcal
    if kj is not None:
        return round(kj * KJ_TO_KCAL, 1)
    return 0


def search_usda(query, page_size=15, api_key=None):
    """Search the USDA FoodData Central database.

    Returns (results_list, error_string_or_None).
    """
    key = api_key or USDA_API_KEY
    try:
        resp = requests.post(
            f"{USDA_BASE_URL}/foods/search",
            params={"api_key": key},
            json={
                "query": query,
                "pageSize": page_size,
                "dataType": ["Survey (FNDDS)", "SR Legacy", "Branded"],
            },
            timeout=10,
        )
        if resp.status_code == 429:
            return [], "Rate limit exceeded. Get a free API key at https://fdc.nal.usda.gov/api-key-signup"
        if resp.status_code == 403:
            return [], "Invalid API key. Get a free key at https://fdc.nal.usda.gov/api-key-signup"
        resp.raise_for_status()
        data = resp.json()
        results = []
        for food in data.get("foods", []):
            nutrients = {n["nutrientName"]: n.get("value", 0) for n in food.get("foodNutrients", [])}
            calories = _extract_calories(food.get("foodNutrients", []))
            results.append({
                "name": food.get("description", "Unknown"),
                "brand": food.get("brandName") or food.get("brandOwner", ""),
                "fdc_id": food.get("fdcId"),
                "serving_size": food.get("servingSize") or 100,
                "serving_unit": food.get("servingSizeUnit") or "g",
                "calories": calories,
                "protein": nutrients.get("Protein", 0),
                "carbs": nutrients.get("Carbohydrate, by difference", 0),
                "fat": nutrients.get("Total lipid (fat)", 0),
                "fiber": nutrients.get("Fiber, total dietary", 0),
                "sugar": nutrients.get("Total Sugars", nutrients.get("Sugars, total including NLEA", 0)),
                "sodium": nutrients.get("Sodium, Na", 0),
                "source": "usda",
            })
        return results, None
    except requests.exceptions.Timeout:
        return [], "Request timed out. Try again."
    except requests.exceptions.ConnectionError:
        return [], "Could not connect to USDA API. Check your internet connection."
    except Exception as e:
        return [], f"Search failed: {e}"


def lookup_barcode(barcode):
    """Look up a food product by barcode using Open Food Facts.

    Returns (result_dict_or_None, error_string_or_None).
    """
    try:
        resp = requests.get(
            f"{OFF_BASE_URL}/{barcode}.json",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 1:
            return None, "Barcode not found in Open Food Facts database."
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
        }, None
    except requests.exceptions.Timeout:
        return None, "Request timed out. Try again."
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to Open Food Facts. Check your internet connection."
    except Exception as e:
        return None, f"Barcode lookup failed: {e}"
