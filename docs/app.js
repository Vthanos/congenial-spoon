// Scrappy front end: plain JS, no build step, works on GitHub Pages.
const EFFORTS = [
  ["no-cook", "No cook"], ["heat-only", "Just heat"], ["cook", "Cooking"], ["drink", "Drinks"],
];
const state = {
  products: [],
  efforts: new Set(JSON.parse(localStorage.getItem("efforts") || '["no-cook","heat-only","drink"]')),
  stores: new Set(),
  list: JSON.parse(localStorage.getItem("list") || "{}"), // id -> {qty, product snapshot}
};
const $ = (s) => document.querySelector(s);
const gbp = (n) => (n < 1 ? Math.round(n * 100) + "p" : "£" + n.toFixed(2));

function chip(label, pressed, onClick) {
  const b = document.createElement("button");
  b.className = "chip";
  b.textContent = label;
  b.setAttribute("aria-pressed", pressed);
  b.onclick = () => { onClick(); b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true"); render(); };
  return b;
}

function buildFilters() {
  const ec = $("#effortChips");
  for (const [key, label] of EFFORTS) {
    ec.append(chip(label, state.efforts.has(key), () => {
      state.efforts.has(key) ? state.efforts.delete(key) : state.efforts.add(key);
      localStorage.setItem("efforts", JSON.stringify([...state.efforts]));
    }));
  }
  const stores = [...new Set(state.products.map((p) => p.store))].sort();
  stores.forEach((s) => state.stores.add(s));
  const sc = $("#storeChips");
  for (const s of stores) {
    sc.append(chip(s, true, () => (state.stores.has(s) ? state.stores.delete(s) : state.stores.add(s))));
  }
  const cats = [...new Set(state.products.map((p) => p.category))].sort();
  for (const c of cats) $("#category").append(new Option(c, c));
  for (const id of ["#search", "#category", "#sort", "#offersOnly", "#hideLoyalty"]) {
    $(id).addEventListener("input", render);
  }
}

function filtered() {
  const q = $("#search").value.trim().toLowerCase();
  const cat = $("#category").value;
  const offers = $("#offersOnly").checked;
  const noLoyalty = $("#hideLoyalty").checked;
  return state.products.filter((p) =>
    state.efforts.has(p.effort) && state.stores.has(p.store) &&
    (!cat || p.category === cat) && (!offers || p.on_offer) && (!noLoyalty || !p.loyalty) &&
    (!q || (p.name + " " + p.category).toLowerCase().includes(q)));
}

const sorters = {
  saving: (a, b) => (b.saving_pct || 0) - (a.saving_pct || 0) || a.price - b.price,
  price: (a, b) => a.price - b.price,
  unit: (a, b) => (a.unit_price ?? 1e9) - (b.unit_price ?? 1e9),
  name: (a, b) => a.name.localeCompare(b.name),
};

function card(p) {
  const el = $("#cardTpl").content.firstElementChild.cloneNode(true);
  const img = el.querySelector("img");
  if (p.image) img.src = p.image; else img.removeAttribute("src");
  const h = el.querySelector("h3");
  if (p.url) { const a = document.createElement("a"); a.href = p.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = p.name; h.append(a); }
  else h.textContent = p.name;
  const badges = el.querySelector(".badges");
  const badge = (text, cls) => { const s = document.createElement("span"); s.className = "badge " + cls; s.textContent = text; badges.append(s); };
  badge(p.store, "store");
  if (p.saving_pct) badge(`-${p.saving_pct}%`, "save");
  if (p.loyalty) badge(p.store === "Lidl" ? "Lidl Plus" : p.store === "Tesco" ? "Clubcard" : "App/card", "plus");
  else if (p.offer && !p.saving_pct) badge(p.offer, "");
  if (p.is_lowest) badge("Lowest we've seen", "low");
  if (p.stale) badge("old data", "stale");
  const sub = [p.pack, p.offer && p.saving_pct ? p.offer : null,
    p.valid_until ? "until " + new Date(p.valid_until).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : null]
    .filter(Boolean).join(" · ");
  el.querySelector(".sub").textContent = sub;
  el.querySelector(".price").textContent = gbp(p.price);
  el.querySelector(".was").textContent = p.was_price ? gbp(p.was_price) : "";
  el.querySelector(".unit").textContent = p.unit_price ? `${gbp(p.unit_price)}/${p.unit}` : (p.unit_text || "");
  const add = el.querySelector(".add");
  const sync = () => { const inList = !!state.list[p.id]; add.classList.toggle("in", inList); add.textContent = inList ? "✓" : "+"; };
  add.onclick = () => { state.list[p.id] ? delete state.list[p.id] : (state.list[p.id] = { qty: 1, p }); saveList(); sync(); };
  sync();
  return el;
}

function render() {
  const items = filtered();
  const sort = sorters[$("#sort").value];

  // Top deals strip: biggest % savings on low-effort food in the current filter.
  const deals = $("#deals");
  deals.replaceChildren();
  const top = items.filter((p) => p.saving_pct && p.effort !== "cook").sort(sorters.saving).slice(0, 8);
  if (top.length && !$("#search").value) {
    const h = document.createElement("h2"); h.textContent = "🔥 Best low-effort deals right now";
    const g = document.createElement("div"); g.className = "grid"; top.forEach((p) => g.append(card(p)));
    deals.append(h, g);
  }

  const groups = {};
  for (const p of items) (groups[p.category] ||= []).push(p);
  const res = $("#results");
  res.replaceChildren();
  if (!items.length) { res.innerHTML = '<p class="empty">Nothing matches — try ticking more filters.</p>'; return; }
  const order = Object.keys(groups).sort((a, b) =>
    groups[b].filter((p) => p.on_offer).length - groups[a].filter((p) => p.on_offer).length || a.localeCompare(b));
  for (const cat of order) {
    const list = groups[cat].sort(sort);
    const h = document.createElement("h2"); h.className = "cat";
    const offers = list.filter((p) => p.on_offer).length;
    h.innerHTML = `<span></span><small>${list.length} items${offers ? ` · ${offers} on offer` : ""}</small>`;
    h.firstChild.textContent = cat;
    const g = document.createElement("div"); g.className = "grid";
    list.forEach((p) => g.append(card(p)));
    res.append(h, g);
  }
}

// ---- shopping list ----
function saveList() { localStorage.setItem("list", JSON.stringify(state.list)); renderList(); }
function renderList() {
  const entries = Object.entries(state.list);
  $("#listCount").textContent = entries.length;
  const body = $("#listBody");
  body.replaceChildren();
  if (!entries.length) { body.innerHTML = '<p class="empty">Tap + on anything to add it here.</p>'; return; }
  const byStore = {};
  for (const [id, e] of entries) (byStore[e.p.store] ||= []).push([id, e]);
  let total = 0, saved = 0;
  for (const store of Object.keys(byStore).sort()) {
    let sub = 0;
    const t = document.createElement("div"); t.className = "store-total";
    body.append(t);
    for (const [id, { qty, p }] of byStore[store]) {
      sub += p.price * qty; saved += (p.saving || 0) * qty;
      const row = document.createElement("div"); row.className = "li";
      const name = document.createElement("span"); name.textContent = `${qty}× ${p.name}`;
      const right = document.createElement("span");
      const minus = document.createElement("button"); minus.textContent = "−";
      minus.onclick = () => { if (--state.list[id].qty <= 0) delete state.list[id]; saveList(); render(); };
      const plus = document.createElement("button"); plus.textContent = "+";
      plus.onclick = () => { state.list[id].qty++; saveList(); };
      right.append(gbp(p.price * qty) + " ", minus, plus);
      row.append(name, right); body.append(row);
    }
    t.innerHTML = `<span></span><span>${gbp(sub)}</span>`; t.firstChild.textContent = store;
    total += sub;
  }
  const g = document.createElement("div"); g.className = "grand";
  g.innerHTML = `<span>Total</span><span>${gbp(total)}</span>`;
  body.append(g);
  if (saved) { const s = document.createElement("div"); s.className = "saved"; s.textContent = `You're saving about ${gbp(saved)} with offers`; body.append(s); }
}

$("#listBtn").onclick = () => { $("#drawer").hidden = false; };
$("#closeList").onclick = () => { $("#drawer").hidden = true; };
$("#clearList").onclick = () => { if (confirm("Clear the shopping list?")) { state.list = {}; saveList(); render(); } };
$("#copyList").onclick = async () => {
  const lines = Object.values(state.list).map(({ qty, p }) => `${qty}x ${p.name} (${p.store}) ${gbp(p.price * qty)}`);
  await navigator.clipboard.writeText(lines.join("\n"));
  $("#copyList").textContent = "Copied!"; setTimeout(() => ($("#copyList").textContent = "Copy list"), 1500);
};

fetch("data/prices.json", { cache: "no-cache" })
  .then((r) => r.json())
  .then((data) => {
    state.products = data.products;
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
      const span = document.createElement("span");
      span.textContent = ` · ${name === "Manual" ? "Your Tesco/M&S deals" : name}: ${s.ok ? s.count : "failed, showing old data"}`;
      if (!s.ok) span.className = "bad";
      meta.append(span);
    }
    buildFilters(); render(); renderList();
  })
  .catch((e) => { $("#meta").textContent = "Couldn't load prices: " + e; });
