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
  public: "#4a3d6b",
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

let industryRu = {};

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
    cat_public: "Government & NGOs",
    cat_food: "Food & drink",
    cat_health: "Health",
    cat_stay: "Stay",
    cat_craft: "Craft",
    cat_mobility: "Mobility",
    cat_amenity: "Services",
    cat_other: "Other",
    allCategories: "All categories",
    allTypes: "All types",
    clear: "Clear",
    selectedHint: "Selected · tap to open",
    onMap: "Shown on map",
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
    cat_public: "Государство и НКО",
    cat_food: "Еда и напитки",
    cat_health: "Медицина",
    cat_stay: "Жильё",
    cat_craft: "Ремесло",
    cat_mobility: "Транспорт",
    cat_amenity: "Услуги",
    cat_other: "Другое",
    allCategories: "Все категории",
    allTypes: "Все типы",
    clear: "Очистить",
    selectedHint: "Выбрано · нажмите для карточки",
    onMap: "На карте",
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
let comboSuppressUntil = 0;

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
const CAT_ORDER = ["shop", "office", "public", "food", "health", "stay", "craft", "mobility", "amenity", "other"];

const COMBO_LISTS = ["category-suggest", "industry-suggest", "city-suggest"];

const PUBLIC_OFFICE_RU = {
  "office:government": "госорган",
  "office:diplomatic": "диппредставительство",
  "office:ngo": "НКО",
  "office:association": "ассоциация",
  "office:political_party": "политическая партия",
  "office:religion": "религиозная организация",
};

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
  let name = label || "";
  if (lang === "ru") {
    name = industryRu[id] || PUBLIC_OFFICE_RU[id] || label || "";
  }
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
  for (const el of document.querySelectorAll("[data-i18n-aria]")) {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  }
  for (const btn of document.querySelectorAll(".lang button")) {
    btn.classList.toggle("on", btn.dataset.lang === lang);
    btn.setAttribute("aria-pressed", btn.dataset.lang === lang ? "true" : "false");
  }
  syncFilterInputs();
  paintCount();
  paintHint();
  if (lastResults.length || $("results").childElementCount) paintResults();
  if (lastCompany) paintDetail(lastCompany);
  if ($("category")?.matches(":focus")) openCategoryCombo();
  if ($("industry")?.matches(":focus")) openIndustryCombo();
}

function normCombo(s) {
  return (s || "").trim().toLowerCase();
}

function hideAllCombos() {
  for (const id of COMBO_LISTS) $(id)?.classList.add("hidden");
}

function closeComboInput(inputId, suppressMs = 320) {
  hideAllCombos();
  comboSuppressUntil = Date.now() + suppressMs;
  const el = $(inputId);
  if (el) el.blur();
}

function bindSuggestPick(box, selector, onPick) {
  for (const li of box.querySelectorAll(selector)) {
    li.addEventListener("mousedown", (e) => e.preventDefault());
    li.onclick = () => onPick(li.dataset.value ?? li.dataset.city ?? "");
  }
}

