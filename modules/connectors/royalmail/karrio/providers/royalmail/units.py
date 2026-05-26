import csv
import datetime
import pathlib
import re
import typing

import karrio.lib as lib
import karrio.core.models as models
import karrio.core.units as units


SERVICES_CSV = pathlib.Path(__file__).resolve().parent / "services.csv"

_SERVICE_CODE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _row_value(row: dict, *names: str) -> typing.Optional[str]:
    """Return the first non-empty CSV cell value for the given column names."""
    for name in names:
        value = row.get(name)

        if value is None:
            continue

        value = str(value).strip()

        if value != "":
            return value

    return None


def _to_bool(
    value: typing.Any,
    default: typing.Optional[bool] = None,
) -> typing.Optional[bool]:
    """Normalize a CSV/config value to bool."""
    if value is None:
        return default

    value = str(value).strip().lower()

    if value == "":
        return default

    if value in ("1", "true", "yes", "y", "on"):
        return True

    if value in ("0", "false", "no", "n", "off"):
        return False

    raise ValueError(f"Invalid boolean value in Royal Mail services.csv: {value!r}")

def is_active_flag(
    value: typing.Any,
    default: bool = True,
) -> bool:
    """
    Normalize an active/enabled flag defensively.

    Why this exists:
    - services.csv loads booleans correctly.
    - Karrio server/rate-sheet/reference paths can sometimes round-trip values
      as strings such as "False".
    - Python treats non-empty strings as truthy, so `if service.active` would
      incorrectly include `"False"` services in rates.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    try:
        parsed = _to_bool(value, default=default)
    except ValueError:
        # Unknown non-empty values are treated as enabled for backward
        # compatibility, but known CSV/config false values are handled above.
        return default if str(value).strip() == "" else bool(value)

    return default if parsed is None else parsed


def service_is_active(
    service: typing.Any,
    default: bool = True,
) -> bool:
    """Return whether a service-like object/dict should be exposed/rated."""
    if isinstance(service, dict):
        value = service.get("active", default)
    else:
        value = getattr(service, "active", default)

    return is_active_flag(value, default=default) is True


def active_service_levels(
    services: typing.Optional[typing.Iterable[typing.Any]],
) -> typing.List[typing.Any]:
    """Return only active service definitions."""
    return [
        service
        for service in list(services or [])
        if service_is_active(service)
    ]

def _to_float(
    value: typing.Any,
    default: typing.Optional[float] = None,
) -> typing.Optional[float]:
    """Convert a CSV value to float when possible."""
    if value is None or str(value).strip() == "":
        return default

    return float(value)


def _to_int(
    value: typing.Any,
    default: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a CSV value to int when possible."""
    if value is None or str(value).strip() == "":
        return default

    return int(value)


def _to_list(value: typing.Any) -> typing.List[str]:
    """Split a CSV list cell into trimmed tokens."""
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    return [
        item.strip()
        for item in re.split(r"[,;|:]+", str(value))
        if item.strip()
    ]

# ---------------------------------------------------------------------------
# Royal Mail UK domestic surcharges
# ---------------------------------------------------------------------------

ROYALMAIL_FUEL_ENERGY_SURCHARGE_ID = "royalmail_fuel_energy"
ROYALMAIL_PARCELFORCE_FUEL_ENERGY_SURCHARGE_ID = "royalmail_parcelforce_fuel_energy"
ROYALMAIL_GREEN_SURCHARGE_ID = "royalmail_green"
ROYALMAIL_PEAK_SURCHARGE_ID = "royalmail_peak"

ROYALMAIL_SIGNATURE_SURCHARGE_ID = "royalmail_signature_on_delivery"
ROYALMAIL_AGE_VERIFICATION_SURCHARGE_ID = "royalmail_age_verification"
ROYALMAIL_ID_VERIFICATION_SURCHARGE_ID = "royalmail_id_verification"

ROYALMAIL_SURCHARGE_IDS = {
    ROYALMAIL_FUEL_ENERGY_SURCHARGE_ID,
    ROYALMAIL_PARCELFORCE_FUEL_ENERGY_SURCHARGE_ID,
    ROYALMAIL_GREEN_SURCHARGE_ID,
    ROYALMAIL_PEAK_SURCHARGE_ID,
}

# Royal Mail published UK domestic peak window:
# 17 November 2025 to 9 January 2026 inclusive. now included in the csv just not deleted this yet till i'm confident the code works
ROYALMAIL_PEAK_SURCHARGE_START_DATE = datetime.date(2025, 11, 17)
ROYALMAIL_PEAK_SURCHARGE_END_DATE = datetime.date(2026, 1, 9)

#VAT Rules
ROYALMAIL_UK_VAT_CHARGE_ID = "royalmail_uk_vat"
ROYALMAIL_DEFAULT_UK_VAT_RATE_PERCENTAGE = 20.0

def parse_surcharge_date(
    value: typing.Any = None,
    default: typing.Optional[datetime.date] = None,
) -> typing.Optional[datetime.date]:
    """Return a parsed surcharge date, or default when empty/unparseable."""
    if value in [None, ""]:
        return default

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    text = str(value).strip()
    if not text:
        return default

    # Accept plain dates and ISO datetimes, including UTC "Z" values.
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        pass

    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return default


def is_peak_surcharge_date(
    value: typing.Any = None,
    start_date: typing.Any = None,
    end_date: typing.Any = None,
) -> bool:
    """
    Return whether Royal Mail's UK domestic peak surcharge is active.

    The service/CSV dates are used when provided. The module constants are only
    fallback defaults for backward compatibility.
    """
    date = parse_surcharge_date(value, default=datetime.date.today())
    start = parse_surcharge_date(
        start_date,
        default=ROYALMAIL_PEAK_SURCHARGE_START_DATE,
    )
    end = parse_surcharge_date(
        end_date,
        default=ROYALMAIL_PEAK_SURCHARGE_END_DATE,
    )

    if date is None or start is None or end is None:
        return False

    return start <= date <= end


def active_royalmail_surcharges(
    surcharges: typing.Iterable[models.Surcharge],
    at_date: typing.Any = None,
    peak_start_date: typing.Any = None,
    peak_end_date: typing.Any = None,
) -> typing.List[models.Surcharge]:
    """
    Filter service-level Royal Mail surcharges before Karrio universal rating.

    Karrio's universal apply_surcharges helper applies every surcharge present
    on the ServiceLevel. Royal Mail Peak surcharge is date-limited, so the
    extension removes it unless the requested rating/shipping date falls inside
    the service's configured Peak window.

    Fuel/Energy and Green surcharge rows are current tariff entries and remain
    active whenever they are present in services.csv.
    """
    peak_active = is_peak_surcharge_date(
        at_date,
        start_date=peak_start_date,
        end_date=peak_end_date,
    )

    return [
        surcharge
        for surcharge in list(surcharges or [])
        if getattr(surcharge, "active", True) is not False
        and (
            getattr(surcharge, "id", None) != ROYALMAIL_PEAK_SURCHARGE_ID
            or peak_active
        )
    ]


def _service_surcharges(row: dict) -> typing.List[models.Surcharge]:
    """Build Karrio surcharge objects from Royal Mail services.csv columns."""
    currency = _row_value(row, "currency") or "GBP"
    service_code = (_row_value(row, "service_code") or "").lower()
    surcharges: typing.List[models.Surcharge] = []

    fuel_energy_percentage = _to_float(
        _row_value(
            row,
            "fuel_energy_surcharge_percentage",
            "surcharge_fuel_energy_percentage",
            "fuel_surcharge_percentage",
        )
    )

    if fuel_energy_percentage not in [None, 0]:
        is_parcelforce = service_code.startswith("parcel_force")

        surcharges.append(
            models.Surcharge(
                id=(
                    ROYALMAIL_PARCELFORCE_FUEL_ENERGY_SURCHARGE_ID
                    if is_parcelforce
                    else ROYALMAIL_FUEL_ENERGY_SURCHARGE_ID
                ),
                name="Fuel and Energy Surcharge",
                amount=fuel_energy_percentage,
                surcharge_type="percentage",
                active=True,
            )
        )

    green_amount = _to_float(
        _row_value(
            row,
            "green_surcharge_amount",
            "surcharge_green_amount",
        )
    )

    if green_amount not in [None, 0]:
        surcharges.append(
            models.Surcharge(
                id=ROYALMAIL_GREEN_SURCHARGE_ID,
                name="Green Surcharge",
                amount=green_amount,
                surcharge_type="fixed",
                active=True,
            )
        )

    peak_amount = _to_float(
        _row_value(
            row,
            "peak_surcharge_amount",
            "surcharge_peak_amount",
        )
    )

    if peak_amount not in [None, 0]:
        surcharges.append(
            models.Surcharge(
                id=ROYALMAIL_PEAK_SURCHARGE_ID,
                name="Peak Surcharge",
                amount=peak_amount,
                surcharge_type="fixed",
                active=True,
            )
        )

    # The Karrio core Surcharge model does not carry currency. Currency is
    # supplied to ChargeDetails by the universal rating engine.
    _ = currency

    return surcharges


def _surcharge_identity(surcharge: models.Surcharge) -> typing.Tuple:
    """Return a stable key used to de-duplicate surcharge definitions."""
    return (
        getattr(surcharge, "id", None),
        getattr(surcharge, "name", None),
        getattr(surcharge, "amount", None),
        getattr(surcharge, "surcharge_type", None),
    )

def _clean_unit(value: typing.Any, default: str) -> str:
    """Normalize a unit label for unit conversion lookups."""
    if value in [None, ""]:
        return default

    return str(value).strip().upper()


def _normalize_weight_unit(unit: typing.Any) -> str:
    """Normalize CSV/carrier weight units to Karrio universal rating units."""
    unit = _clean_unit(unit, "KG")

    if unit in ["KG", "LB"]:
        return unit

    # Karrio core WeightUnit only supports KG/LB as constructor units.
    # G and OZ are available as computed properties, not constructor units.
    return "KG"


def _normalize_dimension_unit(unit: typing.Any) -> str:
    """Normalize CSV/carrier dimension units to Karrio universal rating units."""
    unit = _clean_unit(unit, "CM")

    if unit in ["CM", "IN"]:
        return unit

    # Karrio core DimensionUnit only supports CM/IN as constructor units.
    # MM and M are available as computed properties, not constructor units.
    return "CM"

def _normalize_dimension_limits(
    max_length: typing.Optional[float],
    max_width: typing.Optional[float],
    max_height: typing.Optional[float],
) -> typing.Tuple[
    typing.Optional[float],
    typing.Optional[float],
    typing.Optional[float],
]:
    """
    Preserve the services.csv field mapping after unit conversion.

    Important:
    - This function must not sort dimensions.
    - The service catalog tests expect:
        CSV max_length -> ServiceLevel.max_length
        CSV max_width  -> ServiceLevel.max_width
        CSV max_height -> ServiceLevel.max_height

    Royal Mail size limits are orientation-independent, but Karrio universal
    rating compares length/width/height positionally. We handle that by
    normalizing the parcel/request dimensions before rating, not by mutating the
    service catalog dimensions.
    """
    return max_length, max_width, max_height

def _convert_weight_value(
    value: typing.Any,
    source_unit: typing.Any,
    target_unit: typing.Any = None,
) -> typing.Optional[float]:
    """Convert CSV/carrier weight values into Karrio rating units."""
    numeric = _to_float(value)

    if numeric is None:
        return None

    source_unit = _clean_unit(source_unit, "KG")
    target_unit = _clean_unit(target_unit or _normalize_weight_unit(source_unit), "KG")

    # Convert source value to kilograms first.
    if source_unit in ["G", "GRAM", "GRAMS"]:
        kg = numeric / 1000
    elif source_unit in ["KG", "KGS", "KILOGRAM", "KILOGRAMS"]:
        kg = numeric
    elif source_unit in ["LB", "LBS", "POUND", "POUNDS"]:
        kg = numeric / 2.20462262185
    elif source_unit in ["OZ", "OUNCE", "OUNCES"]:
        kg = numeric / 35.27396195
    else:
        kg = numeric

    if target_unit == "LB":
        return kg * 2.20462262185

    return kg

RATE_TABLE_MIN_WEIGHT = 0.001
RATE_TABLE_WEIGHT_PRECISION = 6


def _round_rate_table_weight(value: typing.Any) -> typing.Optional[float]:
    """Round rate-table weights for stable JSON/UI output."""
    if value is None:
        return None

    return round(float(value), RATE_TABLE_WEIGHT_PRECISION)


def _normalize_rate_table_weight_band(
    min_weight: typing.Any,
    max_weight: typing.Any,
) -> typing.Tuple[typing.Optional[float], typing.Optional[float]]:
    """
    Normalize a Royal Mail rate-table weight band.

    Rules:
    - A rate-table ServiceZone must have both min_weight and max_weight.
    - The lower bound must not be zero.
    - Karrio rating uses min inclusive / max exclusive:
          min_weight <= package_weight < max_weight
    """
    normalized_min = _round_rate_table_weight(min_weight)
    normalized_max = _round_rate_table_weight(max_weight)

    if normalized_min is None or normalized_max is None:
        return None, None

    if normalized_min <= 0 or normalized_min < RATE_TABLE_MIN_WEIGHT:
        normalized_min = RATE_TABLE_MIN_WEIGHT

    normalized_min = _round_rate_table_weight(normalized_min)
    normalized_max = _round_rate_table_weight(normalized_max)

    if normalized_max is None or normalized_max <= normalized_min:
        return None, None

    return normalized_min, normalized_max

def _convert_dimension_value(
    value: typing.Any,
    source_unit: typing.Any,
    target_unit: typing.Any = None,
) -> typing.Optional[float]:
    """Convert CSV/carrier dimension values into Karrio rating units."""
    numeric = _to_float(value)

    if numeric is None:
        return None

    source_unit = _clean_unit(source_unit, "CM")
    target_unit = _clean_unit(
        target_unit or _normalize_dimension_unit(source_unit),
        "CM",
    )

    # Convert source value to centimetres first.
    if source_unit in ["MM", "MMS", "MILLIMETRE", "MILLIMETRES", "MILLIMETER", "MILLIMETERS"]:
        cm = numeric / 10
    elif source_unit in ["CM", "CMS", "CENTIMETRE", "CENTIMETRES", "CENTIMETER", "CENTIMETERS"]:
        cm = numeric
    elif source_unit in ["M", "METRE", "METRES", "METER", "METERS"]:
        cm = numeric * 100
    elif source_unit in ["IN", "INS", "INCH", "INCHES"]:
        cm = numeric * 2.54
    else:
        cm = numeric

    if target_unit == "IN":
        return cm / 2.54

    return cm

# ---------------------------------------------------------------------------
# Royal Mail destination zones
# ---------------------------------------------------------------------------
#
# Karrio universal rating matches zones by recipient.country_code.
#
# Royal Mail World Zone 1 is defined as:
#   "all countries not defined as Europe, World Zone 2 or World Zone 3"
#
# Karrio zones do not support negative country-code rules, so World Zone 1 is
# represented as a catch-all zone with an empty country_codes list. Karrio's
# zone selection prefers more specific zones, so Europe/World Zone 2/World Zone
# 3 will win when their country_codes match; otherwise World Zone 1 is selected.
#
# The services.csv file should stay compact and use zone_id markers:
#
#   intl_generic -> Europe Zones 1/2/3 + World Zones 1/2/3
#   intl_europe  -> Europe Zones 1/2/3 only
#   intl_row     -> World Zones 1/2/3 only
#
# If you later load zone-specific prices, you can still add explicit CSV rows
# with zone_label values such as "Europe Zone 1" or "World Zone 2".

ROYALMAIL_EUROPE_ZONE_1_COUNTRY_CODES = [
    # Republic of Ireland, France, Germany, Corsica, Denmark, Monaco
    # Corsica uses France's ISO country code.
    "IE",
    "FR",
    "DE",
    "DK",
    "MC",
]

ROYALMAIL_EUROPE_ZONE_2_COUNTRY_CODES = [
    # Austria, Latvia
    "AT",
    "LV",

    # Azores, Portugal, Madeira
    # Azores and Madeira use Portugal's ISO country code.
    "PT",

    # Lithuania, Balearic Islands, Canary Islands, Spain
    # Balearic Islands and Canary Islands use Spain's ISO country code.
    "LT",
    "ES",

    # Luxembourg, Belgium, Bulgaria, Malta, Netherlands, Croatia, Poland,
    # Cyprus, Romania, Czech Republic, Slovakia, Estonia, Slovenia, Finland,
    # Greece, Hungary, Sweden, Italy
    "LU",
    "BE",
    "BG",
    "MT",
    "NL",
    "HR",
    "PL",
    "CY",
    "RO",
    "CZ",
    "SK",
    "EE",
    "SI",
    "FI",
    "GR",
    "HU",
    "SE",
    "IT",
]

ROYALMAIL_EUROPE_ZONE_3_COUNTRY_CODES = [
    # Albania, Moldova, Andorra, Montenegro, Armenia, North Macedonia,
    # Azerbaijan, Norway including Spitzbergen/Svalbard, Belarus, Russia,
    # Bosnia & Herzegovina, San Marino, Faroe Islands, Serbia, Georgia,
    # Switzerland, Gibraltar, Tajikistan, Greenland, Turkey, Iceland,
    # Turkmenistan, Kazakhstan, Ukraine, Kosovo, Uzbekistan, Kyrgyzstan,
    # Vatican City State, Liechtenstein
    "AL",
    "MD",
    "AD",
    "ME",
    "AM",
    "MK",
    "AZ",
    "NO",
    "SJ",
    "BY",
    "RU",
    "BA",
    "SM",
    "FO",
    "RS",
    "GE",
    "CH",
    "GI",
    "TJ",
    "GL",
    "TR",
    "IS",
    "TM",
    "KZ",
    "UA",
    "XK",
    "UZ",
    "KG",
    "VA",
    "LI",
]

# World Zone 1 is intentionally empty/catch-all.
ROYALMAIL_WORLD_ZONE_1_COUNTRY_CODES = []

