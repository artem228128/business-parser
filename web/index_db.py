from __future__ import annotations

import gzip
import os
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "netherlands.sqlite"
INDEX_DB = ROOT / "data" / "handelskaart.sqlite"
INDEX_GZ = ROOT / "data" / "handelskaart.sqlite.gz"

POSTCODE = re.compile(r"^\d{4}\s?[A-Z]{2}$", re.I)

CITY_ALIAS = {
    "'s-gravenhage": "Den Haag",
    "s-gravenhage": "Den Haag",
    "'s-hertogenbosch": "Den Bosch",
    "s-hertogenbosch": "Den Bosch",
}

FOOD = {
    "restaurant",
    "cafe",
    "fast_food",
    "bar",
    "pub",
    "biergarten",
    "food_court",
    "ice_cream",
}
HEALTH = {"pharmacy", "clinic", "dentist", "doctors", "veterinary", "hospital"}
MOBILITY = {
    "fuel",
    "car_rental",
    "car_wash",
    "car_sharing",
    "charging_station",
    "taxi",
    "boat_rental",
    "bicycle_rental",
}

PUBLIC_OFFICE_TYPES = frozenset(
    {"government", "diplomatic", "ngo", "association", "political_party", "religion"}
)


def city_from(addr: str) -> str:
    if not addr:
        return ""
    tail = addr.rsplit(",", 1)[-1].strip()
    parts = tail.split()
    while parts and POSTCODE.match(parts[0]):
        parts.pop(0)
    city = " ".join(parts).strip(" ,")
    key = city.lower().lstrip("'")
    return CITY_ALIAS.get(city.lower(), CITY_ALIAS.get(key, city))


STAY_TOURISM = {
    "hotel",
    "motel",
    "guest_house",
    "hostel",
    "apartment",
    "chalet",
    "camp_site",
    "caravan_site",
}


def category_of(industry: str) -> str:
    kind, _, val = (industry or "").partition(":")
    if kind == "shop":
        return "shop"
    if kind == "office":
        if val in PUBLIC_OFFICE_TYPES:
            return "public"
        return "office"
    if kind == "craft":
        return "craft"
    if kind == "healthcare":
        return "health"
    if kind in {"industrial", "man_made", "building"}:
        return "other"
    if kind == "leisure":
        if val in {"fitness_centre", "sports_centre", "spa", "swimming_pool", "ice_rink"}:
            return "health"
        return "amenity"
    if kind == "tourism":
        return "stay" if val in STAY_TOURISM else "amenity"
    if kind == "amenity":
        if val in FOOD:
            return "food"
        if val in HEALTH:
            return "health"
        if val in MOBILITY:
            return "mobility"
        return "amenity"
    return "other"


def humanize(industry: str) -> str:
    if not industry:
        return ""
    _, _, val = industry.partition(":")
    return (val or industry).replace("_", " ")


def needs_rebuild() -> bool:
    if not SOURCE_DB.exists():
        return False
    if not INDEX_DB.exists():
        return True
    return INDEX_DB.stat().st_mtime < SOURCE_DB.stat().st_mtime


def rebuild() -> Path:
    INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
    if INDEX_DB.exists():
        INDEX_DB.unlink()

    src = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(INDEX_DB)
    dst.execute("PRAGMA journal_mode=WAL")
    dst.execute("PRAGMA synchronous=NORMAL")
    dst.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT NOT NULL,
            industry TEXT,
            industry_label TEXT,
            category TEXT,
            website TEXT,
            general_email TEXT,
            phone TEXT,
            business_address TEXT,
            city TEXT,
            kvk_number TEXT,
            source_url TEXT UNIQUE,
            verification_date TEXT,
            lat REAL,
            lon REAL,
            source TEXT,
            has_website INTEGER,
            has_email INTEGER,
            has_phone INTEGER,
            has_kvk INTEGER
        );
        CREATE INDEX idx_city ON companies(city);
        CREATE INDEX idx_cat ON companies(category);
        CREATE INDEX idx_industry ON companies(industry);
        CREATE INDEX idx_geo ON companies(lat, lon);
        CREATE INDEX idx_email ON companies(has_email);
        CREATE INDEX idx_phone ON companies(has_phone);
        CREATE INDEX idx_web ON companies(has_website);
        CREATE VIRTUAL TABLE companies_fts USING fts5(
            company_name,
            industry_label,
            business_address,
            city,
            general_email,
            website,
            content='companies',
            content_rowid='id',
            tokenize='unicode61'
        );
        """
    )

    rows = src.execute("SELECT * FROM businesses").fetchall()
    payload = []
    for i, row in enumerate(rows, 1):
        lat = lon = None
        try:
            lat = float(row["lat"]) if row["lat"] else None
            lon = float(row["lon"]) if row["lon"] else None
        except ValueError:
            lat = lon = None
        industry = row["industry"] or ""
        city = city_from(row["business_address"] or "")
        payload.append(
            (
                i,
                row["company_name"] or "",
                industry,
                humanize(industry),
                category_of(industry),
                row["website"] or "",
                row["general_email"] or "",
                row["phone"] or "",
                row["business_address"] or "",
                city,
                row["kvk_number"] or "",
                row["source_url"] or "",
                row["verification_date"] or "",
                lat,
                lon,
                row["source"] or "",
                1 if row["website"] else 0,
                1 if row["general_email"] else 0,
                1 if row["phone"] else 0,
                1 if row["kvk_number"] else 0,
            )
        )

    dst.executemany(
        """
        INSERT INTO companies (
            id, company_name, industry, industry_label, category, website,
            general_email, phone, business_address, city, kvk_number, source_url,
            verification_date, lat, lon, source, has_website, has_email, has_phone, has_kvk
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        payload,
    )
    dst.execute(
        """
        INSERT INTO companies_fts(
            rowid, company_name, industry_label, business_address, city, general_email, website
        )
        SELECT id, company_name, industry_label, business_address, city, general_email, website
        FROM companies
        """
    )
    dst.execute("ANALYZE")
    dst.commit()
    src.close()
    dst.close()
    return INDEX_DB


def prepare_index() -> Path:
    if needs_rebuild():
        rebuild()
        return INDEX_DB
    if INDEX_DB.exists() and not os.environ.get("VERCEL"):
        return INDEX_DB
    if INDEX_GZ.exists():
        tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "handelskaart.sqlite"
        if not tmp.exists() or tmp.stat().st_mtime < INDEX_GZ.stat().st_mtime:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(INDEX_GZ, "rb") as src, tmp.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        return tmp
    if INDEX_DB.exists():
        return INDEX_DB
    raise FileNotFoundError("missing data/handelskaart.sqlite or .sqlite.gz")


def connect() -> sqlite3.Connection:
    path = prepare_index()
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con
