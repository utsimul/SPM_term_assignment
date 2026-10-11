"""MODULE 2 - Dark-Store Inventory (WMS): store lookup by location, stock levels, restock, low-stock alerts."""
from flask import Blueprint, jsonify, request

from db import get_db, haversine_km

bp = Blueprint("inventory", __name__, url_prefix="/api")


def nearest_store(conn, lat, lng):
    """Return (store_row, distance_km) of the closest dark store, or (None, None)."""
    best, best_d = None, None
    for s in conn.execute("SELECT * FROM stores").fetchall():
        d = haversine_km(lat, lng, s["lat"], s["lng"])
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best, best_d


@bp.get("/localities")
def localities():
    conn = get_db()
    rows = conn.execute("SELECT * FROM localities ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/serviceability")
def serviceability():
    """Geographic constraint: a locality is serviceable only if within a dark store's radius."""
    loc_id = request.args.get("locality_id", type=int)
    conn = get_db()
    loc = conn.execute("SELECT * FROM localities WHERE id=?", (loc_id,)).fetchone()
    if not loc:
        conn.close()
        return jsonify(error="Unknown locality"), 404
    store, dist = nearest_store(conn, loc["lat"], loc["lng"])
    conn.close()
    ok = dist is not None and dist <= store["radius_km"]
    return jsonify(serviceable=ok, store_id=store["id"] if ok else None,
                   store_name=store["name"] if ok else None, distance_km=round(dist, 2),
                   message=None if ok else f"Sorry, we don't deliver here yet (nearest store is {dist:.1f} km away).")


@bp.get("/stores")
def stores():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stores").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/stores/<int:store_id>/inventory")
def store_inventory(store_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT p.id AS product_id, p.name, p.category, p.emoji, p.unit, i.qty, i.reorder_level, "
        "(i.qty <= i.reorder_level) AS low FROM inventory i JOIN products p ON p.id = i.product_id "
        "WHERE i.store_id=? ORDER BY low DESC, i.qty ASC, p.name", (store_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/stores/<int:store_id>/restock")
def restock(store_id):
    data = request.get_json(force=True)
    pid, qty = data.get("product_id"), int(data.get("qty", 0))
    if qty <= 0:
        return jsonify(error="Quantity must be positive"), 400
    conn = get_db()
    cur = conn.execute("UPDATE inventory SET qty = qty + ? WHERE store_id=? AND product_id=?",
                       (qty, store_id, pid))
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return jsonify(error="Item not stocked at this store"), 404
    row = conn.execute("SELECT qty FROM inventory WHERE store_id=? AND product_id=?",
                       (store_id, pid)).fetchone()
    conn.close()
    return jsonify(product_id=pid, qty=row["qty"])
