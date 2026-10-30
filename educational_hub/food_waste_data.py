"""Food waste per capita from the UN SDG 12.3.1 dataset, via Our World in Data.

The CSV is fetched on the server and cached. If the source is down, the last
good copy is served (marked stale); with no copy at all the page shows a notice.
"""
import csv
import io
import logging
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SOURCE_URL = (
    "https://ourworldindata.org/grapher/food-waste-per-capita.csv"
    "?v=1&csvType=full&useColumnShortNames=true"
)
SOURCE_PAGE = "https://ourworldindata.org/grapher/food-waste-per-capita"
FRESH_KEY = "eh-food-waste-data"
LAST_GOOD_KEY = "eh-food-waste-data-last-good"
FRESH_SECONDS = 12 * 60 * 60
FETCH_TIMEOUT_SECONDS = 5

COLUMNS = {
    "retail": "_12_3_1__ag_food_wst_pc__retail",
    "out_of_home": "_12_3_1__ag_food_wst_pc__out_of_home_consumption",
    "households": "_12_3_1__ag_food_wst_pc__households",
}


@dataclass(frozen=True)
class FoodWasteRow:
    entity: str
    code: str
    year: int
    households: float | None
    retail: float | None
    out_of_home: float | None

    @property
    def is_region(self):
        # Countries use ISO 3166 alpha-3 codes; regions use codes like OWID_WRL or none.
        return len(self.code) != 3

    @property
    def total(self):
        parts = (self.households, self.retail, self.out_of_home)
        return None if None in parts else round(sum(parts), 2)


@dataclass(frozen=True)
class FoodWasteData:
    rows: tuple
    fetched_at: object = None
    available: bool = True
    stale: bool = False


def _number(value):
    return float(value) if value not in ("", None) else None


def _parse(text):
    reader = csv.DictReader(io.StringIO(text))
    missing = {"entity", "code", "year", *COLUMNS.values()} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Unexpected columns, missing {sorted(missing)}")
    return tuple(
        FoodWasteRow(
            entity=row["entity"],
            code=row["code"],
            year=int(row["year"]),
            **{name: _number(row[column]) for name, column in COLUMNS.items()},
        )
        for row in reader
    )


def _fetch():
    request = Request(SOURCE_URL, headers={"User-Agent": "FoodPrint/1.0 (educational project)"})
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return _parse(response.read().decode("utf-8"))


def get_food_waste_data():
    cached = cache.get(FRESH_KEY)
    if cached:
        return cached

    try:
        data = FoodWasteData(rows=_fetch(), fetched_at=timezone.now())
    except (URLError, TimeoutError, OSError, ValueError, KeyError) as error:
        logger.warning("Food waste data source unavailable: %s", error)
        last_good = cache.get(LAST_GOOD_KEY)
        if last_good:
            return FoodWasteData(rows=last_good.rows, fetched_at=last_good.fetched_at, stale=True)
        return FoodWasteData(rows=(), available=False)

    cache.set(FRESH_KEY, data, FRESH_SECONDS)
    cache.set(LAST_GOOD_KEY, data, None)
    return data
