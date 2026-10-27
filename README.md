# Handelskaart

Searchable atlas of Dutch businesses from OpenStreetMap. FastAPI + SQLite + a map UI.

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn web.app:app --reload --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Rebuild the search index from `data/netherlands.sqlite`:

```bash
PYTHONPATH=. python -c "from web.index_db import rebuild; rebuild()"
gzip -9 -k data/handelskaart.sqlite
```

## Vercel

Repo is ready for [Vercel](https://vercel.com):

1. Import [github.com/artem228128/business-parser](https://github.com/artem228128/business-parser).
2. Framework preset: **Other**.
3. Deploy. No env vars.

The Python function serves `/api/*` and the static UI. The SQLite index is shipped as `data/handelskaart.sqlite.gz` and unpacked to `/tmp` on cold start.

CLI:

```bash
npx vercel
```
