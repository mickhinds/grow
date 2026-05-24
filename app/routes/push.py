"""Push notification routes — subscribe/unsubscribe from Web Push."""

import logging
from flask import Blueprint, request, jsonify, current_app
from app.models import db, PushSubscription

logger = logging.getLogger(__name__)

bp = Blueprint("push", __name__, url_prefix="/push")


@bp.route("/subscribe", methods=["POST"])
def subscribe():
    """Save a push subscription from the browser."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data"}), 400

    endpoint = data.get("endpoint", "").strip()
    p256dh = data.get("p256dh", "").strip()
    auth = data.get("auth", "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Missing fields"}), 400

    # Validate lengths
    if len(endpoint) > 2000 or len(p256dh) > 500 or len(auth) > 500:
        return jsonify({"error": "Fields too long"}), 400

    # Upsert — update if endpoint already exists, otherwise create
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = request.headers.get("User-Agent", "")[:300]
    else:
        sub = PushSubscription(
            user_id=1,  # Single user
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=request.headers.get("User-Agent", "")[:300],
        )
        db.session.add(sub)

    db.session.commit()
    logger.info("Push subscription saved.")
    return jsonify({"ok": True}), 201


@bp.route("/unsubscribe", methods=["POST"])
def unsubscribe():
    """Remove a push subscription."""
    data = request.get_json(silent=True)
    if not data or not data.get("endpoint"):
        return jsonify({"error": "No endpoint"}), 400

    sub = PushSubscription.query.filter_by(endpoint=data["endpoint"]).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
        logger.info("Push subscription removed.")

    return jsonify({"ok": True}), 200


@bp.route("/vapid-key")
def vapid_key():
    """Return the VAPID public key (for debugging/manual setup)."""
    key = current_app.config.get("VAPID_PUBLIC_KEY", "")
    return jsonify({"vapidPublicKey": key})
