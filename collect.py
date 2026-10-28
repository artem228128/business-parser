#!/usr/bin/env python3
"""NL business collector from open sources (OSM Overpass). Optional KVK / Google Places APIs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
MAIN_SQLITE = ROOT / "data" / "netherlands.sqlite"
MAIN_CSV = ROOT / "data" / "netherlands.csv"
NL_COLLECT_STATE = ROOT / "data" / "nl-collect.state"
NL_PARTS_STATE = ROOT / "data" / "nl-parts.state"
NL_GEMEENTEN_CACHE = ROOT / "data" / "nl-gemeenten.txt"
NL_GEMEENTE_STATE = ROOT / "data" / "nl-gemeente.state"
MERGE_LOCK = threading.Lock()

OVERPASS_ENDPOINTS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "BusinessParser/1.0 (+https://www.openstreetmap.org/copyright; ODbL reuse)"
KVK_OPEN_KEY = "l7xx1f26914529804b55a22aa8e0a9512a91"
KVK_OPEN_URL = "https://opendata.kvk.nl/api/v1/hvds/basisbedrijfsgegevens/kvknummer/{kvk}"
KVK_SEARCH_URL = "https://api.kvk.nl/api/v2/zoeken"
KVK_PROFILE_URL = "https://api.kvk.nl/api/v1/basisprofielen/{kvk}"
PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

NL_PROVINCES = {
    "NL-DR": "Drenthe",
    "NL-FL": "Flevoland",
    "NL-FR": "Friesland",
    "NL-GE": "Gelderland",
    "NL-GR": "Groningen",
    "NL-LI": "Limburg",
    "NL-NB": "Noord-Brabant",
    "NL-NH": "Noord-Holland",
    "NL-OV": "Overijssel",
    "NL-UT": "Utrecht",
    "NL-ZE": "Zeeland",
    "NL-ZH": "Zuid-Holland",
}

# amenity=* with a name but not a commercial POI (schools, infra, worship, …)
NON_BUSINESS_AMENITIES = frozenset(
    {
        "bench",
        "waste_basket",
        "waste_disposal",
        "recycling",
        "compost",
        "drinking_water",
        "fountain",
        "parking",
        "parking_space",
        "parking_entrance",
        "bicycle_parking",
        "motorcycle_parking",
        "parking_meter",
        "toilets",
        "shower",
        "shelter",
        "clock",
        "post_box",
        "letter_box",
        "give_box",
        "vending_machine",
        "telephone",
        "emergency_phone",
        "fire_station",
        "police",
        "ambulance_station",
        "ranger_station",
        "townhall",
        "courthouse",
        "prison",
        "social_facility",
        "community_centre",
        "place_of_worship",
        "monastery",
        "grave_yard",
        "mortuary",
        "school",
        "university",
        "college",
        "library",
        "public_bookcase",
        "public_building",
        "hunting_stand",
        "loading_dock",
        "vehicle_inspection",
        "bbq",
        "trolley_bay",
        "bus_station",
        "ferry_terminal",
    }
)

# Overpass filter for amenity=* (faster than nwr["amenity"]["name"] on whole provinces).
COMMERCIAL_AMENITIES = frozenset(
    {
        "accountant",
        "animal_boarding",
        "animal_breeding",
        "animal_shelter",
        "animal_training",
        "architect",
        "art_gallery",
        "arts_centre",
        "atm",
        "bank",
        "bar",
        "bbq",
        "biergarten",
        "bicycle_repair_station",
        "bicycle_rental",
        "boat_rental",
        "brothel",
        "bureau_de_change",
        "cafe",
        "car_rental",
        "car_sharing",
        "car_wash",
        "casino",
        "charging_station",
        "childcare",
        "cinema",
        "clinic",
        "clock",
        "conference_centre",
        "copy_shop",
        "coworking_space",
        "dentist",
        "doctors",
        "driving_school",
        "dry_cleaning",
        "employment_agency",
        "estate_agent",
        "events_venue",
        "fast_food",
        "food_court",
        "fuel",
        "gambling",
        "hairdresser",
        "hospital",
        "ice_cream",
        "insurance",
        "internet_cafe",
        "kindergarten",
        "language_school",
        "lawyer",
        "laundry",
        "marketplace",
        "massage",
        "money_transfer",
        "music_school",
        "music_venue",
        "nightclub",
        "notary",
        "parcel_locker",
        "pharmacy",
        "photo_booth",
        "prep_school",
        "pub",
        "restaurant",
        "salon",
        "spa",
        "stripclub",
        "studio",
        "tattoo",
        "taxi",
        "theatre",
        "training",
        "travel_agency",
        "veterinary",
        "beauty",
    }
) - NON_BUSINESS_AMENITIES

AMENITY_OVERPASS = "|".join(sorted(COMMERCIAL_AMENITIES))

NON_BUSINESS_TOURISM = frozenset(
    {
        "viewpoint",
        "picnic_site",
        "information",
        "camp_pitch",
        "wilderness_hut",
        "artwork",
        "yes",
    }
)

BUSINESS_BUILDINGS = frozenset(
    {
        "commercial",
        "retail",
        "industrial",
        "warehouse",
        "office",
        "service",
        "kiosk",
        "garage",
        "depot",
        "manufacture",
        "farm",
        "supermarket",
        "bakehouse",
        "greenhouse",
    }
)

BUSINESS_LEISURE = frozenset(
    {
        "fitness_centre",
        "sports_centre",
        "bowling_alley",
        "adult_gaming_centre",
        "dance",
        "spa",
        "water_park",
        "marina",
        "stadium",
        "horse_riding",
        "miniature_golf",
        "trampoline_park",
        "amusement_arcade",
        "escape_game",
        "disc_golf_course",
        "ice_rink",
        "swimming_pool",
    }
)

BUILDING_OVERPASS = "|".join(sorted(BUSINESS_BUILDINGS))
LEISURE_OVERPASS = "|".join(sorted(BUSINESS_LEISURE))

# OSM office=* — separate collect via --public-offices; excluded from default --nl/--city
PUBLIC_OFFICE_TYPES = frozenset(
    {"government", "diplomatic", "ngo", "association", "political_party", "religion"}
)
PUBLIC_OFFICE_OVERPASS = "|".join(sorted(PUBLIC_OFFICE_TYPES))

FIELDS = [
    "company_name",
    "industry",
    "website",
    "general_email",
    "phone",
    "business_address",
    "kvk_number",
    "source_url",
    "verification_date",
    "lat",
    "lon",
    "source",
]

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
GENERIC_LOCAL = {
    "info",
    "hello",
    "contact",
    "office",
    "sales",
    "support",
    "admin",
    "mail",
    "klantenservice",
    "service",
    "inquiries",
    "enquiry",
    "team",
    "welcome",
    "reservations",
    "booking",
    "boekingen",
    "reserveringen",
}


def first(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def tag(el: dict, *keys: str) -> str:
    tags = el.get("tags") or {}
    return first(*(tags.get(k) for k in keys))


def industry_of(el: dict) -> str:
    tags = el.get("tags") or {}
    for key in (
        "office",
        "shop",
        "craft",
        "healthcare",
        "industrial",
        "man_made",
        "building",
        "leisure",
        "tourism",
        "amenity",
        "company",
    ):
        val = tags.get(key)
        if val:
            return f"{key}:{val}"
    return ""


def address_of(el: dict) -> str:
    tags = el.get("tags") or {}
    street = first(tags.get("addr:street"), tags.get("contact:street"))
    number = first(tags.get("addr:housenumber"), tags.get("contact:housenumber"))
    postcode = first(tags.get("addr:postcode"), tags.get("contact:postcode"))
    city = first(tags.get("addr:city"), tags.get("addr:place"), tags.get("contact:city"))
    parts = []
    if street and number:
        parts.append(f"{street} {number}")
    elif street:
        parts.append(street)
    loc = " ".join(p for p in (postcode, city) if p)
    if loc:
        parts.append(loc)
    elif city:
        parts.append(city)
    return ", ".join(parts)


def coords(el: dict) -> tuple[str, str]:
    if "lat" in el and "lon" in el:
        return str(el["lat"]), str(el["lon"])
    c = el.get("center") or {}
    if "lat" in c and "lon" in c:
        return str(c["lat"]), str(c["lon"])
    return "", ""


def osm_url(el: dict) -> str:
    return f"https://www.openstreetmap.org/{el['type']}/{el['id']}"


def is_business(el: dict, *, public_offices_only: bool = False) -> bool:
    tags = el.get("tags") or {}
    name = first(tags.get("name"), tags.get("name:nl"), tags.get("name:en"))
    if not name:
        return False
    office = tags.get("office")
    if public_offices_only:
        return office in PUBLIC_OFFICE_TYPES
    if tags.get("shop") or tags.get("craft") or tags.get("company"):
        return True
    if tags.get("healthcare") or tags.get("industrial"):
        return True
    if tags.get("man_made") == "works":
        return True
    building = tags.get("building")
    if building in BUSINESS_BUILDINGS:
        return True
    leisure = tags.get("leisure")
    if leisure in BUSINESS_LEISURE:
        return True
    if office and office not in PUBLIC_OFFICE_TYPES:
        return True
    tourism = tags.get("tourism")
    if tourism and tourism not in NON_BUSINESS_TOURISM:
        return True
    amenity = tags.get("amenity")
    if amenity and amenity not in NON_BUSINESS_AMENITIES:
        return True
    return False


def to_record(el: dict, verified: str) -> dict[str, str]:
    tags = el.get("tags") or {}
    lat, lon = coords(el)
    return {
        "company_name": first(tags.get("name"), tags.get("name:nl"), tags.get("name:en")),
        "industry": industry_of(el),
        "website": first(
            tags.get("website"),
            tags.get("contact:website"),
            tags.get("url"),
            tags.get("contact:url"),
        ),
        "general_email": first(tags.get("email"), tags.get("contact:email")),
        "phone": first(tags.get("phone"), tags.get("contact:phone"), tags.get("mobile"), tags.get("contact:mobile")),
        "business_address": address_of(el),
        "kvk_number": first(tags.get("ref:kvk"), tags.get("kvk"), tags.get("ref:KVK")),
        "source_url": osm_url(el),
        "verification_date": verified,
        "lat": lat,
        "lon": lon,
        "source": "openstreetmap",
    }


def overpass_query(
    area_filter: str,
    timeout: int,
    *,
    public_offices_only: bool = False,
    factories_only: bool = False,
) -> str:
    """Same single query per province as the first full NL run, plus the extra POI types."""
    if factories_only:
        # Bbox of the Netherlands. Area lookup was the part that failed on the mirror that answers.
        return f"""
