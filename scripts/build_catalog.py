"""
build_catalog.py
================
Builds a static STAC 1.0.0 catalog for FAO WaPOR v3 data.

All assets point directly to Cloud Optimized GeoTIFFs hosted by FAO on
Google Cloud Storage.
"""

import argparse
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import pystac
from pystac import (
    Asset,
    Catalog,
    CatalogType,
    Collection,
    Extent,
    Item,
    Link,
    SpatialExtent,
    TemporalExtent,
)

CATALOG_BASE_URL = "https://SBAI15.github.io/wapor-stac/stac"

BUCKET       = "fao-gismgr-wapor-3-data"
GCS_BASE_URL = f"https://storage.googleapis.com/{BUCKET}"
STAC_DIR     = Path(__file__).parent.parent / "stac"
CATALOG_ID   = "wapor-v3"
DATA_START   = 2018

BBOX_L1 = [-180.0, -90.0, 180.0, 90.0]

BBOX_L2 = [-30.0, -40.0, 70.0, 54.0]

BBOX_L3_DEFAULT = [-30.0, -40.0, 70.0, 54.0]

LEVEL_BBOX = {"L1": BBOX_L1, "L2": BBOX_L2, "L3": BBOX_L3_DEFAULT}

BBOX_L3_AREAS = {
    "AWA": [ 39.174909,   8.308597,  40.027053,   8.914825],
    "BKA": [ 35.720490,  33.608540,  36.234892,  34.045017],
    "BUS": [ 34.088783,   0.300457,  34.434984,   0.778289],
    "ENO": [ 29.048659,  26.984181,  33.101446,  31.634063],
    "ERB": [ 43.491467,  35.783072,  44.118273,  36.472632],
    "GAR": [ 45.762770,  31.648769,  46.118967,  32.431805],
    "GEZ": [ 33.155874,  14.177173,  33.586206,  14.453248],
    "JAF": [ 35.429937,  29.982027,  36.230146,  30.531843],
    "JEN": [  8.449291,  36.391204,   9.226464,  36.657115],
    "JVA": [ 35.545224,  32.342492,  35.665835,  32.683810],
    "KAI": [  9.677211,  35.495864,  10.051617,  35.735637],
    "KMW": [ 37.171131,  -0.847472,  37.582870,  -0.552146],
    "KOG": [ 36.980879,  11.302976,  37.264886,  11.551545],
    "KTB": [ 39.804069,  -1.508396,  40.033416,  -1.076272],
    "KWL": [ 71.510185,  29.879342,  72.508154,  30.744271],
    "LAK": [ 30.545633,  -2.164374,  30.844384,  -1.840508],
    "LAM": [ 34.051369, -19.452905,  34.450667, -19.180030],
    "LCE": [ 14.200894,  26.500142,  14.546008,  26.750842],
    "LDA": [ 16.118709,  28.964713,  16.417320,  29.178662],
    "LOT": [ 13.578414,  32.242877,  13.701167,  32.439335],
    "LOU": [ -6.425299,  34.519981,  -5.825645,  35.171092],
    "MAG": [-74.357004,  10.501446, -74.085597,  10.991365],
    "MAL": [ 80.182998,   8.135607,  80.535055,   8.682301],
    "MBL": [ 32.804968, -25.129487,  33.792005, -24.385009],
    "MIT": [  2.386124,  36.390183,   3.406043,  36.805562],
    "MUV": [ 30.231524,  -1.683534,  30.474523,  -1.047185],
    "NAJ": [ 44.234790,  31.600806,  44.631249,  32.229365],
    "NDV": [-76.137600,   4.399477, -75.899834,   4.874153],
    "ODN": [ -6.265016,  13.753041,  -5.854749,  14.557988],
    "PAL": [ 35.359621,  31.741931,  35.571397,  32.199728],
    "SAN": [ 43.973349,  15.214236,  44.489386,  15.609255],
    "SED": [-16.261089,  16.226290, -15.868510,  16.493998],
    "SNG": [ 68.432576,  25.489954,  69.653496,  26.468195],
    "VTM": [107.695775,  12.395096, 108.054632,  12.753666],
    "YAN": [ 29.918628,  -1.942265,  30.038902,  -1.755220],
    "ZAN": [ 31.191520,  30.338054,  31.632729,  30.750348],
}