ROYALMAIL_WORLD_ZONE_2_COUNTRY_CODES = [
    # Australia, Belau/Palau, British Indian Ocean Territory,
    # Christmas Island Indian Ocean, Cocos/Keeling Islands, Cook Islands,
    # Fiji, French Polynesia/Tahiti, French Southern/Antarctic Territories,
    # Kiribati, Macao, Nauru, New Caledonia, New Zealand,
    # New Zealand Antarctic Territory, Niue, Norfolk Island,
    # Norwegian Antarctic Territory, Papua New Guinea, Laos, Pitcairn,
    # Singapore, Solomon Islands, Tokelau, Tonga, Tuvalu,
    # US Samoa/American Samoa, Western Samoa/Samoa.
    #
    # Notes:
    # - Coral Sea Islands are administered by Australia, so AU is used.
    # - Tahiti uses French Polynesia's ISO country code PF.
    # - Keeling is represented by Cocos Islands CC.
    # - Antarctic territory entries are represented by AQ/BV where practical.
    "AU",
    "PW",
    "IO",
    "CX",
    "CC",
    "CK",
    "FJ",
    "PF",
    "TF",
    "KI",
    "MO",
    "NR",
    "NC",
    "NZ",
    "AQ",
    "NU",
    "NF",
    "BV",
    "PG",
    "LA",
    "PN",
    "SG",
    "SB",
    "TK",
    "TO",
    "TV",
    "AS",
    "WS",
]

ROYALMAIL_WORLD_ZONE_3_COUNTRY_CODES = [
    # United States of America
    "US",
]


ROYALMAIL_ZONE_TEMPLATES: typing.Dict[str, dict] = {
    "europe_zone_1": {
        "id": "europe_zone_1",
        "label": "Europe Zone 1",
        "country_codes": ROYALMAIL_EUROPE_ZONE_1_COUNTRY_CODES,
    },
    "europe_zone_2": {
        "id": "europe_zone_2",
        "label": "Europe Zone 2",
        "country_codes": ROYALMAIL_EUROPE_ZONE_2_COUNTRY_CODES,
    },
    "europe_zone_3": {
        "id": "europe_zone_3",
        "label": "Europe Zone 3",
        "country_codes": ROYALMAIL_EUROPE_ZONE_3_COUNTRY_CODES,
    },
    "world_zone_1": {
        "id": "world_zone_1",
        "label": "World Zone 1",
        "country_codes": ROYALMAIL_WORLD_ZONE_1_COUNTRY_CODES,
    },
    "world_zone_2": {
        "id": "world_zone_2",
        "label": "World Zone 2",
        "country_codes": ROYALMAIL_WORLD_ZONE_2_COUNTRY_CODES,
    },
    "world_zone_3": {
        "id": "world_zone_3",
        "label": "World Zone 3",
        "country_codes": ROYALMAIL_WORLD_ZONE_3_COUNTRY_CODES,
    },
}


ROYALMAIL_EUROPE_ZONE_KEYS = (
    "europe_zone_1",
    "europe_zone_2",
    "europe_zone_3",
)

ROYALMAIL_WORLD_ZONE_KEYS = (
    "world_zone_1",
    "world_zone_2",
    "world_zone_3",
)

ROYALMAIL_WORLDWIDE_ZONE_KEYS = (
    "europe_zone_1",
    "europe_zone_2",
    "europe_zone_3",
    "world_zone_1",
    "world_zone_2",
    "world_zone_3",
)


ROYALMAIL_ZONE_GROUPS: typing.Dict[str, typing.Tuple[str, ...]] = {
    # Current services.csv group ids.
    "intl_generic": ROYALMAIL_WORLDWIDE_ZONE_KEYS,
    "intl_europe": ROYALMAIL_EUROPE_ZONE_KEYS,
    "intl_row": ROYALMAIL_WORLD_ZONE_KEYS,

    # Friendly aliases for future CSV rows.
    "international": ROYALMAIL_WORLDWIDE_ZONE_KEYS,
    "worldwide": ROYALMAIL_WORLDWIDE_ZONE_KEYS,
    "global": ROYALMAIL_WORLDWIDE_ZONE_KEYS,

    "europe": ROYALMAIL_EUROPE_ZONE_KEYS,
    "european": ROYALMAIL_EUROPE_ZONE_KEYS,

    "row": ROYALMAIL_WORLD_ZONE_KEYS,
    "rest_of_world": ROYALMAIL_WORLD_ZONE_KEYS,
    "world": ROYALMAIL_WORLD_ZONE_KEYS,
}


def _zone_key(value: typing.Any) -> str:
    """Normalize a CSV zone_id/zone_label into a lookup key."""
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().lower(),
    ).strip("_")


def _royalmail_zone_template_keys_for_row(
    row: dict,
) -> typing.Optional[typing.List[str]]:
    """
    Resolve a services.csv zone_id/zone_label into Royal Mail zone template keys.

    Priority:
    1. zone_id, because it is stable and machine-oriented
    2. zone_label, because it is human-readable and useful for explicit rows
    """
    for raw_value in [
        _row_value(row, "zone_id"),
        _row_value(row, "zone_label"),
    ]:
        key = _zone_key(raw_value)

        if not key:
            continue

        if key in ROYALMAIL_ZONE_GROUPS:
            return list(ROYALMAIL_ZONE_GROUPS[key])

        if key in ROYALMAIL_ZONE_TEMPLATES:
            return [key]

    return None

def _zone_from_row(
    row: dict,
    *,
    zone_id: typing.Optional[str] = None,
    zone_label: typing.Optional[str] = None,
    country_codes: typing.Optional[typing.List[str]] = None,
) -> typing.Optional[models.ServiceZone]:
    """
    Build one Royal Mail ServiceZone from a CSV row.

    Important distinction:

    - DEFAULT_SERVICES is the full CSV-backed service catalogue. It may contain
      inactive/no-price services, but their geographic zones should still be
      preserved for metadata, selectors, and zone-expansion tests.

    - REFERENCE_SERVICE_LEVELS is the rate-sheet-safe catalogue. It filters out
      zones without rates before exposing data to Karrio default rate sheets.

    Therefore blank CSV rates must remain None here. They must not be converted
    to 0.0, but they also should not cause the whole zone to be dropped from
    DEFAULT_SERVICES.
    """
    resolved_zone_id = zone_id if zone_id is not None else _row_value(row, "zone_id")
    resolved_zone_label = (
        zone_label if zone_label is not None else _row_value(row, "zone_label")
    )

    resolved_country_codes = (
        list(country_codes)
        if country_codes is not None
        else _to_list(_row_value(row, "country_codes"))
    )

    postal_codes = _to_list(_row_value(row, "postal_codes"))
    cities = _to_list(_row_value(row, "cities"))
    transit_days = _to_int(_row_value(row, "zone_transit_days", "transit_days"))

    # Blank rate means "no static price loaded".
    # Keep it as None. Do not coerce to 0.0.
    rate = _to_float(_row_value(row, "rate"), None)
    cost = _to_float(_row_value(row, "cost"))

    raw_weight_unit = _row_value(row, "weight_unit") or "KG"
    normalized_weight_unit = _normalize_weight_unit(raw_weight_unit)

    # Prefer explicit zone rate-band columns.
    # If those are blank, fall back to service-level min/max. This supports
    # flat domestic rows and inactive catalogue rows where one band describes
    # the full service/package limit.
    raw_zone_min_weight = (
        _row_value(row, "zone_min_weight", "zoneMinWeight")
        or _row_value(row, "min_weight")
    )
    raw_zone_max_weight = (
        _row_value(row, "zone_max_weight", "zoneMaxWeight")
        or _row_value(row, "max_weight")
    )

    zone_min_weight = _convert_weight_value(
        raw_zone_min_weight,
        raw_weight_unit,
        normalized_weight_unit,
    )
    zone_max_weight = _convert_weight_value(
        raw_zone_max_weight,
        raw_weight_unit,
        normalized_weight_unit,
    )

    zone_min_weight, zone_max_weight = _normalize_rate_table_weight_band(
        zone_min_weight,
        zone_max_weight,
    )

    if zone_min_weight is None or zone_max_weight is None:
        return None

    has_zone_data = any(
        [
            resolved_zone_id,
            resolved_zone_label,
            resolved_country_codes,
            postal_codes,
            cities,
        ]
    )

    if not has_zone_data:
        return None

    return models.ServiceZone(
        id=resolved_zone_id,
        label=resolved_zone_label,
        rate=rate,
        cost=cost,
        min_weight=zone_min_weight,
        max_weight=zone_max_weight,
        transit_days=transit_days,
        country_codes=resolved_country_codes,
        postal_codes=postal_codes,
        cities=cities,
    )

def _service_zones(row: dict) -> typing.List[models.ServiceZone]:
    """
    Build Karrio ServiceZone entries for a services.csv row.

    Behaviour:
    - Explicit CSV country_codes/postal_codes/cities are respected as-is.
    - Royal Mail grouped zone ids are expanded into multiple Karrio zones.
    - World Zone 1 is emitted as a catch-all zone with country_codes=[].
    """
    explicit_country_codes = _to_list(_row_value(row, "country_codes"))
    explicit_postal_codes = _to_list(_row_value(row, "postal_codes"))
    explicit_cities = _to_list(_row_value(row, "cities"))

    # If the row has explicit routing data, do not expand it.
    # This lets future zone-specific price rows override or refine the grouped
    # Royal Mail defaults.
    if explicit_country_codes or explicit_postal_codes or explicit_cities:
        zone = _zone_from_row(row)

        return [] if zone is None else [zone]

    zone_template_keys = _royalmail_zone_template_keys_for_row(row)

    if not zone_template_keys:
        zone = _zone_from_row(row)

        return [] if zone is None else [zone]

    zones: typing.List[models.ServiceZone] = []

    for template_key in zone_template_keys:
        template = ROYALMAIL_ZONE_TEMPLATES[template_key]

        zone = _zone_from_row(
            row,
            zone_id=template["id"],
            zone_label=template["label"],
            country_codes=list(template["country_codes"]),
        )

        if zone is not None:
            zones.append(zone)

    return zones


def _zone_identity(zone: models.ServiceZone) -> typing.Tuple:
    """Return a stable identity tuple used to avoid duplicate zones per service."""
    return (
        zone.id,
        zone.label,
        tuple(zone.country_codes or []),
        tuple(zone.postal_codes or []),
        tuple(zone.cities or []),
        zone.min_weight,
        zone.max_weight,
        zone.rate,
        zone.cost,
        zone.transit_days,
    )

CLICK_AND_DROP_PARCEL_FORMAT_IDENTIFIERS = frozenset(
    [
        "parcel",
        "smallParcel",
        "mediumParcel",
        "largeParcel",
    ]
)

def _zone_rate_table_group_key(zone: models.ServiceZone) -> typing.Tuple:
    """Return the grouping key for weight bands belonging to the same zone."""
    return (
        zone.id,
        zone.label,
        tuple(sorted(zone.country_codes or [])),
        tuple(sorted(zone.postal_codes or [])),
        tuple(sorted(zone.cities or [])),
    )

def _normalize_service_zone_bands(
    zones: typing.Iterable[models.ServiceZone],
) -> typing.List[models.ServiceZone]:
    """
    Normalize and de-overlap ServiceZone weight bands.

    This function runs while building DEFAULT_SERVICES, so it must not drop
    no-rate zones. Inactive/no-price services may still need their zones for
    catalogue metadata and zone-expansion tests.

    Rate-sheet safety is handled later by _normalize_reference_zones(), which
    removes zones where rate is None or blank.
    """
    grouped: typing.Dict[typing.Tuple, typing.List[models.ServiceZone]] = {}

    for zone in zones or []:
        if zone is None:
            continue

        min_weight, max_weight = _normalize_rate_table_weight_band(
            zone.min_weight,
            zone.max_weight,
        )

        if min_weight is None or max_weight is None:
            continue

        zone.min_weight = min_weight
        zone.max_weight = max_weight

        grouped.setdefault(_zone_rate_table_group_key(zone), []).append(zone)

    normalized_zones: typing.List[models.ServiceZone] = []

    for _, group in grouped.items():
        group = sorted(
            group,
            key=lambda item: (
                item.min_weight,
                item.max_weight,
                item.rate if item.rate is not None else 0,
            ),
        )

        previous_max_weight: typing.Optional[float] = None
        seen_identities: typing.Set[typing.Tuple] = set()

        for zone in group:
            if previous_max_weight is not None and zone.min_weight < previous_max_weight:
                zone.min_weight = previous_max_weight

            zone.min_weight, zone.max_weight = _normalize_rate_table_weight_band(
                zone.min_weight,
                zone.max_weight,
            )

            if zone.min_weight is None or zone.max_weight is None:
                continue

            identity = _zone_identity(zone)

            if identity in seen_identities:
                continue

            normalized_zones.append(zone)
            seen_identities.add(identity)
            previous_max_weight = zone.max_weight

    return normalized_zones

# Canonical Click & Drop standard packageFormatIdentifier values.
#
# Royal Mail's public YAML documents these values as lower camel case:
#   undefined, letter, largeLetter, smallParcel, mediumParcel,
#   largeParcel, parcel, documents
#
# Carrier validation is case-sensitive enough in practice that we should not
# pass user/API aliases such as "MediumParcel" through unchanged.
CLICK_AND_DROP_STANDARD_PACKAGE_FORMAT_IDENTIFIERS = {
    "undefined": "undefined",
    "letter": "letter",
    "largeletter": "largeLetter",
    "smallparcel": "smallParcel",
    "mediumparcel": "mediumParcel",
    "largeparcel": "largeParcel",
    "parcel": "parcel",
    "documents": "documents",
}


CLICK_AND_DROP_PARCELFORCE_CARRIER_NAME = "Parcelforce Worldwide"
CLICK_AND_DROP_PARCELFORCE_PACKAGE_FORMAT_IDENTIFIER = "parcel"


# Royal Mail OBA domestic parcel service codes where Click & Drop expects the
# generic API package format `parcel`, not the internal Karrio/Royal Mail
# package band values `smallParcel`, `mediumParcel`, or `largeParcel`.
#
# Royal Mail separates billing/rating into package bands, but for several
# Click & Drop shipment service codes the API validates against the generic
# packageFormatIdentifier=`parcel`.
CLICK_AND_DROP_ROYAL_MAIL_OBA_PARCEL_SERVICE_CODES = frozenset(
    [
        "CRL24",
        "CRL48",
        "TPN24",
        "TPN48",
        "TRN24",
        "TRN48",
        "TSS",
    ]
)


# Royal Mail Click & Drop service codes whose package format is intentionally
# selected at package level rather than fixed by the service row.
#
# Example:
#   TPN24 + letter       -> packageFormatIdentifier=letter
#   TPN24 + largeLetter  -> packageFormatIdentifier=largeLetter
#   TPN24 + smallParcel  -> packageFormatIdentifier=parcel
#   TPN24 + mediumParcel -> packageFormatIdentifier=parcel
CLICK_AND_DROP_FLEXIBLE_PACKAGE_FORMAT_SERVICE_CODES = frozenset(
    [
        "TPN24",
    ]
)


def _package_format_identifier_key(value: typing.Any) -> str:
    """Normalize a package format identifier for case/alias-insensitive lookup."""
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").strip().lower(),
    )


def normalize_click_and_drop_package_format_identifier(
    package_format: typing.Optional[str],
) -> typing.Optional[str]:
    """
    Return the canonical Click & Drop packageFormatIdentifier when the value is
    one of Royal Mail's standard identifiers.

    Unknown values are preserved to support ChannelShipper custom package
    formats, which the Click & Drop API allows.

    Examples:
        small_parcel  -> smallParcel
        SmallParcel   -> smallParcel
        MediumParcel  -> mediumParcel
        large letter  -> largeLetter
        myCustomBox   -> myCustomBox
    """
    if package_format in [None, ""]:
        return package_format

    # First allow the provider enum aliases to resolve common Karrio values
    # such as small_box, medium_box, large_box, etc.
    mapped = PackagingType.map(package_format)

    candidate = (
        mapped.value
        if getattr(mapped, "enum", None) is not None
        else str(package_format).strip()
    )

    key = _package_format_identifier_key(candidate)

    return CLICK_AND_DROP_STANDARD_PACKAGE_FORMAT_IDENTIFIERS.get(key, candidate)


def _service_level_is_parcelforce(
    service_level: typing.Optional[models.ServiceLevel],
) -> bool:
    """Return whether a ServiceLevel represents a Parcelforce product."""
    if service_level is None:
        return False

    service_code = str(getattr(service_level, "service_code", "") or "").lower()
    service_name = str(getattr(service_level, "service_name", "") or "").lower()
    metadata = getattr(service_level, "metadata", None) or {}
    carrier_name = str(metadata.get("carrier_name") or "").lower()

    return (
        service_code.startswith("parcel_force_")
        or service_code.startswith("parcelforce_")
        or "parcelforce" in service_name.replace(" ", "")
        or "parcelforce" in carrier_name.replace(" ", "")
    )


def is_parcelforce_service(service: typing.Any) -> bool:
    """
    Return whether a service selector resolves to a Parcelforce service.

    Supports:
    - canonical Karrio service codes, e.g. parcel_force_express_24
    - raw carrier service codes, e.g. NDA
    - enum/member selectors
    """
    service_level = resolve_service_level(service)

    if service_level is not None:
        return _service_level_is_parcelforce(service_level)

    raw_carrier_code = str(service or "").strip().upper()

    if raw_carrier_code == "":
        return False

    # Raw service-code fallback, useful when the selector is NDA/FE0/etc. and
    # resolve_service_level() could not return a unique service.
    carrier_index = globals().get("CARRIER_SERVICES_INDEX", {})
    carrier_matches = carrier_index.get(raw_carrier_code) or []

    return any(_service_level_is_parcelforce(match) for match in carrier_matches)


def resolve_click_and_drop_carrier_name(
    service: typing.Any,
    default: typing.Optional[str] = None,
) -> typing.Optional[str]:
    """
    Resolve Click & Drop postageDetails.carrierName.

    Royal Mail Click & Drop `carrierName` is account-specific. It must match
    the name configured in the customer's Click & Drop carrier settings.

    It is not safe to infer this from the selected service.

    Examples:
        
            config.carrier_name = "Royal Mail"
            config.carrier_name = "Royal Mail OBA"
            config.carrier_name = "My Warehouse Account"



    The `service` parameter is intentionally ignored. It is retained for
    backwards-compatible call sites.
    """
    if default in [None, ""]:
        return None

    return str(default).strip()


