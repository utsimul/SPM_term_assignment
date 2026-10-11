"""MODULE 4 - Order Tracking & Status Workflow: customer tracking view, store-side status changes, cancellation."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from db import add_event, get_db
from modules.dispatch import assign_pending, assign_rider

bp = Blueprint("tracking", __name__, url_prefix="/api")

ACTIVE = ("PLACED", "PACKING", "PACKED", "OUT_FOR_DELIVERY")


def _order_view(conn, o):
    d = dict(o)
    d["items"] = [dict(i) for i in conn.execute(
        "SELECT i.name, i.qty, i.price, p.emoji FROM order_items i LEFT JOIN products p ON p.id=i.product_id "
        "WHERE i.order_id=?", (o["id"],))]
    d["events"] = [dict(e) for e in conn.execute(
        "SELECT status, note, ts FROM order_events WHERE order_id=? ORDER BY id", (o["id"],))]
    store = conn.execute("SELECT name, lat, lng FROM stores WHERE id=?", (o["store_id"],)).fetchone()
    d["store"] = dict(store)
    d["rider"] = None
    if o["rider_id"]:
        r = conn.execute("SELECT id, name FROM riders WHERE id=?", (o["rider_id"],)).fetchone()
        d["rider"] = dict(r)
    if o["status"] in ACTIVE:
        elapsed = (datetime.now() - datetime.fromisoformat(o["created_at"])).total_seconds() / 60
        d["eta_remaining"] = max(1, round(o["eta_minutes"] - elapsed))
    else:
        d["eta_remaining"] = 0
    return d


@bp.get("/orders/<int:order_id>")
def get_order(order_id):
    conn = get_db()
    o = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not o:
        conn.close()
        return jsonify(error="Order not found"), 404
    out = _order_view(conn, o)
    conn.close()
    return jsonify(out)


@bp.get("/orders")
def list_orders():
    phone = request.args.get("phone", "")
    conn = get_db()
    rows = conn.execute("SELECT id, status, total, created_at FROM orders WHERE phone=? ORDER BY id DESC LIMIT 20",
                        (phone,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/stores/<int:store_id>/orders")
def store_orders(store_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders WHERE store_id=? AND status IN ('PLACED','PACKING','PACKED') "
                        "ORDER BY id", (store_id,)).fetchall()
    out = [_order_view(conn, r) for r in rows]
    conn.close()
    return jsonify(out)


@bp.post("/orders/<int:order_id>/status")
def advance(order_id):
    """Dark-store staff actions: PLACED -> PACKING -> PACKED (packed triggers rider dispatch)."""
    target = request.get_json(force=True).get("status")
    allowed = {"PACKING": "PLACED", "PACKED": "PACKING"}
    if target not in allowed:
        return jsonify(error="Invalid status"), 400
    conn = get_db()
    o = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not o or o["status"] != allowed[target]:
        conn.close()
        return jsonify(error=f"Order must be {allowed[target]} before {target}"), 409
    conn.execute("UPDATE orders SET status=? WHERE id=?", (target, order_id))
    add_event(conn, order_id, target, "Packing started" if target == "PACKING" else "Packed and ready")
    rider = assign_rider(conn, order_id) if target == "PACKED" else None
    conn.commit()
    conn.close()
    return jsonify(order_id=order_id, status=target, rider=dict(rider)["name"] if rider else None)


@bp.post("/orders/<int:order_id>/cancel")
def cancel(order_id):
    conn = get_db()
    o = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not o or o["status"] not in ("PLACED", "PACKING"):
        conn.close()
        return jsonify(error="This order can no longer be cancelled"), 409
    for it in conn.execute("SELECT product_id, qty FROM order_items WHERE order_id=?", (order_id,)).fetchall():
        conn.execute("UPDATE inventory SET qty = qty + ? WHERE store_id=? AND product_id=?",
                     (it["qty"], o["store_id"], it["product_id"]))
    conn.execute("UPDATE orders SET status='CANCELLED' WHERE id=?", (order_id,))
    add_event(conn, order_id, "CANCELLED", "Cancelled by customer; stock restored")
    conn.commit()
    conn.close()
    return jsonify(order_id=order_id, status="CANCELLED")
