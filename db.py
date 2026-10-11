"""Database layer: schema, seed data and shared helpers (SQLite, no extra install needed)."""
import math
import os
import random
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blinkit.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
  id INTEGER PRIMARY KEY, name TEXT, area TEXT, lat REAL, lng REAL, radius_km REAL);
CREATE TABLE IF NOT EXISTS localities (
  id INTEGER PRIMARY KEY, name TEXT, lat REAL, lng REAL);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, mrp REAL, unit TEXT, emoji TEXT);
CREATE TABLE IF NOT EXISTS inventory (
  store_id INTEGER, product_id INTEGER, qty INTEGER, reorder_level INTEGER DEFAULT 10,
  PRIMARY KEY (store_id, product_id));
CREATE TABLE IF NOT EXISTS riders (
  id INTEGER PRIMARY KEY, name TEXT, store_id INTEGER, status TEXT DEFAULT 'AVAILABLE',
  lat REAL, lng REAL, deliveries INTEGER DEFAULT 0, earnings REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS promos (
  code TEXT PRIMARY KEY, kind TEXT, value REAL, min_order REAL, max_discount REAL, description TEXT);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT, phone TEXT, address TEXT,
  locality_id INTEGER, lat REAL, lng REAL, store_id INTEGER, rider_id INTEGER,
  status TEXT, subtotal REAL, discount REAL, delivery_fee REAL, total REAL,
  promo_code TEXT, payment_method TEXT, distance_km REAL, eta_minutes INTEGER,
  travel_minutes INTEGER, created_at TEXT, delivered_at TEXT);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, product_id INTEGER,
  name TEXT, price REAL, qty INTEGER);
