"""Walk material -> category -> series -> sections through the API and shape the results with polars."""

import re
from collections import Counter

import pendulum
import polars as pl
from loguru import logger

from scrape_metal import store
from scrape_metal.client import Client, raw_path
from scrape_metal.log import elapsed

MATERIALS = {2: "Steel"}  # 8 = Timber
SITE = "https://www.dlubal.com/en/cross-section-properties/"
IMG = "https://external-crm.dlubal.com/cross-section-properties/images/meta/"
SECTION_META = ["section_id", "series_id", "category_id", "name", "full_name", "order", "url", "image_url", "scraped_at"]
SERIES_TABLE = "GetSeriesTableJson"
INFINITE: Counter[str] = Counter()  # param_id -> count of ±∞ values stored as null


# --- transforms ---------------------------------------------------------------------------------

def blank(value):
    """Dlubal uses '--' for 'none' (no manufacturer, no region, ...)."""
    return None if value in (None, "", "--") else value


def split_regions(region: str | None) -> list[str]:
    return [r.strip() for r in region.split(";")] if blank(region) else []


def norm_unit(unit: str | None) -> str:
    """'cm<sup>4</sup>' -> 'cm4', 'm<sup>2</sup>/m' -> 'm2/m', '--' -> '-' (dimensionless)."""
    return "-" if blank(unit) is None else re.sub(r"</?sup>", "", unit)


def clean_value(value, pid: str) -> str | None:
    """Raw property value -> stripped string, or None for '--' and '±∞' (alpha_pl of thin angles; JSON/DBs can't hold inf).
    Typing to float happens per column in type_params()."""
    if value is None:
        return None
    value = str(value).strip()
    if value.endswith("∞"):
        INFINITE[pid] += 1
        return None
    return blank(value)


def type_params(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, list[str]]]:
    """Cast every fully numeric property column to Float64; the rest (e.g. buckling curves 'a'..'d') stay text."""
    params = [c for c in df.columns if c not in SECTION_META]
    bad = df.select((pl.col(p).cast(pl.Float64, strict=False).is_null() & pl.col(p).is_not_null()).sum() for p in params).row(0)
    text = {p: df[p].drop_nulls().unique().sort().head(6).to_list() for p, n in zip(params, bad) if n}
    df = df.with_columns(pl.col([p for p in params if p not in text]).cast(pl.Float64))
    if text:
        logger.info("text-valued params kept as strings: {}", text)
    return df, text


def category_record(c: dict) -> dict:
    return {
        "category_id": c["id"],
        "material_id": c["sectionId"],
        "material": MATERIALS[c["sectionId"]],
        "code": c["name"],
        "name": c["description"],
        "url": SITE + c["url"],
    }


def series_record(s: dict, c: dict, scraped_at: str) -> dict:
    return {
        "series_id": s["id"],
        "name": s["name"],
        "title": s["title"],
        "description": blank(s["description"]),
        "material_id": c["sectionId"],
        "material": MATERIALS[c["sectionId"]],
        "category_id": c["id"],
        "category": c["description"],
        "category_code": c["name"],
        "shape": blank(s["shape"]),
        "standard": blank(s["standard"]),
        "manufacturer": blank(s["manufacturer"]),
        "regions": split_regions(s["region"]),
        "manufacturing": blank(s["manufacturingName"]),
        "manufacturing_id": s["manufacturingId"],
        "is_valid": s["isValid"],
        "section_count": s["count"] or 0,
        "order": s["order"],
        "unit_system": "metric",
        "url": SITE + s["url"],
        "image_url": f"{IMG}{s['id']}.png",
        "source": "dlubal",
        "scraped_at": scraped_at,
    }


