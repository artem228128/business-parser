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

const INDUSTRY_RU = {
  "amenity:restaurant": "ресторан",
  "office:company": "компания",
  "shop:clothes": "одежда",
  "amenity:fast_food": "фастфуд",
  "shop:hairdresser": "парикмахерская",
  "amenity:cafe": "кафе",
  "shop:supermarket": "супермаркет",
  "amenity:fuel": "АЗС",
  "amenity:pub": "паб",
  "shop:bakery": "пекарня",
  "shop:car_repair": "автосервис",
  "shop:bicycle": "велосипеды",
  "shop:car": "автомобили",
  "tourism:hotel": "отель",
  "amenity:doctors": "врачи",
  "amenity:dentist": "стоматолог",
  "shop:chemist": "бытовая химия",
  "shop:beauty": "красота",
  "shop:convenience": "минимаркет",
  "tourism:guest_house": "гостевой дом",
  "shop:optician": "оптика",
  "shop:furniture": "мебель",
  "shop:florist": "цветы",
  "shop:shoes": "обувь",
  "amenity:pharmacy": "аптека",
  "shop:butcher": "мясная",
  "shop:jewelry": "ювелирные",
  "amenity:bar": "бар",
  "office:yes": "офис",
  "office:estate_agent": "недвижимость",
  "shop:gift": "подарки",
  "shop:alcohol": "алкоголь",
  "shop:books": "книги",
  "shop:doityourself": "стройтовары",
  "shop:interior_decoration": "интерьер",
  "shop:second_hand": "секонд-хенд",
  "amenity:car_wash": "автомойка",
  "shop:garden_centre": "садовый центр",
  "shop:pet": "зоотовары",
  "shop:variety_store": "товары для дома",
  "shop:electronics": "электроника",
  "shop:mobile_phone": "телефоны",
  "amenity:veterinary": "ветеринар",
  "shop:newsagent": "пресса",
  "amenity:theatre": "театр",
  "shop:sports": "спорттовары",
  "shop:kitchen": "кухни",
  "office:it": "IT",
  "shop:department_store": "универмаг",
  "shop:trade": "торговля",
  "shop:seafood": "морепродукты",
  "office:employment_agency": "кадры",
  "amenity:clinic": "клиника",
  "shop:cheese": "сыр",
  "shop:toys": "игрушки",
  "shop:houseware": "товары для дома",
  "shop:greengrocer": "овощи и фрукты",
  "shop:farm": "ферма",
  "office:educational_institution": "образование",
  "amenity:bank": "банк",
  "shop:bed": "кровати",
  "shop:massage": "массаж",
  "shop:wholesale": "опт",
  "shop:deli": "деликатесы",
  "office:lawyer": "юрист",
  "shop:pastry": "кондитерская",
  "shop:hardware": "скобяные товары",
  "shop:tattoo": "тату",
  "shop:travel_agency": "турагентство",
  "shop:yes": "магазин",
  "shop:cannabis": "каннабис",
  "amenity:car_rental": "прокат авто",
  "shop:tailor": "ателье",
  "shop:computer": "компьютеры",
  "shop:art": "искусство",
  "shop:hearing_aids": "слуховые аппараты",
  "shop:perfumery": "парфюмерия",
  "shop:car_parts": "автозапчасти",
  "shop:telecommunication": "связь",
  "shop:tobacco": "табак",
};

