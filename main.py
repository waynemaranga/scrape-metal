"""scrape-metal CLI: sample -> master -> sections (Dlubal steel cross-section properties, metric).

    uv run main.py sample                      # master-table prototype from html/*.html
    uv run main.py master                      # categories + series from the API
    uv run main.py sections --series 25        # section properties for chosen series
    uv run main.py all                         # everything
"""

import argparse

import pendulum
import polars as pl
from bs4 import BeautifulSoup
from loguru import logger

from scrape_metal import DATA, HTML, log, sample, scrape, store
from scrape_metal.client import Client


def cmd_sample(args) -> None:
    files = sorted(HTML.glob("*.html"))
    if not files:
        raise SystemExit(f"no samples in {HTML}")
    for path in files:
        page = sample.parse_page(sample.unwrap_view_source(path))
        logger.info("{}: {} | {} | {}", path.name, page["title"], page["canonical"], page["js_calls"])
    # Every page carries the same shell, so one parse yields the master table and nav.
    soup = BeautifulSoup(sample.unwrap_view_source(files[0]), "html.parser")
    df = pl.DataFrame(sample.parse_series_list(soup), infer_schema_length=None)
    store.save(df, "master/sample_series")
    store.save(pl.DataFrame(sample.parse_categories(soup)), "master/sample_categories")
    logger.info("sample: {} series ({} valid, {} old), {} manufacturers, {} standards, unique ids: {}",
                df.height, df["is_valid"].sum(), (~df["is_valid"]).sum(), df["manufacturer"].drop_nulls().n_unique(),
                df["standard"].drop_nulls().n_unique(), df["series_id"].is_unique().all())


def cmd_master(args) -> None:
    client = Client(delay=args.delay)
    try:
        series = scrape.build_master(client, args.refresh)
    finally:
        client.close()
    sample_path = DATA / "master/sample_series.parquet"
    if sample_path.exists():
        scrape.cross_check(pl.read_parquet(sample_path), series)


def cmd_sections(args) -> None:
    series = store.load("series").collect()
    todo = series
    if args.series:
        todo = todo.filter(pl.col("series_id").is_in(args.series))
    if args.category:
        todo = todo.filter(pl.col("category_id").is_in(args.category))
    if args.valid_only:
        todo = todo.filter("is_valid")
    if args.limit:
        todo = todo.head(args.limit)
    client = Client(delay=args.delay)
    try:
        scrape.scrape_sections(client, series, set(todo["series_id"]), args.refresh, args.per_section)
    finally:
        client.close()


def cmd_all(args) -> None:
    cmd_sample(args)
    cmd_master(args)
    cmd_sections(args)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging on the console")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1.0)")
    p.add_argument("--refresh", action="store_true", help="re-fetch even if the raw cache exists")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="parse html/ samples into the master-table prototype")
    sub.add_parser("master", help="categories + series from the API")
    for name in ("sections", "all"):
        s = sub.add_parser(name, help="section properties" if name == "sections" else "sample + master + sections")
        s.add_argument("--series", type=int, nargs="+", help="series ids")
        s.add_argument("--category", type=int, nargs="+", help="category ids, e.g. 132 (I-beams)")
        s.add_argument("--limit", type=int, help="max series to fetch")
        s.add_argument("--valid-only", action="store_true", help="skip old (invalid) series")
        s.add_argument("--per-section", action="store_true",
                       help="if a series table fails, fetch its sections one by one (slow; e.g. series 243)")
    args = p.parse_args()

    log.setup("DEBUG" if args.verbose else "INFO")
    start = pendulum.now()
    {"sample": cmd_sample, "master": cmd_master, "sections": cmd_sections, "all": cmd_all}[args.cmd](args)
    logger.info("{} finished in {}", args.cmd, log.elapsed(start))


if __name__ == "__main__":
    main()
