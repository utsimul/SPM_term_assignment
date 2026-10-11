"""MODULE 6 - Admin Analytics: KPIs, demand insights, rider utilisation, low-stock alerts, demo reset."""
from datetime import datetime

from flask import Blueprint, jsonify

from db import get_db, reset_db

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
def stats():
    conn = get_db()
    q = lambda sql, *a: conn.execute(sql, a).fetchall()
    valid = "status != 'CANCELLED'"
    total_orders = q(f"SELECT COUNT(*) n, COALESCE(SUM(total),0) rev FROM orders WHERE {valid}")[0]
    delivered = q("SELECT created_at, delivered_at FROM orders WHERE status='DELIVERED'")
    mins = [(datetime.fromisoformat(r["delivered_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds() / 60
            for r in delivered]
    by_status = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) n FROM orders GROUP BY status")}
    top = q("SELECT i.name, SUM(i.qty) units FROM order_items i JOIN orders o ON o.id=i.order_id "
            "WHERE o.status != 'CANCELLED' GROUP BY i.name ORDER BY units DESC LIMIT 5")
    store_perf = q("SELECT s.name, COUNT(o.id) orders, COALESCE(SUM(o.total),0) revenue FROM stores s "
                   "LEFT JOIN orders o ON o.store_id=s.id AND o.status != 'CANCELLED' GROUP BY s.id")
    low = q("SELECT s.name store, p.name product, i.qty FROM inventory i JOIN stores s ON s.id=i.store_id "
            "JOIN products p ON p.id=i.product_id WHERE i.qty <= i.reorder_level ORDER BY i.qty LIMIT 12")
    riders = q("SELECT r.name, r.status, r.deliveries, r.earnings, s.name store FROM riders r "
               "JOIN stores s ON s.id=r.store_id ORDER BY r.deliveries DESC")
    n = total_orders["n"]
    out = {
        "total_orders": n, "revenue": round(total_orders["rev"], 2),
        "avg_order_value": round(total_orders["rev"] / n, 2) if n else 0,
        "avg_delivery_minutes": round(sum(mins) / len(mins), 1) if mins else None,
        "delivered": len(mins), "by_status": by_status,
        "top_products": [dict(r) for r in top], "store_performance": [dict(r) for r in store_perf],
        "low_stock": [dict(r) for r in low], "riders": [dict(r) for r in riders],
        "riders_busy": sum(1 for r in riders if r["status"] == "BUSY"), "riders_total": len(riders),
    }
    conn.close()
    return jsonify(out)


@bp.post("/reset")
def reset():
    reset_db()
    return jsonify(ok=True)