const I18N = {
  en: {
    kicker: "Open register · OSM",
    search: "Search",
    searchPh: "Name, street, industry…",
    category: "Category",
    type: "Type",
    city: "City",
    cityPh: "Start typing a city",
    sort: "Sort",
    sortName: "Name A–Z",
    sortContacts: "Most complete contacts",
    sortCity: "City A–Z",
    sortIndustry: "Type A–Z",
    must: "Must have",
    website: "Website",
    email: "Email",
    phone: "Phone",
    kvk: "KVK number",
    loading: "Loading atlas…",
    companies: "{n} companies",
    matches: "{n} matches",
    reset: "Reset",
    prev: "Prev",
    next: "Next",
    viewList: "List",
    viewMap: "Map",
    empty: "Nothing in this cut.",
    failed: "Failed to load",
    leaflet: "Leaflet failed to load.",
    zoom: "Zoom in — this view is sampled.",
    noPoints: "No mapped points in this view.",
    web: "Web",
    mail: "Mail",
    tel: "Tel",
    address: "Address",
    source: "Source",
    checked: "Checked",
    close: "Close",
    osm: "OpenStreetMap",
    cat_shop: "Shops",
    cat_office: "Offices",
    cat_food: "Food & drink",
    cat_health: "Health",
    cat_stay: "Stay",
    cat_craft: "Craft",
    cat_mobility: "Mobility",
    cat_amenity: "Services",
    cat_other: "Other",
    allCategories: "All categories",
    allTypes: "All types",
    title: "Handelskaart — Dutch businesses",
  },
  ru: {
    kicker: "Открытый реестр · OSM",
    search: "Поиск",
    searchPh: "Название, улица, отрасль…",
    category: "Категория",
    type: "Тип",
    city: "Город",
    cityPh: "Начните вводить город",
    sort: "Сортировка",
    sortName: "Имя А–Я",
    sortContacts: "Сначала с контактами",
    sortCity: "Город А–Я",
    sortIndustry: "Тип А–Я",
    must: "Обязательно",
    website: "Сайт",
    email: "Почта",
    phone: "Телефон",
    kvk: "Номер KVK",
    loading: "Загрузка…",
    companies: "{n} компаний",
    matches: "{n} найдено",
    reset: "Сброс",
    prev: "Назад",
    next: "Дальше",
    viewList: "Список",
    viewMap: "Карта",
    empty: "Ничего не нашлось.",
    failed: "Не удалось загрузить",
    leaflet: "Карта не загрузилась.",
    zoom: "Приблизьте карту — показана часть точек.",
    noPoints: "В этой области нет точек.",
    web: "Сайт",
    mail: "Почта",
    tel: "Тел",
    address: "Адрес",
    source: "Источник",
    checked: "Проверено",
    close: "Закрыть",
    osm: "OpenStreetMap",
    cat_shop: "Магазины",
    cat_office: "Офисы",
    cat_food: "Еда и напитки",
    cat_health: "Медицина",
    cat_stay: "Жильё",
    cat_craft: "Ремесло",
    cat_mobility: "Транспорт",
    cat_amenity: "Услуги",
    cat_other: "Другое",
    allCategories: "Все категории",
    allTypes: "Все типы",
    title: "Handelskaart — компании Нидерландов",
  },
};

let lang = localStorage.getItem("hk-lang") || (navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en");
if (!I18N[lang]) lang = "en";
let statsCache = null;
let industryCache = { city: null, items: null };
let lastResults = [];
let lastCompany = null;
let hintMode = "hidden";
let countMode = "loading";

function t(key, vars) {
  let s = (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  }
  return s;
}

const KIND_NAME = {
  shop: { en: "Shop", ru: "Магазин" },
  office: { en: "Office", ru: "Офис" },
  craft: { en: "Craft", ru: "Ремесло" },
  tourism: { en: "Stay", ru: "Жильё" },
  amenity: { en: "Service", ru: "Услуга" },
};
const CAT_ORDER = ["shop", "office", "food", "health", "stay", "craft", "mobility", "amenity", "other"];

function titleCase(s) {
  if (!s) return "";
  const locale = lang === "ru" ? "ru" : "en";
  return s.replace(/\p{L}+/gu, (word) => word.charAt(0).toLocaleUpperCase(locale) + word.slice(1));
}

function industryName(id, label) {
  const value = (id || "").split(":")[1] || "";
  const kind = (id || "").split(":")[0];
  if (value === "yes" || value === "no") {
    const names = KIND_NAME[kind];
    if (names) return names[lang] || names.en;
  }
  if (id === "office:it") return "IT";
  if (id === "shop:hifi") return "Hi-Fi";
  const name = lang === "ru" && INDUSTRY_RU[id] ? INDUSTRY_RU[id] : label || "";
  return titleCase(name);
}

function applyChrome() {
  document.documentElement.lang = lang;
  document.title = t("title");
  for (const el of document.querySelectorAll("[data-i18n]")) {
    el.textContent = t(el.dataset.i18n);
  }
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  }
  for (const btn of document.querySelectorAll(".lang button")) {
    btn.classList.toggle("on", btn.dataset.lang === lang);
    btn.setAttribute("aria-pressed", btn.dataset.lang === lang ? "true" : "false");
  }
  fillCategories();
  paintCount();
  paintHint();
  if (lastResults.length || $("results").childElementCount) paintResults();
  if (lastCompany) paintDetail(lastCompany);
}

