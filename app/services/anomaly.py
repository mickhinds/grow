"""Anomaly detection — surface metrics only when they're interesting.

A metric earns a spot on the morning view when it deviates from
the user's own 14-day rolling average. What's unusual for you,
not what's unusual in general.
"""

from datetime import date, timedelta
from app.models import db, OuraDaily


def detect_anomalies(user_id: int, today: date) -> list:
    """Return a list of anomaly cards to show on the dashboard.

    Each anomaly is a dict: {"type": ..., "label": ..., "message": ..., "tone": "good"|"concern"|"neutral"}
    Only returns anomalies that are genuinely notable. Empty list = normal day.
    """
    yesterday = today - timedelta(days=1)
    oura = OuraDaily.query.filter_by(user_id=user_id, date=yesterday).first()
    if not oura:
        return []

    # Get 14-day history for baselines (excluding yesterday)
    two_weeks_ago = today - timedelta(days=15)
    history = OuraDaily.query.filter(
        OuraDaily.user_id == user_id,
        OuraDaily.date >= two_weeks_ago,
        OuraDaily.date < yesterday,
    ).all()

    if len(history) < 5:
        # Not enough data for meaningful baselines
        return []

    anomalies = []

    # --- Sleep score ---
    sleep_scores = [d.sleep_score for d in history if d.sleep_score]
    if sleep_scores and oura.sleep_score:
        avg = sum(sleep_scores) / len(sleep_scores)
        if oura.sleep_score < avg - 15:
            anomalies.append({
                "type": "sleep",
                "label": "Sleep",
                "message": f"Score {oura.sleep_score} — that's below your usual {avg:.0f}.",
                "tone": "concern",
            })
        elif oura.sleep_score > avg + 10 and oura.sleep_score >= 85:
            anomalies.append({
                "type": "sleep",
                "label": "Sleep",
                "message": f"Score {oura.sleep_score} — your best in two weeks.",
                "tone": "good",
            })

    # --- Steps ---
    step_counts = [d.steps for d in history if d.steps]
    if step_counts and oura.steps:
        avg = sum(step_counts) / len(step_counts)
        if oura.steps > avg * 1.5 and oura.steps >= 10000:
            anomalies.append({
                "type": "steps",
                "label": "Movement",
                "message": f"{oura.steps:,} steps — well above your {avg:,.0f} average.",
                "tone": "good",
            })
        elif oura.steps < avg * 0.4 and avg > 3000:
            anomalies.append({
                "type": "steps",
                "label": "Movement",
                "message": f"Only {oura.steps:,} steps — much quieter than your usual {avg:,.0f}.",
                "tone": "concern",
            })

    # --- Resting heart rate ---
    rhr_values = [d.resting_heart_rate for d in history if d.resting_heart_rate]
    if rhr_values and oura.resting_heart_rate:
        avg = sum(rhr_values) / len(rhr_values)
        if oura.resting_heart_rate > avg + 5:
            anomalies.append({
                "type": "heart",
                "label": "Resting HR",
                "message": f"{oura.resting_heart_rate} bpm — elevated from your usual {avg:.0f}. Body might be working on something.",
                "tone": "concern",
            })
        elif oura.resting_heart_rate < avg - 4 and oura.resting_heart_rate < 55:
            anomalies.append({
                "type": "heart",
                "label": "Resting HR",
                "message": f"{oura.resting_heart_rate} bpm — lower than usual. Good recovery sign.",
                "tone": "good",
            })

    # --- Readiness ---
    readiness_values = [d.readiness_score for d in history if d.readiness_score]
    if readiness_values and oura.readiness_score:
        avg = sum(readiness_values) / len(readiness_values)
        if oura.readiness_score >= 85 and oura.readiness_score > avg + 8:
            anomalies.append({
                "type": "readiness",
                "label": "Readiness",
                "message": f"Score {oura.readiness_score} — firing on all cylinders today.",
                "tone": "good",
            })
        elif oura.readiness_score < 55 and oura.readiness_score < avg - 12:
            anomalies.append({
                "type": "readiness",
                "label": "Readiness",
                "message": f"Readiness {oura.readiness_score} — your body's asking for a lighter day.",
                "tone": "concern",
            })

    # --- HRV ---
    hrv_values = [d.hrv_daily for d in history if d.hrv_daily]
    if hrv_values and oura.hrv_daily:
        avg = sum(hrv_values) / len(hrv_values)
        if oura.hrv_daily > avg * 1.25:
            anomalies.append({
                "type": "hrv",
                "label": "HRV",
                "message": f"HRV {oura.hrv_daily:.0f} — notably higher than your {avg:.0f} average. Well recovered.",
                "tone": "good",
            })

    # Limit to 2 most relevant anomalies (don't clutter the view)
    # Prioritize concerns over good news
    concerns = [a for a in anomalies if a["tone"] == "concern"]
    goods = [a for a in anomalies if a["tone"] == "good"]
    result = (concerns[:2] if concerns else goods[:2])

    return result