def _service_level_is_domestic_royal_mail_parcel(
    service_level: typing.Optional[models.ServiceLevel],
) -> bool:
    """
    Return whether a service is a domestic Royal Mail parcel service that should
    use Click & Drop packageFormatIdentifier=`parcel`.

    Parcelforce is handled separately by is_parcelforce_service().
    """
    if service_level is None:
        return False

    service_code = str(getattr(service_level, "service_code", "") or "").lower()
    metadata = getattr(service_level, "metadata", None) or {}

    if service_code.startswith("parcel_force_"):
        return False

    if getattr(service_level, "international", False) is True:
        return False

    if not service_code.startswith("royal_mail_"):
        return False

    return metadata.get("package_format_kind") == "parcel"


def resolve_click_and_drop_package_format_identifier(
    service: typing.Optional[str],
    package_format: typing.Optional[str],
) -> typing.Optional[str]:
    """
    Resolve the packageFormatIdentifier value to send to Royal Mail Click & Drop.

    The package format used internally for Royal Mail rating is not always the
    package format Click & Drop expects in the shipment API payload.

    Important examples:

        Royal Mail Tracked 24:
            internal/rating package band: smallParcel / mediumParcel
            Click & Drop payload:        parcel

        Parcelforce express24 NDA:
            internal/rating package band: smallParcel / mediumParcel / largeParcel
            Click & Drop payload:        parcel

    The Click & Drop YAML lists smallParcel, mediumParcel, largeParcel and
    parcel, but Royal Mail performs service-specific validation. Parcelforce
    service codes such as NDA reject Royal Mail parcel-band identifiers and
    expect the generic parcel identifier.
    """
    if package_format in [None, ""]:
        return package_format

    normalized_format = normalize_click_and_drop_package_format_identifier(
        package_format
    )

    service_level = resolve_service_level(service)
    metadata = service_level.metadata or {} if service_level is not None else {}

    # Optional future escape hatch from services.csv metadata.
    # If a service row defines a Click & Drop specific package format, use it.
    explicit_api_format = (
        metadata.get("click_and_drop_package_format_identifier")
        or metadata.get("api_package_format_identifier")
        or metadata.get("package_format_api_identifier")
    )

    if explicit_api_format not in [None, ""]:
        return normalize_click_and_drop_package_format_identifier(
            str(explicit_api_format).strip()
        )

    package_kind = _package_format_register_kind(normalized_format)

    # Only parcel-like formats are collapsed to `parcel`.
    # letter, largeLetter and documents must remain distinct.
    if package_kind != "parcel":
        return normalized_format

    # Parcelforce Click & Drop products such as NDA/FE0/FEM use the serviceCode
    # to identify the Parcelforce product. They should receive the generic
    # packageFormatIdentifier=parcel, not Royal Mail parcel-band values.
    if is_parcelforce_service(service):
        return CLICK_AND_DROP_PARCELFORCE_PACKAGE_FORMAT_IDENTIFIER

    carrier_service_code = str(
        resolve_carrier_service(service) or ""
    ).strip().upper()

    service_register_code = resolve_service_register_code(
        service,
        package_format=normalized_format,
    )

    if (
        carrier_service_code in CLICK_AND_DROP_ROYAL_MAIL_OBA_PARCEL_SERVICE_CODES
        or service_register_code == "02"
        or _service_level_is_domestic_royal_mail_parcel(service_level)
    ):
        return PackagingType.parcel.value

    return normalized_format

def _package_format_register_kind(
    package_format: typing.Optional[str],
) -> typing.Optional[str]:
    """
    Normalize Royal Mail package formats to the service-register grouping.

    Royal Mail commonly uses different serviceRegisterCode values for:

    - letter
    - largeLetter
    - parcel-like formats

    Important:
    Unknown/custom Click & Drop packageFormatIdentifier values must return
    None, not a made-up normalized key. This lets custom package formats pass
    through to Click & Drop without being rejected by local Royal Mail service
    compatibility validation.
    """
    if package_format in [None, ""]:
        return None

    value = str(package_format).strip()
    key = re.sub(r"[^a-z0-9]+", "", value.lower())

    if key == "letter":
        return "letter"

    if key == "largeletter":
        return "large_letter"

    if key in [
        "parcel",
        "smallparcel",
        "mediumparcel",
        "largeparcel",
        "custom",
    ]:
        return "parcel"

    # Unknown/custom identifiers are pass-through Click & Drop values.
    # Do not classify them as a service-register package kind.
    return None


def _infer_package_format_register_kind(row: dict) -> typing.Optional[str]:
    """Infer Royal Mail service-register package grouping from CSV limits."""
    raw_weight_unit = _row_value(row, "weight_unit") or "G"
    raw_dimension_unit = _row_value(row, "dimension_unit") or "MM"

    weight_g = _convert_weight_value(
        _row_value(row, "max_weight"),
        raw_weight_unit,
        "KG",
    )
    weight_g = None if weight_g is None else weight_g * 1000

    dimensions_mm = [
        _convert_dimension_value(_row_value(row, "max_length"), raw_dimension_unit, "CM"),
        _convert_dimension_value(_row_value(row, "max_width"), raw_dimension_unit, "CM"),
        _convert_dimension_value(_row_value(row, "max_height"), raw_dimension_unit, "CM"),
    ]
    dimensions_mm = [
        None if value is None else value * 10
        for value in dimensions_mm
    ]

    if weight_g is None or any(value is None for value in dimensions_mm):
        return None

    max_dim = max(dimensions_mm)
    min_dim = min(dimensions_mm)
    mid_dim = sorted(dimensions_mm)[1]

    if weight_g <= 100 and max_dim <= 240 and mid_dim <= 165 and min_dim <= 5:
        return "letter"

    if weight_g <= 750 and max_dim <= 353 and mid_dim <= 250 and min_dim <= 25:
        return "large_letter"

    return "parcel"

def _infer_package_format_identifier(row: dict) -> typing.Optional[str]:
    """
    Infer the exact Royal Mail packageFormatIdentifier from service limits.

    Important:
    This function is called while DEFAULT_SERVICES is being built at module
    import time. Do not reference PackagingType here because PackagingType is
    declared later in this file.
    """
    raw_weight_unit = _row_value(row, "weight_unit") or "G"
    raw_dimension_unit = _row_value(row, "dimension_unit") or "MM"

    weight_g = _convert_weight_value(
        _row_value(row, "max_weight"),
        raw_weight_unit,
        "KG",
    )
    weight_g = None if weight_g is None else weight_g * 1000

    dimensions_mm = [
        _convert_dimension_value(
            _row_value(row, "max_length"),
            raw_dimension_unit,
            "CM",
        ),
        _convert_dimension_value(
            _row_value(row, "max_width"),
            raw_dimension_unit,
            "CM",
        ),
        _convert_dimension_value(
            _row_value(row, "max_height"),
            raw_dimension_unit,
            "CM",
        ),
    ]
    dimensions_mm = [
        None if value is None else value * 10
        for value in dimensions_mm
    ]

    if weight_g is None or any(value is None for value in dimensions_mm):
        return None

    max_dim = max(dimensions_mm)
    mid_dim = sorted(dimensions_mm)[1]
    min_dim = min(dimensions_mm)

    if weight_g <= 100 and max_dim <= 240 and mid_dim <= 165 and min_dim <= 5:
        return "letter"

    if weight_g <= 750 and max_dim <= 353 and mid_dim <= 250 and min_dim <= 25:
        return "largeLetter"

    if weight_g <= 2000 and max_dim <= 450 and mid_dim <= 350 and min_dim <= 160:
        return "smallParcel"

    if weight_g <= 20000 and max_dim <= 610 and mid_dim <= 460 and min_dim <= 460:
        return "mediumParcel"

    return None

def _validate_service_code(service_code: str) -> None:
    """Ensure service_code can safely be used as a Karrio enum member name."""
    if not _SERVICE_CODE_RE.match(service_code or ""):
        raise ValueError(
            "Invalid Royal Mail services.csv service_code "
            f"{service_code!r}. Use a Karrio-safe snake_case code such as "
            "'royalmail_tracked_24'. Put the Royal Mail API serviceCode in "
            "'carrier_service_code'."
        )

def _service_features(row: dict) -> models.ServiceLevelFeatures:
    """Build Karrio structured service features from CSV columns.

    The services.csv `features` column is the source of truth. It may contain
    colon/comma/pipe/semicolon-separated tokens such as:

        tracked:b2c:b2b
        signature:b2c:b2b
        return:tracked

    A feature should be enabled when either its canonical Karrio feature name
    or one of its aliases appears in the CSV token list.
    """
    feature_tokens = {
        str(item).strip().lower()
        for item in _to_list(_row_value(row, "features", "feature_codes"))
        if str(item).strip()
    }

    explicit_return_service = _to_bool(
        _row_value(row, "return_service"),
        default=None,
    )
    inferred_return_service = any(
        token in ["return", "returns", "return_service"]
        for token in feature_tokens
    )
    is_return_service = (
        explicit_return_service
        if explicit_return_service is not None
        else inferred_return_service
    )

    def feature_bool(
        column: str,
        *aliases: str,
    ) -> typing.Optional[bool]:
        """Resolve a ServiceLevelFeatures boolean from CSV columns/tokens.

        Priority:
        1. An explicit CSV boolean column, if present.
        2. The `features` token list.
        3. None when no feature information is available.

        Important: when aliases are supplied, the canonical column name must
        still be checked. For example:

            feature_bool("signature", "signed")

        should match both `signature` and `signed`.
        """
        value = _row_value(row, column)

        if value is not None:
            return _to_bool(value)

        if feature_tokens:
            candidates = {
                str(item).strip().lower()
                for item in [column, *aliases]
                if item not in [None, ""]
            }

            return any(candidate in feature_tokens for candidate in candidates)

        return None

    return models.ServiceLevelFeatures(
        first_mile=_row_value(row, "first_mile"),
        last_mile=_row_value(row, "last_mile"),
        form_factor=_row_value(row, "form_factor"),
        b2c=feature_bool("b2c"),
        b2b=feature_bool("b2b"),
        shipment_type=(
            _row_value(row, "shipment_type")
            or ("returns" if is_return_service else "outbound")
        ),
        age_check=_row_value(row, "age_check"),
        signature=feature_bool("signature", "signed"),
        tracked=feature_bool("tracked", "tracking"),
        insurance=feature_bool(
            "insurance",
            "insured",
            "extra_compensation",
            "compensation",
        ),
        express=feature_bool("express", "priority"),
        dangerous_goods=feature_bool("dangerous_goods", "dangerous", "hazmat"),
        saturday_delivery=feature_bool("saturday_delivery", "saturday"),
        sunday_delivery=feature_bool("sunday_delivery", "sunday"),
        multicollo=feature_bool("multicollo", "multi_piece", "multipiece"),
        neighbor_delivery=feature_bool("neighbor_delivery", "neighbour_delivery"),
    )

def _friendly_service_name(value: typing.Any) -> typing.Optional[str]:
    """
    Return a selector-friendly Royal Mail service name.

    Example:
        "Tracked 24 (01 / 214655TN)" -> "Tracked 24"
    """
    if value in [None, ""]:
        return None

    text = str(value).strip()
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text or None

def _service_metadata(row: dict) -> dict:
    """Build Royal Mail-specific metadata from CSV columns."""
    feature_codes = _to_list(_row_value(row, "features", "feature_codes"))

    explicit_return_service = _to_bool(
        _row_value(row, "return_service"),
        default=None,
    )
    inferred_return_service = any(
        str(token).strip().lower() in ["return", "returns", "return_service"]
        for token in feature_codes
    )
    is_return_service = (
        explicit_return_service
        if explicit_return_service is not None
        else inferred_return_service
    )

    raw_weight_unit = _row_value(row, "weight_unit")
    raw_dimension_unit = _row_value(row, "dimension_unit")

    explicit_package_format = _row_value(
        row,
        "package_format_identifier",
        "packageFormatIdentifier",
    )
    explicit_package_format_kind = _package_format_register_kind(
        explicit_package_format
    )

    inferred_package_format = _infer_package_format_identifier(row)
    inferred_package_format_kind = (
        _package_format_register_kind(inferred_package_format)
        or _infer_package_format_register_kind(row)
    )

    package_format_identifier_is_explicit = explicit_package_format not in [
        None,
        "",
    ]

    metadata = {
# Ithink i have a possible issue with parcel force and 01 and 02 contracts but as I'm still uncertain how this works
# I think if we send X amount of parcels we can use 01 and if we send greater than X we can use 02 
# I think the way to handle this is a parcelforce specific fallback but i've not implemented it yet
#
        # Royal Mail Click & Drop postageDetails fields.
        "carrier_name": _row_value(row, "carrier_name", "carrierName"),
        "service_register_code": _row_value(
            row,
            "service_register_code",
            "serviceRegisterCode",
        ),
        "consequential_loss": _to_int(
            _row_value(row, "consequential_loss", "consequentialLoss")
        ),

        # Royal Mail / Parcelforce included compensation cover.
        #
        # This is used to filter rates when Karrio's generic insurance option is
        # selected:
        #
        #   options.insurance = 2100
        #
        # Only services with included_compensation >= 2100 should be returned.
        "included_compensation": _to_float(
            _row_value(
                row,
                "included_compensation",
                "includedCompensation",
                "compensation",
                "included_coverage",
                "coverage_amount",
            )
        ),

        # Important:
        # This is the exact packageFormatIdentifier configured in services.csv.
        # Do not replace a blank CSV value with an inferred package band here.
        #
        # For TPN24 the blank value is intentional: Click & Drop accepts
        # packageFormatIdentifier=letter, largeLetter, or parcel with the same
        # serviceCode.
        "package_format_identifier": explicit_package_format,
        "package_format_identifier_is_explicit": package_format_identifier_is_explicit,

        # Keep inferred values separately. These are useful for capabilities,
        # rate-table matching, register-code grouping, and safety checks, but
        # they must not pretend to be explicit CSV package configuration.
        "inferred_package_format_identifier": inferred_package_format,

        # Package kind is less strict than exact package_format_identifier.
        #
        # For example, CRL24 medium parcel has no explicit API package format
        # because Click & Drop may expect generic `parcel`, but it is still a
        # parcel-kind product and should not accept letter/largeLetter unless the
        # carrier code is explicitly marked flexible.
        # the seperation between the service register code achieves this
        "package_format_kind": (
            explicit_package_format_kind
            or inferred_package_format_kind
        ),
        "package_format_kind_is_inferred": (
            explicit_package_format_kind in [None, ""]
            and inferred_package_format_kind not in [None, ""]
        ),

        "return_service": is_return_service,

        # Preserve carrier-native CSV units/limits for transparency.
        "carrier_weight_unit": raw_weight_unit,
        "carrier_dimension_unit": raw_dimension_unit,
        "carrier_min_weight": _to_float(_row_value(row, "min_weight")),
        "carrier_max_weight": _to_float(_row_value(row, "max_weight")),
        "carrier_max_length": _to_float(_row_value(row, "max_length")),
        "carrier_max_width": _to_float(_row_value(row, "max_width")),
        "carrier_max_height": _to_float(_row_value(row, "max_height")),

        # Royal Mail UK domestic surcharge transparency. The actual ChargeDetails
        # are built from ServiceLevel.surcharges by Karrio universal rating.
        "fuel_energy_surcharge_percentage": _to_float(
            _row_value(row, "fuel_energy_surcharge_percentage")
        ),
        "green_surcharge_amount": _to_float(_row_value(row, "green_surcharge_amount")),
        "peak_surcharge_amount": _to_float(_row_value(row, "peak_surcharge_amount")),
        "peak_surcharge_start_date": _row_value(row, "peak_surcharge_start_date"),
        "peak_surcharge_end_date": _row_value(row, "peak_surcharge_end_date"),
        "surcharge_notes": _row_value(row, "surcharge_notes"),

        # Royal Mail optional feature/accessorial charges.
        #
        # These are not added to ServiceLevel.surcharges at load time because
        # they only apply when the user selects the matching Karrio option.
        #
        # Example:
        #   options.signature_confirmation = true
        #   -> add metadata["signature_surcharge_amount"] to the local rate.
        "signature_surcharge_amount": _to_float(
            _row_value(
                row,
                "signature_surcharge_amount",
                "signature_addon_amount",
                "signature_price",
            )
        ),
        "signature_surcharge_letter_amount": _to_float(
            _row_value(
                row,
                "signature_surcharge_letter_amount",
                "signature_letter_surcharge_amount",
                "signature_letter_price",
            )
        ),
        "signature_surcharge_large_letter_amount": _to_float(
            _row_value(
                row,
                "signature_surcharge_large_letter_amount",
                "signature_large_letter_surcharge_amount",
                "signature_large_letter_price",
            )
        ),
        "signature_surcharge_parcel_amount": _to_float(
            _row_value(
                row,
                "signature_surcharge_parcel_amount",
                "signature_parcel_surcharge_amount",
                "signature_parcel_price",
            )
        ),
        "age_verification_surcharge_amount": _to_float(
            _row_value(
                row,
                "age_verification_surcharge_amount",
                "age_verification_addon_amount",
                "age_verification_price",
            )
        ),
        "id_verification_surcharge_amount": _to_float(
            _row_value(
                row,
                "id_verification_surcharge_amount",
                "id_verification_addon_amount",
                "id_verification_price",
            )
        ),

        # Optional raw feature labels from CSV.
        "feature_codes": feature_codes,

                # UK VAT handling.
        #
        # Royal Mail prices in services.csv are VAT-exclusive / net prices.
        # The Royal Mail mapper can gross-up Karrio rates by adding a separate
        # ChargeDetails tax line after universal rating has calculated the net
        # service total.
        "vat_applicable": _to_bool(
            _row_value(
                row,
                "vat_applicable",
                "taxable",
                "apply_vat",
                "apply_uk_vat",
            ),
            default=None,
        ),
        "vat_rate_percentage": _to_float(
            _row_value(
                row,
                "vat_rate_percentage",
                "uk_vat_rate_percentage",
                "tax_rate_percentage",
            )
        ),
        "prices_include_vat": _to_bool(
            _row_value(
                row,
                "prices_include_vat",
                "vat_included",
                "tax_included",
            ),
            default=False,
        ),
        "vat_notes": _row_value(
            row,
            "vat_notes",
            "tax_notes",
        ),
    }

    # Allow custom metadata using CSV columns prefixed with meta_.
    for key, value in row.items():
        if key is None:
            continue

        key = str(key).strip()

        if not key.startswith("meta_"):
            continue

        clean_value = str(value).strip() if value is not None else ""

        if clean_value:
            metadata[key.removeprefix("meta_")] = clean_value

    return {
        key: value
        for key, value in metadata.items()
        if value not in (None, "", [])
    }