[out:json][timeout:{timeout}];
(
  nwr["man_made"="works"]["name"](50.75,3.20,53.70,7.23);
  nwr["industrial"="factory"]["name"](50.75,3.20,53.70,7.23);
);
out center tags;
""".strip()
    elif public_offices_only:
        body = f'  nwr["office"~"{PUBLIC_OFFICE_OVERPASS}"]["name"](area.a);'
    else:
        body = f"""
  nwr["shop"]["name"](area.a);
  nwr["office"]["name"](area.a);
  nwr["craft"]["name"](area.a);
  nwr["company"]["name"](area.a);
  nwr["healthcare"]["name"](area.a);
  nwr["industrial"]["name"](area.a);
  nwr["man_made"="works"]["name"](area.a);
  nwr["building"~"{BUILDING_OVERPASS}"]["name"](area.a);
  nwr["leisure"~"{LEISURE_OVERPASS}"]["name"](area.a);
  nwr["tourism"~"hotel|motel|guest_house|hostel|apartment|chalet|camp_site|caravan_site"]["name"](area.a);
  nwr["amenity"~"restaurant|cafe|fast_food|bar|pub|pharmacy|bank|clinic|dentist|doctors|veterinary|studio|theatre|cinema|nightclub|fuel|car_rental|car_wash|post_office|hairdresser|marketplace"]["name"](area.a);
