from __future__ import annotations

import csv
import io
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from web.index_db import connect

FTS_TOKEN = re.compile(r"[A-Za-z0-9À-ÿ@.+'-]+")
CATEGORIES = [
    ("shop", "Shops"),
    ("office", "Offices"),
    ("public", "Government & NGOs"),
    ("food", "Food & drink"),
    ("health", "Health"),
    ("stay", "Stay"),
    ("craft", "Craft"),
    ("mobility", "Mobility"),
    ("amenity", "Services"),
    ("other", "Other"),
]

app = FastAPI(title="Handelskaart")
DB: sqlite3.Connection | None = None

# api/index.py is mounted at /api, so Vercel calls this app with /stats, not /api/stats.
_API_TAILS = (
    "/stats",
    "/cities",
    "/industries",
    "/search",
    "/points",
    "/bounds",
    "/company",
    "/export",
    "/health",
)


class RestoreApiPrefix:
    def __init__(self, asgi):
        self.asgi = asgi

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path") or "/"
            if any(path == tail or path.startswith(tail + "/") for tail in _API_TAILS):
                scope = dict(scope)
                scope["path"] = "/api" + path
                scope["raw_path"] = scope["path"].encode()
        await self.asgi(scope, receive, send)


app.add_middleware(RestoreApiPrefix)


@app.exception_handler(404)
async def show_path_on_404(request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "path": request.url.path,
            "root_path": request.scope.get("root_path") or "",
        },
    )


def db() -> sqlite3.Connection:
    global DB
    if DB is None:
        DB = connect()
    return DB


def fts_match(q: str) -> str | None:
    tokens = FTS_TOKEN.findall(q.strip())
    if not tokens:
        return None
    parts = []
    for t in tokens[:8]:
        clean = t.replace('"', "")
        if not clean:
            continue
        parts.append(f"{clean}*")
    return " AND ".join(parts) if parts else None


SORTS = {
    "contacts": "(c.has_website + c.has_email + c.has_phone) DESC, ltrim(c.company_name, '''\"& ') COLLATE NOCASE",
    "name": "ltrim(c.company_name, '''\"& ') COLLATE NOCASE",
    "city": "c.city COLLATE NOCASE, ltrim(c.company_name, '''\"& ') COLLATE NOCASE",
    "industry": "c.industry_label COLLATE NOCASE, ltrim(c.company_name, '''\"& ') COLLATE NOCASE",
}


def where_clause(
    q: str,
    city: str,
    category: str,
    industry: str,
    has_website: bool | None,
    has_email: bool | None,
    has_phone: bool | None,
    has_kvk: bool | None,
    bbox: str,
) -> tuple[str, list[Any], str]:
    clauses = ["1=1"]
    params: list[Any] = []
    join = ""
    match = fts_match(q) if q else None
    if match:
        join = "JOIN companies_fts ON companies_fts.rowid = c.id"
        clauses.append("companies_fts MATCH ?")
        params.append(match)
    if city:
        clauses.append("c.city = ?")
        params.append(city)
    if category:
        clauses.append("c.category = ?")
        params.append(category)
    if industry:
        clauses.append("c.industry = ?")
        params.append(industry)
    if has_website is True:
        clauses.append("c.has_website = 1")
    if has_email is True:
        clauses.append("c.has_email = 1")
    if has_phone is True:
        clauses.append("c.has_phone = 1")
    if has_kvk is True:
        clauses.append("c.has_kvk = 1")
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
            clauses.append("c.lat BETWEEN ? AND ? AND c.lon BETWEEN ? AND ?")
            params.extend([s, n, w, e])
        except ValueError:
            pass
    return " AND ".join(clauses), params, join


def row_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "company_name": r["company_name"],
        "industry": r["industry"],
        "industry_label": r["industry_label"],
        "category": r["category"],
        "website": r["website"],
        "general_email": r["general_email"],
        "phone": r["phone"],
        "business_address": r["business_address"],
        "city": r["city"],
        "kvk_number": r["kvk_number"],
        "source_url": r["source_url"],
        "verification_date": r["verification_date"],
        "lat": r["lat"],
        "lon": r["lon"],
        "source": r["source"],
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    from web.index_db import INDEX_DB, INDEX_GZ, prepare_index

    info: dict[str, Any] = {
        "gz": str(INDEX_GZ),
        "gz_exists": INDEX_GZ.exists(),
        "sqlite": str(INDEX_DB),
        "sqlite_exists": INDEX_DB.exists(),
    }
    try:
        path = prepare_index()
        info["db"] = str(path)
        info["rows"] = db().execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        info["ok"] = True
    except Exception as exc:  # noqa: BLE001
        info["ok"] = False
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    r = db().execute(
        """
        SELECT COUNT(*) n,
               SUM(has_website) web,
               SUM(has_phone) phone,
               SUM(has_email) email,
               SUM(has_kvk) kvk,
               SUM(CASE WHEN lat IS NOT NULL THEN 1 ELSE 0 END) geo
        FROM companies
        """
    ).fetchone()
    return {
        "total": r["n"],
        "website": r["web"],
        "phone": r["phone"],
        "email": r["email"],
        "kvk": r["kvk"],
        "geo": r["geo"],
        "categories": [{"id": i, "label": l} for i, l in CATEGORIES],
    }


