"""
Adaptive TDEE estimation algorithm.

Uses an exponentially-weighted moving average approach similar to nSuns / MacroFactor:
  - Smooths both daily calorie intake and daily weight
  - Computes weekly rate of weight change
  - Estimates TDEE = smoothed_intake - (weekly weight change in lbs * 3500 / 7)
  - Blends with the previous estimate to reduce noise
"""

from datetime import date, timedelta
import database as db


def _ewma(values, span=10):
    """Compute exponentially weighted moving average."""
    if not values:
        return []
    alpha = 2 / (span + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def compute_adaptive_tdee(lookback_days=28):
    """
    Compute an adaptive TDEE estimate based on recent calorie and weight data.

    Returns a dict with:
      - tdee: estimated daily energy expenditure
      - weight_trend: smoothed recent weight
      - weekly_rate: estimated weekly weight change (lbs)
      - data_quality: 'good', 'fair', or 'insufficient'
      - calorie_avg: average daily intake over period
    """
    profile = db.get_profile()
    calorie_history = db.get_calorie_history(days=lookback_days)
    weight_history = db.get_weight_history(days=lookback_days)

    # Build day-by-day maps
    cal_map = {r["log_date"]: r["total_calories"] for r in calorie_history}
    wt_map = {r["log_date"]: r["weight"] for r in weight_history}

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(lookback_days - 1, -1, -1)]
    date_strs = [d.isoformat() for d in dates]

    # Fill in calorie and weight series (skip missing days)
    cal_vals = [cal_map[d] for d in date_strs if d in cal_map]
    wt_vals = [wt_map[d] for d in date_strs if d in wt_map]

    # Determine data quality
    if len(cal_vals) < 7 or len(wt_vals) < 3:
        return {
            "tdee": profile.get("tdee_estimate", 2000),
            "weight_trend": wt_vals[-1] if wt_vals else None,
            "weekly_rate": 0,
            "data_quality": "insufficient",
            "calorie_avg": sum(cal_vals) / len(cal_vals) if cal_vals else 0,
            "message": "Need at least 7 days of food logging and 3 weigh-ins for adaptive estimates.",
        }

    data_quality = "good" if len(cal_vals) >= 14 and len(wt_vals) >= 7 else "fair"

    # Smooth calorie intake and weight
    smooth_cal = _ewma(cal_vals, span=7)
    smooth_wt = _ewma(wt_vals, span=10)

    avg_cal = sum(smooth_cal[-7:]) / min(7, len(smooth_cal))

    # Estimate weekly rate of weight change
    if len(smooth_wt) >= 7:
        recent_wt = sum(smooth_wt[-3:]) / 3
        earlier_wt = sum(smooth_wt[:3]) / 3
        weeks_span = len(smooth_wt) / 7
        weekly_rate = (recent_wt - earlier_wt) / max(weeks_span, 1)
    else:
        weekly_rate = (smooth_wt[-1] - smooth_wt[0]) / max(len(smooth_wt) / 7, 0.5)

    # TDEE = avg intake - (surplus/deficit implied by weight change)
    # 1 lb ≈ 3500 kcal
    daily_surplus = (weekly_rate * 3500) / 7
    tdee = avg_cal - daily_surplus

    # Clamp to reasonable range
    tdee = max(1000, min(6000, tdee))

    # Blend with previous estimate for stability
    prev_tdee = profile.get("tdee_estimate") or 2000
    blend_factor = 0.3 if data_quality == "good" else 0.2
    blended_tdee = blend_factor * tdee + (1 - blend_factor) * prev_tdee

    # Save updated estimate
    db.update_profile(tdee_estimate=round(blended_tdee))

    return {
        "tdee": round(blended_tdee),
        "weight_trend": round(smooth_wt[-1], 1) if smooth_wt else None,
        "weekly_rate": round(weekly_rate, 2),
        "data_quality": data_quality,
        "calorie_avg": round(avg_cal),
        "message": f"Based on {len(cal_vals)} days of intake and {len(wt_vals)} weigh-ins.",
    }


def suggest_calories(goal="maintain"):
    """Suggest daily calorie targets based on TDEE and goal."""
    result = compute_adaptive_tdee()
    tdee = result["tdee"]

    adjustments = {
        "aggressive_cut": -750,
        "cut": -500,
        "slow_cut": -250,
        "maintain": 0,
        "slow_bulk": 250,
        "bulk": 500,
    }

    offset = adjustments.get(goal, 0)
    target = max(1200, tdee + offset)

    return {
        "tdee": tdee,
        "goal": goal,
        "calorie_target": round(target),
        "deficit_surplus": offset,
        "data_quality": result["data_quality"],
    }