function fillCategories() {
  const sel = $("category");
  if (!sel || !statsCache) return;
  const current = state.category || sel.value;
  let cats = statsCache.categories;
  if (state.city && industryCache.items) {
    const present = new Set(industryCache.items.map((i) => i.category));
    cats = cats.filter((c) => present.has(c.id));
  }
  sel.innerHTML =
    `<option value="">${esc(t("allCategories"))}</option>` +
    cats.map((c) => `<option value="${esc(c.id)}">${esc(t("cat_" + c.id))}</option>`).join("");
  sel.value = cats.some((c) => c.id === current) ? current : "";
  state.category = sel.value;
}

function paintCount() {
  const el = $("count");
  if (!el) return;
  if (countMode === "loading") el.textContent = t("loading");
  else if (countMode === "failed") el.textContent = t("failed");
  else if (countMode === "companies") el.textContent = t("companies", { n: fmt(statsCache?.total || 0) });
  else el.textContent = t("matches", { n: fmt(state.total) });
}

function paintHint() {
  const hint = $("hint");
  if (!hint) return;
  if (hintMode === "zoom") {
    hint.classList.remove("hidden");
    hint.textContent = t("zoom");
  } else if (hintMode === "empty") {
    hint.classList.remove("hidden");
    hint.textContent = t("noPoints");
  } else {
    hint.classList.add("hidden");
  }
}

function setView(view) {
  const mapMode = view === "map";
  const cold = mapMode && map && map.getSize().x === 0;
  document.body.classList.toggle("view-map", mapMode);
  for (const btn of document.querySelectorAll(".viewbar button")) {
    btn.classList.toggle("on", btn.dataset.view === (mapMode ? "map" : "list"));
  }
  if (!map || !mapMode) return;
  requestAnimationFrame(() => {
    map.invalidateSize({ animate: false });
    if (cold) map.fitBounds(NL_BOUNDS, { padding: [20, 20], maxZoom: 8, animate: false });
  });
}

function setLang(next) {
  if (!I18N[next] || next === lang) return;
  lang = next;
  localStorage.setItem("hk-lang", lang);
  loadIndustries().then(applyChrome);
}

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
  return new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-GB").format(n);
}

function initMap() {
  if (typeof L === "undefined") {
    hintMode = "empty";
    $("hint").classList.remove("hidden");
    $("hint").textContent = t("leaflet");
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
  statsCache = await (await fetch("/api/stats")).json();
  applyChrome();
  await loadIndustries();
  document.querySelector(".lang").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang]");
    if (btn) setLang(btn.dataset.lang);
  });
  document.querySelector(".viewbar").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-view]");
    if (btn) setView(btn.dataset.view);
  });

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

  countMode = "companies";
  paintCount();
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

function typeOption(i) {
  return `<option value="${esc(i.id)}">${esc(industryName(i.id, i.label))} · ${fmt(i.n)}</option>`;
}