def _service_zone(row: dict) -> typing.Optional[models.ServiceZone]:
    """
    Build an optional ServiceZone from a CSV row.

    Royal Mail ServiceZone entries used by rate sheets must be priced and
    weight-banded, so delegate to _zone_from_row().
    """
    return _zone_from_row(row)


def load_services_from_csv(
    csv_path: pathlib.Path = SERVICES_CSV,
) -> typing.List[models.ServiceLevel]:
    """
    Load Royal Mail Click & Drop service definitions from services.csv.

    services.csv remains the source of truth, but values are normalized into
    Karrio universal-rating units:

    - Royal Mail G -> Karrio KG
    - Royal Mail MM -> Karrio CM

    Raw carrier units and limits are preserved in ServiceLevel.metadata.

    Royal Mail grouped international zone ids are expanded into Karrio
    ServiceZone objects:

    - intl_generic -> Europe Zones 1/2/3 + World Zones 1/2/3
    - intl_europe  -> Europe Zones 1/2/3
    - intl_row     -> World Zones 1/2/3

    Important for Karrio 2026.1.31+:
    - Every ServiceLevel gets a stable id equal to service_code.
    - Zones are attached directly to the service data.
    - Multiple CSV rows with the same service_code are merged into one
      ServiceLevel with multiple zone/rate bands.
    """
    if not csv_path.exists():
        return []

    services_by_code: typing.Dict[str, dict] = {}

    def _append_unique(
        target: typing.List[typing.Any],
        values: typing.Iterable[typing.Any],
        identity_fn: typing.Callable[[typing.Any], typing.Tuple],
    ) -> None:
        existing_identities = {
            identity_fn(existing)
            for existing in target
        }

        for value in values:
            identity = identity_fn(value)

            if identity in existing_identities:
                continue

            target.append(value)
            existing_identities.add(identity)

    with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            service_code = _row_value(row, "service_code")

            if service_code is None:
                continue

            _validate_service_code(service_code)

            row_active = is_active_flag(
                _row_value(row, "active", "enabled"),
                default=True,
            )

            service_name = (
                _row_value(row, "service_name", "name")
                or service_code.replace("_", " ").title()
            )

            carrier_service_code = (
                _row_value(
                    row,
                    "carrier_service_code",
                    "royalmail_service_code",
                    "serviceCode",
                )
                or service_code
            )

            raw_weight_unit = _row_value(row, "weight_unit") or "KG"
            raw_dimension_unit = _row_value(row, "dimension_unit") or "CM"

            weight_unit = _normalize_weight_unit(raw_weight_unit)
            dimension_unit = _normalize_dimension_unit(raw_dimension_unit)

            row_zones = _service_zones(row)
            row_surcharges = _service_surcharges(row)

            normalized_dimensions = _normalize_dimension_limits(
                _convert_dimension_value(
                    _row_value(row, "max_length"),
                    raw_dimension_unit,
                    dimension_unit,
                ),
                _convert_dimension_value(
                    _row_value(row, "max_width"),
                    raw_dimension_unit,
                    dimension_unit,
                ),
                _convert_dimension_value(
                    _row_value(row, "max_height"),
                    raw_dimension_unit,
                    dimension_unit,
                ),
            )

            if service_code not in services_by_code:
                services_by_code[service_code] = {
                    # Critical for Karrio 2026.1.31+ rate-sheet references.
                    # Without this, transform_to_shared_zones_format() uses
                    # positional service IDs such as "0", "1", "2".
                    "id": service_code,

                    "service_name": service_name,
                    "service_code": service_code,
                    "carrier_service_code": carrier_service_code,
                    "description": _row_value(row, "description", "notes") or "",
                    "active": row_active,
                    "currency": _row_value(row, "currency") or "GBP",

                    # Normalized Karrio rating units.
                    "weight_unit": weight_unit,
                    "dimension_unit": dimension_unit,

                    # Normalized Karrio rating limits.
                    "min_weight": _convert_weight_value(
                        _row_value(row, "min_weight"),
                        raw_weight_unit,
                        weight_unit,
                    ),
                    "max_weight": _convert_weight_value(
                        _row_value(row, "max_weight"),
                        raw_weight_unit,
                        weight_unit,
                    ),
                    "max_length": normalized_dimensions[0],
                    "max_width": normalized_dimensions[1],
                    "max_height": normalized_dimensions[2],

                    "cost": _to_float(_row_value(row, "cost")),
                    "transit_days": _to_int(_row_value(row, "transit_days")),
                    "domicile": _to_bool(_row_value(row, "domicile")),
                    "international": _to_bool(_row_value(row, "international")),
                    "features": _service_features(row),
                    "metadata": _service_metadata(row),

                    # Attach first-row zones and surcharges immediately.
                    "zones": list(row_zones),
                    "surcharges": list(row_surcharges),
                }

                continue

            service_data = services_by_code[service_code]

            # If multiple CSV rows share the same service_code, keep the merged
            # service inactive if any row is inactive.
            service_data["active"] = (
                is_active_flag(service_data.get("active"), default=True)
                and row_active
            )

            _append_unique(
                service_data.setdefault("zones", []),
                row_zones,
                _zone_identity,
            )

            _append_unique(
                service_data.setdefault("surcharges", []),
                row_surcharges,
                _surcharge_identity,
            )

    for service_data in services_by_code.values():
        service_data["zones"] = _normalize_service_zone_bands(
            service_data.get("zones") or []
        )

    return [
        models.ServiceLevel(**service_data)
        for service_data in services_by_code.values()
    ]

DEFAULT_SERVICES = load_services_from_csv()
ACTIVE_DEFAULT_SERVICES = active_service_levels(DEFAULT_SERVICES)

ALL_SERVICE_LEVEL_BY_CODE: typing.Dict[str, models.ServiceLevel] = {
    service.service_code: service
    for service in DEFAULT_SERVICES
    if service.service_code
}

ALL_SERVICES_INDEX: typing.Dict[str, models.ServiceLevel] = {
    str(service.service_code).lower(): service
    for service in DEFAULT_SERVICES
    if service.service_code
}

SERVICE_LEVEL_BY_CODE: typing.Dict[str, models.ServiceLevel] = {
    service.service_code: service
    for service in ACTIVE_DEFAULT_SERVICES
    if service.service_code
}

SERVICE_CODE_BY_CARRIER_CODE: typing.Dict[str, str] = {}

for service in ACTIVE_DEFAULT_SERVICES:
    if service.carrier_service_code:
        SERVICE_CODE_BY_CARRIER_CODE.setdefault(
            service.carrier_service_code,
            service.service_code,
        )


def _create_shipping_service_enum(
    service_levels: typing.List[models.ServiceLevel],
) -> typing.Type[lib.Enum]:
    """
    Create the Karrio ShippingService enum from active services.csv rows.

    Important:
    The enum value is intentionally the Karrio service_code, not the Royal Mail
    API serviceCode. The Royal Mail API code is stored in
    ServiceLevel.carrier_service_code.

    Inactive rows are excluded so they do not appear in Karrio service selectors.
    """
    members = {
        service.service_code: service.service_code
        for service in service_levels
        if service_is_active(service)
    }

    return units.create_enum("ShippingService", members)


ShippingService = _create_shipping_service_enum(ACTIVE_DEFAULT_SERVICES)


DEFAULT_SERVICE_CODE = next(
    (
        service.service_code
        for service in ACTIVE_DEFAULT_SERVICES
        if service.service_code
    ),
    None,
)



def _normalize_service_key(service: typing.Any) -> typing.Optional[str]:
    """
    Normalize a selector to a canonical Royal Mail Karrio `service_code`.

    Important:
    - exact `service_code` values always win
    - ambiguous selectors such as duplicated carrier codes or friendly names
      resolve to `None`
    - raw carrier service codes are handled separately by
      `resolve_carrier_service()` when a canonical `service_code` is not required
    """
    if service is None:
        return None

    key = str(service if isinstance(service, str) else getattr(service, "name", service)).strip()

    if key == "":
        return None

    if key in SERVICE_LEVEL_BY_CODE:
        return key

    mapped = ShippingService.map(key)

    if mapped.name in SERVICE_LEVEL_BY_CODE:
        return mapped.name

    if mapped.value in SERVICE_LEVEL_BY_CODE:
        return mapped.value

    return resolve_service_code(key)


def get_service_level(service: typing.Any) -> typing.Optional[models.ServiceLevel]:
    """Return the ServiceLevel definition for a Karrio service enum/string."""
    service_code = _normalize_service_key(service)

    if service_code is None:
        return None

    return SERVICE_LEVEL_BY_CODE.get(service_code)


def get_carrier_service_code(service: typing.Any) -> typing.Optional[str]:
    """Return Royal Mail Click & Drop postageDetails.serviceCode."""
    service_level = get_service_level(service)

    if service_level is not None:
        return service_level.carrier_service_code or service_level.service_code

    if isinstance(service, str):
        return service

    return getattr(service, "value", None)


def get_service_register_code(service: typing.Any) -> typing.Optional[str]:
    """Return Royal Mail Click & Drop postageDetails.serviceRegisterCode."""
    service_level = get_service_level(service)

    if service_level is None:
        return None

    return (service_level.metadata or {}).get("service_register_code")


def get_service_postage_metadata(service: typing.Any) -> dict:
    """
    Return Royal Mail postage metadata for shipment creation.

    Useful fields:
        carrier_name
        service_register_code
        consequential_loss
        package_format_identifier
    """
    service_level = get_service_level(service)

    if service_level is None:
        return {}

    return service_level.metadata or {}



def shipping_services_initializer(
    services: typing.List[str],
    **kwargs,
) -> units.Services:
    """
    Build Karrio Services from CSV-generated ShippingService enum.

    Accepts:
    - Karrio `service_code`
    - unique carrier service selectors
    - unique full/friendly service-name selectors

    Notes:
    - ambiguous selectors intentionally resolve to no service
    - no implicit fallback/default service is injected
    """
    if isinstance(services, str):
        services = [services]

    requested_services = [
        _normalize_service_key(service)
        for service in services or []
        if service
    ]

    requested_services = [service for service in requested_services if service]

    # Preserve order while removing duplicates.
    requested_services = list(dict.fromkeys(requested_services))

    return units.Services(requested_services, ShippingService)


def _service_register_by_carrier_and_format_index(
    services: typing.Iterable[models.ServiceLevel],
) -> dict[tuple[str, str], str]:
    """
    Index serviceRegisterCode values by carrier service code and package kind.

    This must be able to use inactive CSV rows because some inactive rows are
    intentionally retained as Click & Drop metadata rows. For example:

        CRL24 + largeLetter -> 01
        CRL24 + parcel      -> 02

    The parcel rows may be inactive for Karrio rating/reference purposes but
    are still required to serialize Click & Drop shipment requests correctly.
    """
    index: dict[tuple[str, str], str] = {}

    for service in services or []:
        carrier_service_code = str(
            service.carrier_service_code or ""
        ).strip().upper()
        metadata = service.metadata or {}

        service_register_code = metadata.get("service_register_code")
        package_format_kind = metadata.get("package_format_kind")

        if not carrier_service_code or not service_register_code or not package_format_kind:
            continue

        key = (carrier_service_code, package_format_kind)

        # Keep the first value. Duplicate rows such as smallParcel/mediumParcel
        # should normally agree on the same register code.
        index.setdefault(key, service_register_code)

    return index

def _service_register_by_carrier_index(
    services: typing.Iterable[models.ServiceLevel],
) -> dict[str, str]:
    """
    Index serviceRegisterCode values by carrier service code only when the
    carrier code is genuinely package-format independent.

    Important:
    This fallback is intentionally narrower than
    _service_register_by_carrier_and_format_index(...).

    Some Royal Mail Click & Drop catalogue rows have a fixed register code and
    no package-format kind. Example:

        MPR -> 01

    Those rows can safely be resolved by carrier code alone because there is no
    letter/largeLetter/parcel distinction in the row metadata.

    But many rows have a blank package_format_identifier while still having an
    inferred package_format_kind from dimensions/weight. Example:

        royal_mail_first_class_letter / BPL1
        serviceRegisterCode = 01
        package_format_identifier = blank
        package_format_kind = letter

    A blank API packageFormatIdentifier does not mean the service is flexible.
    Therefore package-specific rows must not be included in this carrier-level
    fallback, otherwise BPL1 would incorrectly resolve for smallParcel.
    """
    grouped: dict[str, dict[str, typing.Any]] = {}

    for service in services or []:
        carrier_service_code = str(
            service.carrier_service_code or ""
        ).strip().upper()

        metadata = service.metadata or {}

        service_register_code = str(
            metadata.get("service_register_code") or ""
        ).strip()

        package_format_kind = metadata.get("package_format_kind")

        if not carrier_service_code or not service_register_code:
            continue

        entry = grouped.setdefault(
            carrier_service_code,
            {
                "register_codes": set(),
                "has_package_format_kind": False,
            },
        )

        entry["register_codes"].add(service_register_code)

        # If any row for this carrier service code has a package kind, then the
        # carrier code is not safe to resolve through the generic carrier-level
        # fallback. It must be resolved through the carrier+package-kind index
        # or through the final strict service-level compatibility checks.
        if package_format_kind not in [None, ""]:
            entry["has_package_format_kind"] = True

    resolved: dict[str, str] = {}

    for carrier_service_code, entry in grouped.items():
        register_codes = entry["register_codes"]

        if entry["has_package_format_kind"]:
            continue

        if len(register_codes) != 1:
            continue

        resolved[carrier_service_code] = next(iter(register_codes))

    return resolved

ACTIVE_SERVICE_REGISTER_BY_CARRIER_AND_FORMAT = (
    _service_register_by_carrier_and_format_index(ACTIVE_DEFAULT_SERVICES)
)

SERVICE_REGISTER_BY_CARRIER_AND_FORMAT = (
    _service_register_by_carrier_and_format_index(DEFAULT_SERVICES)
)

ACTIVE_SERVICE_REGISTER_BY_CARRIER = (
    _service_register_by_carrier_index(ACTIVE_DEFAULT_SERVICES)
)

SERVICE_REGISTER_BY_CARRIER = (
    _service_register_by_carrier_index(DEFAULT_SERVICES)
)

class ReferenceRecord(dict):
    """
    Dict-like wrapper used for plugin metadata service_levels.

    Why this exists:
    - `/v1/references` needs JSON-serializable service metadata
    - tests and metadata consumers still expect attribute access like
      `service.service_code` and `service.features.tracked`

    This wrapper preserves both behaviors by:
    - remaining a dict for JSON encoding
    - exposing keys via attribute access
    - recursively wrapping nested dict/list structures
    """

    __slots__ = ()

    def __getattr__(self, name):
        """Lazily resolve enum aliases for backwards-compatible option access."""
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    @classmethod
    def wrap(cls, value):
        """Return the nested enum wrapper used for legacy option aliases."""
        if isinstance(value, dict):
            return cls({key: cls.wrap(item) for key, item in value.items()})

        if isinstance(value, list):
            return [cls.wrap(item) for item in value]

        return value

def _reference_zone_has_priced_weight_band(zone: typing.Any) -> bool:
    """Return whether a reference zone is usable in a default rate sheet."""
    if isinstance(zone, dict):
        rate = zone.get("rate")
        min_weight = zone.get("min_weight")
        max_weight = zone.get("max_weight")
    else:
        rate = getattr(zone, "rate", None)
        min_weight = getattr(zone, "min_weight", None)
        max_weight = getattr(zone, "max_weight", None)

    if rate in [None, ""]:
        return False

    min_weight, max_weight = _normalize_rate_table_weight_band(
        min_weight,
        max_weight,
    )

    return min_weight is not None and max_weight is not None


def _reference_zone_group_key(zone: dict) -> typing.Tuple:
    return (
        zone.get("id"),
        zone.get("label"),
        tuple(sorted(zone.get("country_codes") or [])),
        tuple(sorted(zone.get("postal_codes") or [])),
        tuple(sorted(zone.get("cities") or [])),
    )


def _normalize_reference_zones(zones: typing.Iterable[dict]) -> typing.List[dict]:
    """Normalize dict zones used by METADATA.service_levels references."""
    grouped: typing.Dict[typing.Tuple, typing.List[dict]] = {}

    for zone in zones or []:
        if not _reference_zone_has_priced_weight_band(zone):
            continue

        normalized_zone = dict(zone)

        min_weight, max_weight = _normalize_rate_table_weight_band(
            normalized_zone.get("min_weight"),
            normalized_zone.get("max_weight"),
        )

        if min_weight is None or max_weight is None:
            continue

        normalized_zone["min_weight"] = min_weight
        normalized_zone["max_weight"] = max_weight

        grouped.setdefault(
            _reference_zone_group_key(normalized_zone),
            [],
        ).append(normalized_zone)

    normalized_zones: typing.List[dict] = []

    for _, group in grouped.items():
        group = sorted(
            group,
            key=lambda item: (
                item.get("min_weight"),
                item.get("max_weight"),
                item.get("rate") if item.get("rate") is not None else 0,
            ),
        )

        previous_max_weight: typing.Optional[float] = None
        seen: typing.Set[typing.Tuple] = set()

        for zone in group:
            if previous_max_weight is not None and zone["min_weight"] < previous_max_weight:
                zone["min_weight"] = previous_max_weight

            min_weight, max_weight = _normalize_rate_table_weight_band(
                zone.get("min_weight"),
                zone.get("max_weight"),
            )

            if min_weight is None or max_weight is None:
                continue

            zone["min_weight"] = min_weight
            zone["max_weight"] = max_weight

            identity = (
                zone.get("id"),
                zone.get("label"),
                tuple(sorted(zone.get("country_codes") or [])),
                tuple(sorted(zone.get("postal_codes") or [])),
                tuple(sorted(zone.get("cities") or [])),
                zone.get("min_weight"),
                zone.get("max_weight"),
                zone.get("rate"),
                zone.get("cost"),
                zone.get("transit_days"),
            )

            if identity in seen:
                continue

            normalized_zones.append(zone)
            seen.add(identity)
            previous_max_weight = zone["max_weight"]

    return normalized_zones