@lru_cache(maxsize=1)
def _cities() -> list[dict[str, Any]]:
    rows = db().execute(
        """
        SELECT city, COUNT(*) n FROM companies
        WHERE city != ''
        GROUP BY city
        HAVING n >= 20
        ORDER BY n DESC
        """
    ).fetchall()
    return [{"name": r["city"], "n": r["n"]} for r in rows]


@app.get("/api/cities")
def cities(q: str = "") -> list[dict[str, Any]]:
    all_cities = _cities()
    if not q:
        return all_cities[:40]
    ql = q.lower()
    return [c for c in all_cities if ql in c["name"].lower()][:20]


@app.get("/api/industries")
def industries(category: str = "", city: str = "") -> list[dict[str, Any]]:
    sql = """
        SELECT industry, industry_label, category, COUNT(*) n
        FROM companies
        WHERE industry != ''
    """
    params: list[Any] = []
    if city:
        sql += " AND city = ?"
        params.append(city)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " GROUP BY industry, industry_label, category ORDER BY n DESC"
    rows = db().execute(sql, params).fetchall()
    return [
        {"id": r["industry"], "label": r["industry_label"], "category": r["category"], "n": r["n"]}
        for r in rows
    ]


@app.get("/api/search")
def search(
    q: str = "",
    city: str = "",
    category: str = "",
    industry: str = "",
    has_website: bool | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_kvk: bool | None = None,
    sort: str = "name",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
) -> dict[str, Any]:
    where, params, join = where_clause(
        q, city, category, industry, has_website, has_email, has_phone, has_kvk, ""
    )
    order = SORTS.get(sort, SORTS["name"])
    total = db().execute(f"SELECT COUNT(*) FROM companies c {join} WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * limit
    rows = db().execute(
        f"""
        SELECT c.* FROM companies c {join}
        WHERE {where}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total else 0,
        "results": [row_dict(r) for r in rows],
    }


@app.get("/api/points")
def points(
    bbox: str = "",
    q: str = "",
    city: str = "",
    category: str = "",
    industry: str = "",
    has_website: bool | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_kvk: bool | None = None,
    limit: int = Query(1800, ge=1, le=4000),
) -> dict[str, Any]:
    where, params, join = where_clause(
        q, city, category, industry, has_website, has_email, has_phone, has_kvk, bbox
    )
    where += " AND c.lat IS NOT NULL"
    rows = db().execute(
        f"""
        SELECT c.id, c.company_name, c.industry_label, c.category, c.lat, c.lon, c.city
        FROM companies c {join}
        WHERE {where}
        LIMIT ?
        """,
        [*params, limit + 1],
    ).fetchall()
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "truncated": truncated,
        "points": [
            {
                "id": r["id"],
                "name": r["company_name"],
                "label": r["industry_label"],
                "category": r["category"],
                "lat": r["lat"],
                "lon": r["lon"],
                "city": r["city"],
            }
            for r in rows
        ],
    }


@app.get("/api/bounds")
def bounds(
    q: str = "",
    city: str = "",
    category: str = "",
    industry: str = "",
    has_website: bool | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_kvk: bool | None = None,
) -> dict[str, Any]:
    where, params, join = where_clause(
        q, city, category, industry, has_website, has_email, has_phone, has_kvk, ""
    )
    r = db().execute(
        f"""
        SELECT MIN(c.lat) south, MAX(c.lat) north, MIN(c.lon) west, MAX(c.lon) east, COUNT(*) cnt
        FROM companies c {join}
        WHERE {where} AND c.lat IS NOT NULL
        """,
        params,
    ).fetchone()
    if not r or not r["cnt"]:
        return {"empty": True}
    return {
        "south": r["south"],
        "north": r["north"],
        "west": r["west"],
        "east": r["east"],
        "n": r["cnt"],
    }


@app.get("/api/company/{company_id}")
def company(company_id: int) -> dict[str, Any]:
    r = db().execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not r:
        return {"error": "not found"}
    return row_dict(r)


@app.get("/api/export")
def export_csv(
    q: str = "",
    city: str = "",
    category: str = "",
    industry: str = "",
    has_website: bool | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_kvk: bool | None = None,
) -> StreamingResponse:
    where, params, join = where_clause(
        q, city, category, industry, has_website, has_email, has_phone, has_kvk, ""
    )
    rows = db().execute(
        f"SELECT c.* FROM companies c {join} WHERE {where} ORDER BY c.company_name LIMIT 20000",
        params,
    )

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "company_name",
                "industry",
                "website",
                "general_email",
                "phone",
                "business_address",
                "kvk_number",
                "source_url",
                "verification_date",
            ]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for r in rows:
            w.writerow(
                [
                    r["company_name"],
                    r["industry"],
                    r["website"],
                    r["general_email"],
                    r["phone"],
                    r["business_address"],
                    r["kvk_number"],
                    r["source_url"],
                    r["verification_date"],
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=handelskaart.csv"},
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
