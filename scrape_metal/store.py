"""Polars-first persistence: every table is a DataFrame, written to Parquet (canonical) then JSON (export)."""

import polars as pl
from loguru import logger

from scrape_metal import DATA


def save(df: pl.DataFrame, name: str, json: bool = True) -> None:
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path.with_suffix(".parquet"))
    if json:
        df.write_json(path.with_suffix(".json"))
    logger.info("saved {:,} rows x {} cols -> data/{}.{}", df.height, df.width, name, "{parquet,json}" if json else "parquet")


def load(name: str) -> pl.LazyFrame:
    return pl.scan_parquet(DATA / f"{name}.parquet")


def pack_properties(df: pl.DataFrame, meta: list[str]) -> pl.DataFrame:
    """Wide section rows -> meta columns + a `properties` struct, dropping params that are all-null here."""
    params = [c for c in df.columns if c not in meta]
    counts = df.select(pl.col(params).null_count()).row(0) if params else ()
    keep = [p for p, nulls in zip(params, counts) if nulls < df.height]
    props = pl.struct(keep) if keep else pl.lit(None)
    return df.select(*[c for c in meta if c in df.columns], props.alias("properties"))


def save_series_sections(df: pl.DataFrame, meta: list[str]) -> None:
    """One JSON per series at data/sections/<series_id>.json: a list of sections with nested properties."""
    out = DATA / "sections"
    out.mkdir(parents=True, exist_ok=True)
    parts = df.partition_by("series_id", as_dict=True, maintain_order=True)
    for (series_id,), part in parts.items():
        pack_properties(part.sort("order"), meta).write_json(out / f"{series_id}.json")
    logger.info("saved {:,} series JSON files -> data/sections/", len(parts))