def _reference_service_level_dicts(
    services: typing.Iterable[models.ServiceLevel],
    *,
    include_inactive: bool = False,
    require_rate_data: bool = True,
) -> typing.List[dict]:
    """
    Build service-level reference data for Karrio's rate-table defaults.

    Karrio builds default rate sheets from:

        METADATA.service_levels
            -> references["ratesheets"][carrier]
            -> transform_to_shared_zones_format(...)

    Therefore Royal Mail references must only expose active services with usable
    priced weight bands.
    """
    service_dicts = lib.to_dict(list(services or []), clear_empty=False)

    if not isinstance(service_dicts, list):
        return []

    normalized_services: typing.List[dict] = []

    for service in service_dicts:
        service_code = service.get("service_code")

        if not service_code:
            continue

        if not include_inactive and not service_is_active(service):
            continue

        service["id"] = service.get("id") or service_code

        if require_rate_data:
            service["zones"] = _normalize_reference_zones(service.get("zones") or [])

            if not service["zones"]:
                continue

        normalized_services.append(service)

    # Make duplicate service names unique for Karrio rate-sheet service_rate
    # remapping. Ideally active CSV service_name values should already be unique.
    name_counts: typing.Dict[str, int] = {}

    for service in normalized_services:
        service_name = service.get("service_name") or service.get("service_code")

        if service_name:
            name_counts[service_name] = name_counts.get(service_name, 0) + 1

    for service in normalized_services:
        service_name = service.get("service_name")
        service_code = service.get("service_code")

        if not service_name or not service_code:
            continue

        if name_counts.get(service_name, 0) <= 1:
            continue

        metadata = service.get("metadata") or {}

        package_format = (
            metadata.get("package_format_identifier")
            or metadata.get("inferred_package_format_identifier")
            or metadata.get("package_format_kind")
        )

        suffix = package_format or service_code
        service["service_name"] = f"{service_name} - {suffix}"

    return normalized_services


# Rate-table/default-reference catalogue.
#
# Important:
# Karrio builds references["ratesheets"]["royalmail"] from METADATA.service_levels.
# Therefore this must not include inactive CSV services or services without
# usable static rate bands.
REFERENCE_SERVICE_LEVELS = ReferenceRecord.wrap(
    _reference_service_level_dicts(
        ACTIVE_DEFAULT_SERVICES,
        include_inactive=False,
        require_rate_data=True,
    )
)

ACTIVE_REFERENCE_SERVICE_LEVELS = ReferenceRecord.wrap(
    _reference_service_level_dicts(
        ACTIVE_DEFAULT_SERVICES,
        include_inactive=False,
        require_rate_data=True,
    )
)


def _service_selector_key(value: typing.Any) -> typing.Optional[str]:
    """Normalize a user-supplied service selector for lookup."""
    text = str(value or "").strip().lower()
    if text == "":
        return None

    return re.sub(r"[^a-z0-9]+", "", text)


def _service_selector_values(service: models.ServiceLevel) -> typing.List[str]:
    """Return all selector aliases that identify a service level."""
    values = [
        service.service_code,
        service.carrier_service_code,
        service.service_name,
        _friendly_service_name(service.service_name),
    ]

    return [str(value).strip() for value in values if value not in [None, ""]]


def _services_index() -> dict[str, models.ServiceLevel]:
    """Build the active canonical service-code lookup table."""
    return {
        str(service.service_code).lower(): service
        for service in ACTIVE_DEFAULT_SERVICES
        if service.service_code
    }


def _carrier_services_index() -> dict[str, typing.List[models.ServiceLevel]]:
    """Build the active carrier service-code lookup table."""
    index: dict[str, typing.List[models.ServiceLevel]] = {}

    for service in ACTIVE_DEFAULT_SERVICES:
        carrier_service_code = str(service.carrier_service_code or "").strip().upper()

        if carrier_service_code == "":
            continue

        index.setdefault(carrier_service_code, []).append(service)

    return index

def _all_service_selector_index() -> dict[str, typing.Set[str]]:
    """
    Build a selector index from the full CSV catalogue.

    This is used to detect ambiguity across active and inactive rows.

    Example:
        CRL24 appears as large letter and parcel variants. Even if only one row
        is active, the raw selector CRL24 must not resolve to that one active
        row because the correct Click & Drop serviceRegisterCode depends on the
        package format.
    """
    index: dict[str, typing.Set[str]] = {}

    for service in DEFAULT_SERVICES:
        if not service.service_code:
            continue

        for selector in _service_selector_values(service):
            key = _service_selector_key(selector)

            if key is not None:
                index.setdefault(key, set()).add(service.service_code)

    return index


def _service_selector_index() -> dict[str, typing.Set[str]]:
    """
    Build the active selector index while respecting full-catalogue ambiguity.

    Inactive services are excluded from normal Karrio selector resolution, but
    inactive rows still count when deciding whether a raw/friendly selector is
    ambiguous.

    This prevents raw carrier codes such as CRL24 from resolving to whichever
    package-band row happens to be active.
    """
    all_index = _all_service_selector_index()
    index: dict[str, typing.Set[str]] = {}

    for service in ACTIVE_DEFAULT_SERVICES:
        if not service.service_code:
            continue

        for selector in _service_selector_values(service):
            key = _service_selector_key(selector)

            if key is None:
                continue

            all_matches = all_index.get(key) or set()

            # Only expose selectors that uniquely identify the same service in
            # the full CSV catalogue.
            if len(all_matches) == 1 and service.service_code in all_matches:
                index.setdefault(key, set()).add(service.service_code)

    for name, member in ShippingService.__members__.items():
        for selector in [name, name.replace("_", " "), member.value]:
            key = _service_selector_key(selector)

            if key is not None:
                index.setdefault(key, set()).add(name)

    return index

SERVICES_INDEX = _services_index()
CARRIER_SERVICES_INDEX = _carrier_services_index()

ALL_CARRIER_SERVICE_CODES: typing.Set[str] = {
    str(service.carrier_service_code).strip().upper()
    for service in DEFAULT_SERVICES
    if service.carrier_service_code
}

ALL_SERVICE_SELECTOR_INDEX = _all_service_selector_index()
SERVICE_SELECTOR_INDEX = _service_selector_index()

def _service_level_is_return_service(service: models.ServiceLevel) -> bool:
    """Return whether a ServiceLevel represents a Royal Mail return service."""
    if service is None:
        return False

    metadata = getattr(service, "metadata", None) or {}
    features = getattr(service, "features", None)

    return (
        metadata.get("return_service") is True
        or getattr(features, "shipment_type", None) == "returns"
    )


def _return_service_codes_index(
    services: typing.Iterable[models.ServiceLevel],
) -> typing.Set[str]:
    """Build return service carrier-code indexes from services.csv."""
    return {
        str(service.carrier_service_code).strip().upper()
        for service in services or []
        if service.carrier_service_code
        and _service_level_is_return_service(service)
    }

def _return_service_selector_index(
    services: typing.Iterable[models.ServiceLevel],
) -> dict[str, typing.Set[str]]:
    """
    Build a return-service selector index.

    The caller decides whether to pass the active catalogue or the full CSV
    catalogue.

    - ACTIVE_DEFAULT_SERVICES is used for runtime/service-catalog checks.
    - DEFAULT_SERVICES is used for POST /returns where Royal Mail may accept
      return services that are inactive for rating because they have no static
      public price table.
    """
    index: dict[str, typing.Set[str]] = {}

    for service in services or []:
        if not _service_level_is_return_service(service):
            continue

        carrier_service_code = str(service.carrier_service_code or "").strip().upper()

        if carrier_service_code == "":
            continue

        selectors = list(_service_selector_values(service))

        # Convenience alias:
        # royal_mail_tracked_returns_48 -> tracked_returns_48
        if service.service_code:
            selectors.append(
                re.sub(
                    r"^royal_mail_",
                    "",
                    str(service.service_code),
                    flags=re.IGNORECASE,
                )
            )

        for selector in selectors:
            key = _service_selector_key(selector)

            if key is not None:
                index.setdefault(key, set()).add(carrier_service_code)

    return index


# Active return services only.
# Used by runtime/service-catalog checks.
RETURN_SERVICE_CODES = _return_service_codes_index(ACTIVE_DEFAULT_SERVICES)

# All known Royal Mail return carrier service codes from services.csv.
# Used by POST /returns resolution.
ALL_RETURN_SERVICE_CODES = _return_service_codes_index(DEFAULT_SERVICES)

# Active-only selector index.
RETURN_SERVICE_SELECTOR_INDEX = _return_service_selector_index(
    ACTIVE_DEFAULT_SERVICES
)

# Full selector index, including inactive/no-price return services.
ALL_RETURN_SERVICE_SELECTOR_INDEX = _return_service_selector_index(
    DEFAULT_SERVICES
)

def resolve_service_code(service: typing.Optional[str]) -> typing.Optional[str]:
    """
    Resolve any supported selector to the canonical Karrio `service_code`.

    Resolution rules:
    1. exact `service_code` match
    2. exact ShippingService enum member/value match
    3. normalized selector lookup when it resolves uniquely
    4. ambiguous selector => `None`
    """
    if service in [None, ""]:
        return None

    raw = str(service).strip()

    if raw in SERVICE_LEVEL_BY_CODE:
        return raw

    mapped = ShippingService.map(raw)

    if mapped.name in SERVICE_LEVEL_BY_CODE:
        return mapped.name

    if mapped.value in SERVICE_LEVEL_BY_CODE:
        return mapped.value

    key = _service_selector_key(raw)
    if key is None:
        return None

    matches = SERVICE_SELECTOR_INDEX.get(key) or set()

    if len(matches) == 1:
        return next(iter(matches))

    return None


def resolve_service_level(
    service: typing.Optional[str],
) -> typing.Optional[models.ServiceLevel]:
    """Resolve a Karrio or Royal Mail service selector to a ServiceLevel."""
    resolved_service_code = resolve_service_code(service)
    if resolved_service_code is None:
        return None

    return SERVICES_INDEX.get(str(resolved_service_code).lower())

def resolve_any_service_level(
    service: typing.Optional[str],
) -> typing.Optional[models.ServiceLevel]:
    """
    Resolve an exact service selector against the active catalogue first, then
    the full CSV catalogue.

    This is intentionally broader than resolve_service_level() and should be
    used only for carrier/shipment metadata lookups, not for exposing Karrio
    runtime services or rating references.
    """
    service_level = resolve_service_level(service)

    if service_level is not None:
        return service_level

    if service in [None, ""]:
        return None

    raw = str(service).strip()

    if raw == "":
        return None

    return (
        ALL_SERVICE_LEVEL_BY_CODE.get(raw)
        or ALL_SERVICES_INDEX.get(raw.lower())
    )

def _state_or_value(value: typing.Any) -> typing.Any:
    """Return a raw value from a Karrio option state wrapper or scalar."""
    return value.state if hasattr(value, "state") else value


def _coverage_amount(value: typing.Any) -> typing.Optional[float]:
    """Convert a coverage/compensation value to a positive float."""
    value = _state_or_value(value)

    if value in [None, ""]:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in ["", "false", "no", "off", "0"]:
            return None

        if normalized in ["true", "yes", "on"]:
            return None

    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None

    # Reject NaN / infinity without importing math.
    if amount != amount or amount in [float("inf"), float("-inf")]:
        return None

    if amount <= 0:
        return None

    return amount


def _option_lookup_value(source: typing.Any, *names: str) -> typing.Any:
    """
    Read a value from a dict, ShippingOptions object, or plain object.

    Used for generic Karrio options such as `insurance`, which are not Royal
    Mail API fields but still arrive in payload.options from the Karrio UI.
    """
    if source is None:
        return None

    if isinstance(source, dict):
        normalized = normalize_option_keys(source)

        for name in names:
            if name in normalized:
                return normalized[name]

            if name in source:
                return source[name]

        return None

    content = getattr(source, "content", None)
    if isinstance(content, dict):
        value = _option_lookup_value(content, *names)

        if value not in [None, ""]:
            return value

    for name in names:
        option = getattr(source, name, None)

        if option is not None:
            return _state_or_value(option)

    return None


def resolve_insurance_coverage_amount(
    options: typing.Any,
    declared_value: typing.Any = None,
) -> typing.Optional[float]:
    """
    Resolve Karrio's generic insurance/coverage option.

    Karrio UI behaviour:
        Add insurance coverage checkbox + Coverage value input
        -> payload.options.insurance = <number>

    Royal Mail interpretation:
        options.insurance is the requested compensation/coverage amount.

    Supported aliases:
        insurance
        insured_value
        insuredValue
        coverage
        coverage_value
        coverageValue

    If a boolean true value is supplied, fall back to declared_value where
    available. This keeps the connector tolerant of API/UI variants, while the
    normal Karrio UI sends a numeric value.
    """
    value = _option_lookup_value(
        options,
        "insurance",
        "insured_value",
        "insuredValue",
        "coverage",
        "coverage_value",
        "coverageValue",
    )

    raw_value = _state_or_value(value)

    if isinstance(raw_value, bool):
        if raw_value is not True:
            return None

        return _coverage_amount(declared_value)

    if isinstance(raw_value, str) and raw_value.strip().lower() in [
        "true",
        "yes",
        "on",
    ]:
        return _coverage_amount(declared_value)

    return _coverage_amount(raw_value)


def included_compensation_amount(
    service: typing.Any,
) -> typing.Optional[float]:
    """
    Return the included compensation amount for a Royal Mail service.

    The value comes from services.csv metadata:

        included_compensation
    """
    service_level = (
        service
        if hasattr(service, "metadata") and hasattr(service, "service_code")
        else resolve_service_level(service)
    )

    if service_level is None:
        return None

    metadata = getattr(service_level, "metadata", None) or {}

    if not isinstance(metadata, dict):
        return None

    return _coverage_amount(
        metadata.get("included_compensation")
        or metadata.get("includedCompensation")
        or metadata.get("compensation")
        or metadata.get("included_coverage")
        or metadata.get("coverage_amount")
    )


def service_supports_insurance(
    service: typing.Any,
    requested_coverage: typing.Any,
) -> bool:
    """
    Return whether a service includes enough compensation for the requested
    Karrio insurance value.

    If no insurance value is requested, the service is allowed.

    Example:
        requested_coverage = 2100

        parcel_force_express_24_insured_750
            included_compensation = 750
            -> False

        parcel_force_express_24_insured_2500
            included_compensation = 2500
            -> True
    """
    coverage = _coverage_amount(requested_coverage)

    if coverage is None:
        return True

    included = included_compensation_amount(service)

    if included is None:
        return False

    return included >= coverage

def service_supports_package_format(
    service: typing.Any,
    package_format: typing.Optional[str],
) -> bool:
    """
    Return whether a local-rating/shipment service is compatible with the
    requested Royal Mail package format.

    Rules:

    1. If services.csv explicitly sets package_format_identifier, enforce that
       exact package band, but compare using canonical Click & Drop casing.

    2. If the service carrier code is explicitly marked flexible, allow Royal
       Mail's known Click & Drop package classes.

    3. Otherwise, for blank package_format_identifier rows, enforce the inferred
       package kind. This prevents letter services accidentally accepting parcel
       shipments just because package_format_identifier is blank.

    4. Unknown/custom Click & Drop package formats are passed through instead of
       rejected locally.
    """
    if package_format in [None, ""]:
        return True

    requested_format = normalize_click_and_drop_package_format_identifier(
        package_format
    )
    requested_kind = _package_format_register_kind(requested_format)

    # Unknown/custom Click & Drop package identifiers should pass through.
    if requested_kind is None:
        return True

    service_level = resolve_service_level(service)

    if service_level is None:
        return True

    metadata = service_level.metadata or {}

    service_format = metadata.get("package_format_identifier")
    service_kind = metadata.get("package_format_kind")
    package_format_identifier_is_explicit = metadata.get(
        "package_format_identifier_is_explicit",
        service_format not in [None, ""],
    )

    carrier_service_code = str(
        service_level.carrier_service_code
        or resolve_carrier_service(service)
        or ""
    ).strip().upper()

    # Strict exact-band validation only applies when services.csv explicitly
    # configured package_format_identifier.
    if package_format_identifier_is_explicit and service_format not in [None, ""]:
        normalized_service_format = normalize_click_and_drop_package_format_identifier(
            service_format
        )
        normalized_service_kind = _package_format_register_kind(
            normalized_service_format
        )

        if normalized_service_format == requested_format:
            return True

        # Generic Click & Drop `parcel` is compatible with parcel-band services.
        if (
            requested_format == PackagingType.parcel.value
            and normalized_service_kind == "parcel"
            and requested_kind == "parcel"
        ):
            return True

        return False

    # Some Royal Mail services intentionally use packageFormatIdentifier as the
    # package-level discriminator. TPN24 is the key example: the same serviceCode
    # can be used with letter, largeLetter, or parcel.
    if carrier_service_code in CLICK_AND_DROP_FLEXIBLE_PACKAGE_FORMAT_SERVICE_CODES:
        return requested_kind in ["letter", "large_letter", "parcel"]

    # For all other blank package_format_identifier rows, enforce the inferred
    # package kind so that letter services do not accept parcels and parcel
    # services do not accept letters.
    if service_kind not in [None, ""]:
        return service_kind == requested_kind

    # Generic services with no package-format metadata should not be returned
    # for letter or large-letter requests.
    if requested_kind in ["letter", "large_letter"]:
        return False

    # Keep generic services available for parcel-like shipments.
    return requested_kind == "parcel"