MAPSET_META = {
    "L1-AETI-A":      ("Actual Evapotranspiration and Interception — L1 Annual 300 m",
                       "Annual total actual evapotranspiration and interception (ETIa, mm/year). "
                       "Sum of soil evaporation (E), canopy transpiration (T), and rainfall "
                       "interception (I). Global coverage at 300 m spatial resolution.",
                       "mm/year", "A"),
    "L1-AETI-D":      ("Actual Evapotranspiration and Interception — L1 Dekadal 300 m",
                       "Dekadal actual evapotranspiration and interception (ETIa, mm/day). "
                       "Global coverage at 300 m. Released approximately 5 days after the end "
                       "of each dekad; a higher-quality final version follows after 6 dekads.",
                       "mm/day", "D"),
    "L1-AETI-M":      ("Actual Evapotranspiration and Interception — L1 Monthly 300 m",
                       "Monthly total actual evapotranspiration and interception (ETIa, mm/month). "
                       "Global coverage at 300 m spatial resolution.",
                       "mm/month", "M"),
    "L1-E-A":         ("Evaporation — L1 Annual 300 m",
                       "Annual soil evaporation (E, mm/year). Global coverage at 300 m.",
                       "mm/year", "A"),
    "L1-E-D":         ("Evaporation — L1 Dekadal 300 m",
                       "Dekadal soil evaporation (E, mm/day). Global coverage at 300 m.",
                       "mm/day", "D"),
    "L1-GBWP-A":      ("Gross Biomass Water Productivity — L1 Annual 300 m",
                       "Annual gross biomass water productivity (GBWP, kg/m3). "
                       "Ratio of total biomass production to actual evapotranspiration. "
                       "Global coverage at 300 m.",
                       "kg/m3", "A"),
    "L1-I-A":         ("Interception — L1 Annual 300 m",
                       "Annual rainfall interception by the vegetation canopy (I, mm/year). "
                       "Global coverage at 300 m.",
                       "mm/year", "A"),
    "L1-I-D":         ("Interception — L1 Dekadal 300 m",
                       "Dekadal rainfall interception (I, mm/day). Global coverage at 300 m.",
                       "mm/day", "D"),
    "L1-NBWP-A":      ("Net Biomass Water Productivity — L1 Annual 300 m",
                       "Annual net biomass water productivity (NBWP, kg/m3). "
                       "Global coverage at 300 m.",
                       "kg/m3", "A"),
    "L1-NPP-D":       ("Net Primary Production — L1 Dekadal 300 m",
                       "Dekadal net primary production (NPP, g C/m2/day). "
                       "Global coverage at 300 m.",
                       "g C/m2/day", "D"),
    "L1-NPP-M":       ("Net Primary Production — L1 Monthly 300 m",
                       "Monthly net primary production (NPP, g C/m2/month). "
                       "Global coverage at 300 m.",
                       "g C/m2/month", "M"),
    "L1-PCP-A":       ("Precipitation — L1 Annual ~5 km",
                       "Annual precipitation (mm/year) from CHIRPS v3. "
                       "Global coverage at approximately 5 km resolution.",
                       "mm/year", "A"),
    "L1-PCP-D":       ("Precipitation — L1 Dekadal ~5 km",
                       "Dekadal precipitation (mm/day) from CHIRPS v3. "
                       "Global coverage at approximately 5 km resolution.",
                       "mm/day", "D"),
    "L1-PCP-E":       ("Precipitation — L1 Daily ~5 km",
                       "Daily precipitation (mm/day) from CHIRPS v3. "
                       "Global coverage at approximately 5 km resolution.",
                       "mm/day", "E"),
    "L1-PCP-M":       ("Precipitation — L1 Monthly ~5 km",
                       "Monthly precipitation (mm/month) from CHIRPS v3. "
                       "Global coverage at approximately 5 km resolution.",
                       "mm/month", "M"),
    "L1-QUAL-LST-D":  ("Land Surface Temperature Quality Flag — L1 Dekadal 300 m",
                       "Dekadal quality flag for land surface temperature (LST) observations. "
                       "Global coverage at 300 m.",
                       "-", "D"),
    "L1-QUAL-NDVI-D": ("NDVI Quality Flag — L1 Dekadal 300 m",
                       "Dekadal quality flag for Normalized Difference Vegetation Index (NDVI) "
                       "observations. Global coverage at 300 m.",
                       "-", "D"),
    "L1-RET-A":       ("Reference Evapotranspiration — L1 Annual 300 m",
                       "Annual reference evapotranspiration (RET, mm/year). "
                       "Global coverage at 300 m.",
                       "mm/year", "A"),
    "L1-RET-D":       ("Reference Evapotranspiration — L1 Dekadal 300 m",
                       "Dekadal reference evapotranspiration (RET, mm/day). "
                       "Global coverage at 300 m.",
                       "mm/day", "D"),
    "L1-RET-E":       ("Reference Evapotranspiration — L1 Daily 300 m",
                       "Daily reference evapotranspiration (RET, mm/day). "
                       "Global coverage at 300 m.",
                       "mm/day", "E"),
    "L1-RET-M":       ("Reference Evapotranspiration — L1 Monthly 300 m",
                       "Monthly reference evapotranspiration (RET, mm/month). "
                       "Global coverage at 300 m.",
                       "mm/month", "M"),
    "L1-RSM-D":       ("Relative Root-Zone Soil Moisture — L1 Dekadal 300 m",
                       "Dekadal relative root-zone soil moisture (fraction, 0 to 1). "
                       "0 = wilting point; 1 = field capacity. Global coverage at 300 m.",
                       "fraction", "D"),
    "L1-T-A":         ("Transpiration — L1 Annual 300 m",
                       "Annual canopy transpiration (T, mm/year). Global coverage at 300 m.",
                       "mm/year", "A"),
    "L1-T-D":         ("Transpiration — L1 Dekadal 300 m",
                       "Dekadal canopy transpiration (T, mm/day). Global coverage at 300 m.",
                       "mm/day", "D"),
    "L1-TBP-A":       ("Total Biomass Production — L1 Annual 300 m",
                       "Annual total above-ground biomass production (TBP, kg DM/ha). "
                       "Global coverage at 300 m.",
                       "kg DM/ha", "A"),
    "L2-AETI-A":      ("Actual Evapotranspiration and Interception — L2 Annual 100 m",
                       "Annual total ETIa (mm/year). National coverage at 100 m resolution.",
                       "mm/year", "A"),
    "L2-AETI-D":      ("Actual Evapotranspiration and Interception — L2 Dekadal 100 m",
                       "Dekadal ETIa (mm/day). National coverage at 100 m resolution.",
                       "mm/day", "D"),
    "L2-AETI-M":      ("Actual Evapotranspiration and Interception — L2 Monthly 100 m",
                       "Monthly ETIa (mm/month). National coverage at 100 m resolution.",
                       "mm/month", "M"),
    "L2-E-A":         ("Evaporation — L2 Annual 100 m",
                       "Annual soil evaporation (mm/year). National coverage at 100 m.",
                       "mm/year", "A"),
    "L2-E-D":         ("Evaporation — L2 Dekadal 100 m",
                       "Dekadal soil evaporation (mm/day). National coverage at 100 m.",
                       "mm/day", "D"),
    "L2-GBWP-A":      ("Gross Biomass Water Productivity — L2 Annual 100 m",
                       "Annual gross biomass water productivity (kg/m3). National 100 m.",
                       "kg/m3", "A"),
    "L2-I-A":         ("Interception — L2 Annual 100 m",
                       "Annual rainfall interception (mm/year). National coverage at 100 m.",
                       "mm/year", "A"),
    "L2-I-D":         ("Interception — L2 Dekadal 100 m",
                       "Dekadal rainfall interception (mm/day). National coverage at 100 m.",
                       "mm/day", "D"),
    "L2-NBWP-A":      ("Net Biomass Water Productivity — L2 Annual 100 m",
                       "Annual net biomass water productivity (kg/m3). National 100 m.",
                       "kg/m3", "A"),
    "L2-NPP-D":       ("Net Primary Production — L2 Dekadal 100 m",
                       "Dekadal net primary production (g C/m2/day). National 100 m.",
                       "g C/m2/day", "D"),
    "L2-NPP-M":       ("Net Primary Production — L2 Monthly 100 m",
                       "Monthly net primary production (g C/m2/month). National 100 m.",
                       "g C/m2/month", "M"),
    "L2-QUAL-NDVI-D": ("NDVI Quality Flag — L2 Dekadal 100 m",
                       "Dekadal NDVI quality flag. National coverage at 100 m.",
                       "-", "D"),
    "L2-RSM-D":       ("Relative Root-Zone Soil Moisture — L2 Dekadal 100 m",
                       "Dekadal relative root-zone soil moisture (fraction, 0 to 1). "
                       "National coverage at 100 m.",
                       "fraction", "D"),
    "L2-T-A":         ("Transpiration — L2 Annual 100 m",
                       "Annual canopy transpiration (mm/year). National coverage at 100 m.",
                       "mm/year", "A"),
    "L2-T-D":         ("Transpiration — L2 Dekadal 100 m",
                       "Dekadal canopy transpiration (mm/day). National coverage at 100 m.",
                       "mm/day", "D"),
    "L2-TBP-A":       ("Total Biomass Production — L2 Annual 100 m",
                       "Annual total above-ground biomass production (kg DM/ha). National 100 m.",
                       "kg DM/ha", "A"),
    "L3-AETI-A":      ("Actual Evapotranspiration and Interception — L3 Annual 20 m",
                       "Annual ETIa (mm/year). Sub-national irrigation schemes at 20 m resolution.",
                       "mm/year", "A"),
    "L3-AETI-D":      ("Actual Evapotranspiration and Interception — L3 Dekadal 20 m",
                       "Dekadal ETIa (mm/day). Sub-national irrigation schemes at 20 m.",
                       "mm/day", "D"),
    "L3-AETI-E":      ("Actual Evapotranspiration and Interception — L3 Daily 20 m",
                       "Daily ETIa (mm/day). Sub-national irrigation schemes at 20 m.",
                       "mm/day", "E"),
    "L3-AETI-M":      ("Actual Evapotranspiration and Interception — L3 Monthly 20 m",
                       "Monthly ETIa (mm/month). Sub-national irrigation schemes at 20 m.",
                       "mm/month", "M"),
    "L3-CROP-TYPE":   ("Crop Type Classification — L3 20 m",
                       "Seasonal crop type classification. Sub-national irrigation schemes "
                       "at 20 m resolution. Period codes include growing season identifiers "
                       "(e.g. 2024.GS1, 2024.GS2).",
                       "-", "A"),
    "L3-E-A":         ("Evaporation — L3 Annual 20 m",
                       "Annual soil evaporation (mm/year). Sub-national 20 m.",
                       "mm/year", "A"),
    "L3-E-D":         ("Evaporation — L3 Dekadal 20 m",
                       "Dekadal soil evaporation (mm/day). Sub-national 20 m.",
                       "mm/day", "D"),
    "L3-E-E":         ("Evaporation — L3 Daily 20 m",
                       "Daily soil evaporation (mm/day). Sub-national 20 m.",
                       "mm/day", "E"),
    "L3-GBWP-A":      ("Gross Biomass Water Productivity — L3 Annual 20 m",
                       "Annual gross biomass water productivity (kg/m3). Sub-national 20 m.",
                       "kg/m3", "A"),
    "L3-I-A":         ("Interception — L3 Annual 20 m",
                       "Annual rainfall interception (mm/year). Sub-national 20 m.",
                       "mm/year", "A"),
    "L3-I-D":         ("Interception — L3 Dekadal 20 m",
                       "Dekadal rainfall interception (mm/day). Sub-national 20 m.",
                       "mm/day", "D"),
    "L3-I-E":         ("Interception — L3 Daily 20 m",
                       "Daily rainfall interception (mm/day). Sub-national 20 m.",
                       "mm/day", "E"),
    "L3-NBWP-A":      ("Net Biomass Water Productivity — L3 Annual 20 m",
                       "Annual net biomass water productivity (kg/m3). Sub-national 20 m.",
                       "kg/m3", "A"),
    "L3-NPP-D":       ("Net Primary Production — L3 Dekadal 20 m",
                       "Dekadal net primary production (g C/m2/day). Sub-national 20 m.",
                       "g C/m2/day", "D"),
    "L3-NPP-E":       ("Net Primary Production — L3 Daily 20 m",
                       "Daily net primary production (g C/m2/day). Sub-national 20 m.",
                       "g C/m2/day", "E"),
    "L3-NPP-M":       ("Net Primary Production — L3 Monthly 20 m",
                       "Monthly net primary production (g C/m2/month). Sub-national 20 m.",
                       "g C/m2/month", "M"),
    "L3-QUAL-NDVI-D": ("NDVI Quality Flag — L3 Dekadal 20 m",
                       "Dekadal NDVI quality flag. Sub-national 20 m.",
                       "-", "D"),
    "L3-RSM-D":       ("Relative Root-Zone Soil Moisture — L3 Dekadal 20 m",
                       "Dekadal relative root-zone soil moisture (fraction, 0 to 1). "
                       "Sub-national 20 m.",
                       "fraction", "D"),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

GCS_XML_NS = "http://doc.s3.amazonaws.com/2006-03-01"

def _gcs_xml_page(prefix, delimiter="", marker=None):
    """Fetch one page from the GCS XML listing API."""
    params = {"prefix": prefix, "max-keys": 1000}
    if delimiter:
        params["delimiter"] = delimiter
    if marker:
        params["marker"] = marker
    response = requests.get(GCS_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {"s3": GCS_XML_NS}
    keys = [el.text for el in root.findall("s3:Contents/s3:Key", ns) if el.text]
    prefixes = [el.text for el in root.findall("s3:CommonPrefixes/s3:Prefix", ns) if el.text]
    truncated = root.findtext("s3:IsTruncated", namespaces=ns) == "true"
    next_marker = root.findtext("s3:NextMarker", namespaces=ns)
    if truncated and not next_marker and keys:
        next_marker = keys[-1]
    return prefixes, keys, truncated, next_marker

def gcs_list_all(prefix):
    """Return all object keys under a GCS prefix, handling pagination."""
    all_keys = []
    marker = None
    while True:
        _, keys, truncated, next_marker = _gcs_xml_page(prefix, marker=marker)
        all_keys.extend(keys)
        if not truncated:
            break
        marker = next_marker
        if not marker:
            break
    return all_keys

def gcs_list_prefixes(prefix):
    """Return immediate child prefixes one level deep under a GCS prefix."""
    prefixes, _, _, _ = _gcs_xml_page(prefix, delimiter="/")
    return prefixes

def parse_period(code, temporal_type):
    """
    Parse a WaPOR period code into (start_datetime, end_datetime).

    Supported formats:
        Annual  (A): "2018" or "2024.GS1"
        Monthly (M): "2018-01"
        Dekadal (D): "2018-01-D1", "2018-01-D2", "2018-01-D3"
        Daily   (E): "2018-01-01"

    Returns aware UTC datetimes. Falls back to DATA_START on failure.
    """
    try:
        if temporal_type == "A":
            gs_match = re.match(r"(\d{4})\.(GS\d+)", code)
            year = int(gs_match.group(1)) if gs_match else int(code)
            return (
                datetime(year, 1, 1, tzinfo=timezone.utc),
                datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            )

        if temporal_type == "M":
            year, month = int(code[:4]), int(code[5:7])
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            return start, end

        if temporal_type == "D":
            match = re.match(r"(\d{4})-(\d{2})-D([123])", code)
            if not match:
                raise ValueError(f"Unrecognised dekad code: {code!r}")
            year, month, dnum = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if dnum == 1:
                return (
                    datetime(year, month, 1, tzinfo=timezone.utc),
                    datetime(year, month, 10, 23, 59, 59, tzinfo=timezone.utc),
                )
            if dnum == 2:
                return (
                    datetime(year, month, 11, tzinfo=timezone.utc),
                    datetime(year, month, 20, 23, 59, 59, tzinfo=timezone.utc),
                )
            start = datetime(year, month, 21, tzinfo=timezone.utc)
            if month == 12:
                end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            return start, end

        if temporal_type == "E":
            start = datetime.strptime(code, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return start, start.replace(hour=23, minute=59, second=59)

    except Exception as exc:
        log.warning("Could not parse period %r (type=%s): %s", code, temporal_type, exc)

    fallback = datetime(DATA_START, 1, 1, tzinfo=timezone.utc)
    return fallback, fallback

def _bbox_to_geometry(bbox):
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [east, south],
            [east, north], [west, north],
            [west, south],
        ]],
    }

