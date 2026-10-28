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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
MAIN_SQLITE = ROOT / "data" / "netherlands.sqlite"
MAIN_CSV = ROOT / "data" / "netherlands.csv"

OVERPASS_ENDPOINTS = [
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

BUSINESS_AMENITIES = {
    "restaurant",
    "cafe",
    "fast_food",
    "bar",
    "pub",
    "biergarten",
    "food_court",
    "ice_cream",
    "pharmacy",
    "bank",
    "atm",
    "bureau_de_change",
    "clinic",
    "dentist",
    "doctors",
    "veterinary",
    "hospital",
    "studio",
    "theatre",
    "cinema",
    "nightclub",
    "casino",
    "brothel",
    "stripclub",
    "gambling",
    "internet_cafe",
    "coworking_space",
    "conference_centre",
    "events_venue",
    "marketplace",
    "fuel",
    "car_rental",
    "car_wash",
    "car_sharing",
    "charging_station",
    "taxi",
    "boat_rental",
    "bicycle_rental",
    "bicycle_repair_station",
    "post_office",
    "parcel_locker",
    "money_transfer",
    "insurance",
    "lawyer",
    "notary",
    "accountant",
    "estate_agent",
    "employment_agency",
    "travel_agency",
    "copy_shop",
    "photo_booth",
    "salon",
    "hairdresser",
    "beauty",
    "spa",
    "massage",
    "tattoo",
    "laundry",
    "dry_cleaning",
    "childcare",
    "kindergarten",
    "language_school",
    "driving_school",
    "music_school",
    "prep_school",
    "training",
}

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
    for key in ("office", "shop", "craft", "tourism", "amenity", "healthcare"):
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
    if tags.get("shop") or tags.get("craft"):
        return True
    if office and office not in PUBLIC_OFFICE_TYPES:
        return True
    if tags.get("tourism") in {"hotel", "motel", "guest_house", "hostel", "apartment", "chalet"}:
        return True
    amenity = tags.get("amenity")
    if amenity in BUSINESS_AMENITIES:
        return True
    if tags.get("company"):
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


def overpass_query(area_filter: str, timeout: int, *, public_offices_only: bool = False) -> str:
    if public_offices_only:
        body = f'  nwr["office"~"{PUBLIC_OFFICE_OVERPASS}"]["name"](area.a);'
    else:
        body = """
  nwr["shop"]["name"](area.a);
  nwr["office"]["name"](area.a);
  nwr["craft"]["name"](area.a);
  nwr["company"]["name"](area.a);
  nwr["tourism"~"hotel|motel|guest_house|hostel"]["name"](area.a);
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


def fetch_overpass(query: str, session: requests.Session) -> list[dict]:
    last_err = None
    for url in OVERPASS_ENDPOINTS:
        for attempt in range(4):
            try:
                r = session.post(url, data={"data": query}, timeout=300)
                if r.status_code in {429, 504, 502, 503}:
                    time.sleep(20 * (attempt + 1))
                    continue
                r.raise_for_status()
                payload = r.json()
                return payload.get("elements") or []
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(8 * (attempt + 1))
        time.sleep(3)
    raise RuntimeError(f"Overpass failed: {last_err}")


def collect_area(
    session: requests.Session,
    area_ql: str,
    timeout: int,
    *,
    public_offices_only: bool = False,
) -> list[dict]:
    verified = date.today().isoformat()
    elements = fetch_overpass(
        overpass_query(area_ql, timeout, public_offices_only=public_offices_only),
        session,
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


def collect_nl(session: requests.Session, timeout: int, *, public_offices_only: bool = False) -> list[dict]:
    all_rows: list[dict] = []
    for iso, name in NL_PROVINCES.items():
        print(f"[osm] {name} ({iso})", file=sys.stderr)
        ql = f'area["ISO3166-2"="{iso}"]->.a;'
        rows = collect_area(session, ql, timeout, public_offices_only=public_offices_only)
        print(f"[osm] {name}: {len(rows)}", file=sys.stderr)
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


def merge_into_main(rows: list[dict]) -> tuple[int, int]:
    """Upsert into data/netherlands.sqlite and .csv. Returns (sqlite_total, batch_size)."""
    if not rows:
        return 0, 0
    write_sqlite(MAIN_SQLITE, rows)
    total = merge_csv(MAIN_CSV, rows)
    return total, len(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect NL businesses from OSM (open). Optional paid KVK / Google Places.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--city", help="Dutch municipality name as in OSM, e.g. Amsterdam, Haarlem")
    g.add_argument("--nl", action="store_true", help="All 12 provinces via OSM (large, slow, incomplete vs KVK)")
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
    rows: list[dict] = []
    if args.city:
        label = "public offices" if po else "city"
        print(f"[osm] {label}={args.city}", file=sys.stderr)
        rows = collect_city(session, args.city, args.timeout, public_offices_only=po)
    elif args.nl:
        if po:
            print("[osm] Netherlands public offices only", file=sys.stderr)
        rows = collect_nl(session, args.timeout, public_offices_only=po)

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

    if po and args.nl and rows:
        main_total, batch = merge_into_main(rows)
        print(
            f"[main] merged {batch} public offices into {MAIN_SQLITE} (total ~{main_total} rows in csv)",
            file=sys.stderr,
        )

    with_email = sum(1 for r in rows if r.get("general_email"))
    with_web = sum(1 for r in rows if r.get("website"))
    with_phone = sum(1 for r in rows if r.get("phone"))
    print(f"rows={len(rows)} website={with_web} phone={with_phone} email={with_email} csv={out} sqlite={args.sqlite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