def flatten_section(sec: dict, series_id: int, category_id: int, scraped_at: str, heads: dict) -> dict:
    """One wide row: section metadata + {param_id: float}. Collects the table heads into `heads`."""
    row = {
        "section_id": sec["id"],
        "series_id": series_id,
        "category_id": category_id,
        "name": sec["name"],
        "full_name": sec["fullName"],
        "order": sec["order"],
        "url": SITE + sec["url"],
        "image_url": f"{IMG}{series_id}-{sec['id']}.png",
        "scraped_at": scraped_at,
    }
    if sec.get("errorMsg"):
        logger.warning("section {} ({}) errorMsg: {}", sec["id"], sec["name"], sec["errorMsg"])
    for branch in sec.get("branches") or []:
        for p in branch["parameters"]:
            pid = p["id"]
            if pid in row:
                logger.error("param id {!r} collides with a column in section {}", pid, sec["id"])
                continue
            row[pid] = clean_value(p.get("valueJson") or p.get("value"), pid)
            head = {
                "category_id": category_id,
                "param_id": pid,
                "branch": branch["name"],
                "branch_order": branch["order"],
                "order": p["order"],
                "description": p["description"],
                "symbol_html": p["symbol"],
                "unit": norm_unit(p["unit"]),
            }
            seen = heads.setdefault((category_id, pid), head)
            if seen["unit"] != head["unit"]:
                logger.warning("unit mismatch for {} in category {}: {} vs {}", pid, category_id, seen["unit"], head["unit"])
    return row


# --- stages -------------------------------------------------------------------------------------

def build_master(client: Client, refresh: bool = False) -> pl.DataFrame:
    """material -> categories -> series. Saves categories + series; returns the series frame."""
    cats, series = [], []
    for material_id, material in MATERIALS.items():
        categories, _ = client.cached("GetCategoriesBySectionIdJson", material_id, refresh, id=material_id)
        logger.info("{}: {} categories", material, len(categories))
        for c in categories:
            data, fetched_at = client.cached("GetSeriesByCategoryIdJson", c["id"], refresh, id=c["id"])
            rows = [series_record(s, c, fetched_at) for s in data["series"]]
            sections = sum(r["section_count"] for r in rows)
            logger.info("  {:>4} {:<48} {:>4} series {:>7,} sections", c["id"], c["description"], len(rows), sections)
            cats.append(category_record(c) | {"series_count": len(rows), "section_count": sections})
            series += rows
    store.save(pl.DataFrame(cats), "categories")
    df = pl.DataFrame(series, infer_schema_length=None)
    store.save(df, "series")
    logger.info("master: {:,} series ({:,} valid), {:,} sections", df.height, df["is_valid"].sum(), df["section_count"].sum())
    return df


def cross_check(sample: pl.DataFrame, series: pl.DataFrame) -> None:
    """The HTML sample (category 132) must agree with the API master row for row."""
    cols = ["name", "standard", "manufacturer", "shape", "manufacturing", "is_valid", "url"]
    joined = sample.join(series.select("series_id", "regions", *cols), on="series_id", how="left", suffix="_api")
    missing = joined.filter(pl.col("name_api").is_null()).height
    joined = joined.with_columns(pl.col("regions", "regions_api").list.join(";"))
    diffs = {c: joined.filter(pl.col(c).ne_missing(pl.col(f"{c}_api"))).height for c in [*cols, "regions"]}
    bad = {c: n for c, n in diffs.items() if n}
    if missing or bad:
        logger.warning("sample vs API: {} of {} sample rows missing, mismatches {}", missing, sample.height, bad)
    else:
        logger.success("sample vs API: all {} sample rows match", sample.height)


def fetch_per_section(client: Client, s: dict, refresh: bool = False) -> tuple[dict, str]:
    """Fallback for a series whose metric table 500s server-side (e.g. 243, CHS GB/T 17395-2008).
    Section ids come from the imperial table (which works); values are fetched in metric one section at a time,
    then assembled and cached as the regular series table so later rebuilds need no special case."""
    sid, start = s["series_id"], pendulum.now()
    imperial, _ = client.cached(SERIES_TABLE, f"{sid}-imperial", refresh, id=sid, TableSectionDescOrder=False, unitType=2)
    stubs = imperial["seriesTable"]["sections"]
    logger.warning("series {} {}: metric table fails, fetching {} sections one by one", sid, s["title"], len(stubs))
    sections = []
    for i, stub in enumerate(stubs, 1):
        try:
            data, _ = client.cached("GetSeriesSectionJson", f"{sid}-{stub['id']}", refresh, seriesId=sid, sectionId=stub["id"], unitType=1)
        except RuntimeError as e:
            logger.error("section {} {} skipped: {}", stub["id"], stub["name"], e)
            continue
        sec = {k: v for k, v in data["section"].items() if k != "diagrams"}
        sections.append(sec | {"order": stub["order"]})  # the section endpoint reports order 0
        if i % 100 == 0:
            left = (pendulum.now() - start).total_seconds() / i * (len(stubs) - i)
            logger.info("series {} per-section: {}/{} (eta {})", sid, i, len(stubs), pendulum.duration(seconds=int(left)).in_words())
    params = {"id": sid, "unitType": 1, "assembled_from": "GetSeriesSectionJson"}
    return client.save(SERIES_TABLE, sid, {"seriesTable": {"id": sid, "sections": sections}}, params)