""".strip()
    return f"""
[out:json][timeout:{timeout}];
{area_filter}
(
{body}
);
out center tags;
""".strip()


def fetch_overpass(query: str, session: requests.Session | None = None, *, timeout: int = 180) -> list[dict]:
    last_err = None
    own = session is None
    if own:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
    for url in OVERPASS_ENDPOINTS:
        host = url.split("/")[2]
        for attempt in range(4):
            print(f"[osm] {host} attempt {attempt + 1}", file=sys.stderr, flush=True)
            try:
                r = session.post(url, data={"data": query}, timeout=timeout + 30)
                if r.status_code in {429, 504, 502, 503}:
                    time.sleep(15 * (attempt + 1))
                    continue
                r.raise_for_status()
                payload = r.json()
                remark = str(payload.get("remark") or "")
                low = remark.lower()
                if "timed out" in low or "runtime error" in low:
                    raise RuntimeError(remark[:240] or "Overpass timed out")
                return payload.get("elements") or []
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                print(f"[osm] {host} failed: {exc}", file=sys.stderr, flush=True)
                time.sleep(6 * (attempt + 1))
        time.sleep(2)
    raise RuntimeError(f"Overpass failed: {last_err}")


def _fetch_overpass_part(query: str, label: str) -> tuple[str, list[dict], float]:
    t0 = time.monotonic()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            batch = fetch_overpass(query, session=None)
            return label, batch, time.monotonic() - t0
        except RuntimeError as exc:
            last_err = exc
            time.sleep(8 * (attempt + 1))
    raise last_err or RuntimeError("Overpass failed")


def collect_area(
    session: requests.Session,
    area_ql: str,
    timeout: int,
    *,
    public_offices_only: bool = False,
    factories_only: bool = False,
) -> list[dict]:
    verified = date.today().isoformat()
    elements = fetch_overpass(
        overpass_query(
            area_ql,
            timeout,
            public_offices_only=public_offices_only,
            factories_only=factories_only,
        ),
        session,
        timeout=timeout,
    )
    rows = []
    seen: set[tuple[str, str]] = set()
    for el in elements:
        if not is_business(el, public_offices_only=public_offices_only):
            continue
        rec = to_record(el, verified)
        key = (rec["company_name"].lower(), rec["business_address"].lower() or rec["source_url"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(rec)
    return rows


def collect_city(
    session: requests.Session,
    city: str,
    timeout: int,
    *,
    public_offices_only: bool = False,
) -> list[dict]:
    ql = f'area["name"="{city}"]["admin_level"="8"]->.a;'
    return collect_area(session, ql, timeout, public_offices_only=public_offices_only)


def _province_start_index(resume: bool, start_after: str) -> int:
    items = list(NL_PROVINCES.items())
    if start_after:
        for i, (iso, _) in enumerate(items):
            if iso == start_after:
                return i + 1
        print(f"[osm] unknown --after {start_after}, from start", file=sys.stderr)
        return 0
    if not resume or not NL_COLLECT_STATE.exists():
        return 0
    last = NL_COLLECT_STATE.read_text(encoding="utf-8").strip()
    for i, (iso, _) in enumerate(items):
        if iso == last:
            print(f"[osm] resume after {last}", file=sys.stderr)
            return i + 1
    return 0


def area_ql_gemeente(name: str) -> str:
    safe = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'area["name"="{safe}"]["admin_level"="8"]->.a;'


def fetch_nl_gemeenten(session: requests.Session, timeout: int) -> list[str]:
    if NL_GEMEENTEN_CACHE.exists():
        names = [ln.strip() for ln in NL_GEMEENTEN_CACHE.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if names:
            return names
    names: set[str] = set()
    tlim = min(timeout, 90)
    for iso, pname in NL_PROVINCES.items():
        print(f"[osm] gemeenten list: {pname}", file=sys.stderr)
        q = f"""
