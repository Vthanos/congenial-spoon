// Scrappy front end: plain JS, no build step, works on GitHub Pages.
const EFFORTS = [
  ["no-cook", "No cook"], ["heat-only", "Just heat"], ["cook", "Cooking"], ["drink", "Drinks"],
];
const LOYALTY = { Lidl: "Lidl Plus", Tesco: "Clubcard" };
const state = {
  products: [],
  favourites: [],
  view: localStorage.getItem("view") || "mine",
  efforts: new Set(JSON.parse(localStorage.getItem("efforts") || '["no-cook","heat-only","drink"]')),
  stores: new Set(),
  list: JSON.parse(localStorage.getItem("list") || "{}"), // id -> {qty, p}
};
const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const gbp = (n) => (n < 1 ? Math.round(n * 100) + "p" : "£" + n.toFixed(2));
const unitPrice = (p) => (p.unit_price ? `${gbp(p.unit_price)}/${p.unit}` : p.unit_text || "");

// ---------- filters ----------
function chip(label, pressed, onClick) {
  const b = el("button", "chip", label);
  b.setAttribute("aria-pressed", pressed);
  b.onclick = () => { onClick(); b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true"); render(); };
  return b;
}

function buildFilters() {
  for (const [key, label] of EFFORTS) {
    $("#effortChips").append(chip(label, state.efforts.has(key), () => {
      state.efforts.has(key) ? state.efforts.delete(key) : state.efforts.add(key);
      localStorage.setItem("efforts", JSON.stringify([...state.efforts]));
    }));
  }
  for (const s of [...new Set(state.products.map((p) => p.store))].sort()) {
    state.stores.add(s);
    $("#storeChips").append(chip(s, true, () => (state.stores.has(s) ? state.stores.delete(s) : state.stores.add(s))));
  }
  for (const c of [...new Set(state.products.map((p) => p.category))].sort()) $("#category").append(new Option(c, c));

  $("#hideDearer").checked = localStorage.getItem("hideDearer") !== "no";
  $("#hideDearer").addEventListener("input", () => localStorage.setItem("hideDearer", $("#hideDearer").checked ? "yes" : "no"));
  for (const id of ["#search", "#category", "#sort", "#offersOnly", "#hideLoyalty", "#hideDearer"]) {
    $(id).addEventListener("input", render);
  }
  for (const b of document.querySelectorAll(".tabs button")) {
    b.onclick = () => { state.view = b.dataset.view; localStorage.setItem("view", state.view); render(); };
  }
}

// Filters shared by both views: which shops, and whether app-only prices count.
const visible = (p) => state.stores.has(p.store) && !($("#hideLoyalty").checked && p.loyalty);

const sorters = {
  saving: (a, b) => (b.saving_pct || 0) - (a.saving_pct || 0) || a.price - b.price,
  price: (a, b) => a.price - b.price,
  unit: (a, b) => (a.unit_price ?? 1e9) - (b.unit_price ?? 1e9),
  name: (a, b) => a.name.localeCompare(b.name),
};

// ---------- product card ----------
function card(p) {
  const c = $("#cardTpl").content.firstElementChild.cloneNode(true);
  const img = c.querySelector("img");
  if (p.image) img.src = p.image; else img.removeAttribute("src");

  const h = c.querySelector("h3");
  if (p.url) { const a = el("a", null, p.name); a.href = p.url; a.target = "_blank"; a.rel = "noopener"; h.append(a); }
  else h.textContent = p.name;

  const badges = c.querySelector(".badges");
  const badge = (text, cls) => badges.append(el("span", "badge " + cls, text));
  badge(p.store, "store");
  if (p.best_across_shops) badge("Cheapest shop", "best");
  if (p.saving_pct) badge(`-${p.saving_pct}%`, "save");
  if (p.loyalty) badge(LOYALTY[p.store] || "App/card", "plus");
  else if (p.offer && !p.saving_pct) badge(p.offer, "");
  if (p.is_lowest) badge("Lowest we've seen", "low");
  if (p.stale) badge("old data", "stale");

  const until = p.valid_until && new Date(p.valid_until).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  c.querySelector(".sub").textContent = [p.pack, p.offer && p.saving_pct ? p.offer : null, until && "until " + until]
    .filter(Boolean).join(" · ");
  c.querySelector(".price").textContent = gbp(p.price);
  c.querySelector(".was").textContent = p.was_price ? gbp(p.was_price) : "";
  c.querySelector(".unit").textContent = unitPrice(p);
  if (p.cheaper_at) {
    const x = p.cheaper_at;
    c.querySelector(".cmp").textContent =
      `Cheaper at ${x.store}: ${x.unit_price ? `${gbp(x.unit_price)}/${x.unit}` : gbp(x.price)}${x.loyalty ? ` (${LOYALTY[x.store] || "card"})` : ""}`;
  }

  const add = c.querySelector(".add");
  const sync = () => { const inList = !!state.list[p.id]; add.classList.toggle("in", inList); add.textContent = inList ? "✓" : "+"; };
  add.onclick = () => { state.list[p.id] ? delete state.list[p.id] : (state.list[p.id] = { qty: 1, p }); saveList(); sync(); };
  sync();
  return c;
}

const grid = (items) => { const g = el("div", "grid"); items.forEach((p) => g.append(card(p))); return g; };

// ---------- "My shop": your regular items, cheapest first across shops ----------
function rankByValue(items) {
  // Compare like with like: use the most common unit (£/kg or £/l), others after.
  const counts = {};
  for (const p of items) if (p.unit_price) counts[p.unit] = (counts[p.unit] || 0) + 1;
  const unit = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
  const score = (p) => (p.unit_price && p.unit === unit ? p.unit_price : 1e6 + p.price);
  return [...items].sort((a, b) => score(a) - score(b));
}

function renderMine() {
  const root = $("#mine");
  root.replaceChildren();
  const pool = state.products.filter(visible);
  for (const fav of state.favourites) {
    const yes = new RegExp(fav.match, "i");
    const no = fav.exclude ? new RegExp(fav.exclude, "i") : null;
    const items = rankByValue(pool.filter((p) => yes.test(p.name) && !(no && no.test(p.name))));

    const box = el("section", "fav");
    const head = el("div", "fav-head");
    head.append(el("h2", null, fav.name));
    if (fav.why) head.append(el("small", null, fav.why));
    box.append(head);

    // One line per shop: its best option, cheapest shop highlighted.
    const shops = el("div", "shop-sum");
    for (const store of [...state.stores].sort()) {
      const best = items.find((p) => p.store === store);
      const s = el("span", "shop" + (best && best === items[0] ? " win" : best ? "" : " none"));
      s.textContent = best ? `${store} ${unitPrice(best) || gbp(best.price)}` : `${store}: not listed`;
      shops.append(s);
    }
    box.append(shops);

    if (!items.length) { box.append(el("p", "empty", "No prices for this yet.")); root.append(box); continue; }
    const g = grid(items.slice(0, 3));
    box.append(g);
    if (items.length > 3) {
      const more = el("button", "more", `Show all ${items.length}`);
      more.onclick = () => { items.slice(3).forEach((p) => g.append(card(p))); more.remove(); };
      box.append(more);
    }
    root.append(box);
  }
}

// ---------- "All deals": browse everything by category ----------
function renderAll() {
  const q = $("#search").value.trim().toLowerCase();
  const cat = $("#category").value;
  const items = state.products.filter((p) =>
    visible(p) && state.efforts.has(p.effort) &&
    (!cat || p.category === cat) &&
    (!$("#offersOnly").checked || p.on_offer) &&
    (!$("#hideDearer").checked || !p.cheaper_at) &&
    (!q || (p.name + " " + p.category).toLowerCase().includes(q)));

  const deals = $("#deals");
  deals.replaceChildren();
  const top = items.filter((p) => p.saving_pct && p.effort !== "cook").sort(sorters.saving).slice(0, 8);
  if (top.length && !q) deals.append(el("h2", null, "🔥 Best low-effort deals right now"), grid(top));

  const res = $("#results");
  res.replaceChildren();
  if (!items.length) { res.append(el("p", "empty", "Nothing matches — try ticking more filters.")); return; }
  const groups = {};
  for (const p of items) (groups[p.category] ||= []).push(p);
  const offers = (cat) => groups[cat].filter((p) => p.on_offer).length;
  const order = Object.keys(groups).sort((a, b) => offers(b) - offers(a) || a.localeCompare(b));
  for (const cat of order) {
    const list = groups[cat].sort(sorters[$("#sort").value]);
    const h = el("h2", "cat");
    h.append(el("span", null, cat), el("small", null, `${list.length} items${offers(cat) ? ` · ${offers(cat)} on offer` : ""}`));
    res.append(h, grid(list));
  }
}

function render() {
  document.body.dataset.view = state.view;
  for (const b of document.querySelectorAll(".tabs button")) b.setAttribute("aria-pressed", b.dataset.view === state.view);
  state.view === "mine" ? renderMine() : renderAll();
}

// ---------- shopping list ----------
function saveList() { localStorage.setItem("list", JSON.stringify(state.list)); renderList(); }

function renderList() {
  const entries = Object.entries(state.list);
  $("#listCount").textContent = entries.length;
  const body = $("#listBody");
  body.replaceChildren();
  if (!entries.length) { body.append(el("p", "empty", "Tap + on anything to add it here.")); return; }
  const byStore = {};
  for (const [id, e] of entries) (byStore[e.p.store] ||= []).push([id, e]);
  let total = 0, saved = 0;
  for (const store of Object.keys(byStore).sort()) {
    const head = el("div", "store-total");
    body.append(head);
    let sub = 0;
    for (const [id, { qty, p }] of byStore[store]) {
      sub += p.price * qty; saved += (p.saving || 0) * qty;
      const minus = el("button", null, "−");
      minus.onclick = () => { if (--state.list[id].qty <= 0) delete state.list[id]; saveList(); render(); };
      const plus = el("button", null, "+");
      plus.onclick = () => { state.list[id].qty++; saveList(); };
      const right = el("span");
      right.append(gbp(p.price * qty) + " ", minus, plus);
      const row = el("div", "li");
      row.append(el("span", null, `${qty}× ${p.name}`), right);
      body.append(row);
    }
    head.append(el("span", null, store), el("span", null, gbp(sub)));
    total += sub;
  }
  const g = el("div", "grand");
  g.append(el("span", null, "Total"), el("span", null, gbp(total)));
  body.append(g);
  if (saved) body.append(el("div", "saved", `You're saving about ${gbp(saved)} with offers`));
}

$("#listBtn").onclick = () => { $("#drawer").hidden = false; };
$("#closeList").onclick = () => { $("#drawer").hidden = true; };
$("#clearList").onclick = () => { if (confirm("Clear the shopping list?")) { state.list = {}; saveList(); render(); } };
$("#copyList").onclick = async () => {
  const lines = Object.values(state.list).map(({ qty, p }) => `${qty}x ${p.name} (${p.store}) ${gbp(p.price * qty)}`);
  await navigator.clipboard.writeText(lines.join("\n"));
  $("#copyList").textContent = "Copied!"; setTimeout(() => ($("#copyList").textContent = "Copy list"), 1500);
};

// ---------- start ----------
Promise.all([
  fetch("data/prices.json", { cache: "no-cache" }).then((r) => r.json()),
  fetch("favourites.json", { cache: "no-cache" }).then((r) => r.json()),
])
  .then(([data, favourites]) => {
    state.products = data.products;
    state.favourites = favourites;
    // refresh list items with today's prices; drop ones no longer sold
    const byId = Object.fromEntries(data.products.map((p) => [p.id, p]));
    for (const id of Object.keys(state.list)) {
      if (byId[id]) state.list[id].p = byId[id]; else if (!state.list[id].p.manual) delete state.list[id];
    }
    localStorage.setItem("list", JSON.stringify(state.list));

    const when = new Date(data.generated_at).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const meta = $("#meta");
    meta.textContent = `Updated ${when} · ${data.products.length} products`;
    for (const [name, s] of Object.entries(data.sources)) {
      const span = el("span", s.ok ? null : "bad",
        ` · ${name === "Manual" ? "Tesco & M&S (checked in browser)" : name}: ${s.ok ? s.count : "failed, showing old data"}`);
      meta.append(span);
    }
    buildFilters(); render(); renderList();
  })
  .catch((e) => { $("#meta").textContent = "Couldn't load prices: " + e; });
