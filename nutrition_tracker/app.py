import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta, datetime

import database as db
import food_api
import tdee as tdee_module

# ── Init ────────────────────────────────────────────────────────────────
db.init_db()

st.set_page_config(
    page_title="NutriTrack",
    page_icon="\U0001F34F",
    layout="wide",
    initial_sidebar_state="expanded",
)

MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack"]

# ── Sidebar navigation ─────────────────────────────────────────────────
st.sidebar.title("\U0001F34F NutriTrack")
page = st.sidebar.radio(
    "Navigate",
    [
        "\U0001F4CA Dashboard",
        "\U0001F354 Food Log",
        "\u2696\uFE0F Weight Tracker",
        "\U0001F50D Food Search",
        "\U0001F4F7 Barcode Scanner",
        "\U0001F373 Recipes",
        "\U0001F4CB Meal Plans",
        "\u2699\uFE0F Settings",
    ],
)

profile = db.get_profile()


# ── Helpers ─────────────────────────────────────────────────────────────
def macro_donut(label, current, target, color):
    pct = min(current / target * 100, 100) if target else 0
    fig = go.Figure(go.Pie(
        values=[current, max(0, target - current)],
        hole=0.7,
        marker_colors=[color, "#2d2d2d"],
        textinfo="none",
        hoverinfo="skip",
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=140,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=f"<b>{current:.0f}</b><br>{label}",
            x=0.5, y=0.5, font_size=13, showarrow=False,
        )],
    )
    return fig


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if page.startswith("\U0001F4CA"):
    st.title("\U0001F4CA Daily Dashboard")
    sel_date = st.date_input("Date", value=date.today())
    totals = db.get_daily_totals(sel_date)

    # Targets
    cal_target = profile.get("calorie_target", 2000)
    pro_target = profile.get("protein_target", 150)
    carb_target = profile.get("carbs_target", 250)
    fat_target = profile.get("fat_target", 65)

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    c1.plotly_chart(macro_donut("Calories", totals["calories"], cal_target, "#ff6b6b"), use_container_width=True)
    c2.plotly_chart(macro_donut("Protein", totals["protein"], pro_target, "#4ecdc4"), use_container_width=True)
    c3.plotly_chart(macro_donut("Carbs", totals["carbs"], carb_target, "#ffe66d"), use_container_width=True)
    c4.plotly_chart(macro_donut("Fat", totals["fat"], fat_target, "#a78bfa"), use_container_width=True)

    remaining = cal_target - totals["calories"]
    if remaining > 0:
        st.info(f"\U0001F7E2 {remaining:.0f} calories remaining today")
    else:
        st.warning(f"\U0001F534 {abs(remaining):.0f} calories over target")

    # Adaptive TDEE card
    st.subheader("Adaptive TDEE Estimate")
    tdee_data = tdee_module.compute_adaptive_tdee()
    tc1, tc2, tc3 = st.columns(3)
    tc1.metric("Estimated TDEE", f"{tdee_data['tdee']} kcal")
    tc2.metric("Weekly Rate", f"{tdee_data['weekly_rate']:+.2f} lbs/wk")
    tc3.metric("Data Quality", tdee_data["data_quality"].capitalize())
    st.caption(tdee_data.get("message", ""))

    # Trend chart (last 14 days)
    st.subheader("14-Day Calorie Trend")
    history = db.get_calorie_history(days=14)
    if history:
        df = pd.DataFrame(history)
        fig = px.bar(df, x="log_date", y="total_calories",
                     labels={"log_date": "Date", "total_calories": "Calories"},
                     color_discrete_sequence=["#ff6b6b"])
        fig.add_hline(y=cal_target, line_dash="dash", line_color="#4ecdc4",
                      annotation_text=f"Target: {cal_target}")
        fig.update_layout(height=300, margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Start logging food to see your trend chart!")

    # Today's meals breakdown
    st.subheader("Today's Meals")
    log = db.get_food_log(sel_date)
    if log:
        for meal in MEAL_TYPES:
            items = [e for e in log if e["meal_type"].lower() == meal.lower()]
            if items:
                st.markdown(f"**{meal}**")
                for item in items:
                    cal = item["calories"] * item["servings"]
                    st.write(f"  - {item['name']} — {item['servings']}x — {cal:.0f} kcal")
    else:
        st.info("No meals logged yet for this date.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FOOD LOG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\U0001F354"):
    st.title("\U0001F354 Food Log")
    sel_date = st.date_input("Log date", value=date.today())

    # Quick-add from saved foods
    st.subheader("Log a Food")
    all_foods = db.get_all_foods()
    if all_foods:
        food_options = {f"{f['name']} ({f['brand']})" if f["brand"] else f["name"]: f["id"] for f in all_foods}
        with st.form("log_food_form"):
            chosen = st.selectbox("Select food", list(food_options.keys()))
            col1, col2 = st.columns(2)
            servings = col1.number_input("Servings", min_value=0.25, value=1.0, step=0.25)
            meal_type = col2.selectbox("Meal", MEAL_TYPES)
            if st.form_submit_button("Add to Log"):
                db.log_food(food_options[chosen], sel_date, meal_type.lower(), servings)
                st.success(f"Logged {chosen}!")
                st.rerun()
    else:
        st.info("No foods in your database yet. Use **Food Search** or **Barcode Scanner** to add foods first.")

    # Show log
    st.subheader(f"Log for {sel_date}")
    log = db.get_food_log(sel_date)
    if log:
        for entry in log:
            cal = entry["calories"] * entry["servings"]
            pro = entry["protein"] * entry["servings"]
            col1, col2, col3 = st.columns([4, 2, 1])
            col1.write(f"**{entry['name']}** ({entry['meal_type']}) — {entry['servings']}x")
            col2.write(f"{cal:.0f} kcal | {pro:.0f}g protein")
            if col3.button("\U0000274C", key=f"del_{entry['id']}"):
                db.delete_food_log_entry(entry["id"])
                st.rerun()

        st.divider()
        totals = db.get_daily_totals(sel_date)
        st.markdown(
            f"**Daily Total:** {totals['calories']:.0f} kcal | "
            f"P: {totals['protein']:.0f}g | C: {totals['carbs']:.0f}g | F: {totals['fat']:.0f}g"
        )
    else:
        st.info("No entries yet for this date.")

    # Manual food entry
    st.subheader("Add Custom Food")
    with st.form("manual_food"):
        name = st.text_input("Food name")
        brand = st.text_input("Brand (optional)")
        c1, c2, c3 = st.columns(3)
        serving_size = c1.number_input("Serving size", value=100.0, min_value=0.1)
        serving_unit = c2.selectbox("Unit", ["g", "ml", "oz", "cup", "tbsp", "tsp", "piece"])
        calories = c3.number_input("Calories", value=0.0, min_value=0.0)
        c4, c5, c6 = st.columns(3)
        protein = c4.number_input("Protein (g)", value=0.0, min_value=0.0)
        carbs = c5.number_input("Carbs (g)", value=0.0, min_value=0.0)
        fat = c6.number_input("Fat (g)", value=0.0, min_value=0.0)
        if st.form_submit_button("Save Food"):
            if name:
                db.add_food(name, brand, serving_size, serving_unit,
                            calories, protein, carbs, fat)
                st.success(f"Saved '{name}' to your food database!")
                st.rerun()
            else:
                st.error("Food name is required.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WEIGHT TRACKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\u2696"):
    st.title("\u2696\uFE0F Weight Tracker")

    with st.form("log_weight"):
        c1, c2, c3 = st.columns(3)
        w_date = c1.date_input("Date", value=date.today())
        weight = c2.number_input("Weight", min_value=50.0, max_value=600.0, value=170.0, step=0.1)
        unit = c3.selectbox("Unit", ["lbs", "kg"])
        notes = st.text_input("Notes (optional)")
        if st.form_submit_button("Log Weight"):
            db.log_weight(w_date, weight, unit, notes)
            st.success(f"Logged {weight} {unit} for {w_date}")
            st.rerun()

    # Weight chart
    history = db.get_weight_history(days=90)
    if history:
        df = pd.DataFrame(history)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["log_date"], y=df["weight"],
            mode="lines+markers", name="Weight",
            line=dict(color="#4ecdc4", width=2),
            marker=dict(size=6),
        ))

        # Add trend line (EWMA)
        if len(df) >= 3:
            alpha = 2 / (10 + 1)
            trend = [df["weight"].iloc[0]]
            for w in df["weight"].iloc[1:]:
                trend.append(alpha * w + (1 - alpha) * trend[-1])
            fig.add_trace(go.Scatter(
                x=df["log_date"], y=trend,
                mode="lines", name="Trend",
                line=dict(color="#ff6b6b", width=2, dash="dash"),
            ))

        fig.update_layout(
            height=350,
            margin=dict(t=30, b=30),
            xaxis_title="Date",
            yaxis_title=f"Weight ({history[0]['unit']})",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Stats
        latest = db.get_latest_weight()
        if latest and len(df) >= 2:
            change = df["weight"].iloc[-1] - df["weight"].iloc[0]
            st.metric(
                "Current Weight",
                f"{latest['weight']} {latest['unit']}",
                delta=f"{change:+.1f} {latest['unit']} over {len(df)} entries",
                delta_color="inverse",
            )
    else:
        st.info("No weight entries yet. Log your first weigh-in above!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FOOD SEARCH (USDA)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\U0001F50D"):
    st.title("\U0001F50D Food Search")
    st.caption("Search the USDA FoodData Central database and save foods to your local library.")

    query = st.text_input("Search for a food", placeholder="e.g. chicken breast, oatmeal, banana")
    if query:
        with st.spinner("Searching USDA database..."):
            results, error = food_api.search_usda(query)
        if error:
            st.error(error)
        elif results:
            for i, food in enumerate(results):
                with st.expander(f"{food['name']} — {food['brand']}" if food["brand"] else food["name"]):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Calories", f"{food['calories']:.0f}")
                    c2.metric("Protein", f"{food['protein']:.1f}g")
                    c3.metric("Carbs", f"{food['carbs']:.1f}g")
                    c4.metric("Fat", f"{food['fat']:.1f}g")
                    st.caption(
                        f"Serving: {food['serving_size']}{food['serving_unit']} | "
                        f"Fiber: {food['fiber']:.1f}g | Sugar: {food['sugar']:.1f}g"
                    )
                    if st.button("Save to My Foods", key=f"save_usda_{i}"):
                        db.add_food(
                            name=food["name"], brand=food.get("brand", ""),
                            serving_size=food["serving_size"],
                            serving_unit=food["serving_unit"],
                            calories=food["calories"], protein=food["protein"],
                            carbs=food["carbs"], fat=food["fat"],
                            fiber=food["fiber"], sugar=food["sugar"],
                            sodium=food["sodium"], source="usda",
                        )
                        st.success(f"Saved '{food['name']}'!")
        else:
            st.warning("No results found. Try a different search term.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BARCODE SCANNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\U0001F4F7"):
    st.title("\U0001F4F7 Barcode Scanner")
    st.caption("Look up food by barcode using the Open Food Facts database.")

    barcode = st.text_input("Enter barcode number", placeholder="e.g. 0049000006346")

    # Camera input for barcode image (user can snap a photo)
    camera_photo = st.camera_input("Or take a photo of the barcode")
    if camera_photo:
        st.info(
            "Image-based barcode decoding requires the `pyzbar` library and system dependency `libzbar0`. "
            "If not installed, please enter the barcode number manually above."
        )
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(camera_photo.getvalue()))
            decoded = decode(img)
            if decoded:
                barcode = decoded[0].data.decode("utf-8")
                st.success(f"Detected barcode: {barcode}")
            else:
                st.warning("Could not detect a barcode in the image. Try entering it manually.")
        except ImportError:
            st.warning("pyzbar not installed. Enter the barcode manually above.")

    if barcode:
        with st.spinner("Looking up barcode..."):
            result, error = food_api.lookup_barcode(barcode)
        if error:
            st.error(error)
        elif result:
            st.success(f"Found: **{result['name']}** — {result['brand']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Calories", f"{result['calories']:.0f}")
            c2.metric("Protein", f"{result['protein']:.1f}g")
            c3.metric("Carbs", f"{result['carbs']:.1f}g")
            c4.metric("Fat", f"{result['fat']:.1f}g")
            if st.button("Save to My Foods"):
                db.add_food(
                    name=result["name"], brand=result.get("brand", ""),
                    serving_size=result["serving_size"],
                    serving_unit=result["serving_unit"],
                    calories=result["calories"], protein=result["protein"],
                    carbs=result["carbs"], fat=result["fat"],
                    fiber=result["fiber"], sugar=result["sugar"],
                    sodium=result["sodium"], barcode=barcode, source="openfoodfacts",
                )
                st.success(f"Saved '{result['name']}'!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RECIPES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\U0001F373"):
    st.title("\U0001F373 Recipe Builder")

    tab1, tab2 = st.tabs(["My Recipes", "Create Recipe"])

    with tab1:
        recipes = db.get_all_recipes()
        if recipes:
            for recipe in recipes:
                data = db.get_recipe(recipe["id"])
                if not data:
                    continue
                with st.expander(f"{recipe['name']} ({recipe['servings']} servings)"):
                    total_cal = total_pro = total_carb = total_fat = 0
                    for ing in data["ingredients"]:
                        ing_cal = ing["calories"] * ing["servings"]
                        ing_pro = ing["protein"] * ing["servings"]
                        ing_carb = ing["carbs"] * ing["servings"]
                        ing_fat = ing["fat"] * ing["servings"]
                        total_cal += ing_cal
                        total_pro += ing_pro
                        total_carb += ing_carb
                        total_fat += ing_fat
                        st.write(
                            f"- {ing['name']} — {ing['servings']}x "
                            f"({ing_cal:.0f} kcal, {ing_pro:.1f}g P)"
                        )

                    servings = data["recipe"]["servings"]
                    st.divider()
                    st.markdown(
                        f"**Per serving:** {total_cal/servings:.0f} kcal | "
                        f"P: {total_pro/servings:.1f}g | "
                        f"C: {total_carb/servings:.1f}g | "
                        f"F: {total_fat/servings:.1f}g"
                    )
                    st.markdown(
                        f"**Total recipe:** {total_cal:.0f} kcal | "
                        f"P: {total_pro:.1f}g | C: {total_carb:.1f}g | F: {total_fat:.1f}g"
                    )

                    # Save recipe as a food for easy logging
                    if st.button("Save as Food (per serving)", key=f"recipe_food_{recipe['id']}"):
                        db.add_food(
                            name=f"{recipe['name']} (recipe)",
                            calories=total_cal / servings,
                            protein=total_pro / servings,
                            carbs=total_carb / servings,
                            fat=total_fat / servings,
                            source="recipe",
                        )
                        st.success("Saved as a food for easy logging!")

                    if st.button("Delete Recipe", key=f"del_recipe_{recipe['id']}"):
                        db.delete_recipe(recipe["id"])
                        st.rerun()
        else:
            st.info("No recipes yet. Create one in the 'Create Recipe' tab!")

    with tab2:
        all_foods = db.get_all_foods()
        if not all_foods:
            st.warning("You need to add some foods first (via Food Search or manually) before building recipes.")
        else:
            with st.form("create_recipe"):
                recipe_name = st.text_input("Recipe name")
                recipe_servings = st.number_input("Number of servings", min_value=1, value=4)
                recipe_notes = st.text_area("Notes (optional)")

                st.markdown("**Add ingredients:**")
                food_options = {f"{f['name']} ({f['brand']})" if f["brand"] else f["name"]: f["id"] for f in all_foods}
                ingredient_names = []
                ingredient_servings = []
                for i in range(10):
                    c1, c2 = st.columns([3, 1])
                    ing = c1.selectbox(f"Ingredient {i+1}", ["(none)"] + list(food_options.keys()), key=f"ing_{i}")
                    srv = c2.number_input(f"Servings", min_value=0.25, value=1.0, step=0.25, key=f"srv_{i}")
                    ingredient_names.append(ing)
                    ingredient_servings.append(srv)

                if st.form_submit_button("Create Recipe"):
                    if recipe_name:
                        rid = db.add_recipe(recipe_name, recipe_servings, recipe_notes)
                        for ing_name, srv in zip(ingredient_names, ingredient_servings):
                            if ing_name != "(none)":
                                db.add_recipe_ingredient(rid, food_options[ing_name], srv)
                        st.success(f"Created recipe '{recipe_name}'!")
                        st.rerun()
                    else:
                        st.error("Recipe name is required.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MEAL PLANS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\U0001F4CB"):
    st.title("\U0001F4CB Meal Plans")
    st.caption("Create reusable meal plan templates and quickly log an entire day.")

    tab1, tab2 = st.tabs(["My Plans", "Create Plan"])

    with tab1:
        plans = db.get_all_meal_plans()
        if plans:
            for plan in plans:
                data = db.get_meal_plan(plan["id"])
                if not data:
                    continue
                with st.expander(plan["name"]):
                    total_cal = 0
                    for meal in MEAL_TYPES:
                        items = [it for it in data["items"] if it["meal_type"].lower() == meal.lower()]
                        if items:
                            st.markdown(f"**{meal}:**")
                            for it in items:
                                if it["food_name"]:
                                    cal = (it["food_cal"] or 0) * it["servings"]
                                    total_cal += cal
                                    st.write(f"  - {it['food_name']} — {it['servings']}x ({cal:.0f} kcal)")
                                elif it["recipe_name"]:
                                    st.write(f"  - {it['recipe_name']} (recipe) — {it['servings']}x")

                    st.divider()
                    st.markdown(f"**Estimated total:** {total_cal:.0f} kcal")

                    log_date = st.date_input("Log this plan for date:", value=date.today(), key=f"plan_date_{plan['id']}")
                    if st.button("Log Entire Plan", key=f"log_plan_{plan['id']}"):
                        for it in data["items"]:
                            if it["food_id"]:
                                db.log_food(it["food_id"], log_date, it["meal_type"], it["servings"])
                        st.success(f"Logged meal plan '{plan['name']}' for {log_date}!")

                    if st.button("Delete Plan", key=f"del_plan_{plan['id']}"):
                        db.delete_meal_plan(plan["id"])
                        st.rerun()
        else:
            st.info("No meal plans yet. Create one in the 'Create Plan' tab!")

    with tab2:
        all_foods = db.get_all_foods()
        if not all_foods:
            st.warning("Add some foods first before creating meal plans.")
        else:
            with st.form("create_plan"):
                plan_name = st.text_input("Plan name", placeholder="e.g. Weekday Cutting Plan")
                food_options = {f"{f['name']} ({f['brand']})" if f["brand"] else f["name"]: f["id"] for f in all_foods}

                for meal in MEAL_TYPES:
                    st.markdown(f"**{meal}:**")
                    for j in range(3):
                        c1, c2 = st.columns([3, 1])
                        food = c1.selectbox(
                            f"{meal} item {j+1}",
                            ["(none)"] + list(food_options.keys()),
                            key=f"plan_{meal}_{j}",
                        )
                        srv = c2.number_input("Qty", min_value=0.25, value=1.0, step=0.25, key=f"plan_srv_{meal}_{j}")
                        # Store in session state
                        st.session_state[f"_plan_{meal}_{j}_food"] = food
                        st.session_state[f"_plan_{meal}_{j}_srv"] = srv

                if st.form_submit_button("Create Meal Plan"):
                    if plan_name:
                        pid = db.add_meal_plan(plan_name)
                        for meal in MEAL_TYPES:
                            for j in range(3):
                                food = st.session_state.get(f"_plan_{meal}_{j}_food", "(none)")
                                srv = st.session_state.get(f"_plan_{meal}_{j}_srv", 1.0)
                                if food != "(none)":
                                    db.add_meal_plan_item(pid, meal.lower(), srv, food_id=food_options[food])
                        st.success(f"Created meal plan '{plan_name}'!")
                        st.rerun()
                    else:
                        st.error("Plan name is required.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SETTINGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page.startswith("\u2699"):
    st.title("\u2699\uFE0F Settings & Goals")

    with st.form("settings"):
        st.subheader("Personal Info")
        c1, c2 = st.columns(2)
        height = c1.number_input("Height", value=float(profile.get("height") or 70), min_value=36.0, max_value=96.0)
        height_unit = c2.selectbox("Height unit", ["in", "cm"], index=0 if profile.get("height_unit", "in") == "in" else 1)
        weight_unit = st.selectbox("Preferred weight unit", ["lbs", "kg"], index=0 if profile.get("weight_unit", "lbs") == "lbs" else 1)

        st.subheader("Activity & Goal")
        activity = st.select_slider(
            "Activity level",
            options=["sedentary", "light", "moderate", "active", "very_active"],
            value=profile.get("activity_level", "moderate"),
        )
        goal = st.selectbox(
            "Goal",
            ["aggressive_cut", "cut", "slow_cut", "maintain", "slow_bulk", "bulk"],
            index=["aggressive_cut", "cut", "slow_cut", "maintain", "slow_bulk", "bulk"].index(
                profile.get("goal", "maintain")
            ),
        )

        st.subheader("Daily Targets")
        c1, c2, c3, c4 = st.columns(4)
        cal_target = c1.number_input("Calories", value=float(profile.get("calorie_target", 2000)), step=50.0)
        pro_target = c2.number_input("Protein (g)", value=float(profile.get("protein_target", 150)), step=5.0)
        carb_target = c3.number_input("Carbs (g)", value=float(profile.get("carbs_target", 250)), step=5.0)
        fat_target = c4.number_input("Fat (g)", value=float(profile.get("fat_target", 65)), step=5.0)

        if st.form_submit_button("Save Settings"):
            db.update_profile(
                height=height, height_unit=height_unit, weight_unit=weight_unit,
                activity_level=activity, goal=goal,
                calorie_target=cal_target, protein_target=pro_target,
                carbs_target=carb_target, fat_target=fat_target,
            )
            st.success("Settings saved!")
            st.rerun()

    # TDEE suggestion
    st.subheader("Auto-Suggest Targets")
    st.caption("Based on your adaptive TDEE estimate and selected goal.")
    if st.button("Get Suggestion"):
        suggestion = tdee_module.suggest_calories(profile.get("goal", "maintain"))
        st.metric("Suggested Calories", f"{suggestion['calorie_target']} kcal/day")
        st.caption(
            f"TDEE: {suggestion['tdee']} kcal | "
            f"Goal adjustment: {suggestion['deficit_surplus']:+d} kcal | "
            f"Data quality: {suggestion['data_quality']}"
        )

    # API key config
    st.subheader("USDA API Key")
    st.caption(
        "The default DEMO_KEY has strict rate limits (~30 requests/hour). "
        "Get a free personal key for unlimited use."
    )
    current_key = food_api.USDA_API_KEY
    display_key = current_key if current_key == "DEMO_KEY" else current_key[:8] + "..."
    st.text(f"Current key: {display_key}")
    new_key = st.text_input(
        "USDA API Key",
        placeholder="Paste your key from https://fdc.nal.usda.gov/api-key-signup",
        label_visibility="collapsed",
    )
    if st.button("Update API Key"):
        if new_key.strip():
            food_api.USDA_API_KEY = new_key.strip()
            st.success("API key updated for this session! To make it permanent, set the USDA_API_KEY environment variable.")
        else:
            st.error("Please enter a valid API key.")

    # Data management
    st.subheader("Your Food Library")
    all_foods = db.get_all_foods()
    if all_foods:
        st.write(f"You have **{len(all_foods)}** foods saved.")
        if st.checkbox("Show all foods"):
            df = pd.DataFrame(all_foods)
            st.dataframe(
                df[["name", "brand", "calories", "protein", "carbs", "fat", "serving_size", "serving_unit", "source"]],
                use_container_width=True,
            )
    else:
        st.info("No foods saved yet.")
