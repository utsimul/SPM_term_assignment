"""MODULE 5 - Delivery-Partner Dispatch: nearest-available-rider allocation + rider app actions."""
from flask import Blueprint, jsonify, request

from db import add_event, get_db, haversine_km, now

bp = Blueprint("dispatch", __name__, url_prefix="/api")


def assign_rider(conn, order_id):
    """Assign the closest AVAILABLE rider of the order's store. Returns rider row or None."""
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order or order["status"] != "PACKED" or order["rider_id"]:
        return None
    store = conn.execute("SELECT * FROM stores WHERE id=?", (order["store_id"],)).fetchone()
    riders = conn.execute("SELECT * FROM riders WHERE store_id=? AND status='AVAILABLE'",
                          (order["store_id"],)).fetchall()
    if not riders:
        return None
    rider = min(riders, key=lambda r: haversine_km(r["lat"], r["lng"], store["lat"], store["lng"]))
    conn.execute("UPDATE riders SET status='BUSY' WHERE id=?", (rider["id"],))
    conn.execute("UPDATE orders SET rider_id=? WHERE id=?", (rider["id"], order_id))
    add_event(conn, order_id, "PACKED", f"Rider {rider['name']} assigned")
    return rider


def assign_pending(conn, store_id):
    """Called whenever a rider frees up: serve the oldest packed-but-unassigned order."""
    pending = conn.execute("SELECT id FROM orders WHERE store_id=? AND status='PACKED' AND rider_id IS NULL "
                           "ORDER BY id", (store_id,)).fetchall()
    for p in pending:
        if not assign_rider(conn, p["id"]):
            break


def _current_order(conn, rider_id):
    row = conn.execute("SELECT * FROM orders WHERE rider_id=? AND status IN ('PACKED','OUT_FOR_DELIVERY') "
                       "ORDER BY id DESC LIMIT 1", (rider_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["items"] = [dict(i) for i in conn.execute("SELECT name, qty FROM order_items WHERE order_id=?", (row["id"],))]
    return d


@bp.get("/riders")
def riders():
    conn = get_db()
    rows = conn.execute("SELECT r.*, s.name AS store_name FROM riders r JOIN stores s ON s.id=r.store_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/riders/<int:rider_id>")
def rider_detail(rider_id):
    conn = get_db()
    r = conn.execute("SELECT r.*, s.name AS store_name FROM riders r JOIN stores s ON s.id=r.store_id "
                     "WHERE r.id=?", (rider_id,)).fetchone()
    if not r:
        conn.close()
        return jsonify(error="Rider not found"), 404
    out = dict(r)
    out["current_order"] = _current_order(conn, rider_id)
    conn.close()
    return jsonify(out)


@bp.post("/riders/<int:rider_id>/availability")
def availability(rider_id):
    status = request.get_json(force=True).get("status")
    if status not in ("AVAILABLE", "OFFLINE"):
        return jsonify(error="Invalid status"), 400
    conn = get_db()
    r = conn.execute("SELECT * FROM riders WHERE id=?", (rider_id,)).fetchone()
    if not r or r["status"] == "BUSY":
        conn.close()
        return jsonify(error="Rider is busy with an order"), 409
    conn.execute("UPDATE riders SET status=? WHERE id=?", (status, rider_id))
    if status == "AVAILABLE":
        assign_pending(conn, r["store_id"])
    conn.commit()
    conn.close()
    return jsonify(status=status)


@bp.post("/riders/<int:rider_id>/pickup")
def pickup(rider_id):
    conn = get_db()
    o = conn.execute("SELECT * FROM orders WHERE rider_id=? AND status='PACKED'", (rider_id,)).fetchone()
    if not o:
        conn.close()
        return jsonify(error="No packed order waiting for pickup"), 409
    conn.execute("UPDATE orders SET status='OUT_FOR_DELIVERY' WHERE id=?", (o["id"],))
    add_event(conn, o["id"], "OUT_FOR_DELIVERY", "Rider picked up the order")
    conn.commit()
    conn.close()
    return jsonify(order_id=o["id"], status="OUT_FOR_DELIVERY")


@bp.post("/riders/<int:rider_id>/deliver")
def deliver(rider_id):
    conn = get_db()
    o = conn.execute("SELECT * FROM orders WHERE rider_id=? AND status='OUT_FOR_DELIVERY'", (rider_id,)).fetchone()
    if not o:
        conn.close()
        return jsonify(error="No order out for delivery"), 409
    earning = round(25 + 6 * o["distance_km"], 2)
    conn.execute("UPDATE orders SET status='DELIVERED', delivered_at=? WHERE id=?", (now(), o["id"]))
    conn.execute("UPDATE riders SET status='AVAILABLE', deliveries=deliveries+1, earnings=earnings+?, "
                 "lat=?, lng=? WHERE id=?", (earning, o["lat"], o["lng"], rider_id))
    add_event(conn, o["id"], "DELIVERED", "Delivered to customer")
    assign_pending(conn, o["store_id"])
    conn.commit()
    conn.close()
    return jsonify(order_id=o["id"], status="DELIVERED", earning=earning)