def _common_assets(base_href, stem, tif_name):
    return {
        "data": Asset(
            href=f"{base_href}/{tif_name}",
            media_type="image/tiff; application=geotiff; profile=cloud-optimized",
            title="Cloud Optimized GeoTIFF",
            roles=["data"],
        ),
        "metadata": Asset(
            href=f"{base_href}/{stem}.json",
            media_type="application/json",
            title="FAO GISMGR item metadata",
            roles=["metadata"],
        ),
    }

def make_item_l1_l2(tif_name, mapset_code, temporal_type, level, base_href):
    """Build a STAC Item for an L1 or L2 raster file."""
    stem = tif_name[:-4]
    parts = stem.split(".", 2)
    if len(parts) < 3:
        return None
    period_code = parts[2]
    start_dt, end_dt = parse_period(period_code, temporal_type)
    bbox = LEVEL_BBOX[level]

    item = Item(
        id=stem,
        geometry=_bbox_to_geometry(bbox),
        bbox=bbox,
        datetime=start_dt,
        properties={
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "wapor:mapset": mapset_code,
            "wapor:period": period_code,
            "wapor:level": level,
            "wapor:version": "3",
        },
    )
    for key, asset in _common_assets(base_href, stem, tif_name).items():
        item.add_asset(key, asset)
    return item

