# Blinkit Quick-Commerce Platform - SPM Innovative Assignment

A working prototype of the project defined in Tutorial 1 (Project Identification).
Stack: **Flask (Python) + SQLite + vanilla HTML/CSS/JS**. No Node, no build step, no database install.

## Run on macOS

```bash
cd blinkit_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5001** (port 5001 because macOS uses 5000 for AirPlay).
The SQLite database (`blinkit.db`) is created and seeded automatically on first run.

## Modules (mapped to the project scope)

| # | Module | File | What it does |
|---|--------|------|--------------|
| 1 | Catalog & Search | `modules/catalog.py` | 43 products, 8 categories, search, sort, live per-store stock |
| 2 | Dark-Store Inventory (WMS) | `modules/inventory.py` | Nearest dark store lookup, serviceable-radius check, stock view, restock, low-stock alerts |
| 3 | Cart, Promotions & Checkout | `modules/orders.py` | Pricing engine, promo codes, delivery fee rules, atomic stock reservation, ETA calculation |
| 4 | Order Tracking | `modules/tracking.py` | Status workflow (Placed > Packing > Packed > On the way > Delivered), live timeline + map, cancellation with stock restore |
| 5 | Delivery-Partner Dispatch | `modules/dispatch.py` | Auto-assigns the nearest free rider when an order is packed, queues orders if no rider is free, rider app, earnings |
| 6 | Admin Analytics | `modules/admin.py` | Orders, revenue, avg order value, avg delivery time, store/rider performance, top products, low stock |

## How the constraints from the tutorial show up in the code

- **10-20 min delivery SLA** - `compute_eta()` in `orders.py` (packing + pickup + travel time, minimum 10 min).
- **Geographic constraint** - `serviceability` endpoint rejects addresses outside a store's 3 km radius (pick "Far Outskirts" to see it).
- **Concurrency / stock accuracy** - stock is decremented with `UPDATE ... WHERE qty >= ?`, so two customers cannot buy the last unit.
- **Resource constraint (riders)** - if no rider is free, packed orders wait and are assigned the moment a rider completes a trip or goes online.
- **Promotions engine** - codes `WELCOME50`, `SAVE10`, `FREEDEL`.

## Demo script (open two browser tabs)

1. **Shop**: choose a location, add items, apply `SAVE10`, fill name / 10-digit phone / address, **Place order**.
2. **Dark store** tab: click **Start packing**, then **Mark packed** -> a rider is auto-assigned.
3. **Rider app** tab: select the assigned rider -> **Confirm pickup** -> **Mark delivered**.
4. **Track order** tab: watch the timeline, ETA and scooter on the map update every 3 seconds.
5. **Admin** tab: see revenue, delivery time, rider earnings and low-stock alerts update.
   *Reset demo data* restores everything.

## API quick reference

```
GET  /api/products?q=&category=&store_id=&sort=     GET  /api/serviceability?locality_id=
POST /api/orders/quote                              POST /api/orders
GET  /api/orders/<id>                               POST /api/orders/<id>/status | /cancel
GET  /api/stores/<id>/inventory | /orders           POST /api/stores/<id>/restock
GET  /api/riders | /api/riders/<id>                 POST /api/riders/<id>/pickup | /deliver | /availability
GET  /api/admin/stats                               POST /api/admin/reset
```

## Project structure

```
blinkit_project/
  app.py            Flask entry point (registers the 6 module blueprints)
  db.py             Schema, seed data, helpers
  modules/          catalog, inventory, orders, tracking, dispatch, admin
  static/           index.html, style.css, app.js  (the frontend)
  requirements.txt
```
# SPM_term_assignment