CREATE TABLE IF NOT EXISTS order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, status TEXT, note TEXT, ts TEXT);
"""

STORES = [
    (1, "Dark Store - Sector 29", "Sector 29", 28.4595, 77.0680, 3.0),
    (2, "Dark Store - DLF Phase 3", "DLF Phase 3", 28.4930, 77.0950, 3.0),
    (3, "Dark Store - Sohna Road", "Sohna Road", 28.4120, 77.0430, 3.0),
]
LOCALITIES = [
    (1, "Sector 29 Market", 28.4650, 77.0700),
    (2, "Sector 40", 28.4480, 77.0580),
    (3, "DLF Phase 3", 28.4920, 77.0940),
    (4, "Sushant Lok 1", 28.4650, 77.0770),
    (5, "Golf Course Road", 28.4880, 77.1010),
    (6, "Sohna Road, Sector 47", 28.4150, 77.0400),
    (7, "South City 2", 28.4190, 77.0500),
    (8, "Far Outskirts (not serviceable)", 28.5500, 77.2000),
]
# name, category, price, mrp, unit, emoji
PRODUCTS = [
    ("Toned Milk", "Dairy & Eggs", 28, 28, "500 ml", "🥛"),
    ("Farm Eggs", "Dairy & Eggs", 54, 60, "6 pcs", "🥚"),
    ("Fresh Paneer", "Dairy & Eggs", 90, 95, "200 g", "🧀"),
    ("Salted Butter", "Dairy & Eggs", 58, 60, "100 g", "🧈"),
    ("Set Curd", "Dairy & Eggs", 38, 40, "400 g", "🥣"),
    ("Bananas", "Fruits & Vegetables", 45, 50, "6 pcs", "🍌"),
    ("Tomato", "Fruits & Vegetables", 24, 30, "500 g", "🍅"),
    ("Onion", "Fruits & Vegetables", 38, 45, "1 kg", "🧅"),
    ("Potato", "Fruits & Vegetables", 34, 40, "1 kg", "🥔"),
    ("Apple", "Fruits & Vegetables", 120, 140, "4 pcs", "🍎"),
    ("Spinach", "Fruits & Vegetables", 20, 25, "250 g", "🥬"),
    ("Lemon", "Fruits & Vegetables", 22, 25, "6 pcs", "🍋"),
    ("Potato Chips", "Snacks", 20, 20, "52 g", "🍟"),
    ("Salted Peanuts", "Snacks", 45, 50, "200 g", "🥜"),
    ("Cream Biscuits", "Snacks", 30, 35, "120 g", "🍪"),
    ("Namkeen Mixture", "Snacks", 55, 60, "200 g", "🥨"),
    ("Dark Chocolate", "Snacks", 90, 100, "55 g", "🍫"),
    ("Cola", "Beverages", 40, 45, "750 ml", "🥤"),
    ("Orange Juice", "Beverages", 110, 120, "1 L", "🍊"),
    ("Tea Leaves", "Beverages", 130, 145, "250 g", "🍵"),
    ("Instant Coffee", "Beverages", 150, 165, "50 g", "☕"),
    ("Mineral Water", "Beverages", 20, 20, "1 L", "💧"),
    ("Whole Wheat Atta", "Staples", 245, 270, "5 kg", "🌾"),
    ("Basmati Rice", "Staples", 120, 135, "1 kg", "🍚"),
    ("Toor Dal", "Staples", 165, 180, "1 kg", "🫘"),
    ("Sunflower Oil", "Staples", 145, 160, "1 L", "🛢️"),
    ("Sugar", "Staples", 48, 52, "1 kg", "🍬"),
    ("Iodised Salt", "Staples", 28, 30, "1 kg", "🧂"),
    ("White Bread", "Bakery", 45, 50, "400 g", "🍞"),
    ("Pav", "Bakery", 30, 32, "6 pcs", "🥖"),
    ("Tea Rusk", "Bakery", 40, 45, "200 g", "🥐"),
    ("Instant Noodles", "Instant Food", 14, 14, "70 g", "🍜"),
    ("Pasta", "Instant Food", 95, 105, "500 g", "🍝"),
    ("Tomato Ketchup", "Instant Food", 105, 115, "500 g", "🥫"),
    ("Dishwash Liquid", "Household", 99, 110, "500 ml", "🧴"),
    ("Detergent Powder", "Household", 130, 150, "1 kg", "🧺"),
    ("Toilet Cleaner", "Household", 89, 99, "500 ml", "🚽"),
    ("Garbage Bags", "Household", 75, 85, "30 pcs", "🗑️"),
    ("Tissue Rolls", "Household", 70, 80, "2 pack", "🧻"),
    ("Toothpaste", "Personal Care", 95, 105, "150 g", "🪥"),
    ("Shampoo", "Personal Care", 160, 185, "180 ml", "🧴"),
    ("Bathing Soap", "Personal Care", 140, 160, "4 pack", "🧼"),
    ("Hand Wash", "Personal Care", 85, 95, "200 ml", "🫧"),
]
RIDERS = [
    ("Ravi Kumar", 1), ("Imran Sheikh", 1), ("Suresh Yadav", 1),
    ("Amit Singh", 2), ("Deepak Verma", 2), ("Manoj Gupta", 2),
    ("Vikram Rao", 3), ("Sanjay Patil", 3),
]
PROMOS = [
    ("WELCOME50", "flat", 50, 199, 50, "Flat Rs.50 off on orders above Rs.199"),
    ("SAVE10", "percent", 10, 149, 60, "10% off up to Rs.60 on orders above Rs.149"),
    ("FREEDEL", "freedelivery", 0, 99, 0, "Free delivery on orders above Rs.99"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def add_event(conn, order_id, status, note=""):
    conn.execute("INSERT INTO order_events (order_id, status, note, ts) VALUES (?,?,?,?)",
                 (order_id, status, note, now()))


def seed(conn):
    conn.executemany("INSERT INTO stores VALUES (?,?,?,?,?,?)", STORES)
    conn.executemany("INSERT INTO localities VALUES (?,?,?,?)", LOCALITIES)
    for i, p in enumerate(PRODUCTS, start=1):
        conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)", (i, *p))
    rnd = random.Random(7)
    for s in STORES:
        for i in range(1, len(PRODUCTS) + 1):
            qty = rnd.choice([3, 6, 25, 40, 60, 80]) if rnd.random() < 0.15 else rnd.randint(20, 80)
            conn.execute("INSERT INTO inventory VALUES (?,?,?,10)", (s[0], i, qty))
    stores = {s[0]: s for s in STORES}
    for i, (name, sid) in enumerate(RIDERS, start=1):
        st = stores[sid]
        conn.execute("INSERT INTO riders (id,name,store_id,status,lat,lng) VALUES (?,?,?,?,?,?)",
                     (i, name, sid, "AVAILABLE", st[3] + rnd.uniform(-.004, .004), st[4] + rnd.uniform(-.004, .004)))
    conn.executemany("INSERT INTO promos VALUES (?,?,?,?,?,?)", PROMOS)


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


def reset_db():
    conn = get_db()
    for t in ["stores", "localities", "products", "inventory", "riders", "promos",
              "orders", "order_items", "order_events"]:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()
    init_db()