def normalize_carrier_specific_options(
    options: dict,
    configured_option_names: typing.Optional[typing.Iterable[str]] = None,
    carrier_names: typing.Optional[typing.Iterable[str]] = None,
) -> dict:
    """
    Normalize Royal Mail options submitted by different Karrio UI/API paths.

    Supported input shapes:

        {
            "include_returns_label": true
        }

        {
            "royalmail": {
                "include_returns_label": true
            }
        }

        {
            "royalmail": {
                "includeReturnsLabel": true
            }
        }

    Some Karrio CE UI screens submit carrier-specific options as array indexes
    under the carrier key, based on config.shipping_options, e.g.

        {
            "royalmail": {
                "0": true
            }
        }

    If configured_option_names=["include_returns_label"], this helper maps
    "0" back to "include_returns_label".
    """
    raw_options = dict(options or {})

    aliases = {
        "royalmail",
        "royal_mail",
        "royal-mail",
        "royalmail_click_and_drop",
        "royalmail_clickanddrop",
        "click_and_drop",
    }

    for carrier_name in carrier_names or []:
        if carrier_name not in [None, ""]:
            aliases.add(str(carrier_name))

    configured_names = shipping_option_names_initializer(
        configured_option_names or []
    )

    flattened = {}

    for key, value in raw_options.items():
        if key in aliases and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                resolved_key = None

                if str(nested_key).isdigit():
                    index = int(str(nested_key))

                    if 0 <= index < len(configured_names):
                        resolved_key = configured_names[index]
                else:
                    resolved_key = normalize_shipping_option_name(nested_key)

                if resolved_key:
                    flattened[resolved_key] = nested_value

            continue

        flattened[key] = value

    return flattened

def resolve_carrier_service(service: typing.Optional[str]) -> typing.Optional[str]:
    """
    Resolve a supported selector to the Royal Mail API `serviceCode`.

    Behaviour:
    - Active Karrio service selectors resolve normally.
    - Exact inactive CSV service codes may still resolve for direct Click & Drop
      shipment serialization.
    - Raw Royal Mail carrier codes such as CRL24 pass through when known in the
      full CSV catalogue.
    - Ambiguous raw carrier codes should not be converted to one arbitrary
      Karrio service_code.
    """
    service_level = resolve_service_level(service)

    if service_level is not None:
        return service_level.carrier_service_code

    raw = str(service or "").strip()

    if raw == "":
        return None

    # Exact inactive/full-catalogue Karrio service_code fallback.
    service_level = (
        ALL_SERVICE_LEVEL_BY_CODE.get(raw)
        or ALL_SERVICES_INDEX.get(raw.lower())
    )

    if service_level is not None:
        return service_level.carrier_service_code

    raw_upper = raw.upper()

    # Raw active carrier code passthrough.
    if raw_upper in CARRIER_SERVICES_INDEX:
        return raw_upper

    # Raw full-catalogue carrier code passthrough. This is required for direct
    # Click & Drop shipment creation with raw codes such as CRL24/CRL48.
    if raw_upper in ALL_CARRIER_SERVICE_CODES:
        return raw_upper

    mapped = ShippingService.map(service)

    if getattr(mapped, "enum", None) is not None:
        service_code = (
            mapped.name
            if mapped.name in SERVICE_LEVEL_BY_CODE
            else mapped.value
        )
        service_level = SERVICE_LEVEL_BY_CODE.get(service_code)

        if service_level is not None:
            return service_level.carrier_service_code

    return None

def resolve_return_carrier_service(
    service: typing.Optional[str],
    include_inactive: bool = True,
) -> typing.Optional[str]:
    """
    Resolve a return shipment selector to a Royal Mail return serviceCode.

    By default this is permissive because POST /returns may need to accept
    Royal Mail return services that are inactive in services.csv for local
    rating/rate-sheet purposes.

    Use include_inactive=False for runtime/service-catalog checks.
    """
    if service in [None, ""]:
        return None

    return_codes = (
        ALL_RETURN_SERVICE_CODES
        if include_inactive
        else RETURN_SERVICE_CODES
    )
    selector_index = (
        ALL_RETURN_SERVICE_SELECTOR_INDEX
        if include_inactive
        else RETURN_SERVICE_SELECTOR_INDEX
    )

    # First try the normal active-service resolver. This handles active
    # service_code, carrier_service_code, service_name, friendly name, and enum
    # selectors.
    carrier_service_code = resolve_carrier_service(service)

    if carrier_service_code:
        carrier_service_code = str(carrier_service_code).strip().upper()

        if carrier_service_code in return_codes:
            return carrier_service_code

    raw = str(service).strip()
    raw_upper = raw.upper()

    # Raw Royal Mail return serviceCode passthrough, e.g. TSS.
    # With include_inactive=False this only allows active return carrier codes.
    if raw_upper in return_codes:
        return raw_upper

    key = _service_selector_key(raw)

    if key is None:
        return None

    matches = selector_index.get(key) or set()

    if len(matches) == 1:
        return next(iter(matches))

    return None


def is_return_service(service: typing.Optional[str]) -> bool:
    """
    Return whether a selector resolves to an active runtime return service.

    This intentionally excludes inactive CSV return services such as insured
    return variants that are present for Click & Drop passthrough but should not
    be exposed as active runtime services.
    """
    return resolve_return_carrier_service(
        service,
        include_inactive=False,
    ) is not None

def resolve_service_register_code(
    service: typing.Optional[str],
    package_format: typing.Optional[str] = None,
) -> typing.Optional[str]:
    """
    Resolve any supported selector to the Royal Mail API `serviceRegisterCode`.

    Important:
    This resolver is used for Click & Drop shipment serialization, so it must be
    broader than the active Karrio rating/reference catalogue.

    Rules:
    - Prefer package-format-specific carrier mappings.
    - Use the full CSV catalogue for metadata, because inactive rows may still
      contain required Click & Drop register data.
    - If no package-format-specific mapping exists, fall back to a carrier-level
      mapping only when that carrier code has exactly one unambiguous register
      code across the catalogue.
    - Preserve active-only service exposure elsewhere; do not use this function
      to decide whether a service should appear in Karrio rates/references.
    """
    if service in [None, ""]:
        return None

    package_format_kind = _package_format_register_kind(package_format)

    carrier_service_code_candidates: typing.List[str] = []

    def append_carrier_candidate(value: typing.Any) -> None:
        if value in [None, ""]:
            return

        candidate = str(value).strip().upper()

        if candidate and candidate not in carrier_service_code_candidates:
            carrier_service_code_candidates.append(candidate)

    append_carrier_candidate(resolve_carrier_service(service))

    raw = str(service or "").strip()

    if raw:
        raw_upper = raw.upper()

        if raw_upper in ALL_CARRIER_SERVICE_CODES:
            append_carrier_candidate(raw_upper)

    service_level = resolve_any_service_level(service)

    if service_level is not None:
        append_carrier_candidate(service_level.carrier_service_code)

    # First resolve by carrier serviceCode + package kind. This is the critical
    # path for services where the register code depends on format, for example:
    #
    #   CRL24 + largeLetter -> 01
    #   CRL24 + parcel      -> 02
    if package_format_kind:
        for carrier_service_code in carrier_service_code_candidates:
            active_register_code = (
                ACTIVE_SERVICE_REGISTER_BY_CARRIER_AND_FORMAT.get(
                    (carrier_service_code, package_format_kind)
                )
            )

            if active_register_code not in [None, ""]:
                return active_register_code

            register_code = SERVICE_REGISTER_BY_CARRIER_AND_FORMAT.get(
                (carrier_service_code, package_format_kind)
            )

            if register_code not in [None, ""]:
                return register_code

    # If the package-format-specific lookup did not find a value, fall back to
    # carrier-level metadata only when it is unambiguous. This fixes DDP/DTP
    # services such as MPR where the CSV row has serviceRegisterCode=01 but no
    # package_format_identifier/package kind.
    for carrier_service_code in carrier_service_code_candidates:
        active_register_code = ACTIVE_SERVICE_REGISTER_BY_CARRIER.get(
            carrier_service_code
        )

        if active_register_code not in [None, ""]:
            return active_register_code

        register_code = SERVICE_REGISTER_BY_CARRIER.get(carrier_service_code)

        if register_code not in [None, ""]:
            return register_code

    if service_level is None:
        return None

    metadata = service_level.metadata or {}
    service_register_code = metadata.get("service_register_code")

    if service_register_code in [None, ""]:
        return None

    service_kind = metadata.get("package_format_kind")

    carrier_service_code = str(
        service_level.carrier_service_code
        or next(iter(carrier_service_code_candidates), "")
        or ""
    ).strip().upper()

    # No package kind supplied: the service-level register code is the best
    # available value.
    if package_format_kind is None:
        return service_register_code

    # TPN24-style flexible services use the service-level register code while
    # packageFormatIdentifier carries the letter/largeLetter/parcel distinction.
    if carrier_service_code in CLICK_AND_DROP_FLEXIBLE_PACKAGE_FORMAT_SERVICE_CODES:
        return service_register_code

    # Non-flexible services must not silently reuse a letter register code for a
    # parcel shipment, or vice versa.
    if service_kind in [None, ""]:
        return None

    if service_kind != package_format_kind:
        return None

    return service_register_code


def resolve_service_name(
    service: typing.Optional[str],
    friendly: bool = True,
) -> typing.Optional[str]:
    """Return the display name for a resolved Royal Mail service."""
    service_level = resolve_service_level(service)
    if service_level is None:
        return None

    if friendly:
        return (
            _friendly_service_name(service_level.service_name)
            or service_level.service_name
        )

    return service_level.service_name


KNOWN_UNSUPPORTED_EMAIL_NOTIFICATION_SERVICES: typing.Set[str] = {
    "CRL24",
    "CRL48",
}


def _service_metadata_bool(
    service: typing.Any,
    *keys: str,
) -> typing.Optional[bool]:
    """Read a boolean metadata flag from a ServiceLevel."""
    service_level = resolve_service_level(service)
    if service_level is None:
        return None

    metadata = service_level.metadata or {}

    for key in keys:
        if key not in metadata:
            continue

        value = metadata.get(key)

        if isinstance(value, bool):
            return value

        if value in [None, ""]:
            continue

        return _to_bool(value, default=None)

    return None

DUTY_PAID_INCOTERMS: typing.Set[str] = {
    "DDP",  # Delivered Duty Paid
    "DTP",  # Royal Mail / Parcelforce duty-and-tax-paid style selector
}

DUTY_UNPAID_INCOTERMS: typing.Set[str] = {
    "DAP",  # Delivered At Place
    "DDU",  # Delivered Duty Unpaid, legacy/non-Incoterms but commonly used
    "DPU",
    "DAT",
    "EXW",
    "FCA",
    "FAS",
    "FOB",
    "CFR",
    "CIF",
    "CPT",
    "CIP",
}

DUTY_PAID_FEATURE_TOKENS: typing.Set[str] = {
    "ddp",
    "dtp",
    "duty_paid",
    "dutypaid",
    "duties_paid",
    "dutiespaid",
    "delivery_duty_paid",
    "deliverydutypaid",
    "taxes_paid",
    "taxespaid",
    "duties_taxes_paid",
    "dutiestaxespaid",
    "duty_tax_paid",
    "dutytaxpaid",
}

DUTY_UNPAID_FEATURE_TOKENS: typing.Set[str] = {
    "dap",
    "ddu",
    "duty_unpaid",
    "dutyunpaid",
    "duties_unpaid",
    "dutiesunpaid",
    "delivery_duty_unpaid",
    "deliverydutyunpaid",
}

DUTY_PAID_BY_VALUES: typing.Set[str] = {
    "sender",
    "shipper",
    "merchant",
    "seller",
    "account",
    "account_holder",
}

DUTY_UNPAID_BY_VALUES: typing.Set[str] = {
    "recipient",
    "receiver",
    "consignee",
    "customer",
    "buyer",
}


def _normalize_duty_token(value: typing.Any) -> typing.Optional[str]:
    """Normalize incoterm/feature/service tokens used for duty-paid routing."""
    value = _raw_state_value(value)

    if value in [None, ""]:
        return None

    text = str(value).strip().lower()

    if text == "":
        return None

    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _selector_has_duty_paid_marker(*values: typing.Any) -> bool:
    """
    Return whether a service selector/name visibly represents DDP/DTP.

    This intentionally supports inactive/full-catalogue services whose CSV
    feature list may not include `ddp`, but whose Royal Mail product name or
    Karrio service_code contains `ddp` or `dtp`.
    """
    for value in values:
        token = _normalize_duty_token(value)

        if token in [None, ""]:
            continue

        parts = {part for part in token.split("_") if part}

        if parts.intersection({"ddp", "dtp"}):
            return True

        if any(marker in token for marker in DUTY_PAID_FEATURE_TOKENS):
            return True

    return False


def _service_level_feature_tokens(
    service_level: typing.Optional[models.ServiceLevel],
) -> typing.Set[str]:
    """Return normalized feature tokens from a ServiceLevel metadata object."""
    if service_level is None:
        return set()

    metadata = service_level.metadata or {}
    feature_codes = metadata.get("feature_codes") or []

    if isinstance(feature_codes, str):
        feature_codes = _to_list(feature_codes)

    return {
        token
        for token in (
            _normalize_duty_token(raw_token)
            for raw_token in feature_codes
        )
        if token
    }


def _service_feature_tokens(service: typing.Any) -> typing.Set[str]:
    """Return normalized feature tokens from active service metadata."""
    return _service_level_feature_tokens(resolve_service_level(service))


def service_supports_ddp(service: typing.Any) -> bool:
    """
    Return whether a Royal Mail service is DDP/DTP / duty-paid capable.

    Royal Mail Click & Drop exposes duty-paid handling primarily through the
    selected service/product. The Click & Drop order field `customsDutyCosts`
    is documented as supported only for DDP services.

    This resolver intentionally checks:
    - active service catalogue
    - full/inactive CSV catalogue
    - raw carrier service codes
    - visible DDP/DTP markers in service_code/service_name
    """
    if service in [None, ""]:
        return False

    if hasattr(service, "service_code") and hasattr(service, "carrier_service_code"):
        service_level = service
    else:
        service_level = resolve_any_service_level(service)

    if service_level is not None:
        feature_tokens = _service_level_feature_tokens(service_level)

        if feature_tokens.intersection(DUTY_PAID_FEATURE_TOKENS):
            return True

        return _selector_has_duty_paid_marker(
            getattr(service_level, "service_code", None),
            getattr(service_level, "service_name", None),
            getattr(service_level, "carrier_service_code", None),
        )

    raw_selector = str(service).strip()

    if raw_selector == "":
        return False

    if _selector_has_duty_paid_marker(raw_selector):
        return True

    raw_carrier_code = raw_selector.upper()

    carrier_matches = [
        candidate
        for candidate in DEFAULT_SERVICES
        if str(candidate.carrier_service_code or "").strip().upper()
        == raw_carrier_code
    ]

    return any(service_supports_ddp(candidate) for candidate in carrier_matches)


def service_supports_email_notification(service: typing.Any) -> bool:
    """
    Resolve whether a Royal Mail service supports email notifications.

    Priority:
    1. Explicit service metadata in services.csv via meta_* columns
    2. Explicit feature tokens such as `email_notification`
    3. Explicit deny-list / no-notification feature tokens
    4. Known unsupported carrier-code deny-list
    5. Conservative fallback to False when capability is unknown
    """
    explicit = _service_metadata_bool(
        service,
        "supports_email_notification",
        "email_notification_supported",
        "receive_email_notification",
    )
    if explicit is not None:
        return explicit

    feature_tokens = _service_feature_tokens(service)

    if any(
        token in feature_tokens
        for token in ["email_notification", "email_notifications"]
    ):
        return True

    if any(
        token in feature_tokens
        for token in [
            "no_email_notification",
            "email_notification_disabled",
            "notifications_disabled",
        ]
    ):
        return False

    carrier_service_code = resolve_carrier_service(service)

    if carrier_service_code in KNOWN_UNSUPPORTED_EMAIL_NOTIFICATION_SERVICES:
        return False

    return False


