"""MODULE 1 - Catalog & Search: categories, product listing, search, sort, per-store availability."""
from flask import Blueprint, jsonify, request

from db import get_db

bp = Blueprint("catalog", __name__, url_prefix="/api")


@bp.get("/categories")
def categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) AS n FROM products GROUP BY category ORDER BY category").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/products")
def products():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    store_id = request.args.get("store_id", type=int) or 1
    sort = request.args.get("sort", "relevance")

    sql = ("SELECT p.*, COALESCE(i.qty, 0) AS stock FROM products p "
           "LEFT JOIN inventory i ON i.product_id = p.id AND i.store_id = ? WHERE 1=1")
    params = [store_id]
    if q:
        sql += " AND (p.name LIKE ? OR p.category LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND p.category = ?"
        params.append(category)
    order = {"price_asc": "p.price ASC", "price_desc": "p.price DESC",
             "discount": "(p.mrp - p.price) / p.mrp DESC"}.get(sort, "p.id ASC")
    sql += f" ORDER BY {order}"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
