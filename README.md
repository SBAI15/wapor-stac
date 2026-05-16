# WaPOR v3 STAC Catalog

A community-built **SpatioTemporal Asset Catalog (STAC 1.0.0)** for
[FAO WaPOR version 3](https://wapor.apps.fao.org/) data — the FAO portal for
monitoring agricultural water productivity through open-access remotely sensed data.

> This catalog is a metadata index that points directly
> to publicly available Cloud Optimized GeoTIFFs (COGs) hosted by FAO on
> Google Cloud Storage. All data is open under **CC-BY-4.0**.

---

## What is STAC?

A **SpatioTemporal Asset Catalog** is a standardised JSON metadata format that
makes geospatial data discoverable, searchable, and machine-readable. Tools like
[QGIS](https://qgis.org), [GDAL](https://gdal.org), [stackstac](https://stackstac.readthedocs.io),
[odc-stac](https://odc-stac.readthedocs.io), and [pystac-client](https://pystac-client.readthedocs.io)
can read this catalog directly to load WaPOR data without any custom download code.

---

## Catalog Access

| Resource | URL |
|---|---|
| Root catalog | `https://SBAI15.github.io/wapor-stac/stac/catalog.json` |
| Browse online | *(STAC Browser link — see below)* |

### Quick access with Python

```python
import pystac

# Load the root catalog
catalog = pystac.Catalog.from_file(
    "https://SBAI15.github.io/wapor-stac/stac/catalog.json"
)

# List all collections
for col in catalog.get_children():
    print(col.id, "-", col.title)

# Get all L1-AETI-D items (dekadal ETIa, global 300m)
collection = catalog.get_child("l1-aeti-d")
for item in collection.get_items():
    print(item.id, item.datetime)
    print("  TIF:", item.assets["data"].href)
```

### Access with pystac-client + stackstac

```python
from pystac_client import Client
import stackstac

client = Client.open(
    "https://SBAI15.github.io/wapor-stac/stac/catalog.json"
)

items = client.search(
    collections=["l1-aeti-d"],
    datetime="2023-01-01/2023-03-31",
    bbox=[30.0, 5.0, 42.0, 15.0],   # Horn of Africa example
).item_collection()

ds = stackstac.stack(items, assets=["data"])
print(ds)
```

---

## Data Coverage

### L1 — Global, 300 m resolution (25 collections)

| Code | Variable | Temporal |
|---|---|---|
| L1-AETI-D / M / A | Actual Evapotranspiration & Interception | Dekadal / Monthly / Annual |
| L1-E-D / A | Evaporation | Dekadal / Annual |
| L1-T-D / A | Transpiration | Dekadal / Annual |
| L1-I-D / A | Interception | Dekadal / Annual |
| L1-NPP-D / M | Net Primary Production | Dekadal / Monthly |
| L1-RET-D / M / A / E | Reference Evapotranspiration | Dekadal / Monthly / Annual / Daily |
| L1-PCP-D / M / A / E | Precipitation (CHIRPS) | Dekadal / Monthly / Annual / Daily |
| L1-RSM-D | Relative Soil Moisture | Dekadal |
| L1-GBWP-A / NBWP-A | Gross & Net Biomass Water Productivity | Annual |
| L1-TBP-A | Total Biomass Production | Annual |
| L1-QUAL-NDVI-D / QUAL-LST-D | Quality flags | Dekadal |

### L2 — National, 100 m resolution (16 collections)

Same variables as L1 but at country level and 100 m resolution.

### L3 — Sub-national, 20 m resolution (18 collections, MOSAICSET)

Field-level data for specific irrigation schemes across Africa and the Near East.
Each item includes an **area code** (e.g. `AWA`, `BKA`, `MAR-LOU`) identifying
the irrigation scheme.

**Temporal coverage:** 2018 – present (updated ~5 days after each dekad)

---

## Repository Structure

```
wapor-stac/
├── stac/                        # Generated STAC JSON files (do not edit manually)
│   ├── catalog.json             # Root catalog
│   ├── l1-aeti-d/
│   │   ├── collection.json
│   │   └── items/
│   │       ├── WAPOR-3.L1-AETI-D.2018-01-D1.json
│   │       └── ...
│   └── ...
├── scripts/
│   ├── build_catalog.py         # Full rebuild from scratch
│   └── update_catalog.py        # Incremental updater (used by CI)
├── .github/
│   └── workflows/
│       └── update.yml           # Scheduled GitHub Actions workflow
├── requirements.txt
└── README.md
```

---

## Running Locally

```bash
# Clone
git clone https://github.com/SBAI15/wapor-stac.git
cd wapor-stac

# Install dependencies
pip install -r requirements.txt

# Quick test (3 collections, 5 items each — fast)
python scripts/build_catalog.py --test

# Full build (all collections, all years — takes ~10-20 min)
python scripts/build_catalog.py

# Incremental update (add only new items)
python scripts/update_catalog.py
```

---

## How Updates Work

A **GitHub Actions** workflow runs automatically on the 1st, 11th, and 21st of
every month (aligned with WaPOR's dekadal release cycle). It:

1. Checks the GCS bucket for new `.tif` files not yet in the catalog
2. Generates new STAC Item JSON files for each
3. Commits and pushes the changes to this repository
4. GitHub Pages automatically re-publishes the updated catalog

---

## Data Source & License

- **Data provider:** [FAO UN](https://www.fao.org/) — Water Productivity Open Access Portal (WaPOR)
- **Data license:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
- **This catalog:** CC-BY-4.0 — community contribution, not affiliated with FAO

**Citation for WaPOR data:**
> FAO 2023. WaPOR v3 Database. Remote Sensing for Water Productivity.
> Rome, FAO. https://wapor.apps.fao.org/

**Scale factor note:** Pixel values in downloaded GeoTIFFs must be multiplied
by the scale factor stored in the GeoTIFF metadata (automatically applied by
GDAL, QGIS, ArcGIS from WaPOR v3 onward).

---

## Contributing

Issues and pull requests are welcome — especially:
- Improved bounding boxes per L2 country / L3 irrigation scheme
- Additional STAC extensions (EO, Projection)
- Integration examples (Jupyter notebooks, QGIS workflows)