def make_item_l3(tif_name, mapset_code, temporal_type, area_code, base_href):
    """Build a STAC Item for an L3 raster file."""
    stem = tif_name[:-4]
    parts = stem.split(".", 3)
    if len(parts) < 4:
        return None
    period_code = parts[3]
    start_dt, end_dt = parse_period(period_code, temporal_type)
    bbox = BBOX_L3_AREAS.get(area_code, BBOX_L3_DEFAULT)

    item = Item(
        id=stem,
        geometry=_bbox_to_geometry(bbox),
        bbox=bbox,
        datetime=start_dt,
        properties={
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "wapor:mapset": mapset_code,
            "wapor:period": period_code,
            "wapor:area_code": area_code,
            "wapor:level": "L3",
            "wapor:version": "3",
        },
    )
    for key, asset in _common_assets(base_href, stem, tif_name).items():
        item.add_asset(key, asset)
    return item

def build_collection(mapset_code):
    """Build a pystac Collection for the given mapset code."""
    title, description, unit, _ = MAPSET_META[mapset_code]
    level = mapset_code.split("-")[0]

    if level == "L3":
        all_bboxes = list(BBOX_L3_AREAS.values())
        bbox = [
            min(b[0] for b in all_bboxes),
            min(b[1] for b in all_bboxes),
            max(b[2] for b in all_bboxes),
            max(b[3] for b in all_bboxes),
        ]
    else:
        bbox = LEVEL_BBOX.get(level, BBOX_L1)

    collection = Collection(
        id=mapset_code.lower(),
        title=title,
        description=description,
        extent=Extent(
            spatial=SpatialExtent(bboxes=[bbox]),
            temporal=TemporalExtent(intervals=[
                [datetime(DATA_START, 1, 1, tzinfo=timezone.utc), None]
            ]),
        ),
        license="CC-BY-4.0",
        extra_fields={
            "wapor:mapset": mapset_code,
            "wapor:level": level,
            "wapor:unit": unit,
            "wapor:version": "3",
            "wapor:provider": "FAO UN",
            "wapor:portal": "https://wapor.apps.fao.org/",
        },
    )
    collection.add_link(Link(
        rel="license",
        target="https://creativecommons.org/licenses/by/4.0/",
        media_type="text/html",
        title="Creative Commons Attribution 4.0 International",
    ))
    collection.add_link(Link(
        rel="about",
        target="https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-access/en",
        media_type="text/html",
        title="WaPOR Data Access",
    ))
    return collection

