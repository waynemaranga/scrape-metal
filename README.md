# scrape-metal

Scrapes steel cross-section properties (metric) from [Dlubal's cross-section library](https://www.dlubal.com/en/cross-section-properties). Results are saved as polars Parquet and JSON and served by a small FastAPI read API. See [LAYOUT.md](LAYOUT.md) for the site map, [TODO.md](TODO.md) for open work and [CHANGELOG.md](CHANGELOG.md) for history.

```sh
uv run main.py sample                         # master-table prototype from html/*.html
uv run main.py master                         # categories + series from the API
uv run main.py sections --series 25           # one series (or --category 132, --limit N, --valid-only)
uv run main.py sections                       # all steel series (resumable, ~20 min at 1 req/s)
uv run fastapi dev scrape_metal/api.py        # http://127.0.0.1:8000/docs
```

## Output (`data/`)

| File | Contents |
|---|---|
| `categories.{parquet,json}` | the 14 steel shape categories |
| `series.{parquet,json}` | master list: one row per series (standard, manufacturer, regions, manufacturing, is_valid, links) |
| `sections/{series_id}.json` | list of sections per series, with numeric `properties` |
| `sections.parquet` | all sections, wide: metadata + one Float64 column per property |
| `parameters.{parquet,json}` | table-heads dictionary: property id → branch, description, symbol, unit, per category |
| `raw/` | gzip cache of the raw API responses (resume/rebuild without re-fetching) |

Logs are written to `logs/{run_id}.log`.
