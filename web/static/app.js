const state = {
  q: "",
  city: "",
  category: "",
  industry: "",
  has_website: false,
  has_email: false,
  has_phone: false,
  has_kvk: false,
  sort: "name",
  page: 1,
  pages: 1,
  total: 0,
  skipMove: false,
};

const CAT_COLORS = {
  shop: "#b84a1f",
  office: "#2f4f4b",
  food: "#c47a2c",
  health: "#5a6b3f",
  stay: "#6b4a6b",
  craft: "#8a5a32",
  mobility: "#3d5a80",
  amenity: "#4a5560",
  other: "#6b6458",
};

const NL_BOUNDS = [[50.75, 3.2], [53.7, 7.3]];
const $ = (id) => document.getElementById(id);

function qs() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.city) p.set("city", state.city);
  if (state.category) p.set("category", state.category);
  if (state.industry) p.set("industry", state.industry);
  if (state.sort) p.set("sort", state.sort);
  for (const f of ["has_website", "has_email", "has_phone", "has_kvk"]) {
    if (state[f]) p.set(f, "true");
  }
  return p;
}

let map, cluster, debounceTimer, mapTimer, cityTimer, filterSeq = 0;

function pinIcon(cat) {
  const c = CAT_COLORS[cat] || CAT_COLORS.other;
  return L.divIcon({
    className: "hk-pin",
    html: `<span style="display:block;width:12px;height:12px;border-radius:50%;background:${c};border:2px solid #f8f1e2;box-shadow:0 1px 4px rgba(0,0,0,.35)"></span>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function fmt(n) {
  return new Intl.NumberFormat("nl-NL").format(n);
}

function initMap() {
  if (typeof L === "undefined") {
    $("hint").classList.remove("hidden");
    $("hint").textContent = "Leaflet failed to load.";
    return;
  }
  map = L.map("map", {
    zoomControl: true,
    minZoom: 6,
    maxZoom: 18,
    maxBounds: [
      [49.4, 2.5],
      [54.2, 8.2],
    ],
    maxBoundsViscosity: 0.8,
  });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);
  cluster = L.markerClusterGroup({
    maxClusterRadius: 52,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true,
    disableClusteringAtZoom: 16,
  });
  map.addLayer(cluster);
  const ready = () => {
    state.skipMove = true;
    map.invalidateSize({ animate: false });
    map.fitBounds(NL_BOUNDS, { padding: [20, 20], maxZoom: 8, animate: false });
    setTimeout(() => {
      state.skipMove = false;
      loadPoints();
    }, 80);
  };
  requestAnimationFrame(ready);
  setTimeout(ready, 200);
  map.on("moveend", () => {
    if (state.skipMove) return;
    clearTimeout(mapTimer);
    mapTimer = setTimeout(loadPoints, 250);
  });
  window.addEventListener("resize", () => map.invalidateSize({ animate: false }));
}

async function boot() {
  initMap();
  const stats = await (await fetch("/api/stats")).json();
  const cat = $("category");
  for (const c of stats.categories) {
    const o = document.createElement("option");
    o.value = c.id;
    o.textContent = c.label;
    cat.append(o);
  }
  await loadIndustries();

  $("q").addEventListener("input", onQuery);
  $("category").addEventListener("change", async () => {
    state.category = $("category").value;
    state.industry = "";
    state.page = 1;
    await loadIndustries();
    refresh({ fit: true });
  });
  $("industry").addEventListener("change", () => {
    state.industry = $("industry").value;
    state.page = 1;
    refresh({ fit: true });
  });
  $("sort").addEventListener("change", () => {
    state.sort = $("sort").value;
    state.page = 1;
    loadList();
  });
  $("city").addEventListener("input", onCityInput);
  $("city").addEventListener("focus", onCityInput);
  $("city").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      pickCity($("city").value.trim());
    }
    if (e.key === "Escape") hideSuggest();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".city-field")) hideSuggest();
  });
  document.querySelector(".must").addEventListener("change", (e) => {
    const box = e.target.closest("input[data-flag]");
    if (!box) return;
    state[box.dataset.flag] = box.checked;
    state.page = 1;
    refresh({ fit: true });
  });
  $("reset").onclick = resetFilters;
  $("prev").onclick = () => {
    if (state.page > 1) {
      state.page -= 1;
      loadList();
    }
  };
  $("next").onclick = () => {
    if (state.page < state.pages) {
      state.page += 1;
      loadList();
    }
  };
  $("export").onclick = () => {
    location.href = `/api/export?${qs().toString()}`;
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "SELECT") {
      e.preventDefault();
      $("q").focus();
    }
    if (e.key === "Escape") $("detail").classList.add("hidden");
  });

  $("count").textContent = `${fmt(stats.total)} companies`;
  loadList();
}

function resetFilters() {
  state.q = state.city = state.category = state.industry = "";
  state.has_website = state.has_email = state.has_phone = state.has_kvk = false;
  state.sort = "name";
  state.page = 1;
  $("q").value = "";
  $("city").value = "";
  $("category").value = "";
  $("industry").value = "";
  $("sort").value = "name";
  for (const box of document.querySelectorAll(".must input")) box.checked = false;
  hideSuggest();
  loadIndustries().then(() => {
    if (map) map.fitBounds(NL_BOUNDS, { padding: [12, 12] });
    refresh();
  });
}

async function loadIndustries() {
  const p = state.category ? `?category=${encodeURIComponent(state.category)}` : "";
  const items = await (await fetch(`/api/industries${p}`)).json();
  $("industry").innerHTML =
    `<option value="">All types</option>` +
    items.map((i) => `<option value="${esc(i.id)}">${esc(i.label)} · ${fmt(i.n)}</option>`).join("");
  if (state.industry) $("industry").value = state.industry;
}

function onQuery() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    state.q = $("q").value.trim();
    state.page = 1;
    refresh({ fit: true });
  }, 220);
}

function onCityInput() {
  clearTimeout(cityTimer);
  cityTimer = setTimeout(async () => {
    const q = $("city").value.trim();
    if (q.length < 1) {
      hideSuggest();
      if (state.city) {
        state.city = "";
        state.page = 1;
        refresh({ fit: true });
      }
      return;
    }
    const items = await (await fetch(`/api/cities?q=${encodeURIComponent(q)}`)).json();
    const box = $("city-suggest");
    if (!items.length) {
      hideSuggest();
      return;
    }
    box.classList.remove("hidden");
    box.innerHTML = items
      .map((c) => `<li data-city="${esc(c.name)}"><span>${esc(c.name)}</span><span class="n">${fmt(c.n)}</span></li>`)
      .join("");
    for (const li of box.querySelectorAll("li")) {
      li.onclick = () => pickCity(li.dataset.city);
    }
  }, 140);
}

function pickCity(name) {
  state.city = name;
  $("city").value = name;
  hideSuggest();
  state.page = 1;
  refresh({ fit: true });
}

function hideSuggest() {
  $("city-suggest").classList.add("hidden");
}

function refresh(opts = {}) {
  loadList();
  if (opts.fit) fitThenPoints();
  else loadPoints();
}

async function fitThenPoints() {
  if (!map) return;
  const data = await (await fetch(`/api/bounds?${qs()}`)).json();
  if (!data.empty && data.south != null) {
    state.skipMove = true;
    map.fitBounds(
      [
        [data.south, data.west],
        [data.north, data.east],
      ],
      { padding: [40, 40], maxZoom: 14 }
    );
    map.invalidateSize({ animate: false });
    setTimeout(() => {
      state.skipMove = false;
      loadPoints();
    }, 200);
  } else {
    loadPoints();
  }
}

async function loadList() {
  const p = qs();
  p.set("page", String(state.page));
  p.set("limit", "24");
  const data = await (await fetch(`/api/search?${p}`)).json();
  state.total = data.total;
  state.pages = data.pages || 1;
  $("count").textContent = `${fmt(data.total)} matches`;
  $("page").textContent = data.pages ? `${data.page} / ${data.pages}` : "";
  $("prev").disabled = data.page <= 1;
  $("next").disabled = data.page >= data.pages;
  $("results").innerHTML = data.results.map(cardHtml).join("") || `<p class="sub">Nothing in this cut.</p>`;
  for (const el of $("results").querySelectorAll(".card")) {
    el.onclick = () => openCompany(+el.dataset.id, true);
  }
}

function cardHtml(r) {
  const bits = [];
  if (r.website) bits.push("<span>Web</span>");
  if (r.general_email) bits.push("<span>Mail</span>");
  if (r.phone) bits.push("<span>Tel</span>");
  if (r.kvk_number) bits.push("<span>KVK</span>");
  return `<button class="card" data-id="${r.id}">
    <h3>${esc(r.company_name)}</h3>
    <p class="sub">${esc(r.industry_label || "—")}${r.city ? " · " + esc(r.city) : ""}</p>
    <div class="badges">${bits.join("")}</div>
  </button>`;
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

async function loadPoints() {
  if (!map || !cluster) return;
  const seq = ++filterSeq;
  const b = map.getBounds();
  const p = qs();
  p.set("bbox", `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`);
  const data = await (await fetch(`/api/points?${p}`)).json();
  if (seq !== filterSeq) return;
  cluster.clearLayers();
  const layers = [];
  for (const pt of data.points) {
    if (pt.lat == null || pt.lon == null) continue;
    const m = L.marker([pt.lat, pt.lon], { icon: pinIcon(pt.category), title: pt.name });
    m.on("click", () => openCompany(pt.id, false));
    layers.push(m);
  }
  cluster.addLayers(layers);
  const hint = $("hint");
  if (data.truncated) {
    hint.classList.remove("hidden");
    hint.textContent = "Zoom in — this view is sampled.";
  } else if (!layers.length) {
    hint.classList.remove("hidden");
    hint.textContent = "No mapped points in this view.";
  } else {
    hint.classList.add("hidden");
  }
}

async function openCompany(id, fly) {
  const r = await (await fetch(`/api/company/${id}`)).json();
  const d = $("detail");
  d.classList.remove("hidden");
  d.innerHTML = `
    <button class="close" aria-label="Close">×</button>
    <h2>${esc(r.company_name)}</h2>
    <p class="sub">${esc(r.industry_label || "")} ${r.city ? "· " + esc(r.city) : ""}</p>
    <dl>
      ${row("Address", r.business_address)}
      ${row("Website", r.website ? `<a href="${esc(r.website)}" target="_blank" rel="noopener">${esc(r.website)}</a>` : "")}
      ${row("Email", r.general_email ? `<a href="mailto:${esc(r.general_email)}">${esc(r.general_email)}</a>` : "")}
      ${row("Phone", r.phone ? `<a href="tel:${esc(r.phone)}">${esc(r.phone)}</a>` : "")}
      ${row("KVK", r.kvk_number)}
      ${row("Source", r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">OpenStreetMap</a>` : "")}
      ${row("Checked", r.verification_date)}
    </dl>
  `;
  d.querySelector(".close").onclick = () => d.classList.add("hidden");
  for (const el of $("results").querySelectorAll(".card")) {
    el.classList.toggle("active", +el.dataset.id === id);
  }
  if (fly && r.lat && r.lon && map) {
    state.skipMove = true;
    map.setView([r.lat, r.lon], Math.max(map.getZoom(), 15), { animate: true });
    setTimeout(() => {
      state.skipMove = false;
      loadPoints();
    }, 280);
  }
}

function row(label, value) {
  if (!value) return "";
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

boot().catch((err) => {
  $("count").textContent = "Failed to load";
  console.error(err);
});
