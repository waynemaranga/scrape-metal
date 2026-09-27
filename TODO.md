# TODO

## Recon
- [x] Unwrap the view-source samples (`html/T1–T3`); map the hierarchy material → category → series → section
- [x] Find the data source: the JSON API on `external-crm.dlubal.com` (flag + origin-only Referer)
- [x] Inventory the categories, counts and unique table heads (189 param ids) → `LAYOUT.md`
- [x] Check robots.txt (no restrictions)

## Master
- [x] Master-table prototype from the HTML sample → `data/master/sample_series`
- [x] Full master from the API → `data/categories`, `data/series` (1,091 steel series)
- [x] Cross-check the sample against the API (256/256 match)

## Sections
- [x] Series table → wide `data/sections.parquet` + `data/sections/{series_id}.json`
- [x] Parameters dictionary → `data/parameters`
- [x] Spot-check section 510 (UKB 1016x305x487)
- [x] Full steel run: 1,090 of 1,091 series, 92,271 sections, 0 duplicates, counts match the master
- [ ] Series 243 (CHS GB/T 17395-2008, 3,198 sections): metric table 500s server-side, so recover with `--per-section`

## API
- [x] FastAPI read API over the Parquet files (`uv run fastapi dev scrape_metal/api.py`)

## Later
- [ ] Load into the DB of choice (Postgres JSONB / Mongo): `series.json` + `sections/*.json` + `parameters.json`
- [ ] Split `standard` into a list: some series carry several standards, `;`-joined (like `regions`)
- [ ] Timber (material 8): add `8: "Timber"` to `MATERIALS` in `scrape_metal/scrape.py`
- [ ] Per-section SVG drawings via `GetSeriesSectionJson` (~95k extra calls) if links stop being enough
- [ ] Imperial units (`unitType=2`) if needed
- [ ] Scheduled refresh (`--refresh`) and diffing against the previous run
