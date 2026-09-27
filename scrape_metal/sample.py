"""Parse the saved Chrome view-source samples in html/ into the master-table prototype.

Every page on the site shares one server shell: the only server-rendered table is
`table.series-list` (I-Beams, category 132). Everything else is filled in by JS from the API.
"""

import html
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

SITE = "https://www.dlubal.com/en/cross-section-properties/"
_CELL = re.compile(r'<td class="line-content">(.*?)</td>', re.S)
_TAG = re.compile(r"<[^>]+>")
_JS_CALL = re.compile(r"urlDirection\.(\w+\([^)]*\))")


def unwrap_view_source(path: Path) -> str:
    """Rebuild the original page source from a Chrome 'view-source:' save."""
    raw = path.read_text(encoding="utf-8")
    return "\n".join(html.unescape(_TAG.sub("", cell)) for cell in _CELL.findall(raw))


def _text(node: Tag | None) -> str | None:
    return " ".join(node.get_text(" ").split()) if node else None


def _blank(value: str | None) -> str | None:
    return None if value in (None, "", "--") else value


def parse_page(src: str) -> dict:
    """Page identity: title, canonical URL and the trailing urlDirection JS calls (carry category/series/section ids)."""
    head = BeautifulSoup(src[: src.find("</head>")], "html.parser")
    canonical = head.find("link", rel="canonical")
    return {
        "title": _text(head.title),
        "canonical": canonical["href"] if canonical else None,
        "js_calls": [" ".join(c.split()) for c in _JS_CALL.findall(src[-5000:])],
    }


def parse_series_list(soup: BeautifulSoup) -> list[dict]:
    """Rows of the server-rendered master table (same field names as scrape.series_record)."""
    rows = []
    for tr in soup.select("table.series-list > tbody > tr"):
        region = tr.select_one("td.tsl-region")
        regions = _blank(region.get("title") if region else None)
        rows.append({
            "series_id": int(tr["series-id"]),
            "category_id": int(tr["category-id"]),
            "material_id": int(tr["section-id"]),
            "name": _text(tr.select_one(".series-name")),
            "standard": _blank(_text(tr.select_one("td.tsl-standard"))),
            "manufacturer": _blank(_text(tr.select_one("td.tsl-manufacturer"))),
            "regions": regions.split(";") if regions else [],
            "shape": _blank(_text(tr.select_one("td.tsl-shape"))),
            "manufacturing": _blank(_text(tr.select_one("td.tsl-manufacturing"))),
            "is_valid": "invalid" not in tr.get("class", []),
            "url": SITE + tr["url"],
        })
    return rows


def parse_categories(soup: BeautifulSoup) -> list[dict]:
    """Material tabs (Steel/Timber) and the shape-category nav of the shell."""
    materials = {int(li["section-id"]): _text(li) for li in soup.select("ul.section-sub > li")}
    return [
        {
            "category_id": int(li["category-id"]),
            "material_id": int(li["section-id"]),
            "material": materials.get(int(li["section-id"])),
            "code": li.img["alt"] if li.img else None,
            "name": li["title"],
            "url": SITE + li["url"],
        }
        for li in soup.select("ul.section__categories-select > li")
    ]