async function loadIndustries() {
  const city = state.city || "";
  if (industryCache.city !== city || !industryCache.items) {
    const p = city ? `?city=${encodeURIComponent(city)}` : "";
    industryCache = { city, items: await (await fetch(`/api/industries${p}`)).json() };
  }
  fillCategories();
  const items = state.category
    ? industryCache.items.filter((i) => i.category === state.category)
    : industryCache.items;
  if (state.industry && !items.some((i) => i.id === state.industry)) state.industry = "";
  let html = `<option value="">${esc(t("allTypes"))}</option>`;
  if (state.category) {
    html += items.map(typeOption).join("");
  } else {
    const groups = {};
    for (const item of items) {
      const key = item.category || "other";
      (groups[key] ||= []).push(item);
    }
    for (const cat of CAT_ORDER) {
      const list = groups[cat];
      if (!list || !list.length) continue;
      html += `<optgroup label="${esc(t("cat_" + cat))}">${list.map(typeOption).join("")}</optgroup>`;
    }
  }
  $("industry").innerHTML = html;
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
        state.industry = "";
        state.page = 1;
        industryCache = { city: null, items: null };
        loadIndustries().then(() => refresh({ fit: true }));
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
  if (industryCache.city !== name) industryCache = { city: null, items: null };
  loadIndustries().then(() => refresh({ fit: true }));
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
  countMode = "matches";
  paintCount();
  $("page").textContent = data.pages ? `${data.page} / ${data.pages}` : "";
  $("prev").disabled = data.page <= 1;
  $("next").disabled = data.page >= data.pages;
  lastResults = data.results;
  paintResults();
}

function paintResults() {
  $("results").innerHTML = lastResults.map(cardHtml).join("") || `<p class="sub">${esc(t("empty"))}</p>`;
  for (const el of $("results").querySelectorAll(".card")) {
    el.onclick = () => openCompany(+el.dataset.id, true);
    el.classList.toggle("active", lastCompany && +el.dataset.id === lastCompany.id);
  }
}

function cardHtml(r) {
  const bits = [];
  if (r.website) bits.push(`<span>${esc(t("web"))}</span>`);
  if (r.general_email) bits.push(`<span>${esc(t("mail"))}</span>`);
  if (r.phone) bits.push(`<span>${esc(t("tel"))}</span>`);
  if (r.kvk_number) bits.push("<span>KVK</span>");
  return `<button class="card" data-id="${r.id}">
    <h3>${esc(r.company_name)}</h3>
    <p class="sub">${esc(industryName(r.industry, r.industry_label) || "—")}${r.city ? " · " + esc(r.city) : ""}</p>
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
  if (data.truncated) hintMode = "zoom";
  else if (!layers.length) hintMode = "empty";
  else hintMode = "hidden";
  paintHint();
}

async function openCompany(id, fly) {
  const r = await (await fetch(`/api/company/${id}`)).json();
  lastCompany = r;
  paintDetail(r);
  if (fly && r.lat && r.lon && map) {
    if (window.matchMedia("(max-width: 800px)").matches) setView("map");
    state.skipMove = true;
    requestAnimationFrame(() => {
      map.invalidateSize({ animate: false });
      map.setView([r.lat, r.lon], Math.max(map.getZoom(), 15), { animate: false });
      setTimeout(() => {
        state.skipMove = false;
        loadPoints();
      }, 280);
    });
  }
}

function paintDetail(r) {
  const d = $("detail");
  d.classList.remove("hidden");
  d.innerHTML = `
    <button class="close" aria-label="${esc(t("close"))}">×</button>
    <h2>${esc(r.company_name)}</h2>
    <p class="sub">${esc(industryName(r.industry, r.industry_label))} ${r.city ? "· " + esc(r.city) : ""}</p>
    <dl>
      ${row(t("address"), r.business_address)}
      ${row(t("website"), r.website ? `<a href="${esc(r.website)}" target="_blank" rel="noopener">${esc(r.website)}</a>` : "")}
      ${row(t("email"), r.general_email ? `<a href="mailto:${esc(r.general_email)}">${esc(r.general_email)}</a>` : "")}
      ${row(t("phone"), r.phone ? `<a href="tel:${esc(r.phone)}">${esc(r.phone)}</a>` : "")}
      ${row("KVK", r.kvk_number)}
      ${row(t("source"), r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(t("osm"))}</a>` : "")}
      ${row(t("checked"), r.verification_date)}
    </dl>
  `;
  d.querySelector(".close").onclick = () => {
    d.classList.add("hidden");
    lastCompany = null;
  };
  for (const el of $("results").querySelectorAll(".card")) {
    el.classList.toggle("active", +el.dataset.id === r.id);
  }
}

function row(label, value) {
  if (!value) return "";
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

boot().catch((err) => {
  countMode = "failed";
  paintCount();
  console.error(err);
});