[out:json][timeout:{tlim}];
area["ISO3166-2"="{iso}"]->.p;
rel(area.p)["admin_level"="8"]["boundary"="administrative"];
out tags;
""".strip()
        for el in fetch_overpass(q, session):
            n = (el.get("tags") or {}).get("name")
            if n:
                names.add(n)
        time.sleep(1)
    if not names:
        raise RuntimeError("Could not load NL gemeenten list from Overpass")
    out = sorted(names)
    NL_GEMEENTEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    NL_GEMEENTEN_CACHE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[osm] {len(out)} gemeenten (cached {NL_GEMEENTEN_CACHE.name})", file=sys.stderr)
    return out


def _gemeente_done() -> set[str]:
    if not NL_GEMEENTE_STATE.exists():
        return set()
    return {ln.strip() for ln in NL_GEMEENTE_STATE.read_text(encoding="utf-8").splitlines() if ln.strip()}


def collect_nl_gemeente(
    session: requests.Session,
    timeout: int,
    *,
    public_offices_only: bool = False,
    merge_main: bool = False,
    resume: bool = False,
    wide_amenity: bool = False,
    parallel_parts: bool = True,
    workers: int = 6,
) -> list[dict]:
    cities = fetch_nl_gemeenten(session, timeout)
    done = _gemeente_done() if resume else set()
    todo = [c for c in cities if c not in done]
    w = max(1, min(workers, 12))
    est = len(todo) * 35 / w
    print(
        f"[plan] {len(todo)}/{len(cities)} gemeenten, {w} workers, "
        f"rough ETA ~{fmt_eta(est)} (Overpass load varies)",
        file=sys.stderr,
    )
    all_rows: list[dict] = []
    times: list[float] = []
    done_n = len(done)
    progress_lock = threading.Lock()

    def one_city(city: str) -> tuple[str, list[dict], float]:
        t0 = time.monotonic()
        _ = wide_amenity, parallel_parts
        rows = collect_area(
            session,
            area_ql_gemeente(city),
            timeout,
            public_offices_only=public_offices_only,
        )
        return city, rows, time.monotonic() - t0

    with ThreadPoolExecutor(max_workers=w) as pool:
        futs = {pool.submit(one_city, city): city for city in todo}
        for fut in as_completed(futs):
            city, rows, elapsed = fut.result()
            with progress_lock:
                done_n += 1
                times.append(elapsed)
                avg = sum(times) / len(times)
                left = len(cities) - done_n
                eta = (left * avg) / w
                print(
                    f"[osm] {done_n}/{len(cities)} {city}: {len(rows)} rows ({elapsed:.0f}s) "
                    f"ETA ~{fmt_eta(eta)}",
                    file=sys.stderr,
                )
                if merge_main and rows:
                    main_total, _ = merge_into_main(rows)
                    print(f"[main] ~{main_total} rows in csv", file=sys.stderr)
                    with NL_GEMEENTE_STATE.open("a", encoding="utf-8") as sf:
                        sf.write(city + "\n")
            all_rows.extend(rows)
    return all_rows


def _done_parts() -> set[tuple[str, str]]:
    if not NL_PARTS_STATE.exists():
        return set()
    done: set[tuple[str, str]] = set()
    for line in NL_PARTS_STATE.read_text(encoding="utf-8").splitlines():
        iso, _, part = line.strip().partition("\t")
        if iso and part:
            done.add((iso, part))
    return done


def _mark_part_done(iso: str, part: str) -> None:
    NL_PARTS_STATE.parent.mkdir(parents=True, exist_ok=True)
    with NL_PARTS_STATE.open("a", encoding="utf-8") as f:
        f.write(f"{iso}\t{part}\n")


NL_BBOX = "50.75,3.20,53.70,7.23"


def extra_selectors() -> list[tuple[str, str]]:
    stay = "hotel|motel|guest_house|hostel|apartment|chalet|camp_site|caravan_site"
    return [
        ("healthcare", f'nwr["healthcare"]["name"]({NL_BBOX});'),
        ("industrial", f'nwr["industrial"]["name"]({NL_BBOX});'),
        ("building", f'nwr["building"~"{BUILDING_OVERPASS}"]["name"]({NL_BBOX});'),
        ("leisure-sport", f'nwr["leisure"~"fitness_centre|sports_centre|swimming_pool|ice_rink"]["name"]({NL_BBOX});'),
        ("leisure-stay", f'nwr["leisure"~"spa|water_park|marina|stadium|horse_riding"]["name"]({NL_BBOX});'),
        ("leisure-play", f'nwr["leisure"~"bowling_alley|adult_gaming_centre|dance|miniature_golf|trampoline_park|amusement_arcade|escape_game|disc_golf_course"]["name"]({NL_BBOX});'),
        ("tourism", f'nwr["tourism"~"{stay}"]["name"]({NL_BBOX});'),
    ]


def collect_extra(session: requests.Session, timeout: int, *, merge_main: bool = False) -> list[dict]:
    """Named healthcare, industry, commercial buildings, leisure and stays. One bbox query each."""
    verified = date.today().isoformat()
    all_rows: list[dict] = []
    failed: list[str] = []
    for name, selector in extra_selectors():
        query = f"[out:json][timeout:{timeout}];\n(\n  {selector}\n);\nout center tags;"
        print(f"[osm] extra {name}", file=sys.stderr)
        try:
            elements = fetch_overpass(query, session, timeout=timeout)
        except RuntimeError as exc:
            print(f"[osm] {name} failed: {exc}", file=sys.stderr)
            failed.append(name)
            continue
        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for el in elements:
            if not is_business(el):
                continue
            rec = to_record(el, verified)
            key = (rec["company_name"].lower(), rec["business_address"].lower() or rec["source_url"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(rec)
        print(f"[osm] {name}: {len(elements)} elements → {len(rows)} rows", file=sys.stderr)
        if merge_main and rows:
            main_total, _ = merge_into_main(rows)
            print(f"[main] ~{main_total} csv rows", file=sys.stderr)
        all_rows.extend(rows)
    if failed:
        raise RuntimeError("failed types: " + ", ".join(failed))
    return all_rows


def collect_nl(
    session: requests.Session,
    timeout: int,
    *,
    public_offices_only: bool = False,
    factories_only: bool = False,
    merge_main: bool = False,
    resume: bool = False,
    start_after: str = "",
) -> list[dict]:
    if factories_only:
        print("[osm] Netherlands factories only (man_made=works, industrial=factory)", file=sys.stderr)
        rows = collect_area(
            session,
            'area["ISO3166-1"="NL"]["admin_level"="2"]->.a;',
            timeout,
            factories_only=True,
        )
        print(f"[osm] factories: {len(rows)}", file=sys.stderr)
        if not rows:
            raise RuntimeError("factory query returned 0 rows")
        if merge_main:
            main_total, _ = merge_into_main(rows)
            print(f"[main] upserted {len(rows)} factories (~{main_total} csv rows)", file=sys.stderr)
        return rows
    all_rows: list[dict] = []
    provinces = list(NL_PROVINCES.items())
    start = _province_start_index(resume, start_after)
    for iso, name in provinces[start:]:
        print(f"[osm] {name} ({iso})", file=sys.stderr)
        ql = f'area["ISO3166-2"="{iso}"]->.a;'
        rows = collect_area(session, ql, timeout, public_offices_only=public_offices_only)
        print(f"[osm] {name}: {len(rows)}", file=sys.stderr)
        if len(rows) == 0 and not public_offices_only:
            raise RuntimeError(f"{name} returned 0 rows (Overpass timeout or empty), not merging")
        if merge_main and rows:
            main_total, _ = merge_into_main(rows)
            print(f"[main] upserted {len(rows)} from {name} (~{main_total} csv rows)", file=sys.stderr)
            NL_COLLECT_STATE.write_text(iso, encoding="utf-8")
        all_rows.extend(rows)
        time.sleep(8)
    return all_rows


def kvk_lookup(session: requests.Session, kvk: str) -> dict:
    """Official open dataset: NO name/address/email. Useful only as activity/legal-form extra."""
    r = session.get(
        KVK_OPEN_URL.format(kvk=kvk),
        headers={"apikey": KVK_OPEN_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def kvk_search(session: requests.Session, api_key: str, plaats: str, page: int) -> dict:
    r = session.get(
        KVK_SEARCH_URL,
        params={"plaats": plaats, "pagina": page, "resultatenPerPagina": 100, "type": "hoofdvestiging"},
        headers={"apikey": api_key, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def kvk_profile(session: requests.Session, api_key: str, kvk: str) -> dict:
    r = session.get(
        KVK_PROFILE_URL.format(kvk=kvk),
        headers={"apikey": api_key, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def places_search(session: requests.Session, api_key: str, query: str, page_token: str | None = None) -> dict:
    body: dict[str, Any] = {
        "textQuery": query,
        "regionCode": "NL",
        "languageCode": "nl",
        "pageSize": 20,
    }
    if page_token:
        body["pageToken"] = page_token
    r = session.post(
        PLACES_TEXT_URL,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
                "places.websiteUri,places.googleMapsUri,places.types,places.location,nextPageToken"
            ),
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def domain_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")


def pick_email(emails: list[str], site: str) -> str:
    host = domain_of(site)
    ranked: list[tuple[int, str]] = []
    for raw in emails:
        e = raw.strip(".,;:()<>\"' ").lower()
        if any(x in e for x in ("noreply", "no-reply", "donotreply", "example.com", "sentry", "wixpress", "cloudflare")):
            continue
        local, _, dom = e.partition("@")
        score = 0
        if host and (dom == host or dom.endswith("." + host) or host.endswith("." + dom)):
            score += 5
        if local in GENERIC_LOCAL:
            score += 3
        if local.startswith("info"):
            score += 2
        ranked.append((score, e))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else ""


def enrich_email(session: requests.Session, rec: dict, delay: float) -> dict:
    site = rec.get("website") or ""
    if rec.get("general_email") or not site:
        return rec
    if not site.startswith("http"):
        site = "https://" + site
        rec["website"] = site
    try:
        r = session.get(site, timeout=12, allow_redirects=True)
        if r.status_code >= 400:
            return rec
        html = r.text[:400_000]
        soup = BeautifulSoup(html, "lxml")
        found: list[str] = []
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href") or ""
            found.extend(EMAIL_RE.findall(href.replace("mailto:", "")))
        found.extend(EMAIL_RE.findall(html))
        contact_hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() or "").lower()
            if any(x in href.lower() or x in text for x in ("contact", "over-ons", "about")):
                contact_hrefs.append(urljoin(r.url, href))
        for href in contact_hrefs[:2]:
            time.sleep(delay)
            cr = session.get(href, timeout=12, allow_redirects=True)
            if cr.status_code < 400:
                found.extend(EMAIL_RE.findall(cr.text[:200_000]))
                for a in BeautifulSoup(cr.text[:200_000], "lxml").select('a[href^="mailto:"]'):
                    found.extend(EMAIL_RE.findall((a.get("href") or "").replace("mailto:", "")))
        rec["general_email"] = pick_email(found, site)
    except Exception:
        return rec
    finally:
        time.sleep(delay)
    return rec


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def write_sqlite(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    cols = ", ".join(f"{c} TEXT" for c in FIELDS)
    con.execute(f"CREATE TABLE IF NOT EXISTS businesses ({cols}, UNIQUE(source_url))")
    con.execute(
        """CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )"""
    )
    con.execute(
        "INSERT OR REPLACE INTO meta VALUES (?, ?)",
        ("generated_at", datetime.now(timezone.utc).isoformat()),
    )
    placeholders = ",".join("?" * len(FIELDS))
    con.executemany(
        f"INSERT OR REPLACE INTO businesses ({','.join(FIELDS)}) VALUES ({placeholders})",
        [tuple(row.get(c, "") for c in FIELDS) for row in rows],
    )
    con.commit()
    con.close()


def merge_csv(path: Path, rows: list[dict]) -> int:
    """Upsert rows into CSV by source_url. Returns total row count in file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    by_url: dict[str, dict[str, str]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = (row.get("source_url") or "").strip()
                if url:
                    by_url[url] = {k: row.get(k, "") or "" for k in FIELDS}
    for row in rows:
        url = (row.get("source_url") or "").strip()
        if not url:
            continue
        by_url[url] = {k: row.get(k, "") or "" for k in FIELDS}
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in by_url.values():
            w.writerow(row)
    return len(by_url)


def fmt_eta(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}ч {m}м"
    if m:
        return f"{m}м {sec}с"
    return f"{sec}с"


def merge_into_main(rows: list[dict]) -> tuple[int, int]:
    """Upsert into data/netherlands.sqlite and .csv. Returns (sqlite_total, batch_size)."""
    if not rows:
        return 0, 0
    with MERGE_LOCK:
        write_sqlite(MAIN_SQLITE, rows)
        total = merge_csv(MAIN_CSV, rows)
    return total, len(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect NL businesses from OSM (open). Optional paid KVK / Google Places.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--city", help="Dutch municipality name as in OSM, e.g. Amsterdam, Haarlem")
    g.add_argument("--nl", action="store_true", help="All 12 provinces, one Overpass query each")
    g.add_argument("--kvk-open", metavar="KVKNR", help="Probe official KVK open dataset for one number (no names)")
    p.add_argument("--out", default="data/businesses.csv")
    p.add_argument("--sqlite", default="data/businesses.sqlite")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--enrich-emails", action="store_true", help="Hit company websites for a public contact email")
    p.add_argument("--email-limit", type=int, default=200)
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--kvk-key", help="Paid KVK API key (Zoeken/Basisprofiel). Not used unless --kvk-city")
    p.add_argument("--kvk-city", help="City name for paid KVK search")
    p.add_argument("--google-key", help="Google Places API key")
    p.add_argument("--google-query", default="bedrijven in Nederland")
    p.add_argument(
        "--public-offices",
        action="store_true",
        help="Only OSM office=government|diplomatic|ngo|association|political_party|religion (with --city or --nl)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Continue after data/nl-gemeente.state or nl-collect.state",
    )
    p.add_argument(
        "--after",
        metavar="ISO",
        help="With --nl: skip provinces until after this ISO3166-2 code (e.g. NL-GE)",
    )
    p.add_argument(
        "--wide-amenity",
        action="store_true",
        help="Extra slow Overpass pass: all amenity=* with name (provinces only if needed)",
    )
    p.add_argument(
        "--sequential-overpass",
        action="store_true",
        help="Run Overpass sub-queries one by one (easier on weak networks)",
    )
    p.add_argument(
        "--factories",
        action="store_true",
        help="With --nl: only named factories (man_made=works and industrial=factory)",
    )
    p.add_argument(
        "--extra",
        action="store_true",
        help="With --nl: healthcare, industrial, commercial buildings, leisure and stays",
    )
    p.add_argument(
        "--gemeenten",
        action="store_true",
        help="Slower: one query per municipality (~350) instead of 12 provinces",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=6,
        metavar="N",
        help="Parallel gemeenten for --nl (default 6; try 3 if rate-limited)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if args.kvk_open:
        data = kvk_lookup(session, args.kvk_open)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(
            "\nKVK open dataset has NO company name, address, phone, email. "
            "Full register is paid: https://developers.kvk.nl/",
            file=sys.stderr,
        )
        return 0

    if args.public_offices and not (args.city or args.nl):
        print("error: --public-offices requires --city or --nl", file=sys.stderr)
        return 2

    po = args.public_offices
    parallel = not args.sequential_overpass
    rows: list[dict] = []
    if args.city:
        label = "public offices" if po else "city"
        print(f"[osm] {label}={args.city}", file=sys.stderr)
        rows = collect_city(session, args.city, args.timeout, public_offices_only=po)
    elif args.nl:
        if po:
            print("[osm] Netherlands public offices only", file=sys.stderr)
        if args.extra:
            rows = collect_extra(session, args.timeout, merge_main=True)
        elif args.gemeenten:
            rows = collect_nl_gemeente(
                session,
                args.timeout,
                public_offices_only=po,
                merge_main=True,
                resume=args.resume,
                wide_amenity=args.wide_amenity,
                parallel_parts=parallel,
                workers=args.workers,
            )
        else:
            rows = collect_nl(
                session,
                args.timeout,
                public_offices_only=po,
                factories_only=args.factories,
                merge_main=True,
                resume=args.resume,
                start_after=(args.after or "").strip().upper(),
            )

    if args.kvk_key and args.kvk_city:
        print(f"[kvk] paid search plaats={args.kvk_city}", file=sys.stderr)
        page = 1
        while page <= 100:
            data = kvk_search(session, args.kvk_key, args.kvk_city, page)
            for item in data.get("resultaten") or []:
                kvk = item.get("kvkNummer") or ""
                addr = item.get("adres") or {}
                binnen = addr.get("binnenlandsAdres") or addr
                address = ", ".join(
                    p
                    for p in (
                        f"{binnen.get('straatnaam', '')} {binnen.get('huisnummer', '')}".strip(),
                        f"{binnen.get('postcode', '')} {binnen.get('plaats', '')}".strip(),
                    )
                    if p
                )
                rows.append(
                    {
                        "company_name": item.get("naam") or "",
                        "industry": "",
                        "website": "",
                        "general_email": "",
                        "phone": "",
                        "business_address": address,
                        "kvk_number": kvk,
                        "source_url": f"https://www.kvk.nl/zoeken/?source=all&q={kvk}",
                        "verification_date": date.today().isoformat(),
                        "lat": "",
                        "lon": "",
                        "source": "kvk_api",
                    }
                )
            if not data.get("volgende") and page * 100 >= int(data.get("totaal") or 0):
                break
            page += 1
            time.sleep(1)

    if args.google_key:
        print(f"[places] {args.google_query}", file=sys.stderr)
        token = None
        for _ in range(3):
            data = places_search(session, args.google_key, args.google_query, token)
            for place in data.get("places") or []:
                loc = place.get("location") or {}
                types = place.get("types") or []
                rows.append(
                    {
                        "company_name": ((place.get("displayName") or {}).get("text") or ""),
                        "industry": types[0] if types else "",
                        "website": place.get("websiteUri") or "",
                        "general_email": "",
                        "phone": place.get("nationalPhoneNumber") or "",
                        "business_address": place.get("formattedAddress") or "",
                        "kvk_number": "",
                        "source_url": place.get("googleMapsUri") or "",
                        "verification_date": date.today().isoformat(),
                        "lat": str(loc.get("latitude") or ""),
                        "lon": str(loc.get("longitude") or ""),
                        "source": "google_places",
                    }
                )
            token = data.get("nextPageToken")
            if not token:
                break
            time.sleep(2)

    if args.enrich_emails:
        need = [r for r in rows if r.get("website") and not r.get("general_email")][: args.email_limit]
        print(f"[email] enriching {len(need)} sites", file=sys.stderr)
        for i, rec in enumerate(need, 1):
            enrich_email(session, rec, args.delay)
            if i % 25 == 0:
                print(f"[email] {i}/{len(need)}", file=sys.stderr)

    out = Path(args.out)
    write_csv(out, rows)
    write_sqlite(Path(args.sqlite), rows)

    with_email = sum(1 for r in rows if r.get("general_email"))
    with_web = sum(1 for r in rows if r.get("website"))
    with_phone = sum(1 for r in rows if r.get("phone"))
    print(f"rows={len(rows)} website={with_web} phone={with_phone} email={with_email} csv={out} sqlite={args.sqlite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
