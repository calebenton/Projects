import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "nutrition.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT DEFAULT '',
            serving_size REAL NOT NULL DEFAULT 100,
            serving_unit TEXT NOT NULL DEFAULT 'g',
            calories REAL NOT NULL DEFAULT 0,
            protein REAL NOT NULL DEFAULT 0,
            carbs REAL NOT NULL DEFAULT 0,
            fat REAL NOT NULL DEFAULT 0,
            fiber REAL NOT NULL DEFAULT 0,
            sugar REAL NOT NULL DEFAULT 0,
            sodium REAL NOT NULL DEFAULT 0,
            barcode TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS food_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            meal_type TEXT NOT NULL DEFAULT 'snack',
            servings REAL NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (food_id) REFERENCES foods(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS weight_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL UNIQUE,
            weight REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'lbs',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            height REAL,
            height_unit TEXT DEFAULT 'in',
            weight_unit TEXT DEFAULT 'lbs',
            activity_level TEXT DEFAULT 'moderate',
            goal TEXT DEFAULT 'maintain',
            calorie_target REAL DEFAULT 2000,
            protein_target REAL DEFAULT 150,
            carbs_target REAL DEFAULT 250,
            fat_target REAL DEFAULT 65,
            tdee_estimate REAL DEFAULT 2000,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            servings REAL NOT NULL DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            servings REAL NOT NULL DEFAULT 1,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY (food_id) REFERENCES foods(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS meal_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS meal_plan_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            food_id INTEGER,
            recipe_id INTEGER,
            meal_type TEXT NOT NULL DEFAULT 'snack',
            servings REAL NOT NULL DEFAULT 1,
            FOREIGN KEY (plan_id) REFERENCES meal_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (food_id) REFERENCES foods(id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id)
        )
    """)

    # Ensure a default profile exists
    c.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")

    conn.commit()
    conn.close()


# --------------- Food CRUD ---------------

def add_food(name, brand="", serving_size=100, serving_unit="g",
             calories=0, protein=0, carbs=0, fat=0,
             fiber=0, sugar=0, sodium=0, barcode="", source="manual"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO foods (name, brand, serving_size, serving_unit,
                           calories, protein, carbs, fat, fiber, sugar, sodium,
                           barcode, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, brand, serving_size, serving_unit,
          calories, protein, carbs, fat, fiber, sugar, sodium,
          barcode, source))
    food_id = c.lastrowid
    conn.commit()
    conn.close()
    return food_id


def search_foods(query):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM foods WHERE name LIKE ? OR brand LIKE ? ORDER BY name LIMIT 50",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_foods():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM foods ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_food(food_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_food(food_id):
    conn = get_connection()
    conn.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()


# --------------- Food Log ---------------

def log_food(food_id, log_date, meal_type="snack", servings=1.0):
    conn = get_connection()
    conn.execute("""
        INSERT INTO food_log (food_id, log_date, meal_type, servings)
        VALUES (?, ?, ?, ?)
    """, (food_id, str(log_date), meal_type, servings))
    conn.commit()
    conn.close()


def get_food_log(log_date):
    conn = get_connection()
    rows = conn.execute("""
        SELECT fl.id, fl.food_id, fl.meal_type, fl.servings, fl.log_date,
               f.name, f.brand, f.serving_size, f.serving_unit,
               f.calories, f.protein, f.carbs, f.fat, f.fiber, f.sugar, f.sodium
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.log_date = ?
        ORDER BY fl.created_at
    """, (str(log_date),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_food_log_entry(entry_id):
    conn = get_connection()
    conn.execute("DELETE FROM food_log WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_daily_totals(log_date):
    entries = get_food_log(log_date)
    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0,
              "fiber": 0, "sugar": 0, "sodium": 0}
    for e in entries:
        mult = e["servings"]
        for key in totals:
            totals[key] += e[key] * mult
    return totals


def get_calorie_history(days=30):
    conn = get_connection()
    rows = conn.execute("""
        SELECT fl.log_date,
               SUM(f.calories * fl.servings) as total_calories,
               SUM(f.protein * fl.servings) as total_protein,
               SUM(f.carbs * fl.servings) as total_carbs,
               SUM(f.fat * fl.servings) as total_fat
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.log_date >= date('now', ?)
        GROUP BY fl.log_date
        ORDER BY fl.log_date
    """, (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------- Weight Log ---------------

def log_weight(log_date, weight, unit="lbs", notes=""):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO weight_log (log_date, weight, unit, notes)
        VALUES (?, ?, ?, ?)
    """, (str(log_date), weight, unit, notes))
    conn.commit()
    conn.close()


