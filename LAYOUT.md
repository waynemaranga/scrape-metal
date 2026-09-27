# Dlubal cross-section properties: site layout and recon map

## Hierarchy (link chain)

```
Standardized ─┬─ material (section-id) 2 Steel  ── 14 shape categories (132 … 172)
              └─ material (section-id) 8 Timber ── 144, 145   (out of scope for now)
                   └─ series   (series-id)   e.g. 25  "Advance UKB | BS 4-1:2005 | Tata Steel"
                        └─ section (section id) e.g. 510 "UKB 1016x305x487"
```

| Level | Page URL (`https://www.dlubal.com/en/cross-section-properties/…`) | Sample |
|---|---|---|
| Library | *(root)*; filters: Region, Manufacturer, Standard, Shape | |
| Category (shape) | `{category.url}`, e.g. `i-beams-h-beams` | `html/T1.html` |
| Series | `series-{slug}`, e.g. `series-advance-ukb-bs-4-1-2005-tata-steel` | `html/T2.html` |
| Section | `{slug}`, e.g. `ukb-1016x305x487-bs-4-1-2005-tata-steel` | `html/T3.html` |

The 14 steel categories:

| id | Category | code | url | series | sections |
|---|---|---|---|---|---|
| 132 | I-Beams, H-Beams | `I_S` | `i-beams-h-beams` | 256 | 12,162 |
| 133 | U-Sections, Steel Channels | `U_S` | `u-sections-steel-channels` | 203 | 5,690 |
| 134 | T-Sections, Steel Tees | `T_S` | `t-sections-steel-tees` | 66 | 3,651 |
| 135 | L-Sections, Steel Angles | `L_S` | `l-sections-steel-angles` | 114 | 4,907 |
| 172 | 2L-Sections, Steel Double Angles | `2L_S` | `2l-sections-steel-double-angles` | 18 | 5,124 |
| 136 | 60 Degree Angles | `L60_S` | `60-degree-angles` | 1 | 13 |
| 137 | Square and Rectangular Hollow Sections | `RHS_S` | `square-and-rectangular-hollow-sections` | 121 | 18,721 |
| 138 | Circular Hollow Sections, Pipes | `CHS_S` | `circular-hollow-sections-pipes` | 108 | 29,901 |
| 139 | Elliptical and Semi-Elliptical Hollow Sections | `EHS_S` | `elliptical-and-semi-elliptical-hollow-sections` | 10 | 326 |
| 140 | Z-Sections, Steel Zees | `Z_S` | `z-sections-steel-zees` | 36 | 1,117 |
| 141 | Rail Sections | `RAIL_S` | `rail-sections` | 24 | 86 |
| 142 | Sheets | `SHEET_S` | `sheets` | 53 | 2,068 |
| 143 | Bar Sections | `BAR_S` | `bar-sections` | 79 | 6,489 |
| 171 | Virtual Joists and Virtual Joist Girders | `VIRTUAL_S` | `virtual-joists-and-virtual-joist-girders` | 2 | 5,214 |

The steel total is **1,091 series (881 valid) and 95,469 sections** (as of 2026-09-27).

## What the HTML contains

- **The samples are Chrome `view-source:` saves.** The page source is HTML-escaped inside `<td class="line-content">`, and entities are double-encoded (`&#x27;`, `&#xD6;`). `scrape_metal/sample.py` unwraps them.
- **Every page returns the same server shell.** The pages differ only in `<title>`, meta/canonical, `og:image` and the trailing JS call:
  - T1: `urlDirection.ChangeUrl('i-beams-h-beams', 'I-Beams, H-Beams')`
  - T2: `urlDirection.StandardizedTableUrl()`
  - T3: `urlDirection.StandardizedSeriesSectionUrl(132, 25, 510)`, i.e. (category, series, section)
- **The only server-rendered table is `table.series-list`,** the master list for I-Beams (category 132). It has 256 rows; 71 carry `class="invalid hidden"` and are old series.
  - `<tr series-id category-id section-id url>`
  - `td.tsl-series .series-name`: Series
  - `td.tsl-standard`: Standard
  - `td.tsl-manufacturer`: Manufacturer (`--` = none)
  - `td.tsl-region[title]`: Region(s), `;`-separated
  - `td.tsl-shape`: Shape
  - `td.tsl-manufacturing`: Manufacturing Type
- **The navigation provides the IDs:**
  - `ul.section-sub > li[section-id]`: materials
  - `ul.section__categories-select > li[category-id][url][title]`: categories
  - `#UnitTypeSelect [unit-type]`: 1 = Metric, 2 = Imperial
