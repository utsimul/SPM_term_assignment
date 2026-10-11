/* Blinkit demo frontend - vanilla JS, talks to the Flask API under /api */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rs = n => "₹" + (Number(n) % 1 ? Number(n).toFixed(2) : Number(n));
const hhmm = iso => new Date(iso).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});

async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    method: opts.method || "GET",
    headers: {"Content-Type": "application/json"},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || "Request failed"), {data});
  return data;
}
let toastTimer;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.hidden = true, 2800);
}

/* ---------- navigation + polling ---------- */
let poller = null;
const loaders = {shop: () => {}, track: loadTrack, store: loadStore, rider: loadRider, admin: loadAdmin};
function show(view) {
  document.querySelectorAll(".view").forEach(v => v.hidden = v.id !== "view-" + view);
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.view === view));
  clearInterval(poller);
  loaders[view]();
  if (view !== "shop") poller = setInterval(loaders[view], 3000);
}
$("#tabs").addEventListener("click", e => { if (e.target.dataset.view) show(e.target.dataset.view); });

/* ---------- MODULE 1: catalog + shop ---------- */
const S = {locs: [], loc: 1, svc: null, cat: "", pmap: {}, list: [],
           cart: JSON.parse(localStorage.getItem("cart") || "{}"),
           promo: "", lastOrder: localStorage.getItem("lastOrder") || ""};
const saveCart = () => localStorage.setItem("cart", JSON.stringify(S.cart));

async function initShop() {
  S.locs = await api("/localities");
  $("#locality").innerHTML = S.locs.map(l => `<option value="${l.id}">${esc(l.name)}</option>`).join("");
  const cats = await api("/categories");
  $("#chips").innerHTML = `<button data-cat="" class="on">All</button>` +
    cats.map(c => `<button data-cat="${esc(c.category)}">${esc(c.category)}</button>`).join("");
  const promos = await api("/promos");
  $("#promo-list").textContent = "Try: " + promos.map(p => p.code).join(", ");
  await onLocationChange();
}

async function onLocationChange() {
  S.loc = Number($("#locality").value) || 1;
  S.svc = await api(`/serviceability?locality_id=${S.loc}`);
  const b = $("#loc-banner");
  b.className = "banner" + (S.svc.serviceable ? "" : " bad");
  b.textContent = S.svc.serviceable
    ? `Delivering from ${S.svc.store_name} (${S.svc.distance_km} km away)`
    : S.svc.message;
  await loadProducts();
  refreshBill();
}

async function loadProducts() {
  const p = new URLSearchParams({q: $("#search").value.trim(), sort: $("#sort").value,
                                 store_id: S.svc?.store_id || 1});
  S.list = await api("/products?" + p);
  S.list.forEach(x => S.pmap[x.id] = x);
  renderProducts();
}

function renderProducts() {
  const items = S.list.filter(p => !S.cat || p.category === S.cat);
  if (!items.length) { $("#products").innerHTML = `<p class="empty">No items match your search.</p>`; return; }
  $("#products").innerHTML = items.map(p => {
    const q = S.cart[p.id] || 0, off = Math.round((p.mrp - p.price) / p.mrp * 100);
    const disabled = !S.svc?.serviceable || p.stock <= 0;
    const ctl = q ? stepper(p.id, q)
      : `<button class="add" data-add="${p.id}" ${disabled ? "disabled" : ""}>${p.stock <= 0 ? "Out of stock" : "Add"}</button>`;
    return `<div class="card"><div class="pic">${p.emoji}</div>
      <div class="nm">${esc(p.name)}</div><div class="un">${esc(p.unit)}</div>
      <div class="pr"><b>${rs(p.price)}</b>${p.mrp > p.price ? `<s>${rs(p.mrp)}</s>` : ""}</div>
      ${off ? `<div class="off">${off}% off</div>` : ""}
      ${p.stock > 0 && p.stock <= 10 ? `<div class="low">Only ${p.stock} left</div>` : ""}
      ${ctl}</div>`;
  }).join("");
}
const stepper = (id, q) => `<div class="step"><button data-dec="${id}" aria-label="Remove one">−</button><span>${q}</span><button data-inc="${id}" aria-label="Add one">+</button></div>`;

function changeQty(id, delta) {
  const p = S.pmap[id], next = (S.cart[id] || 0) + delta;
  if (next > p.stock) return toast(`Only ${p.stock} of ${p.name} in stock`);
  if (next <= 0) delete S.cart[id]; else S.cart[id] = next;
  saveCart(); renderProducts(); refreshBill();
}