def get_weight_history(days=90):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM weight_log
        WHERE log_date >= date('now', ?)
        ORDER BY log_date
    """, (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_weight():
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM weight_log ORDER BY log_date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --------------- User Profile ---------------

def get_profile():
    conn = get_connection()
    row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def update_profile(**kwargs):
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values())
    conn.execute(
        f"UPDATE user_profile SET {sets}, updated_at = datetime('now') WHERE id = 1",
        vals
    )
    conn.commit()
    conn.close()


# --------------- Recipes ---------------

def add_recipe(name, servings=1, notes=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO recipes (name, servings, notes) VALUES (?, ?, ?)",
              (name, servings, notes))
    recipe_id = c.lastrowid
    conn.commit()
    conn.close()
    return recipe_id


def add_recipe_ingredient(recipe_id, food_id, servings=1.0):
    conn = get_connection()
    conn.execute("""
        INSERT INTO recipe_ingredients (recipe_id, food_id, servings)
        VALUES (?, ?, ?)
    """, (recipe_id, food_id, servings))
    conn.commit()
    conn.close()


def get_recipe(recipe_id):
    conn = get_connection()
    recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if not recipe:
        conn.close()
        return None
    ingredients = conn.execute("""
        SELECT ri.*, f.name, f.calories, f.protein, f.carbs, f.fat,
               f.fiber, f.sugar, f.sodium, f.serving_size, f.serving_unit
        FROM recipe_ingredients ri
        JOIN foods f ON ri.food_id = f.id
        WHERE ri.recipe_id = ?
    """, (recipe_id,)).fetchall()
    conn.close()
    return {"recipe": dict(recipe), "ingredients": [dict(i) for i in ingredients]}


def get_all_recipes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_recipe(recipe_id):
    conn = get_connection()
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()


# --------------- Meal Plans ---------------

def add_meal_plan(name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO meal_plans (name) VALUES (?)", (name,))
    plan_id = c.lastrowid
    conn.commit()
    conn.close()
    return plan_id


def add_meal_plan_item(plan_id, meal_type, servings=1.0, food_id=None, recipe_id=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO meal_plan_items (plan_id, food_id, recipe_id, meal_type, servings)
        VALUES (?, ?, ?, ?, ?)
    """, (plan_id, food_id, recipe_id, meal_type, servings))
    conn.commit()
    conn.close()


def get_meal_plan(plan_id):
    conn = get_connection()
    plan = conn.execute("SELECT * FROM meal_plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan:
        conn.close()
        return None
    items = conn.execute("""
        SELECT mpi.*,
               f.name as food_name, f.calories as food_cal, f.protein as food_pro,
               f.carbs as food_carb, f.fat as food_fat,
               r.name as recipe_name
        FROM meal_plan_items mpi
        LEFT JOIN foods f ON mpi.food_id = f.id
        LEFT JOIN recipes r ON mpi.recipe_id = r.id
        WHERE mpi.plan_id = ?
        ORDER BY mpi.meal_type
    """, (plan_id,)).fetchall()
    conn.close()
    return {"plan": dict(plan), "items": [dict(i) for i in items]}


def get_all_meal_plans():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM meal_plans ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_meal_plan(plan_id):
    conn = get_connection()
    conn.execute("DELETE FROM meal_plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
