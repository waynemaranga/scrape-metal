"""Read-only API over the scraped Parquet tables (never scrapes).

    uv run fastapi dev scrape_metal/api.py      # http://127.0.0.1:8000/docs
"""

import re

import polars as pl
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from scrape_metal import DATA
from scrape_metal.scrape import SECTION_META
from scrape_metal.store import pack_properties

app = FastAPI(title="scrape-metal", summary="Dlubal steel cross-section properties (metric units)")


class Category(BaseModel):
    category_id: int
    material_id: int
    material: str
    code: str
    name: str
    url: str
    series_count: int
    section_count: int


class Series(BaseModel):
    series_id: int
    name: str
    title: str
    description: str | None
    material_id: int
    material: str
    category_id: int
    category: str
    category_code: str
    shape: str | None
    standard: str | None
    manufacturer: str | None
    regions: list[str]
    manufacturing: str | None
    manufacturing_id: int | None
    is_valid: bool
    section_count: int
    order: int | None
    unit_system: str
    url: str
    image_url: str
    source: str
    scraped_at: str


class Section(BaseModel):
    section_id: int
    series_id: int
    category_id: int
    name: str
    full_name: str | None
    order: int | None
    url: str
    image_url: str
    scraped_at: str
    properties: dict[str, float | str | None] | None  # str for text params, e.g. buckling curve 'c'


class Parameter(BaseModel):
    category_id: int
    param_id: str
    branch: str
    branch_order: int
    order: int
    description: str | None
    symbol_html: str | None
    unit: str
    dtype: str  # "float" or "text"


def scan(name: str) -> pl.LazyFrame:
    path = DATA / f"{name}.parquet"
    if not path.exists():
        raise HTTPException(503, f"{path.name} not built yet - run `uv run main.py all`")
    return pl.scan_parquet(path)


def one(rows: list[dict], what: str) -> dict:
    if not rows:
        raise HTTPException(404, f"{what} not found")
    return rows[0]


def sections(lf: pl.LazyFrame) -> list[dict]:
    return pack_properties(lf.sort("series_id", "order").collect(), SECTION_META).to_dicts()


@app.get("/categories", response_model=list[Category])
def list_categories():
    return scan("categories").sort("category_id").collect().to_dicts()


@app.get("/series", response_model=list[Series])
def list_series(
    category_id: int | None = None,
    manufacturer: str | None = None,
    standard: str | None = None,
    shape: str | None = None,
    is_valid: bool | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """Text filters are case-insensitive substring matches."""
    lf = scan("series")
    if category_id is not None:
        lf = lf.filter(pl.col("category_id") == category_id)
    if is_valid is not None:
        lf = lf.filter(pl.col("is_valid") == is_valid)
    for col, text in {"manufacturer": manufacturer, "standard": standard, "shape": shape}.items():
        if text:
            lf = lf.filter(pl.col(col).str.contains(f"(?i){re.escape(text)}"))
    return lf.sort("category_id", "order").slice(offset, limit).collect().to_dicts()


@app.get("/series/{series_id}", response_model=Series)
def get_series(series_id: int):
    return one(scan("series").filter(pl.col("series_id") == series_id).collect().to_dicts(), f"series {series_id}")


@app.get("/series/{series_id}/sections", response_model=list[Section])
def get_series_sections(series_id: int):
    rows = sections(scan("sections").filter(pl.col("series_id") == series_id))
    if not rows:
        raise HTTPException(404, f"no sections for series {series_id}")
    return rows


@app.get("/sections/{section_id}", response_model=Section)
def get_section(section_id: int):
    return one(sections(scan("sections").filter(pl.col("section_id") == section_id)), f"section {section_id}")


@app.get("/parameters", response_model=list[Parameter])
def list_parameters(category_id: int | None = None):
    """The table-heads dictionary: what each property id means and its unit, per category."""
    lf = scan("parameters")
    if category_id is not None:
        lf = lf.filter(pl.col("category_id") == category_id)
    return lf.collect().to_dicts()
