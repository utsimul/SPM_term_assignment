"""MODULE 3 - Cart, Promotions & Checkout: pricing engine, promo codes, stock-safe order placement, ETA."""
from flask import Blueprint, jsonify, request

from db import add_event, get_db, haversine_km, now
from modules.inventory import nearest_store

bp = Blueprint("orders", __name__, url_prefix="/api")

DELIVERY_FEE = 25
FREE_DELIVERY_ABOVE = 199
RIDER_SPEED_KMPH = 18
PACKING_MINUTES = 3
PICKUP_MINUTES = 2


def compute_eta(distance_km):
    travel = max(2, round(distance_km / RIDER_SPEED_KMPH * 60))
    return max(10, PACKING_MINUTES + PICKUP_MINUTES + travel), travel


def price_cart(conn, items, promo_code, store_id):
    """Price a cart. Returns dict with lines, totals, and any stock / promo problems."""
    lines, issues, subtotal = [], [], 0.0
    for it in items:
        pid, qty = it.get("product_id"), int(it.get("qty", 0))
        if qty <= 0:
            continue
        row = conn.execute(
            "SELECT p.*, COALESCE(i.qty,0) AS stock FROM products p "
            "LEFT JOIN inventory i ON i.product_id=p.id AND i.store_id=? WHERE p.id=?",
            (store_id, pid)).fetchone()
        if not row:
            issues.append(f"Product {pid} not found")
            continue
        if qty > row["stock"]:
            issues.append(f"Only {row['stock']} left of {row['name']}")
        lines.append({"product_id": pid, "name": row["name"], "emoji": row["emoji"],
                      "price": row["price"], "qty": qty, "line_total": row["price"] * qty})
        subtotal += row["price"] * qty

    delivery_fee = 0 if subtotal >= FREE_DELIVERY_ABOVE or subtotal == 0 else DELIVERY_FEE
    discount, promo_msg, promo_ok = 0.0, None, False
    code = (promo_code or "").strip().upper()
    if code:
        promo = conn.execute("SELECT * FROM promos WHERE code=?", (code,)).fetchone()
        if not promo:
            promo_msg = "Invalid promo code"
        elif subtotal < promo["min_order"]:
            promo_msg = f"Add Rs.{promo['min_order'] - subtotal:.0f} more to use {code}"
        else:
            promo_ok = True
            if promo["kind"] == "flat":
                discount = promo["value"]
            elif promo["kind"] == "percent":
                discount = min(subtotal * promo["value"] / 100, promo["max_discount"])
            elif promo["kind"] == "freedelivery":
                discount = 0
                delivery_fee = 0
            promo_msg = f"{code} applied: {promo['description']}"
    discount = min(discount, subtotal)
    total = max(0, subtotal - discount + delivery_fee)
    return {"lines": lines, "subtotal": round(subtotal, 2), "discount": round(discount, 2),
            "delivery_fee": delivery_fee, "total": round(total, 2), "issues": issues,
            "promo_code": code if promo_ok else None, "promo_message": promo_msg, "promo_ok": promo_ok}


def _resolve_location(conn, locality_id):
    loc = conn.execute("SELECT * FROM localities WHERE id=?", (locality_id,)).fetchone()
    if not loc:
        return None, None, None, "Please choose a delivery location"
    store, dist = nearest_store(conn, loc["lat"], loc["lng"])
    if dist > store["radius_km"]:
        return loc, None, dist, "We don't deliver to this location yet"
    return loc, store, dist, None


@bp.get("/promos")
def promos():
    conn = get_db()
    rows = conn.execute("SELECT code, description FROM promos").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/orders/quote")
def quote():
    data = request.get_json(force=True)
    conn = get_db()
    loc, store, dist, err = _resolve_location(conn, data.get("locality_id"))
    if err:
        conn.close()
        return jsonify(error=err), 400
    result = price_cart(conn, data.get("items", []), data.get("promo_code"), store["id"])
    eta, _ = compute_eta(dist)
    result.update(store_name=store["name"], eta_minutes=eta)
    conn.close()
    return jsonify(result)


@bp.post("/orders")
def place_order():
    data = request.get_json(force=True)
    name, phone = (data.get("customer_name") or "").strip(), (data.get("phone") or "").strip()
    address, payment = (data.get("address") or "").strip(), data.get("payment_method", "UPI")
    if not name or not phone.isdigit() or len(phone) != 10 or not address:
        return jsonify(error="Enter your name, a 10-digit phone number and an address"), 400

    conn = get_db()
    loc, store, dist, err = _resolve_location(conn, data.get("locality_id"))
    if err:
        conn.close()
        return jsonify(error=err), 400
    cart = price_cart(conn, data.get("items", []), data.get("promo_code"), store["id"])
    if not cart["lines"]:
        conn.close()
        return jsonify(error="Your cart is empty"), 400
    if cart["issues"]:
        conn.close()
        return jsonify(error="Some items are unavailable", issues=cart["issues"]), 409

    # Atomic stock reservation: each UPDATE only succeeds if enough stock remains.
    try:
        for ln in cart["lines"]:
            cur = conn.execute(
                "UPDATE inventory SET qty = qty - ? WHERE store_id=? AND product_id=? AND qty >= ?",
                (ln["qty"], store["id"], ln["product_id"], ln["qty"]))
            if cur.rowcount == 0:
                raise ValueError(f"{ln['name']} just went out of stock")
        eta, travel = compute_eta(dist)
        cur = conn.execute(
            "INSERT INTO orders (customer_name, phone, address, locality_id, lat, lng, store_id, status, "
            "subtotal, discount, delivery_fee, total, promo_code, payment_method, distance_km, "
            "eta_minutes, travel_minutes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, phone, address, loc["id"], loc["lat"], loc["lng"], store["id"], "PLACED",
             cart["subtotal"], cart["discount"], cart["delivery_fee"], cart["total"], cart["promo_code"],
             payment, round(dist, 2), eta, travel, now()))
        oid = cur.lastrowid
        for ln in cart["lines"]:
            conn.execute("INSERT INTO order_items (order_id, product_id, name, price, qty) VALUES (?,?,?,?,?)",
                         (oid, ln["product_id"], ln["name"], ln["price"], ln["qty"]))
        add_event(conn, oid, "PLACED", f"Order confirmed at {store['name']}")
        conn.commit()
    except ValueError as e:
        conn.rollback()
        conn.close()
        return jsonify(error=str(e), issues=[str(e)]), 409
    conn.close()
    return jsonify(order_id=oid, total=cart["total"], eta_minutes=eta, store_name=store["name"]), 201
