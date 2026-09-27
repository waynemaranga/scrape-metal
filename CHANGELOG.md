# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-09-27

### Added
- `scrape_metal/sample.py` rebuilds the page source from the Chrome view-source samples. It parses the server-rendered `table.series-list` (the I-Beams master table) and the category nav.
- `scrape_metal/client.py` is an httpx client for the Dlubal JSON API. It throttles to 1 req/s, retries with backoff, and keeps a gzip raw cache under `data/raw/` for resume and rebuild.
- `scrape_metal/scrape.py` walks steel from material → categories → series → sections.
  - Values come out as metric floats.
  - Units are normalized (`cm<sup>4</sup>` → `cm4`, `--` → `-`), and `--` becomes null.
  - Regions are split into lists.
  - The parameter (table-heads) dictionary is built per category.
  - Output is checked for section counts and duplicate IDs.
- `scrape_metal/store.py` saves everything polars-first: Parquet (canonical) then JSON. It writes per-series section JSON with nested `properties`.
- `scrape_metal/api.py` is a FastAPI read API: `/categories`, `/series`, `/series/{id}`, `/series/{id}/sections`, `/sections/{id}`, `/parameters`.
- `scrape_metal/log.py` sets up loguru with a pendulum run ID: a console sink plus a UTF-8 file sink at `logs/{run_id}.log`, with elapsed time and ETA in words.
- `main.py` is the CLI: `sample | master | sections | all`.
- `LAYOUT.md` holds the recon map; `TODO.md` holds the checklist.
- Dependencies: `httpx`, `fastapi[standard]`.

### Notes
- Only the origin may be sent as `Referer`. A Referer with a path, or a missing `X-Requested-With` flag, gets a 302.
- Dlubal reports `+∞` for some plastic shape factors (`alpha_pl_*`, mainly angles and bars). These are stored as null, because JSON and databases can't hold infinity, and counted in one summary log line.
- Some properties are text, e.g. the buckling curve `BC_BS_y` = `a`–`d`. Columns are typed per property by polars: fully numeric columns become Float64, and the rest stay String. `parameters.dtype` records which (`float` or `text`).
- A series that keeps failing is logged, skipped and listed at the end, and the run continues. Series 243 (CHS GB/T 17395-2008, 3,198 sections) returns HTTP 500 for metric (`unitType=1`) but works in imperial. This is a server-side bug.
- `sections --per-section`: for a failing series, take the section ids from the imperial table and fetch each section in metric via `GetSeriesSectionJson`. The assembled result is cached as a normal series table, so later rebuilds need no special case. This recovers series 243.