def scrape_sections(client: Client, series: pl.DataFrame, todo: set[int], refresh: bool = False,
                    per_section: bool = False) -> pl.DataFrame:
    """Fetch the series tables in `todo`, then rebuild all section outputs from every cached series table."""
    start = pendulum.now()
    rows, heads = [], {}
    fetch = [s for s in series.iter_rows(named=True) if s["series_id"] in todo and (refresh or not raw_path(SERIES_TABLE, s["series_id"]).exists())]
    logger.info("sections: {} series to fetch, {} requested", len(fetch), len(todo))
    fetch_ids = {s["series_id"] for s in fetch}
    done, failed = 0, []
    for s in series.iter_rows(named=True):
        sid = s["series_id"]
        if sid not in fetch_ids and not raw_path(SERIES_TABLE, sid).exists():
            continue
        try:
            data, fetched_at = client.cached(SERIES_TABLE, sid, sid in fetch_ids, id=sid, TableSectionDescOrder=False, unitType=1)
        except RuntimeError as e:  # one bad series (e.g. server 500) must not sink the run
            if not per_section:
                logger.error("series {} {} ({} sections) skipped: {}", sid, s["title"], s["section_count"], e)
                failed.append(sid)
                continue
            data, fetched_at = fetch_per_section(client, s, refresh)
        secs = data["seriesTable"]["sections"] or []
        rows += [flatten_section(sec, sid, s["category_id"], fetched_at, heads) for sec in secs]
        if len(secs) != s["section_count"]:
            logger.warning("series {} {}: {} sections, master says {}", sid, s["name"], len(secs), s["section_count"])
        if sid in fetch_ids:
            done += 1
            left = (pendulum.now() - start).total_seconds() / done * (len(fetch) - done)
            logger.info("[{}/{}] {} {} -> {} sections (eta {})", done, len(fetch), sid, s["title"], len(secs),
                        pendulum.duration(seconds=int(left)).in_words() if left >= 1 else "-")
    if not rows:
        logger.warning("no series tables cached yet - nothing to save")
        return pl.DataFrame()

    df, text = type_params(pl.DataFrame(rows, infer_schema_length=None))
    store.save(df, "sections", json=False)
    store.save_series_sections(df, SECTION_META)
    params = pl.DataFrame(list(heads.values())).sort("category_id", "branch_order", "order")
    dtype = pl.when(pl.col("param_id").is_in(list(text))).then(pl.lit("text")).otherwise(pl.lit("float"))
    store.save(params.with_columns(dtype.alias("dtype")), "parameters")
    check(df, series)
    if failed:
        logger.error("{} series failed; retry with `uv run main.py sections --series {} --per-section`",
                     len(failed), " ".join(map(str, failed)))
    logger.success("sections done in {} ({} requests, {:,} sections, {} param columns)",
                   elapsed(start), client.calls, df.height, df.width - len(SECTION_META))
    return df


def check(df: pl.DataFrame, series: pl.DataFrame) -> None:
    dupes = df["section_id"].is_duplicated().sum()
    covered = series.filter(pl.col("series_id").is_in(df["series_id"].unique().implode()))
    expected = covered["section_count"].sum()
    level = "SUCCESS" if df.height == expected and not dupes else "WARNING"
    logger.log(level, "check: {:,} sections for {} series (master expects {:,}), {} duplicate section ids",
               df.height, covered.height, expected, dupes)
    if INFINITE:
        logger.info("check: {:,} infinite values stored as null: {}", INFINITE.total(), dict(INFINITE.most_common()))