document.addEventListener("click", e => {
  const t = e.target.closest("[data-add],[data-inc],[data-dec],[data-cat]");
  if (!t) return;
  if (t.dataset.add) changeQty(+t.dataset.add, 1);
  if (t.dataset.inc) changeQty(+t.dataset.inc, 1);
  if (t.dataset.dec) changeQty(+t.dataset.dec, -1);
  if (t.dataset.cat !== undefined && t.closest("#chips")) {
    S.cat = t.dataset.cat;
    document.querySelectorAll("#chips button").forEach(b => b.classList.toggle("on", b === t));
    renderProducts();
  }
});
let searchTimer;
$("#search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadProducts, 250); });
$("#sort").addEventListener("change", loadProducts);
$("#locality").addEventListener("change", onLocationChange);

/* ---------- MODULE 3: cart + checkout ---------- */
async function refreshBill() {
  const ids = Object.keys(S.cart).filter(id => S.pmap[id]);
  if (!ids.length) {
    $("#cart-lines").innerHTML = `<p class="empty">Your cart is empty. Add something from the left.</p>`;
    $("#bill").innerHTML = ""; $("#promo-msg").textContent = ""; $("#place").disabled = true; return;
  }
  $("#cart-lines").innerHTML = ids.map(id => {
    const p = S.pmap[id];
    return `<div class="line"><span>${p.emoji}</span><span>${esc(p.name)}<br><span class="hint">${esc(p.unit)} · ${rs(p.price)}</span></span>${stepper(id, S.cart[id])}</div>`;
  }).join("");
  if (!S.svc?.serviceable) { $("#bill").innerHTML = ""; $("#place").disabled = true; return; }
  try {
    const q = await api("/orders/quote", {method: "POST", body: {
      locality_id: S.loc, promo_code: S.promo,
      items: ids.map(id => ({product_id: +id, qty: S.cart[id]}))}});
    $("#bill").innerHTML = `<div class="bill">
      <div><span>Items</span><span>${rs(q.subtotal)}</span></div>
      ${q.discount ? `<div class="save"><span>Promo discount</span><span>−${rs(q.discount)}</span></div>` : ""}
      <div><span>Delivery</span><span>${q.delivery_fee ? rs(q.delivery_fee) : "Free"}</span></div>
      <div class="tot"><span>Total</span><span>${rs(q.total)}</span></div>
      <div class="hint">Estimated delivery in ~${q.eta_minutes} min</div></div>`;
    const pm = $("#promo-msg");
    pm.textContent = q.promo_message || ""; pm.className = "hint" + (q.promo_message && !q.promo_ok ? " err" : "");
    $("#place-msg").textContent = q.issues.join(". ");
    $("#place").disabled = q.issues.length > 0;
  } catch (err) { $("#place-msg").textContent = err.message; $("#place").disabled = true; }
}
$("#apply-promo").addEventListener("click", () => { S.promo = $("#promo").value.trim(); refreshBill(); });

$("#place").addEventListener("click", async () => {
  const btn = $("#place"), msg = $("#place-msg");
  msg.textContent = ""; btn.disabled = true;
  try {
    const r = await api("/orders", {method: "POST", body: {
      customer_name: $("#c-name").value, phone: $("#c-phone").value, address: $("#c-address").value,
      payment_method: $("#c-pay").value, locality_id: S.loc, promo_code: S.promo,
      items: Object.keys(S.cart).map(id => ({product_id: +id, qty: S.cart[id]}))}});
    S.cart = {}; saveCart(); S.promo = ""; $("#promo").value = "";
    S.lastOrder = r.order_id; localStorage.setItem("lastOrder", r.order_id);
    toast(`Order #${r.order_id} placed - arriving in ~${r.eta_minutes} min`);
    $("#track-id").value = r.order_id;
    show("track");
    loadProducts(); refreshBill();
  } catch (err) {
    msg.textContent = (err.data?.issues || [err.message]).join(". ");
    loadProducts();
  } finally { btn.disabled = false; }
});

/* ---------- MODULE 4: order tracking ---------- */
const STEPS = [["PLACED", "Order placed"], ["PACKING", "Being packed"], ["PACKED", "Packed"],
               ["OUT_FOR_DELIVERY", "On the way"], ["DELIVERED", "Delivered"]];

function mapSvg(o) {
  const a = o.store, b = {lat: o.lat, lng: o.lng};
  let t = 0;
  if (o.status === "OUT_FOR_DELIVERY") {
    const ev = [...o.events].reverse().find(e => e.status === "OUT_FOR_DELIVERY");
    t = Math.min(.92, (Date.now() - new Date(ev.ts)) / 60000 / Math.max(1, o.travel_minutes));
  } else if (o.status === "DELIVERED") t = 1;
  const minLat = Math.min(a.lat, b.lat), maxLat = Math.max(a.lat, b.lat);
  const minLng = Math.min(a.lng, b.lng), maxLng = Math.max(a.lng, b.lng);
  const X = lng => 30 + (maxLng === minLng ? .5 : (lng - minLng) / (maxLng - minLng)) * 340;
  const Y = lat => 120 - (maxLat === minLat ? .5 : (lat - minLat) / (maxLat - minLat)) * 90;
  const x1 = X(a.lng), y1 = Y(a.lat), x2 = X(b.lng), y2 = Y(b.lat);
  const rx = x1 + (x2 - x1) * t, ry = y1 + (y2 - y1) * t;
  return `<svg class="map" viewBox="0 0 400 150" role="img" aria-label="Route from store to your address">
    <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#0c831f" stroke-width="3" stroke-dasharray="6 6"/>
    <circle cx="${x1}" cy="${y1}" r="9" fill="#f8cb46" stroke="#1b1f23" stroke-width="2"/>
    <circle cx="${x2}" cy="${y2}" r="9" fill="#0c831f"/>
    ${o.rider ? `<text x="${rx}" y="${ry + 7}" font-size="22" text-anchor="middle">🛵</text>` : ""}
    <text x="${x1}" y="${y1 - 14}" font-size="11" text-anchor="middle">Dark store</text>
    <text x="${x2}" y="${y2 - 14}" font-size="11" text-anchor="middle">You</text></svg>`;
}

async function loadTrack() {
  const id = $("#track-id").value.trim() || S.lastOrder;
  if (!id) return;
  $("#track-id").value = id;
  const box = $("#track-body");
  try {
    const o = await api("/orders/" + id);
    const idx = STEPS.findIndex(s => s[0] === o.status);
    const cancelled = o.status === "CANCELLED";
    const tl = cancelled ? `<p><span class="pill bad">Cancelled</span> ${esc(o.events.at(-1).note)}</p>` :
      `<ul class="timeline">${STEPS.map(([k, label], i) => {
        const evs = o.events.filter(e => e.status === k), ev = evs.at(-1);
        const text = k === "PACKED" && o.rider ? `Packed - ${esc(o.rider.name)} is your delivery partner` : label;
        return `<li class="${i <= idx ? "done" : ""} ${i === idx && k !== "DELIVERED" ? "now" : ""}">${text}${ev ? `<small>${hhmm(ev.ts)}</small>` : ""}</li>`;
      }).join("")}</ul>`;
    const eta = ["DELIVERED", "CANCELLED"].includes(o.status) ? "" :
      `<div class="eta"><div><span class="hint">Arriving in</span><br><b>${o.eta_remaining} min</b></div><div class="hint">from ${esc(o.store.name)}</div></div>`;
    box.innerHTML = `<div class="row"><h2>Order #${o.id}</h2><span class="pill ${o.status === "DELIVERED" ? "ok" : cancelled ? "bad" : "warn"}">${o.status.replaceAll("_", " ")}</span></div>
      ${eta}${cancelled ? "" : mapSvg(o)}${tl}
      <h3>Items</h3><ul>${o.items.map(i => `<li>${i.emoji || ""} ${esc(i.name)} × ${i.qty}</li>`).join("")}</ul>
      <div class="bill"><div><span>Subtotal</span><span>${rs(o.subtotal)}</span></div>
      ${o.discount ? `<div class="save"><span>Discount (${esc(o.promo_code)})</span><span>−${rs(o.discount)}</span></div>` : ""}
      <div><span>Delivery</span><span>${o.delivery_fee ? rs(o.delivery_fee) : "Free"}</span></div>
      <div class="tot"><span>Total (${esc(o.payment_method)})</span><span>${rs(o.total)}</span></div></div>
      ${["PLACED", "PACKING"].includes(o.status) ? `<p><button class="ghost danger" id="cancel-order">Cancel order</button></p>` : ""}`;
    const c = $("#cancel-order");
    if (c) c.onclick = async () => { await api(`/orders/${o.id}/cancel`, {method: "POST"}); toast("Order cancelled"); loadTrack(); };
  } catch (err) { box.innerHTML = `<p class="hint err">${esc(err.message)}</p>`; }
}
$("#track-go").addEventListener("click", loadTrack);

/* ---------- MODULE 2: dark-store console ---------- */
let storeReady = false;
async function loadStore() {
  if (!storeReady) {
    const stores = await api("/stores");
    $("#store-select").innerHTML = stores.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
    $("#store-select").onchange = loadStore; storeReady = true;
  }
  const sid = $("#store-select").value;
  const [orders, inv] = await Promise.all([api(`/stores/${sid}/orders`), api(`/stores/${sid}/inventory`)]);
  $("#store-orders").innerHTML = orders.length ? orders.map(o => `
    <div class="order"><div class="head"><b>Order #${o.id}</b><span class="pill warn">${o.status}</span></div>
      <div class="hint">${esc(o.customer_name)} · ${esc(o.address)} · ${hhmm(o.created_at)}</div>
      <ul>${o.items.map(i => `<li>${esc(i.name)} × ${i.qty}</li>`).join("")}</ul>
      ${o.status === "PLACED" ? `<button class="primary" data-next="PACKING" data-id="${o.id}">Start packing</button>` : ""}
      ${o.status === "PACKING" ? `<button class="primary" data-next="PACKED" data-id="${o.id}">Mark packed</button>` : ""}
      ${o.status === "PACKED" ? `<span class="hint">${o.rider ? "Waiting for " + esc(o.rider.name) + " to pick up" : "Waiting for a free rider..."}</span>` : ""}
    </div>`).join("") : `<p class="empty">No orders waiting. New orders show up here.</p>`;
  $("#store-inv").innerHTML = `<table><tr><th>Item</th><th>Stock</th><th></th></tr>${inv.map(i => `
    <tr class="${i.low ? "lowrow" : ""}"><td>${i.emoji} ${esc(i.name)} <span class="hint">${esc(i.unit)}</span></td>
    <td>${i.qty} ${i.low ? `<span class="pill warn">low</span>` : ""}</td>
    <td><button class="ghost" data-restock="${i.product_id}">+20</button></td></tr>`).join("")}</table>`;
}
document.addEventListener("click", async e => {
  const n = e.target.closest("[data-next]"), r = e.target.closest("[data-restock]");
  try {
    if (n) {
      const res = await api(`/orders/${n.dataset.id}/status`, {method: "POST", body: {status: n.dataset.next}});
      toast(res.rider ? `Packed - ${res.rider} assigned` : res.status === "PACKED" ? "Packed - waiting for a free rider" : "Packing started");
      loadStore();
    }
    if (r) {
      await api(`/stores/${$("#store-select").value}/restock`, {method: "POST", body: {product_id: +r.dataset.restock, qty: 20}});
      toast("Restocked +20"); loadStore();
    }
  } catch (err) { toast(err.message); }
});

/* ---------- MODULE 5: rider app ---------- */
let riderReady = false;
async function loadRider() {
  if (!riderReady) {
    const rs_ = await api("/riders");
    $("#rider-select").innerHTML = rs_.map(r => `<option value="${r.id}">${esc(r.name)} (${esc(r.store_name.replace("Dark Store - ", ""))})</option>`).join("");
    $("#rider-select").onchange = loadRider; riderReady = true;
  }
  const r = await api("/riders/" + $("#rider-select").value), o = r.current_order;
  const cls = {AVAILABLE: "ok", BUSY: "warn", OFFLINE: ""}[r.status];
  let job = `<p class="empty">${r.status === "AVAILABLE" ? "You're online. Waiting for the next order..." : r.status === "OFFLINE" ? "You're offline." : ""}</p>`;
  if (o) job = `<div class="order"><div class="head"><b>Order #${o.id}</b><span class="pill warn">${o.status === "PACKED" ? "Pick up at store" : "Deliver now"}</span></div>
    <p>${esc(o.customer_name)} · ${esc(o.phone)}<br><span class="hint">${esc(o.address)} · ${o.distance_km} km</span></p>
    <ul>${o.items.map(i => `<li>${esc(i.name)} × ${i.qty}</li>`).join("")}</ul>
    <p class="hint">${o.payment_method === "Cash on delivery" ? "Collect " + rs(o.total) + " in cash" : "Paid online"}</p>
    ${o.status === "PACKED" ? `<button class="primary" id="r-pick">Confirm pickup</button>` : `<button class="primary" id="r-drop">Mark delivered</button>`}</div>`;
  $("#rider-body").innerHTML = `<div class="kpis">
    <div class="kpi"><span>Status</span><b><span class="pill ${cls}">${r.status}</span></b></div>
    <div class="kpi"><span>Deliveries</span><b>${r.deliveries}</b></div>
    <div class="kpi"><span>Earnings</span><b>${rs(r.earnings)}</b></div></div>
    ${r.status !== "BUSY" ? `<p><button class="ghost" id="r-toggle">${r.status === "OFFLINE" ? "Go online" : "Go offline"}</button></p>` : ""}${job}`;
  const act = (sel, path, body, msg) => { const b = $(sel); if (b) b.onclick = async () => {
    try { const res = await api(`/riders/${r.id}/${path}`, {method: "POST", body}); toast(msg(res)); loadRider(); } catch (e) { toast(e.message); } }; };
  act("#r-pick", "pickup", null, () => "Pickup confirmed");
  act("#r-drop", "deliver", null, res => `Delivered! You earned ${rs(res.earning)}`);
  act("#r-toggle", "availability", {status: r.status === "OFFLINE" ? "AVAILABLE" : "OFFLINE"}, () => "Status updated");
}

/* ---------- MODULE 6: admin dashboard ---------- */
async function loadAdmin() {
  const s = await api("/admin/stats");
  const max = Math.max(1, ...Object.values(s.by_status));
  const bars = Object.entries(s.by_status).map(([k, v]) =>
    `<div class="bar"><span>${k.replaceAll("_", " ")}</span><i style="width:${v / max * 100}%"></i><b>${v}</b></div>`).join("") || `<p class="empty">No orders yet.</p>`;
  $("#admin-body").innerHTML = `
    <div class="kpis">
      <div class="kpi"><b>${s.total_orders}</b><span>Orders (excl. cancelled)</span></div>
      <div class="kpi"><b>${rs(s.revenue)}</b><span>Revenue</span></div>
      <div class="kpi"><b>${rs(s.avg_order_value)}</b><span>Avg. order value</span></div>
      <div class="kpi"><b>${s.avg_delivery_minutes ?? "-"}${s.avg_delivery_minutes != null ? " min" : ""}</b><span>Avg. delivery time (${s.delivered} delivered)</span></div>
      <div class="kpi"><b>${s.riders_busy}/${s.riders_total}</b><span>Riders busy</span></div>
    </div>
    <div class="grid3">
      <div><h3>Orders by status</h3>${bars}
        <h3 style="margin-top:1.2rem">Top products</h3>
        <table>${s.top_products.map(p => `<tr><td>${esc(p.name)}</td><td>${p.units} sold</td></tr>`).join("") || `<tr><td class="empty">No sales yet</td></tr>`}</table></div>
      <div><h3>Dark-store performance</h3>
        <table><tr><th>Store</th><th>Orders</th><th>Revenue</th></tr>${s.store_performance.map(x => `<tr><td>${esc(x.name)}</td><td>${x.orders}</td><td>${rs(x.revenue)}</td></tr>`).join("")}</table>
        <h3 style="margin-top:1.2rem">Low-stock alerts</h3>
        <table>${s.low_stock.map(x => `<tr><td>${esc(x.product)}<br><span class="hint">${esc(x.store)}</span></td><td><span class="pill warn">${x.qty} left</span></td></tr>`).join("") || `<tr><td class="empty">All stocked</td></tr>`}</table></div>
      <div><h3>Delivery partners</h3>
        <table><tr><th>Rider</th><th>Status</th><th>Trips</th><th>Earned</th></tr>${s.riders.map(r => `<tr><td>${esc(r.name)}<br><span class="hint">${esc(r.store.replace("Dark Store - ", ""))}</span></td><td>${r.status}</td><td>${r.deliveries}</td><td>${rs(r.earnings)}</td></tr>`).join("")}</table></div>
    </div>`;
}
$("#reset").addEventListener("click", async () => {
  if (!confirm("Delete all orders and restore the demo data?")) return;
  await api("/admin/reset", {method: "POST"});
  S.cart = {}; saveCart(); S.lastOrder = ""; localStorage.removeItem("lastOrder");
  toast("Demo data restored"); loadAdmin(); loadProducts(); refreshBill();
});

initShop().then(refreshBill);