def build_dimensions(package, dimension_type, raw_package=None):
    """Build Karrio Dimension objects from CSV package limits."""
    raw_dimension_unit = _source_value(raw_package, "dimension_unit", "dimensionUnit")

    height_in_mms = (
        dimension_to_mms(_source_value(raw_package, "height"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    width_in_mms = (
        dimension_to_mms(_source_value(raw_package, "width"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    depth_in_mms = (
        dimension_to_mms(_source_value(raw_package, "length"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )

    if height_in_mms is None and package is not None:
        height_in_mms = dimension_in_mms(getattr(package, "height", None))
    if width_in_mms is None and package is not None:
        width_in_mms = dimension_in_mms(getattr(package, "width", None))
    if depth_in_mms is None and package is not None:
        depth_in_mms = dimension_in_mms(getattr(package, "length", None))

    if not all(value is not None for value in [height_in_mms, width_in_mms, depth_in_mms]):
        return None

    return dimension_type(
        heightInMms=height_in_mms,
        widthInMms=width_in_mms,
        depthInMms=depth_in_mms,
    )


def resolve_package_format(
    package=None,
    raw_package=None,
    explicit: typing.Optional[str] = None,
) -> str:
    """
    Resolve Royal Mail package format identifier.

    Priority:
    1. Explicit option override
    2. Raw package packaging_type alias mapping
    3. Normalized package packaging_type alias mapping
    4. Inference from raw dimensions/weight
    5. Fallback to normalized dimensions/weight
    6. Fallback to smallParcel

    If explicit is an unknown string, it is passed through to support
    ChannelShipper custom package format identifiers.
    """
    if explicit:
        mapped = PackagingType.map(explicit).value_or_key
        return mapped if mapped is not None else str(explicit)

    raw_packaging_type = _source_value(raw_package, "packaging_type", "packagingType")
    if raw_packaging_type:
        mapped = PackagingType.map(raw_packaging_type).value_or_key
        if mapped is not None:
            return mapped

    if package is not None and getattr(package, "packaging_type", None):
        mapped = PackagingType.map(package.packaging_type).value_or_key
        if mapped is not None:
            return mapped

    raw_weight = _source_value(raw_package, "weight")
    raw_weight_unit = _source_value(raw_package, "weight_unit", "weightUnit") or "G"
    raw_dimension_unit = _source_value(raw_package, "dimension_unit", "dimensionUnit")

    weight_g = (
        weight_to_grams(raw_weight, raw_weight_unit)
        if raw_weight is not None
        else None
    )
    if weight_g is None and package is not None:
        weight_g = weight_in_grams(getattr(package, "weight", None))

    length_mm = (
        dimension_to_mms(_source_value(raw_package, "length"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    if length_mm is None and package is not None:
        length_mm = dimension_in_mms(getattr(package, "length", None))

    width_mm = (
        dimension_to_mms(_source_value(raw_package, "width"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    if width_mm is None and package is not None:
        width_mm = dimension_in_mms(getattr(package, "width", None))

    height_mm = (
        dimension_to_mms(_source_value(raw_package, "height"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    if height_mm is None and package is not None:
        height_mm = dimension_in_mms(getattr(package, "height", None))

    dims = [length_mm, width_mm, height_mm]
    dims = [d for d in dims if d is not None]

    if len(dims) == 3:
        max_dim = max(dims)
        min_dim = min(dims)
        mid_dim = sorted(dims)[1]

        if (weight_g or 0) <= 100 and max_dim <= 240 and mid_dim <= 165 and min_dim <= 5:
            return PackagingType.letter.value

        if (weight_g or 0) <= 750 and max_dim <= 353 and mid_dim <= 250 and min_dim <= 25:
            return PackagingType.large_letter.value

        if (weight_g or 0) <= 2000 and max_dim <= 450 and mid_dim <= 350 and min_dim <= 160:
            return PackagingType.small_parcel.value

        if (weight_g or 0) <= 20000 and max_dim <= 610 and mid_dim <= 460 and min_dim <= 460:
            return PackagingType.medium_parcel.value

        return PackagingType.large_parcel.value

    if weight_g is not None:
        if weight_g <= 100:
            return PackagingType.letter.value
        if weight_g <= 750:
            return PackagingType.large_letter.value
        if weight_g <= 2000:
            return PackagingType.small_parcel.value
        if weight_g <= 20000:
            return PackagingType.medium_parcel.value
        return PackagingType.large_parcel.value

    return PackagingType.small_parcel.value


def _first_present_value(*values):
    """Return the first non-empty value."""
    for value in values:
        if value not in [None, ""]:
            return value

    return None


def rate_request_package_formats(rate_request: typing.Any) -> typing.List[str]:
    """
    Resolve Royal Mail packageFormatIdentifier values from a Karrio RateRequest.

    Important:
    Do not call `lib.to_packages()` here after converting the request with
    `lib.to_dict()`. At that point parcels are plain dictionaries, while
    `lib.to_packages()` expects Karrio Parcel objects.

    `resolve_package_format()` already supports raw dict parcels, so use that
    directly.
    """
    request_data = lib.to_dict(rate_request, clear_empty=False) or {}

    if not isinstance(request_data, dict):
        return []

    raw_parcels = request_data.get("parcels") or []

    if isinstance(raw_parcels, (list, tuple)):
        raw_parcels = list(raw_parcels)
    else:
        raw_parcels = [raw_parcels]

    request_options = request_data.get("options") or {}

    shipment_package_format = _source_value(
        request_options,
        "package_format_identifier",
        "packageFormatIdentifier",
    )

    package_formats = []

    for raw_package in raw_parcels:
        raw_package_options = _source_value(raw_package, "options") or {}

        package_explicit_format = _first_present_value(
            _source_value(
                raw_package_options,
                "package_format_identifier",
                "packageFormatIdentifier",
            ),
            _source_value(
                raw_package,
                "package_format_identifier",
                "packageFormatIdentifier",
            ),
            shipment_package_format,
        )

        package_format = resolve_package_format(
            package=None if isinstance(raw_package, dict) else raw_package,
            raw_package=raw_package,
            explicit=package_explicit_format,
        )

        if package_format not in [None, ""]:
            package_formats.append(package_format)

    return package_formats


def resolve_rate_service_codes(
    service: typing.Any,
    package_formats: typing.Optional[typing.Iterable[str]] = None,
) -> typing.List[str]:
    """
    Resolve a user-supplied rate service selector into active canonical Karrio
    service codes.

    Important:
    - Exact inactive service_code values return [].
    - Raw Royal Mail carrier codes expand only to active matching services.
    - Unknown custom selectors are preserved for backward compatibility.
    """
    if service in [None, ""]:
        return []

    raw_text = str(service).strip()

    if raw_text == "":
        return []

    exact_service_level = ALL_SERVICE_LEVEL_BY_CODE.get(raw_text)

    if exact_service_level is not None and not service_is_active(exact_service_level):
        return []

    canonical_service_code = resolve_service_code(service)

    if canonical_service_code is not None:
        return [canonical_service_code]

    raw_carrier_code = raw_text.upper()
    carrier_matches = [
        service_level
        for service_level in (CARRIER_SERVICES_INDEX.get(raw_carrier_code) or [])
        if service_is_active(service_level)
    ]

    if not any(carrier_matches):
        return [raw_text]

    formats = [
        package_format
        for package_format in (package_formats or [])
        if package_format not in [None, ""]
    ]

    resolved = []

    for service_level in carrier_matches:
        if any(formats) and not any(
            service_supports_package_format(
                service_level.service_code,
                package_format,
            )
            for package_format in formats
        ):
            continue

        resolved.append(service_level.service_code)

    return list(dict.fromkeys(resolved))


def resolve_rate_services(
    services: typing.Iterable[typing.Any],
    package_formats: typing.Optional[typing.Iterable[str]] = None,
) -> typing.List[str]:
    """
    Resolve all requested rate services into canonical Karrio service codes.
    """
    if services in [None, ""]:
        return []

    if isinstance(services, str):
        services = [services]

    resolved = []

    for service in services or []:
        resolved.extend(
            resolve_rate_service_codes(
                service,
                package_formats=package_formats,
            )
        )

    return list(
        dict.fromkeys(
            item
            for item in resolved
            if item not in [None, ""]
        )
    )


def normalize_customs_category(value: typing.Any) -> typing.Optional[str]:
    """Normalize customs category aliases to Royal Mail enum values."""
    if value in [None, ""]:
        return None

    raw_value = str(value).strip()
    normalized = raw_value.replace("-", "_").replace(" ", "_")
    lower_normalized = normalized.lower()

    mapping = {
        "none": "none",
        "gift": "gift",
        "sample": "commercialSample",
        "commercial_sample": "commercialSample",
        "commercialSample": "commercialSample",
        "documents": "documents",
        "document": "documents",
        "other": "other",
        "return_merchandise": "returnedGoods",
        "returned_goods": "returnedGoods",
        "returnedGoods": "returnedGoods",
        "merchandise": "saleOfGoods",
        "sale_of_goods": "saleOfGoods",
        "saleOfGoods": "saleOfGoods",
        "mixed": "mixedContent",
        "mixed_content": "mixedContent",
        "mixedContent": "mixedContent",
    }

    return mapping.get(
        raw_value,
        mapping.get(normalized, mapping.get(lower_normalized, "other")),
    )

def resolve_customs_category(customs) -> typing.Optional[str]:
    """Resolve a customs category from item metadata or options."""
    if customs is None:
        return None

    customs_options = getattr(customs, "options", None)
    raw_value = (
        _source_value(customs, "content_type", "contentType")
        or _source_value(
            customs_options,
            "customs_declaration_category",
            "customsDeclarationCategory",
        )
    )

    return normalize_customs_category(raw_value)

# ---------------------------------------------------------------------------
# Royal Mail metadata/options/enums/helpers
# ---------------------------------------------------------------------------
# These symbols are required by:
# - karrio.plugins.royalmail.METADATA
# - karrio.providers.royalmail.utils.Settings.connection_config
# - shipment/create.py
# - shipment/return_shipment.py
#
# Keep this section import-safe. The plugin loader imports units.py while
# building PluginMetadata, so missing names here prevent the carrier from being
# registered in karrio.gateway.
# ---------------------------------------------------------------------------


class LabelType(lib.StrEnum):
    """Supported Click & Drop label document types."""
    PDF = "PDF"


class NotificationTarget(lib.StrEnum):
    """Royal Mail notification recipient target values."""
    recipient = "recipient"
    sender = "sender"
    billing = "billing"


class PackagingType(lib.StrEnum):
    # Click & Drop standard packageFormatIdentifier values.
    """Royal Mail Click & Drop package format identifiers and aliases."""
    undefined = "undefined"
    letter = "letter"
    large_letter = "largeLetter"
    largeLetter = "largeLetter"
    small_parcel = "smallParcel"
    smallParcel = "smallParcel"
    medium_parcel = "mediumParcel"
    mediumParcel = "mediumParcel"
    large_parcel = "largeParcel"
    largeParcel = "largeParcel"
    parcel = "parcel"
    documents = "documents"

    # Common Karrio/unified aliases.
    envelope = "letter"
    pak = "largeLetter"
    document = "documents"
    documents_pack = "documents"
    small_box = "smallParcel"
    medium_box = "mediumParcel"
    large_box = "largeParcel"

    # Keep this mapped to smallParcel for internal rating inference.
    # The Click & Drop API conversion to `parcel` happens later in
    # resolve_click_and_drop_package_format_identifier().
    your_packaging = "smallParcel"


PRESET_DEFAULTS = dict(
    weight_unit="KG",
    dimension_unit="CM",
)


class PackagePresets(lib.Enum):
    """Karrio package presets mapped to Royal Mail package formats."""
    royalmail_letter = lib.units.PackagePreset(
        weight=0.1,
        width=16.5,
        height=0.5,
        length=24.0,
        packaging_type=PackagingType.letter.value,
        **PRESET_DEFAULTS,
    )
    royalmail_large_letter = lib.units.PackagePreset(
        weight=0.75,
        width=25.0,
        height=2.5,
        length=35.3,
        packaging_type=PackagingType.large_letter.value,
        **PRESET_DEFAULTS,
    )
    royalmail_small_parcel = lib.units.PackagePreset(
        weight=2.0,
        width=35.0,
        height=16.0,
        length=45.0,
        packaging_type=PackagingType.small_parcel.value,
        **PRESET_DEFAULTS,
    )
    royalmail_medium_parcel = lib.units.PackagePreset(
        weight=20.0,
        width=46.0,
        height=46.0,
        length=61.0,
        packaging_type=PackagingType.medium_parcel.value,
        **PRESET_DEFAULTS,
    )


class ConnectionConfig(lib.Enum):
    """Royal Mail connection-level configuration option definitions."""
    click_and_drop_api_base_url = lib.OptionEnum(
        "click_and_drop_api_base_url",
        str,
        default="https://api.parcel.royalmail.com/api/v1",
    )
    tracking_api_base_url = lib.OptionEnum(
        "tracking_api_base_url",
        str,
        default="https://api.royalmail.net",
    )
    label_type = lib.OptionEnum(
        "label_type",
        LabelType,
        default=LabelType.PDF.value,
    )
    carrier_name = lib.OptionEnum(
        "carrier_name",
        str,
        default="Royal Mail",
    )
    include_label_in_response = lib.OptionEnum(
        "include_label_in_response",
        bool,
        default=True,
    )
    include_return_label_in_response = lib.OptionEnum(
        "include_return_label_in_response",
        bool,
        default=False,
    )

    # Standard Karrio config entries used by the references/config UI.
    shipping_options = lib.OptionEnum("shipping_options", list)
    shipping_services = lib.OptionEnum("shipping_services", list)

    apply_uk_vat_to_rates = lib.OptionEnum(
        "apply_uk_vat_to_rates",
        bool,
        default=False,
    )
    uk_vat_rate_percentage = lib.OptionEnum(
        "uk_vat_rate_percentage",
        float,
        default=20.0,
    )



def connection_config_initializer(options: dict) -> lib.units.ShippingOptions:
    """
    Normalize Royal Mail connection/config option values.

    This primarily guards boolean fields that may arrive as strings from env/UI
    sources, e.g. `"false"` or `"0"`.
    """
    normalized = {}

    for key, value in dict(options or {}).items():
        if key in _CONFIG_BOOLEAN_KEYS:
            normalized[key] = (
                _to_bool(value, default=None)
                if value not in [None, ""]
                else value
            )
        else:
            normalized[key] = value

    return lib.units.ShippingOptions(normalized, ConnectionConfig)

class ShippingOption(lib.Enum):
    # Service/order selection
    """Royal Mail shipment option definitions exposed to Karrio."""
    service_code = lib.OptionEnum("serviceCode", str)
    service_register_code = lib.OptionEnum("serviceRegisterCode", str)
    carrier_name = lib.OptionEnum("carrierName", str)
    order_reference = lib.OptionEnum("orderReference", str)
    order_date = lib.OptionEnum("orderDate", str)
    planned_despatch_date = lib.OptionEnum("plannedDespatchDate", str)

    # Package/label
    package_format_identifier = lib.OptionEnum("packageFormatIdentifier", str)
    include_label_in_response = lib.OptionEnum("includeLabelInResponse", bool)
    include_cn = lib.OptionEnum("includeCN", bool)
    include_returns_label = lib.OptionEnum("includeReturnsLabel", bool)

    # Order values
    subtotal = lib.OptionEnum("subtotal", float)
    shipping_cost_charged = lib.OptionEnum("shippingCostCharged", float)
    shipping_charges = lib.OptionEnum(
        "shipping_charges",
        float,
        meta=dict(category="ORDER_VALUE"),
    )
    other_costs = lib.OptionEnum("otherCosts", float)
    order_tax = lib.OptionEnum("orderTax", float)
    customs_duty_costs = lib.OptionEnum("customsDutyCosts", float)
    duty_paid = lib.OptionEnum(
        "duty_paid",
        bool,
        meta=dict(category="CUSTOMS"),
    )
    total = lib.OptionEnum("total", float)
    currency = lib.OptionEnum("currency", str)

    # Instructions / notes
    shipment_note = lib.OptionEnum(
        "shipment_note",
        str,
        meta=dict(category="INSTRUCTIONS"),
    )
    shipper_instructions = lib.OptionEnum(
        "shipper_instructions",
        str,
        meta=dict(category="INSTRUCTIONS"),
    )
    recipient_instructions = lib.OptionEnum(
        "recipient_instructions",
        str,
        meta=dict(category="INSTRUCTIONS"),
    )
    special_instructions = lib.OptionEnum(
        "special_instructions",
        str,
        meta=dict(category="INSTRUCTIONS"),
    )

    # Notifications
    send_notifications_to = lib.OptionEnum(
        "sendNotificationsTo",
        NotificationTarget,
    )
    receive_email_notification = lib.OptionEnum(
        "receiveEmailNotification",
        bool,
    )
    receive_sms_notification = lib.OptionEnum(
        "receiveSmsNotification",
        bool,
    )
    email_notification_to = lib.OptionEnum(
        "email_notification_to",
        str,
        meta=dict(category="NOTIFICATION"),
    )

        # Rate/service capability filters
    #
    # This is primarily used during rating. Click & Drop does not receive an
    # `is_tracked` field directly; instead, rating uses it to restrict returned
    # services to services whose CSV feature metadata includes `tracked`.
    is_tracked = lib.OptionEnum(
        "is_tracked",
        bool,
        meta=dict(category="TRACKING"),
    )

    # Postage details
    consequential_loss = lib.OptionEnum("consequentialLoss", int)
    request_signature_upon_delivery = lib.OptionEnum(
        "requestSignatureUponDelivery",
        bool,
    )

    # Royal Mail identity / age-check services.
    royalmail_age_verification = lib.OptionEnum(
        "royalmail_age_verification",
        bool,
        meta=dict(category="IDENTITY"),
    )
    royalmail_id_verification = lib.OptionEnum(
        "royalmail_id_verification",
        bool,
        meta=dict(category="IDENTITY"),
    )

    is_local_collect = lib.OptionEnum("isLocalCollect", bool)
    safe_place = lib.OptionEnum("safePlace", str)
    department = lib.OptionEnum("department", str)
    air_number = lib.OptionEnum("AIRNumber", str)
    ioss_number = lib.OptionEnum("IOSSNumber", str)
    requires_export_license = lib.OptionEnum("requiresExportLicense", bool)
    commercial_invoice_number = lib.OptionEnum("commercialInvoiceNumber", str)
    commercial_invoice_date = lib.OptionEnum("commercialInvoiceDate", str)
    invoice_number = lib.OptionEnum(
        "invoice_number",
        str,
        meta=dict(category="INVOICE"),
    )
    invoice_date = lib.OptionEnum(
        "invoice_date",
        str,
        meta=dict(category="INVOICE"),
    )
    recipient_eori_number = lib.OptionEnum("recipientEoriNumber", str)

    # Recipient address book
    address_book_reference = lib.OptionEnum("addressBookReference", str)

    # Importer
    importer_vat_number = lib.OptionEnum("importerVatNumber", str)
    importer_tax_code = lib.OptionEnum("importerTaxCode", str)
    importer_eori_number = lib.OptionEnum("importerEoriNumber", str)

    # Dangerous goods
    contains_dangerous_goods = lib.OptionEnum("containsDangerousGoods", bool)
    dangerous_goods_un_code = lib.OptionEnum("dangerousGoodsUnCode", str)
    dangerous_goods_description = lib.OptionEnum(
        "dangerousGoodsDescription",
        str,
    )
    dangerous_goods_quantity = lib.OptionEnum("dangerousGoodsQuantity", float)

_OPTION_ALIASES = {
    # Service / order selection
    "serviceCode": "service_code",
    "service_code": "service_code",
    "serviceRegisterCode": "service_register_code",
    "carrierName": "carrier_name",
    "orderReference": "order_reference",
    "orderDate": "order_date",
    "plannedDespatchDate": "planned_despatch_date",

    # Package / label
    "packageFormatIdentifier": "package_format_identifier",
    "includeLabelInResponse": "include_label_in_response",
    "includeCN": "include_cn",
    "includeReturnsLabel": "include_returns_label",

    # Order values
    "subtotal": "subtotal",
    "shippingCostCharged": "shipping_cost_charged",
    "shippingCharges": "shipping_charges",
    "shipping_charges": "shipping_charges",
    "otherCosts": "other_costs",
    "orderTax": "order_tax",
    "customsDutyCosts": "customs_duty_costs",
    "currencyCode": "currency",
    "currency": "currency",
    "total": "total",

    # Duty stuff
    "dutyPaid": "duty_paid",
    "duty_paid": "duty_paid",
    "deliveryDutyPaid": "duty_paid",
    "delivery_duty_paid": "duty_paid",
    "ddp": "duty_paid",
    "dtp": "duty_paid",

    "dutyUnpaid": "duty_unpaid",
    "duty_unpaid": "duty_unpaid",
    "deliveryDutyUnpaid": "duty_unpaid",
    "delivery_duty_unpaid": "duty_unpaid",
    "dap": "duty_unpaid",
    "ddu": "duty_unpaid",

    "incoterm": "incoterm",
    "incoterms": "incoterm",
    "termsOfTrade": "terms_of_trade",
    "terms_of_trade": "terms_of_trade",
    "deliveryTerms": "delivery_terms",
    "delivery_terms": "delivery_terms",
    "dutyTerms": "duty_terms",
    "duty_terms": "duty_terms",

    # Instructions / notes
    "shipmentNote": "shipment_note",
    "shipment_note": "shipment_note",
    "shipperInstructions": "shipper_instructions",
    "shipper_instructions": "shipper_instructions",
    "recipientInstructions": "recipient_instructions",
    "recipient_instructions": "recipient_instructions",
    "specialInstructions": "special_instructions",
    "special_instructions": "special_instructions",

    # Notifications
    "sendNotificationsTo": "send_notifications_to",
    "receiveEmailNotification": "receive_email_notification",
    "receiveSmsNotification": "receive_sms_notification",
    "emailNotification": "receive_email_notification",
    "smsNotification": "receive_sms_notification",
    "emailNotificationTo": "email_notification_to",
    "email_notification": "receive_email_notification",
    "sms_notification": "receive_sms_notification",
    "email_notification_to": "email_notification_to",

    # Standard Karrio compatibility aliases
    "signature_confirmation": "request_signature_upon_delivery",
    "signatureConfirmation": "request_signature_upon_delivery",
    "dangerous_good": "contains_dangerous_goods",
    "dangerousGood": "contains_dangerous_goods",

    # Royal Mail feature/accessorial options
    "royalmail_age_verification": "royalmail_age_verification",
    "royalmailAgeVerification": "royalmail_age_verification",
    "age_verification": "royalmail_age_verification",
    "ageVerification": "royalmail_age_verification",

    "royalmail_id_verification": "royalmail_id_verification",
    "royalmailIdVerification": "royalmail_id_verification",
    "id_verification": "royalmail_id_verification",
    "idVerification": "royalmail_id_verification",

    # Postage details
    "consequentialLoss": "consequential_loss",
    "requestSignatureUponDelivery": "request_signature_upon_delivery",
    "isLocalCollect": "is_local_collect",
    "safePlace": "safe_place",
    "department": "department",
    "AIRNumber": "air_number",
    "IOSSNumber": "ioss_number",
    "requiresExportLicense": "requires_export_license",
    "commercialInvoiceNumber": "commercial_invoice_number",
    "commercialInvoiceDate": "commercial_invoice_date",
    "invoiceNumber": "invoice_number",
    "invoice_number": "invoice_number",
    "invoiceDate": "invoice_date",
    "invoice_date": "invoice_date",
    "recipientEoriNumber": "recipient_eori_number",

    # Recipient address
    "addressBookReference": "address_book_reference",

    # Importer
    "importerVatNumber": "importer_vat_number",
    "importerTaxCode": "importer_tax_code",
    "importerEoriNumber": "importer_eori_number",

    # Dangerous goods
    "containsDangerousGoods": "contains_dangerous_goods",
    "dangerousGoodsUnCode": "dangerous_goods_un_code",
    "dangerousGoodsDescription": "dangerous_goods_description",
    "dangerousGoodsQuantity": "dangerous_goods_quantity",

    # Rate/service capability filters
    "is_tracked": "is_tracked",
    "isTracked": "is_tracked",
    "tracked": "is_tracked",
    "tracking": "is_tracked",
    "tracking_required": "is_tracked",
    "trackingRequired": "is_tracked",
}

def canonical_enum_names(enum_type) -> typing.List[str]:
    """
    Return only canonical enum names.

    Python Enum aliases appear in `__members__`, but alias entries have
    `member.name != key`. Filtering on that keeps only canonical names.
    """
    return [
        key
        for key, member in enum_type.__members__.items()
        if getattr(member, "name", None) == key
    ]


def canonical_shipping_option_names() -> typing.List[str]:
    """Return canonical Royal Mail shipping option names only."""
    return canonical_enum_names(ShippingOption)

_BOOLEAN_OPTION_KEYS = {
    "include_label_in_response",
    "include_cn",
    "include_returns_label",
    "receive_email_notification",
    "receive_sms_notification",
    "email_notification",
    "sms_notification",
    "request_signature_upon_delivery",
    "signature_confirmation",
    "is_local_collect",
    "requires_export_license",
    "contains_dangerous_goods",
    "dangerous_good",
    "royalmail_age_verification",
    "royalmail_id_verification",
    "age_verification",
    "id_verification",
    "is_tracked",
    "isTracked",
    "tracked",
    "tracking",
    "tracking_required",
    "trackingRequired",
    "duty_paid",
    "duty_unpaid",
    "ddp",
    "dtp",
    "dap",
    "ddu",
}

_CONFIG_BOOLEAN_KEYS = {
    "include_label_in_response",
    "include_return_label_in_response",
    "apply_uk_vat_to_rates",
}


def _normalize_option_keys(options: dict) -> dict:
    """Create lookup keys for option aliases and enum names."""
    normalized = {}

    for key, value in dict(options or {}).items():
        normalized_key = _OPTION_ALIASES.get(key, key)

        if normalized_key in _BOOLEAN_OPTION_KEYS:
            normalized[normalized_key] = (
                _to_bool(value, default=None)
                if value not in [None, ""]
                else value
            )
            continue

        normalized[normalized_key] = value

    return normalized

PACKAGE_LEVEL_OPTION_KEYS = {
    "package_format_identifier",
}

KNOWN_SHIPPING_OPTION_KEYS = {
    *set(_OPTION_ALIASES.values()),
    *set(canonical_shipping_option_names()),
}

def normalize_shipping_option_name(
    option_name: typing.Optional[str],
) -> typing.Optional[str]:
    """
    Normalize any supported option selector to a canonical Royal Mail
    shipping option name.
    """
    if option_name in [None, ""]:
        return None

    key = str(option_name).strip()
    normalized = _OPTION_ALIASES.get(key, key)
    canonical_names = set(canonical_shipping_option_names())

    if normalized in canonical_names:
        return normalized

    lowered = normalized.lower()
    if lowered in canonical_names:
        return lowered

    return None

def shipping_option_names_initializer(
    option_names: typing.Optional[typing.Iterable[str]],
) -> typing.List[str]:
    """
    Normalize configured connection-level shipping option names into canonical
    Royal Mail option names.

    Supports:
    - canonical snake_case names
    - legacy aliases
    - Royal Mail/API-style camelCase keys
    """
    if isinstance(option_names, str):
        option_names = [option_names]

    normalized_names = [
        normalize_shipping_option_name(option_name)
        for option_name in (option_names or [])
    ]

    normalized_names = [name for name in normalized_names if name]
    return list(dict.fromkeys(normalized_names))

def normalize_option_keys(options: dict) -> dict:
    """
    Public wrapper used by shipment builders/validators to normalize Royal Mail
    shipping option keys without constructing a full ShippingOptions object.
    """
    return _normalize_option_keys(options or {})

def shipping_options_initializer(
    options: dict,
    package_options: lib.units.ShippingOptions = None,
) -> lib.units.ShippingOptions:
    """Initialize Royal Mail shipment options.

    Supports both Karrio snake_case option keys and Royal Mail API-style
    camelCase option keys.
    """
    _options = _normalize_option_keys(options or {})

    if package_options is not None:
        _options.update(_normalize_option_keys(package_options.content))

    return lib.units.ShippingOptions(_options, ShippingOption)


def _source_value(source, *keys, default=None):
    """Return the first present value from a dict/object source."""
    if source is None:
        return default

    for key in keys:
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)

        if value not in [None, ""]:
            return value

    return default


def _number(value, default=None):
    """Convert a value to a finite float when possible."""
    if value in [None, ""]:
        return default

    if hasattr(value, "value"):
        value = value.value

    if value in [None, ""]:
        return default

    try:
        return float(value)
    except Exception:
        return default

def _raw_state_value(value):
    """Return raw value from Karrio state/value wrappers."""
    if hasattr(value, "state"):
        value = value.state

    if hasattr(value, "value") and not isinstance(
        value,
        (str, int, float, bool),
    ):
        value = value.value

    return value


def _source_raw_value(source, *keys, default=None):
    """Return first present value from source and unwrap Karrio wrappers."""
    return _raw_state_value(_source_value(source, *keys, default=default))


def _truthy_config_value(value: typing.Any) -> bool:
    """Return whether a config/option value should be treated as true."""
    value = _raw_state_value(value)

    if value in [None, ""]:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in [
            "1",
            "true",
            "yes",
            "y",
            "on",
            "enabled",
        ]

    return bool(value)


def _option_feature_tokens(value: typing.Any) -> typing.List[str]:
    """Normalize options.features / options.required_features to tokens."""
    value = _raw_state_value(value)

    if value is None:
        return []

    if isinstance(value, dict):
        return [
            str(key).strip()
            for key, enabled in value.items()
            if key not in [None, ""]
            and _truthy_config_value(enabled)
        ]

    if isinstance(value, (list, tuple, set)):
        tokens = []

        for item in value:
            tokens.extend(_option_feature_tokens(item))

        return tokens

    text = str(value).strip()

    if text == "":
        return []

    for separator in [",", ";", "|", ":"]:
        text = text.replace(separator, ",")

    return [
        token.strip()
        for token in text.split(",")
        if token.strip()
    ]


def normalize_customs_incoterm(value: typing.Any) -> typing.Optional[str]:
    """Normalize a customs incoterm / duty-routing value."""
    value = _raw_state_value(value)

    if value in [None, ""]:
        return None

    normalized = str(value).strip().upper().replace("-", "_").replace(" ", "_")

    return normalized or None


def normalize_duty_paid_by(value: typing.Any) -> typing.Optional[str]:
    """Normalize customs.duty.paid_by values."""
    value = _raw_state_value(value)

    if value in [None, ""]:
        return None

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")

    return normalized or None


def _first_raw_value(*values: typing.Any) -> typing.Any:
    """Return the first non-empty raw value from Karrio wrappers/scalars."""
    for value in values:
        value = _raw_state_value(value)

        if value not in [None, ""]:
            return value

    return None


def _request_incoterm(
    customs: typing.Any = None,
    options: typing.Any = None,
) -> typing.Optional[str]:
    """Resolve duty-routing incoterm from customs first, then options."""
    return normalize_customs_incoterm(
        _first_raw_value(
            _source_raw_value(
                customs,
                "incoterm",
                "incoterms",
                "terms_of_trade",
                "termsOfTrade",
            ),
            _source_raw_value(
                options,
                "incoterm",
                "incoterms",
                "terms_of_trade",
                "termsOfTrade",
                "delivery_terms",
                "deliveryTerms",
                "duty_terms",
                "dutyTerms",
            ),
        )
    )


def _duty_has_meaningful_sender_signal(duty: typing.Any) -> bool:
    """
    Return whether customs.duty contains more than Karrio's default paid_by.

    Karrio core defaults models.Duty.paid_by to "sender". Therefore
    paid_by=sender alone is not reliable enough to classify a Royal Mail
    shipment as DDP. Treat it as intentional only when accompanied by another
    duty field.
    """
    return any(
        _source_raw_value(duty, *keys) not in [None, ""]
        for keys in [
            ("declared_value", "declaredValue", "amount", "value"),
            ("account_number", "accountNumber"),
            ("currency",),
            ("id",),
        ]
    )


def customs_duty_amount(
    customs: typing.Any = None,
    options: typing.Any = None,
) -> typing.Any:
    """Return the explicitly supplied customs duty amount, if any."""
    normalized_options = (
        normalize_option_keys(options)
        if isinstance(options, dict)
        else options
    )

    explicit_option_value = _source_raw_value(
        normalized_options,
        "customs_duty_costs",
        "customsDutyCosts",
    )

    if explicit_option_value not in [None, ""]:
        return explicit_option_value

    duty = _source_raw_value(customs, "duty")

    return _source_raw_value(
        duty,
        "declared_value",
        "declaredValue",
        "amount",
        "value",
    )

def is_duty_paid_requested(
    customs: typing.Any = None,
    options: typing.Any = None,
) -> bool:
    """
    Return whether the shipment is explicitly asking for DDP/DTP handling.

    Shipment rules:
    - customs/options incoterm DDP or DTP means duty-paid.
    - customs/options incoterm DAP/DDU/etc means not duty-paid.
    - options.duty_paid / options.ddp / options.dtp means duty-paid.
    - options.duty_unpaid / options.dap / options.ddu means not duty-paid.
    - options.features containing ddp/dtp means duty-paid.
    - options.features containing dap/ddu means not duty-paid.
    - customsDutyCosts means duty-paid only when no explicit non-paid term exists.
    - Karrio's default customs.duty.paid_by == "sender" alone is ignored.
    """
    normalized_options = (
        normalize_option_keys(options)
        if isinstance(options, dict)
        else options
    )

    incoterm = _request_incoterm(
        customs=customs,
        options=normalized_options,
    )

    if incoterm in DUTY_PAID_INCOTERMS:
        return True

    if incoterm in DUTY_UNPAID_INCOTERMS:
        return False

    explicit_duty_unpaid_option = _source_raw_value(
        normalized_options,
        "duty_unpaid",
        "dutyUnpaid",
        "delivery_duty_unpaid",
        "deliveryDutyUnpaid",
        "dap",
        "ddu",
    )

    if explicit_duty_unpaid_option not in [None, ""] and _truthy_config_value(
        explicit_duty_unpaid_option
    ):
        return False

    explicit_duty_paid_option = _source_raw_value(
        normalized_options,
        "duty_paid",
        "dutyPaid",
        "delivery_duty_paid",
        "deliveryDutyPaid",
        "ddp",
        "dtp",
    )

    if explicit_duty_paid_option not in [None, ""]:
        return _truthy_config_value(explicit_duty_paid_option)

    raw_features = _source_raw_value(
        normalized_options,
        "features",
        "service_features",
        "serviceFeatures",
        "required_features",
        "requiredFeatures",
    )

    feature_tokens = {
        token
        for token in (
            _normalize_duty_token(raw_token)
            for raw_token in _option_feature_tokens(raw_features)
        )
        if token
    }

    if feature_tokens.intersection(DUTY_UNPAID_FEATURE_TOKENS):
        return False

    if feature_tokens.intersection(DUTY_PAID_FEATURE_TOKENS):
        return True

    duty = _source_raw_value(customs, "duty")
    paid_by = normalize_duty_paid_by(
        _source_raw_value(
            duty,
            "paid_by",
            "paidBy",
            "payer",
        )
    )

    if paid_by in DUTY_UNPAID_BY_VALUES:
        return False

    if paid_by in DUTY_PAID_BY_VALUES and _duty_has_meaningful_sender_signal(duty):
        return True

    return customs_duty_amount(
        customs=customs,
        options=normalized_options,
    ) not in [None, ""]

def weight_to_grams(
    value,
    unit: typing.Optional[str] = None,
    default: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a raw numeric weight to grams."""
    numeric = _number(value)

    if numeric is None:
        return default

    normalized_unit = str(unit or "KG").strip().upper()

    factors = {
        "G": 1.0,
        "GRAM": 1.0,
        "GRAMS": 1.0,
        "KG": 1000.0,
        "KGS": 1000.0,
        "KILOGRAM": 1000.0,
        "KILOGRAMS": 1000.0,
        "LB": 453.59237,
        "LBS": 453.59237,
        "POUND": 453.59237,
        "POUNDS": 453.59237,
        "OZ": 28.349523125,
        "OUNCE": 28.349523125,
        "OUNCES": 28.349523125,
    }

    factor = factors.get(normalized_unit)

    if factor is None:
        return default

    return int(round(numeric * factor))


def weight_in_grams(
    value,
    default: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a Karrio Weight object or numeric value to grams."""
    if value is None:
        return default

    grams = getattr(value, "G", None)

    if grams not in [None, ""]:
        return int(round(float(grams)))

    unit = getattr(value, "unit", None)

    if unit not in [None, ""]:
        return weight_to_grams(getattr(value, "value", value), unit, default=default)

    # Karrio Package.weight is normally a Weight object. If a raw number reaches
    # here, treat it as kilograms, matching Karrio's common normalized unit.
    return weight_to_grams(value, "KG", default=default)


def dimension_to_mms(
    value,
    unit: typing.Optional[str] = None,
    default: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a raw numeric dimension to millimetres."""
    numeric = _number(value)

    if numeric is None:
        return default

    normalized_unit = str(unit or "CM").strip().upper()

    factors = {
        "MM": 1.0,
        "MMS": 1.0,
        "MILLIMETRE": 1.0,
        "MILLIMETRES": 1.0,
        "MILLIMETER": 1.0,
        "MILLIMETERS": 1.0,
        "CM": 10.0,
        "CMS": 10.0,
        "CENTIMETRE": 10.0,
        "CENTIMETRES": 10.0,
        "CENTIMETER": 10.0,
        "CENTIMETERS": 10.0,
        "M": 1000.0,
        "METRE": 1000.0,
        "METRES": 1000.0,
        "METER": 1000.0,
        "METERS": 1000.0,
        "IN": 25.4,
        "INS": 25.4,
        "INCH": 25.4,
        "INCHES": 25.4,
    }

    factor = factors.get(normalized_unit)

    if factor is None:
        return default

    return int(round(numeric * factor))


def dimension_in_mms(
    value,
    default: typing.Optional[int] = None,
) -> typing.Optional[int]:
    """Convert a Karrio Dimension object or numeric value to millimetres."""
    if value is None:
        return default

    millimetres = getattr(value, "MM", None)

    if millimetres not in [None, ""]:
        return int(round(float(millimetres)))

    unit = getattr(value, "unit", None)

    if unit not in [None, ""]:
        return dimension_to_mms(
            getattr(value, "value", value),
            unit,
            default=default,
        )

    # Karrio Package dimensions are normally Dimension objects. If a raw number
    # reaches here, treat it as centimetres, matching Karrio's common normalized
    # unit for metric packages.
    return dimension_to_mms(value, "CM", default=default)