- **The series table and section modal are empty templates** that JS fills from the JSON API.

## JSON API

The base URL is `https://external-crm.dlubal.com/cross-section-properties/en/websections/`. Two things are required, otherwise the server answers 302 to the landing page:
- the query flag `X-Requested-With=XMLHttpRequest`;
- a `Referer` of exactly `https://www.dlubal.com/` (origin only).

No cookies or auth are needed.

| Endpoint | Params | Used for |
|---|---|---|
| `GetCategoriesBySectionIdJson` | `id` (material) | categories |
| `GetSeriesByCategoryIdJson` | `id` (category) | series list: 22 fields incl. `isValid`, `count`, `manufacturingName` |
| `GetSeriesTableJson` | `id`, `TableSectionDescOrder=false`, `unitType=1` | **all sections of a series with every property** |
| `GetSeriesSectionJson` | `seriesId`, `sectionId`, `unitType` | one section plus `output.outputSvg` (not used: SVGs are links only) |
| `GetSeriesPreviewImageJson` | `id` | series preview SVG (not used) |

Also unused: the `GetMultiple*`, `*Pdf` and `GetParametric*` endpoints, and `GetSearchParts`.

**Images.** These are free links, no API call needed:
- `https://external-crm.dlubal.com/cross-section-properties/images/meta/{series}.png`
- `https://external-crm.dlubal.com/cross-section-properties/images/meta/{series}-{section}.png`

**robots.txt.**
- `www.dlubal.com` has `User-agent: *` with no Disallow rules, only sitemaps.
- `external-crm.dlubal.com` has none (404).

## Section properties (table heads)

`sections[].branches[].parameters[]` looks like `{id, value, valueJson, unit, description, symbol, order}`.

- **Units** are metric (`unitType=1`): mm, cm2, cm3, cm4, cm6, kN, kNm, kg/m, m2/m, cm3/m, 1/m and `-` (dimensionless). Sheets also use `%`, `m/kN`, `m2/kN`, `cm2/m` and `cm4/m`.
- **Precision** is Dlubal's display precision. For example, mm has one decimal, so CHS 6x0.25 has `t = 0.3` mm.
- **Heads vary by category and even by series within a category.** The full steel run has **256 unique property ids**. The union per category is below; the full dictionary is `data/parameters.{parquet,json}`.
- **Branches:** Geometry, Sectional Area, Bending, Shear, Torsion, Warping, Stability, Plasticity and Other, plus *Decisive Properties* and *Shear Field Properties of Trapezoidal Sheeting* (sheets only).
- **Oddities:**
  - `+∞` appears for some `alpha_pl_*` values (291 of them) and is stored as null.
  - One property is text: `BC_BS_y`, the buckling curve per BS, value `c` (in SHS/RHS).

| id | Category | params (union) | Notes |
|---|---|---|---|
| 132 | I-Beams, H-Beams | 76 | Geometry `h b t_w t_f h_i r_1 h_w`; a typical series has 49 |
| 133 | U-Sections, Steel Channels | 154 | 27 shapes (hot rolled and cold formed) |
| 134 | T-Sections, Steel Tees | 74 | |
| 135 | L-Sections, Steel Angles | 120 | principal axes `u/v`, `alpha`, Stability |
| 136 | 60 Degree Angles | 90 | |
| 137 | Square and Rectangular Hollow Sections | 50 | `I_t_StVen`, `I_t_Bredt`, `A_cell`, `BC_BS_y` |
| 138 | Circular Hollow Sections, Pipes | 28 | Geometry `d t` |
| 139 | Elliptical and Semi-Elliptical Hollow Sections | 52 | |
| 140 | Z-Sections, Steel Zees | 129 | |
| 141 | Rail Sections | 50 | Geometry `Cr_*` |
| 142 | Sheets | 83 | trapezoidal sheeting branches (`Tr_*`) |
| 143 | Bar Sections | 90 | |
| 171 | Virtual Joists and Virtual Joist Girders | 17 | reduced set |
| 172 | 2L-Sections, Steel Double Angles | 55 | |

## Known server issue

**Series 243** (CHS GB/T 17395-2008, 3,198 sections) returns HTTP 500 from `GetSeriesTableJson` for metric (`unitType=1`), while imperial works. The workaround is `uv run main.py sections --series 243 --per-section`: it takes the section ids from the imperial table and fetches each section in metric via `GetSeriesSectionJson`. That costs about 3.2k requests, roughly an hour at 1 req/s.