def build_catalog(limit_collections=None, limit_items=None):
    """
    Build the complete WaPOR v3 STAC catalog and write it to STAC_DIR.

    Parameters
    ----------
    limit_collections : int, optional
        Process only this many collections. Useful for quick validation.
    limit_items : int, optional
        Include only this many items per collection. Useful for quick validation.
    """
    log.info("Building WaPOR v3 STAC catalog...")
    STAC_DIR.mkdir(parents=True, exist_ok=True)

    root = Catalog(
        id=CATALOG_ID,
        title="WaPOR v3 — FAO Water Productivity Open Access Portal",
        description=(
            "Community STAC 1.0.0 catalog for FAO WaPOR version 3 data. "
            "Provides spatiotemporal metadata and direct links to Cloud Optimized "
            "GeoTIFFs (COGs) hosted by FAO on Google Cloud Storage. "
            "Covers actual evapotranspiration, precipitation, soil moisture, net primary "
            "production, biomass productivity, and related variables from 2018 to present. "
            "Three spatial levels: L1 (global, 300 m), L2 (national, 100 m), "
            "L3 (sub-national irrigation schemes, 20 m)."
        ),
        catalog_type=CatalogType.ABSOLUTE_PUBLISHED,
    )
    root.add_link(Link(
        rel="license",
        target="https://creativecommons.org/licenses/by/4.0/",
        media_type="text/html",
        title="Creative Commons Attribution 4.0 International",
    ))

    # L1 and L2 — stored under MAPSET/
    log.info("Discovering L1/L2 collections...")
    mapset_prefixes = gcs_list_prefixes("DATA/WAPOR-3/MAPSET/")
    mapset_codes = [
        p.rstrip("/").split("/")[-1]
        for p in mapset_prefixes
        if p.rstrip("/").split("/")[-1] in MAPSET_META
    ]
    if limit_collections:
        mapset_codes = mapset_codes[:limit_collections]

    for mapset_code in mapset_codes:
        temporal_type = MAPSET_META[mapset_code][3]
        level = mapset_code.split("-")[0]
        prefix = f"DATA/WAPOR-3/MAPSET/{mapset_code}/"
        base_href = f"{GCS_BASE_URL}/{prefix.rstrip('/')}"

        log.info("  %s", mapset_code)
        collection = build_collection(mapset_code)
        root.add_child(collection)

        tif_files = sorted(
            f.split("/")[-1]
            for f in gcs_list_all(prefix)
            if f.endswith(".tif")
        )
        if limit_items:
            tif_files = tif_files[:limit_items]

        count = 0
        for tif_name in tif_files:
            item = make_item_l1_l2(tif_name, mapset_code, temporal_type, level, base_href)
            if item:
                collection.add_item(item)
                count += 1
        log.info("    %d items", count)

    # L3 — stored under MOSAICSET/
    log.info("Discovering L3 collections...")
    mosaicset_prefixes = gcs_list_prefixes("DATA/WAPOR-3/MOSAICSET/")
    l3_codes = [
        p.rstrip("/").split("/")[-1]
        for p in mosaicset_prefixes
        if p.rstrip("/").split("/")[-1] in MAPSET_META
    ]
    if limit_collections:
        remaining = max(0, limit_collections - len(mapset_codes))
        l3_codes = l3_codes[:remaining]

    for mapset_code in l3_codes:
        temporal_type = MAPSET_META[mapset_code][3]
        prefix = f"DATA/WAPOR-3/MOSAICSET/{mapset_code}/"
        base_href = f"{GCS_BASE_URL}/{prefix.rstrip('/')}"

        log.info("  %s", mapset_code)
        collection = build_collection(mapset_code)
        root.add_child(collection)

        tif_files = sorted(
            f.split("/")[-1]
            for f in gcs_list_all(prefix)
            if f.endswith(".tif")
        )
        if limit_items:
            tif_files = tif_files[:limit_items]

        count = 0
        for tif_name in tif_files:
            parts = tif_name[:-4].split(".")
            if len(parts) < 4:
                continue
            area_code = parts[2]
            item = make_item_l3(tif_name, mapset_code, temporal_type, area_code, base_href)
            if item:
                collection.add_item(item)
                count += 1
        log.info("    %d items", count)

    log.info("Saving catalog...")
    root.normalize_hrefs(CATALOG_BASE_URL)
    root.save(dest_href=str(STAC_DIR), catalog_type=CatalogType.ABSOLUTE_PUBLISHED)

    total = sum(1 for _ in STAC_DIR.rglob("*.json"))
    log.info("Done. %d JSON files written.", total)
    return root

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the WaPOR v3 STAC catalog."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Quick validation: 3 collections, 5 items each.",
    )
    args = parser.parse_args()

    if args.test:
        log.info("Test mode: 3 collections, 5 items each.")
        build_catalog(limit_collections=3, limit_items=5)
    else:
        build_catalog()
