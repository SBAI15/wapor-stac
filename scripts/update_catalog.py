"""
update_catalog.py
=================
Incrementally updates an existing WaPOR v3 STAC catalog by adding any new
raster files found in the GCS bucket since the last run.
"""

import json
import logging
from pathlib import Path

import pystac
from pystac import CatalogType

from build_catalog import (
    CATALOG_BASE_URL,
    GCS_BASE_URL,
    MAPSET_META,
    STAC_DIR,
    build_catalog,
    gcs_list_all,
    gcs_list_prefixes,
    make_item_l1_l2,
    make_item_l3,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def existing_item_ids(collection_dir: Path) -> set:
    """Return the set of item IDs already saved in a collection directory."""
    ids = set()
    search_dir = collection_dir / "items" if (collection_dir / "items").exists() else collection_dir
    for json_file in search_dir.glob("*.json"):
        if json_file.name == "collection.json":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if data.get("type") == "Feature":
                ids.add(data["id"])
        except Exception:
            pass
    return ids


def update_l1_l2(mapset_code, collection, collection_dir):
    """Add new items to an L1/L2 collection."""
    temporal_type = MAPSET_META[mapset_code][3]
    level = mapset_code.split("-")[0]
    prefix = f"DATA/WAPOR-3/MAPSET/{mapset_code}/"
    base_href = f"{GCS_BASE_URL}/{prefix.rstrip('/')}"

    existing = existing_item_ids(collection_dir)
    tif_files = sorted(
        f.split("/")[-1]
        for f in gcs_list_all(prefix)
        if f.endswith(".tif")
    )

    added = 0
    for tif_name in tif_files:
        stem = tif_name[:-4]
        if stem in existing:
            continue
        item = make_item_l1_l2(tif_name, mapset_code, temporal_type, level, base_href)
        if item:
            collection.add_item(item)
            added += 1
    return added


def update_l3(mapset_code, collection, collection_dir):
    """Add new items to an L3 collection."""
    temporal_type = MAPSET_META[mapset_code][3]
    prefix = f"DATA/WAPOR-3/MOSAICSET/{mapset_code}/"
    base_href = f"{GCS_BASE_URL}/{prefix.rstrip('/')}"

    existing = existing_item_ids(collection_dir)
    tif_files = sorted(
        f.split("/")[-1]
        for f in gcs_list_all(prefix)
        if f.endswith(".tif")
    )

    added = 0
    for tif_name in tif_files:
        stem = tif_name[:-4]
        if stem in existing:
            continue
        parts = stem.split(".")
        if len(parts) < 4:
            continue
        area_code = parts[2]
        item = make_item_l3(tif_name, mapset_code, temporal_type, area_code, base_href)
        if item:
            collection.add_item(item)
            added += 1
    return added


def main():
    catalog_file = STAC_DIR / "catalog.json"

    if not catalog_file.exists():
        log.info("No existing catalog found. Running full build.")
        build_catalog()
        return

    log.info("Scanning local catalog at %s", STAC_DIR)

    collection_dirs = sorted(
        d for d in STAC_DIR.iterdir()
        if d.is_dir() and (d / "collection.json").exists()
    )

    total_added = 0
    updated_codes = []

    for collection_dir in collection_dirs:
        col_data = json.loads(
            (collection_dir / "collection.json").read_text(encoding="utf-8")
        )
        mapset_code = col_data.get("wapor:mapset", "")
        if not mapset_code or mapset_code not in MAPSET_META:
            continue

        log.info("Checking %s", mapset_code)
        collection = pystac.Collection.from_dict(col_data)
        level = mapset_code.split("-")[0]

        if level == "L3":
            added = update_l3(mapset_code, collection, collection_dir)
        else:
            added = update_l1_l2(mapset_code, collection, collection_dir)

        if added:
            log.info("  +%d new items", added)
            total_added += added
            updated_codes.append(mapset_code)

    if total_added == 0:
        log.info("Catalog is up to date. No new items found.")
        return

    log.info("%d new items across %d collections — rebuilding catalog...",
             total_added, len(updated_codes))
    build_catalog()
    log.info("Done.")


if __name__ == "__main__":
    main()