function showComboList(listId, items, onPick) {
  const box = $(listId);
  if (!box) return;
  hideAllCombos();
  if (!items.length) {
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = items
    .map(
      (item) =>
        `<li role="option" data-value="${esc(item.id)}" tabindex="-1">` +
        `<span>${esc(item.label)}</span>` +
        (item.hint ? `<span class="n">${esc(item.hint)}</span>` : "") +
        `</li>`
    )
    .join("");
  bindSuggestPick(box, "li", onPick);
}

function filterByQuery(options, query, extraKeys = []) {
  const q = normCombo(query);
  if (!q) return options;
  return options.filter((o) => {
    const hay = [o.label, o.id, o.search, ...extraKeys.map((k) => o[k])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

function categoryOptions() {
  if (!statsCache) return [];
  let cats = statsCache.categories;
  if (state.city && industryCache.items) {
    const present = new Set(industryCache.items.map((i) => i.category));
    cats = cats.filter((c) => present.has(c.id));
  }
  return [{ id: "", label: t("allCategories") }].concat(
    cats.map((c) => ({ id: c.id, label: categoryLabel(c.id) }))
  );
}

function categoryLabel(id) {
  if (!id) return "";
  const key = "cat_" + id;
  const s = t(key);
  return s !== key ? s : id;
}

function industryOptionsList() {
  if (!industryCache.items) return [{ id: "", label: t("allTypes") }];
  const items = state.category
    ? industryCache.items.filter((i) => i.category === state.category)
    : industryCache.items;
  const opts = [{ id: "", label: t("allTypes") }];
  for (const i of items) {
    const label = `${industryName(i.id, i.label)} · ${fmt(i.n)}`;
    const ru =
      lang === "ru" ? industryRu[i.id] || PUBLIC_OFFICE_RU[i.id] || "" : "";
    opts.push({
      id: i.id,
      label,
      search: `${i.label} ${i.id} ${ru}`,
    });
  }
  return opts;
}

function industryLabel(id) {
  if (!id || !industryCache.items) return "";
  const item = industryCache.items.find((i) => i.id === id);
  return item ? `${industryName(item.id, item.label)} · ${fmt(item.n)}` : "";
}

function syncFilterInputs() {
  const cat = $("category");
  if (cat) cat.value = state.category ? categoryLabel(state.category) : "";
  const ind = $("industry");
  if (ind) ind.value = state.industry ? industryLabel(state.industry) : "";
  const srt = $("sort");
  if (srt) srt.value = state.sort || "name";
  const city = $("city");
  if (city) city.value = state.city || "";
  updateClearButtons();
}

function updateClearButtons() {
  const show = {
    category: !!state.category,
    industry: !!state.industry,
    city: !!state.city,
  };
  for (const [field, on] of Object.entries(show)) {
    const btn = document.querySelector(`.combo-clear[data-clear="${field}"]`);
    if (btn) btn.classList.toggle("hidden", !on);
  }
}

function clearComboField(field) {
  if (field === "category") pickCategory("");
  else if (field === "industry") pickIndustry("");
  else if (field === "city") pickCity("");
}

function openCategoryCombo() {
  showComboList("category-suggest", filterByQuery(categoryOptions(), $("category").value), pickCategory);
}

function pickCategory(id) {
  state.category = id;
  $("category").value = id ? categoryLabel(id) : "";
  closeComboInput("category");
  state.industry = "";
  $("industry").value = "";
  state.page = 1;
  updateClearButtons();
  loadIndustries().then(() => refresh({ fit: true }));
}

function openIndustryCombo() {
  showComboList("industry-suggest", filterByQuery(industryOptionsList(), $("industry").value, ["search"]), pickIndustry);
}

function pickIndustry(id) {
  state.industry = id;
  $("industry").value = id ? industryLabel(id) : "";
  closeComboInput("industry");
  state.page = 1;
  updateClearButtons();
  refresh({ fit: true });
}

function bindCombo(inputId, openFn, pickFromInput) {
  const input = $(inputId);
  if (!input) return;
  const maybeOpen = () => {
    if (Date.now() < comboSuppressUntil) return;
    openFn();
  };
  input.addEventListener("focus", maybeOpen);
  input.addEventListener("click", maybeOpen);
  input.addEventListener("input", openFn);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideAllCombos();
    if (e.key === "Enter") {
      e.preventDefault();
      pickFromInput();
    }
  });
  input.addEventListener("blur", () => {
    setTimeout(() => {
      if (document.activeElement?.closest(".combo-field")) return;
      syncFilterInputs();
    }, 120);
  });
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
  clampSheetHeight();
}

const SHEET_KEY = "hk-sheet-h";
const SHEET_MIN = 132;

function sheetMaxPx() {
  const margin = document.body.classList.contains("view-map") ? 108 : 76;
  return Math.max(SHEET_MIN, window.innerHeight * 0.88 - margin);
}

function sheetHeightPx() {
  const sheet = document.querySelector(".panel-sheet");
  return sheet ? sheet.getBoundingClientRect().height : 0;
}

function applySheetLayout(h, dragY = 0) {
  document.documentElement.style.setProperty("--sheet-h", `${h}px`);
  document.documentElement.style.setProperty("--sheet-drag-y", `${Math.round(dragY)}px`);
  const split = $("panel-split");
  if (split) split.setAttribute("aria-valuenow", String(h));
}

function setSheetHeight(px, persist = true) {
  if (!window.matchMedia("(max-width: 800px)").matches) return;
  const h = Math.round(Math.max(SHEET_MIN, Math.min(sheetMaxPx(), px)));
  applySheetLayout(h, 0);
  if (persist) localStorage.setItem(SHEET_KEY, String(h));
  if (map && document.body.classList.contains("view-map")) {
    requestAnimationFrame(() => map.invalidateSize({ animate: false }));
  }
}

function clampSheetHeight() {
  const h = sheetHeightPx();
  if (h) setSheetHeight(h, false);
}

function initMobileSheet() {
  const split = $("panel-split");
  if (!split) return;
  const mq = window.matchMedia("(max-width: 800px)");
  let dragging = false;
  let startY = 0;
  let startH = 0;

  const applyDefault = () => {
    if (!mq.matches) {
      document.documentElement.style.removeProperty("--sheet-h");
      return;
    }
    const stored = localStorage.getItem(SHEET_KEY);
    if (stored) {
      setSheetHeight(+stored, false);
      return;
    }
    const def = document.body.classList.contains("view-map")
      ? window.innerHeight * 0.34
      : window.innerHeight * 0.42;
    setSheetHeight(def, false);
  };

  applyDefault();
  mq.addEventListener("change", applyDefault);
  window.addEventListener("resize", () => clampSheetHeight());

  const sheet = () => document.querySelector(".panel-sheet");

  split.addEventListener("pointerdown", (e) => {
    if (!mq.matches) return;
    dragging = true;
    startY = e.clientY;
    startH = sheetHeightPx();
    sheet()?.classList.add("is-dragging");
    split.setPointerCapture(e.pointerId);
  });
  split.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dy = e.clientY - startY;
    const target = startH - dy;
    const max = sheetMaxPx();
    const h = Math.round(Math.max(SHEET_MIN, Math.min(max, target)));
    const dragY = dy - (startH - h);
    applySheetLayout(h, dragY);
  });
  const endDrag = (e) => {
    if (!dragging) return;
    dragging = false;
    sheet()?.classList.remove("is-dragging");
    setSheetHeight(sheetHeightPx(), true);
    try {
      split.releasePointerCapture(e.pointerId);
    } catch (_) {
      /* ignore */
    }
  };
  split.addEventListener("pointerup", endDrag);
  split.addEventListener("pointercancel", endDrag);

  split.addEventListener("keydown", (e) => {
    if (!mq.matches) return;
    const h = sheetHeightPx();
    if (e.key === "ArrowUp" || e.key === "PageUp") {
      e.preventDefault();
      setSheetHeight(h + 28);
    } else if (e.key === "ArrowDown" || e.key === "PageDown") {
      e.preventDefault();
      setSheetHeight(h - 28);
    }
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
const markerById = new Map();
let selectedMapId = null;

function pinIcon(cat, selected = false) {
  const c = CAT_COLORS[cat] || CAT_COLORS.other;
  const size = selected ? 18 : 12;
  const border = selected ? 3 : 2;
  const shadow = selected
    ? "0 0 0 3px rgba(184,74,31,.4), 0 2px 6px rgba(0,0,0,.35)"
    : "0 1px 4px rgba(0,0,0,.35)";
  return L.divIcon({
    className: "hk-pin",
    html: `<span style="display:block;width:${size}px;height:${size}px;border-radius:50%;background:${c};border:${border}px solid #f8f1e2;box-shadow:${shadow}"></span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function setMapMarkerSelection(id, category) {
  if (selectedMapId && markerById.has(selectedMapId)) {
    const prev = markerById.get(selectedMapId);
    prev.setIcon(pinIcon(prev._hkCat, false));
    prev.closePopup();
  }
  selectedMapId = id || null;
  if (!id || !markerById.has(id)) return;
  const m = markerById.get(id);
  const cat = category || m._hkCat;
  const apply = () => {
    m.setIcon(pinIcon(cat, true));
    m.openPopup();
  };
  if (cluster?.zoomToShowLayer) {
    state.skipMove = true;
    cluster.zoomToShowLayer(m, () => {
      apply();
      setTimeout(() => {
        state.skipMove = false;
      }, 80);
    });
  } else {
    apply();
  }
}

function focusCompanyInList(id) {
  const box = $("results");
  if (!box) return false;
  const el = box.querySelector(`.card[data-id="${id}"]`);
  if (!el) return false;
  el.classList.add("active");
  el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  return true;
}

function paintSelectedPill(r, inList) {
  const pill = $("selected-pill");
  if (!pill) return;
  if (!r || inList) {
    pill.classList.add("hidden");
    pill.innerHTML = "";
    return;
  }
  pill.classList.remove("hidden");
  pill.innerHTML = `<strong>${esc(r.company_name)}</strong><span>${esc(t("selectedHint"))}</span>`;
  pill.onclick = () => paintDetail(r);
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
    disableClusteringAtZoom: 17,
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
  const [stats, ru] = await Promise.all([
    fetch("/api/stats").then((r) => r.json()),
    fetch("/industry-ru.json")
      .then((r) => r.json())
      .catch(() => ({})),
  ]);
  industryRu = ru;
  statsCache = stats;
  applyChrome();
  await loadIndustries();
  syncFilterInputs();
  document.querySelector(".lang").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang]");
    if (btn) setLang(btn.dataset.lang);
  });
  document.querySelector(".viewbar").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-view]");
    if (btn) setView(btn.dataset.view);
  });

  $("q").addEventListener("input", onQuery);
  bindCombo("category", openCategoryCombo, () => {
    const q = normCombo($("category").value);
    if (!q) pickCategory("");
    else {
      const match = categoryOptions().find((o) => normCombo(o.label) === q);
      if (match) pickCategory(match.id);
      else openCategoryCombo();
    }
  });
  bindCombo("industry", openIndustryCombo, () => {
    const q = normCombo($("industry").value);
    if (!q) pickIndustry("");
    else {
      const match = industryOptionsList().find((o) => normCombo(o.label).startsWith(q) || normCombo(o.search).includes(q));
      if (match) pickIndustry(match.id);
      else openIndustryCombo();
    }
  });
  $("sort").addEventListener("change", () => {
    state.sort = $("sort").value || "name";
    state.page = 1;
    loadList();
  });
  $("city").addEventListener("input", onCityInput);
  $("city").addEventListener("focus", onCityInput);
  $("city").addEventListener("click", onCityInput);
  $("city").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const q = $("city").value.trim();
      const box = $("city-suggest");
      const first = box?.querySelector("li[data-city]");
      if (first && !state.city) pickCity(first.dataset.city);
      else pickCity(q);
    }
    if (e.key === "Escape") hideAllCombos();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".combo-field")) hideAllCombos();
  });
  for (const btn of document.querySelectorAll(".combo-clear")) {
    btn.addEventListener("mousedown", (e) => e.preventDefault());
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      clearComboField(btn.dataset.clear);
    });
  }
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
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "SELECT") {
      e.preventDefault();
      $("q").focus();
    }
    if (e.key === "Escape") $("detail").classList.add("hidden");
  });

  initMobileSheet();

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
  for (const box of document.querySelectorAll(".must input")) box.checked = false;
  hideAllCombos();
  loadIndustries().then(() => {
    syncFilterInputs();
    if (map) map.fitBounds(NL_BOUNDS, { padding: [12, 12] });
    refresh();
  });
}

async function loadIndustries() {
  const city = state.city || "";
  if (industryCache.city !== city || !industryCache.items) {
    const p = city ? `?city=${encodeURIComponent(city)}` : "";
    industryCache = { city, items: await (await fetch(`/api/industries${p}`)).json() };
  }
  const items = state.category
    ? industryCache.items.filter((i) => i.category === state.category)
    : industryCache.items;
  if (state.industry && !items.some((i) => i.id === state.industry)) state.industry = "";
  syncFilterInputs();
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
    if (Date.now() < comboSuppressUntil) return;
    const q = $("city").value.trim();
    if (q.length < 1) {
      if (state.city) {
        state.city = "";
        state.industry = "";
        state.page = 1;
        industryCache = { city: null, items: null };
        loadIndustries().then(() => refresh({ fit: true }));
      }
      const items = await (await fetch("/api/cities")).json();
      renderCitySuggest(items);
      return;
    }
    const items = await (await fetch(`/api/cities?q=${encodeURIComponent(q)}`)).json();
    renderCitySuggest(items);
  }, 100);
}

function renderCitySuggest(items) {
  const box = $("city-suggest");
  hideAllCombos();
  if (!items.length) {
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = items
    .map((c) => `<li role="option" data-city="${esc(c.name)}"><span>${esc(c.name)}</span><span class="n">${fmt(c.n)}</span></li>`)
    .join("");
  for (const li of box.querySelectorAll("li")) {
    const name = li.getAttribute("data-city") || "";
    li.addEventListener("mousedown", (e) => e.preventDefault());
    li.addEventListener("click", (e) => {
      e.stopPropagation();
      pickCity(name);
    });
  }
}

function pickCity(name) {
  clearTimeout(cityTimer);
  const exact = (name || "").trim();
  if (!exact) {
    state.city = "";
    $("city").value = "";
    closeComboInput("city", 450);
    state.page = 1;
    updateClearButtons();
    industryCache = { city: null, items: null };
    loadIndustries().then(() => refresh({ fit: true }));
    return;
  }
  state.city = exact;
  $("city").value = exact;
  closeComboInput("city", 450);
  state.page = 1;
  updateClearButtons();
  if (industryCache.city !== exact) industryCache = { city: null, items: null };
  loadIndustries().then(() => refresh({ fit: true }));
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
  if (lastCompany) {
    const inList = focusCompanyInList(lastCompany.id);
    paintSelectedPill(lastCompany, inList);
  }
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
  markerById.clear();
  const layers = [];
  for (const pt of data.points) {
    if (pt.lat == null || pt.lon == null) continue;
    const m = L.marker([pt.lat, pt.lon], { icon: pinIcon(pt.category), title: pt.name });
    m._hkCat = pt.category;
    m._hkId = pt.id;
    markerById.set(pt.id, m);
    m.bindPopup(`<strong>${esc(pt.name)}</strong><br><span style="color:#6b6458;font-size:11px">${esc(t("onMap"))}</span>`);
    m.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      openCompany(pt.id, false);
    });
    layers.push(m);
  }
  cluster.addLayers(layers);
  if (lastCompany?.id) setMapMarkerSelection(lastCompany.id, lastCompany.category);
  if (data.truncated) hintMode = "zoom";
  else if (!layers.length) hintMode = "empty";
  else hintMode = "hidden";
  paintHint();
}

async function openCompany(id, fly) {
  const r = await (await fetch(`/api/company/${id}`)).json();
  if (r.error) return;
  lastCompany = r;
  paintDetail(r);
  if (fly && r.lat && r.lon && map) {
    if (window.matchMedia("(max-width: 800px)").matches) setView("map");
    state.skipMove = true;
    const z = Math.max(map.getZoom(), 17);
    const onMoved = () => {
      map.off("moveend", onMoved);
      state.skipMove = false;
      loadPoints();
    };
    requestAnimationFrame(() => {
      map.invalidateSize({ animate: false });
      map.flyTo([r.lat, r.lon], z, { duration: 0.35 });
      map.on("moveend", onMoved);
    });
  } else {
    setMapMarkerSelection(r.id, r.category);
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
    setMapMarkerSelection(null);
    paintSelectedPill(null, true);
    for (const el of $("results").querySelectorAll(".card")) el.classList.remove("active");
  };
  for (const el of $("results").querySelectorAll(".card")) {
    el.classList.toggle("active", +el.dataset.id === r.id);
  }
  const inList = focusCompanyInList(r.id);
  paintSelectedPill(r, inList);
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
