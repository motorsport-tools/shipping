import csv
import pathlib
import re
import typing
import unicodedata
import functools

import karrio.core.units as core_units


PARCELFORCE_OVERSIZED_THRESHOLD_KG = 30.0
RATE_TABLE_BOUNDARY_EPSILON = 0.01

PARCELFORCE_ADDITIONAL_KG_SURCHARGE_COLUMN = (
    "Surcharge per Additional kg after 30KG"
)

PARCELFORCE_WEIGHT_BAND_RE = re.compile(
    r"^\s*(?P<min>\d+(?:\.\d+)?)\s*-\s*(?P<max>\d+(?:\.\d+)?)\s*kg\s*$",
    re.IGNORECASE,
)

# The sidecar table contains ECA/GPA/ER3 rows, but the current Karrio catalogue
# tests expect ECA/GPA to remain grouped Royal Mail zone services:
#
#   ECA -> parcel_force_europe -> Europe Zone 1/2/3
#   GPA -> parcel_force_globalpriority_row -> World Zone 1/2/3
#
# ER3 is the service currently expected to use detailed country-specific
# Parcelforce sidecar rate bands.
#
# Future services can opt in via a CSV column such as:
#   use_parcelforce_sidecar_rates=True
PARCELFORCE_SIDECAR_RATE_TABLE_SERVICE_CODES = frozenset(
    [
        "ECA",
        "GPA",
        "ER3",
    ]
)


def _to_bool(
    value: typing.Any,
    default: typing.Optional[bool] = None,
) -> typing.Optional[bool]:
    """Small local bool parser to avoid importing units.py and creating cycles."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text == "":
        return default

    if text in ["1", "true", "yes", "y", "on"]:
        return True

    if text in ["0", "false", "no", "n", "off"]:
        return False

    return default


def _base_row_uses_parcelforce_sidecar_rates(
    base_row: dict,
    carrier_service_code: str,
) -> bool:
    """
    Return whether a services.csv row should be replaced by detailed sidecar
    rate bands.

    By default, only ER3 uses the detailed Parcelforce sidecar table. ECA/GPA
    remain grouped-zone catalogue services because existing service tests expect
    their zones to be Europe Zone 1/2/3 and World Zone 1/2/3 respectively.
    """
    explicit = _row_value(
        base_row,
        "use_parcelforce_sidecar_rates",
        "parcelforce_sidecar_rates",
        "sidecar_rate_table",
    )

    explicit_value = _to_bool(explicit, default=None)

    if explicit_value is not None:
        return explicit_value

    return (
        str(carrier_service_code or "").strip().upper()
        in PARCELFORCE_SIDECAR_RATE_TABLE_SERVICE_CODES
    )


# Royal Mail / Parcelforce destination names that do not exactly match
# karrio.core.units.Country names.
#
# Prefer Karrio's own country codes where it has carrier-specific codes:
# - AC = Ascension Island
# - IC = Canary Islands
# - KV/XK = Kosovo
#
# Some destinations such as PS, PN, TM, WF, CX, CC, UM are not present in older
# Karrio Country enums. They are still useful as explicit zone country codes
# because user payloads may carry those ISO/postal destination codes.
PARCELFORCE_DESTINATION_COUNTRY_CODE_ALIASES = {
    "antigua barbuda": "AG",
    "australia inc island territories": "AU",
    "azores": "PT",
    "balearic isles": "ES",
    "balearic islands": "ES",
    "bosnia": "BA",
    "bosnia and herzegovina": "BA",
    "brunei": "BN",
    "canary islands": "IC",
    "cape verde": "CV",
    "cape verde islands": "CV",
    "christmas island": "CX",
    "cocos keeling islands": "CC",
    "congo dem rep zaire": "CD",
    "corsica": "FR",
    "cote d ivoire": "CI",
    "cuba guantanamo bay via usa": "CU",
    "czechia": "CZ",
    "democratic republic of congo": "CD",
    "east timor": "TL",
    "equatorial guinea": "GQ",
    "eswatini": "SZ",
    "falkland islands": "FK",
    "faroe islands": "FO",
    "french guiana": "GF",
    "french polynesia": "PF",
    "gaza khan yunis": "PS",
    "greenland": "GL",
    "guinea": "GN",
    "guinea bissau": "GW",
    "guinea republic": "GN",
    "guyana": "GY",
    "hong kong": "HK",
    "ireland": "IE",
    "ivory coast": "CI",
    "kosovo": "XK",
    "laos": "LA",
    "macau": "MO",
    "macao": "MO",
    "macedonia": "MK",
    "madeira": "PT",
    "micronesia": "FM",
    "moldova": "MD",
    "myanmar burma": "MM",
    "netherlands antilles": "AN",
    "new zealand island territories": "NZ",
    "niger republic": "NE",
    "northern mariana islands": "MP",
    "pitcairn islands": "PN",
    "reunion": "RE",
    "russia": "RU",
    "sao tome principe": "ST",
    "sardinia": "IT",
    "sicily": "IT",
    "south korea": "KR",
    "spanish territories of north africa": "ES",
    "st helena": "SH",
    "st kitts st nevis": "KN",
    "st lucia": "LC",
    "st vincent grenadines": "VC",
    "swaziland": "SZ",
    "syria": "SY",
    "taiwan": "TW",
    "tanzania": "TZ",
    "trinidad tobago": "TT",
    "tristan da cunha": "SH",
    "turkey": "TR",
    "turkmenistan": "TM",
    "turks caicos islands": "TC",
    "united states of america": "US",
    "usa": "US",
    "usa pddp": "US",
    "vatican city state": "VA",
    "venezuela": "VE",
    "vietnam": "VN",
    "virgin islands": "VI",
    "wake island": "UM",
    "wallis and futuna": "WF",
}


def _normalized_key(value: typing.Any) -> str:
    """Normalize human-readable destination names for matching."""
    text = str(value or "").strip().lower()
    text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _row_value(row: dict, *names: str) -> typing.Optional[str]:
    """Return the first non-empty value from a CSV row."""
    for name in names:
        value = row.get(name)

        if value is None:
            continue

        value = str(value).strip()

        if value != "":
            return value

    return None


def _format_number(value: float) -> str:
    """Format floats for generated CSV-shaped rows."""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _money_text(value: typing.Any) -> typing.Optional[str]:
    """Return a money cell as decimal text, e.g. '£7.30' -> '7.30'."""
    if value in [None, ""]:
        return None

    text = str(value).strip()

    if text in ["-", "–", "—", "n/a", "N/A", "na", "NA"]:
        return None

    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if match is None:
        return None

    return f"{float(match.group(0)):.2f}"


def _money_float(value: typing.Any) -> typing.Optional[float]:
    """Return a money cell as float."""
    text = _money_text(value)

    if text is None:
        return None

    return float(text)

@functools.lru_cache(maxsize=1)
def _country_name_index() -> typing.Dict[str, str]:
    """Build a destination-name to country-code index from Karrio's Country enum."""
    index: typing.Dict[str, str] = {}

    for code, country in getattr(core_units.Country, "__members__", {}).items():
        index.setdefault(_normalized_key(country.value), code)
        index.setdefault(_normalized_key(code), code)

    return index


def resolve_destination_country_code(
    destination: typing.Any,
) -> typing.Optional[str]:
    """Resolve a Parcelforce sidecar destination name to a Karrio country code."""
    key = _normalized_key(destination)

    if key == "":
        return None

    alias = PARCELFORCE_DESTINATION_COUNTRY_CODE_ALIASES.get(key)

    if alias is not None:
        return alias

    return _country_name_index().get(key)


def _weight_band_columns(
    fieldnames: typing.Iterable[str],
) -> typing.List[typing.Tuple[str, float, float]]:
    """Return sidecar weight-band columns as (column_name, min_kg, max_kg)."""
    bands = []

    for fieldname in fieldnames or []:
        match = PARCELFORCE_WEIGHT_BAND_RE.match(str(fieldname or ""))

        if match is None:
            continue

        bands.append(
            (
                fieldname,
                float(match.group("min")),
                float(match.group("max")),
            )
        )

    return sorted(bands, key=lambda item: (item[1], item[2]))


def _base_rows_by_carrier_service_code(
    base_rows: typing.Iterable[dict],
) -> typing.Dict[str, dict]:
    """Index services.csv rows by Royal Mail carrier_service_code."""
    rows_by_carrier_code: typing.Dict[str, dict] = {}

    for row in base_rows or []:
        carrier_service_code = _row_value(
            row,
            "carrier_service_code",
            "royalmail_service_code",
            "serviceCode",
        )

        if carrier_service_code is None:
            continue

        rows_by_carrier_code.setdefault(
            carrier_service_code.strip().upper(),
            row,
        )

    return rows_by_carrier_code


def _sidecar_service_metadata(
    metadata_by_service_code: typing.Dict[str, dict],
    service_code: str,
    country_code: str,
    amount_per_kg: typing.Optional[float],
    base_row: dict,
) -> None:
    """Collect destination-specific oversized surcharge metadata."""
    if amount_per_kg is None:
        return

    metadata = metadata_by_service_code.setdefault(
        service_code,
        {
            "oversized_surcharge_amount_per_kg_by_country": {},
            "oversized_surcharge_threshold_kg": PARCELFORCE_OVERSIZED_THRESHOLD_KG,
            "oversized_surcharge_max_weight_kg": _row_value(
                base_row,
                "oversized_surcharge_max_weight_kg",
                "oversize_surcharge_max_weight_kg",
                "parcelforce_oversized_surcharge_max_weight_kg",
                "parcelforce_oversize_surcharge_max_weight_kg",
            ),
            "oversized_surcharge_rounding": (
                _row_value(
                    base_row,
                    "oversized_surcharge_rounding",
                    "oversize_surcharge_rounding",
                    "parcelforce_oversized_surcharge_rounding",
                    "parcelforce_oversize_surcharge_rounding",
                )
                or "ceil"
            ),
        },
    )

    by_country = metadata.setdefault(
        "oversized_surcharge_amount_per_kg_by_country",
        {},
    )

    # Multiple sidecar destination labels can map to the same country code
    # e.g. Italy/Sardinia/Sicily. Keep the first value. The uploaded table has
    # matching values for these duplicates.
    by_country.setdefault(country_code, amount_per_kg)


def expand_parcelforce_international_rows(
    base_rows: typing.Iterable[dict],
    csv_path: pathlib.Path,
) -> typing.Tuple[typing.List[dict], typing.Dict[str, dict]]:
    """
    Convert parcelforce-international-services.csv into services.csv-shaped rows.

    Returns:
        generated_rows:
            Rows that can be fed through the existing services.csv loader.

        metadata_by_service_code:
            Service-level metadata containing destination-specific additional-kg
            surcharge maps.
    """
    csv_path = pathlib.Path(csv_path)

    if not csv_path.exists():
        return [], {}

    base_rows = list(base_rows or [])
    base_rows_by_carrier_code = _base_rows_by_carrier_service_code(base_rows)

    generated_rows: typing.List[dict] = []
    metadata_by_service_code: typing.Dict[str, dict] = {}
    seen_zone_bands: typing.Set[typing.Tuple[str, str, float, float]] = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        weight_bands = _weight_band_columns(reader.fieldnames or [])

        for sidecar_row in reader:
            carrier_service_code = str(sidecar_row.get("Service") or "").strip().upper()

            if carrier_service_code == "":
                continue

            base_row = base_rows_by_carrier_code.get(carrier_service_code)

            if base_row is None:
                continue

            if not _base_row_uses_parcelforce_sidecar_rates(
                base_row,
                carrier_service_code,
            ):
                continue

            service_code = _row_value(base_row, "service_code")

            if service_code is None:
                continue

            destination = str(sidecar_row.get("Destination") or "").strip()

            if destination == "":
                continue

            country_code = resolve_destination_country_code(destination)

            if country_code is None:
                # Do not create a catch-all zone by accident.
                continue

            amount_per_kg = _money_float(
                sidecar_row.get(PARCELFORCE_ADDITIONAL_KG_SURCHARGE_COLUMN)
            )

            _sidecar_service_metadata(
                metadata_by_service_code,
                service_code,
                country_code,
                amount_per_kg,
                base_row,
            )

            for column_name, min_kg, max_kg in weight_bands:
                rate = _money_text(sidecar_row.get(column_name))

                if rate is None:
                    continue

                zone_band_key = (
                    service_code,
                    country_code,
                    min_kg,
                    max_kg,
                )

                # Avoid duplicate zones where several Royal Mail destination
                # labels map to the same country code with the same table.
                if zone_band_key in seen_zone_bands:
                    continue

                seen_zone_bands.add(zone_band_key)

                generated_row = dict(base_row)

                generated_row.update(
                    {
                        "active": "True",
                        "zone_id": (
                            f"parcelforce_{carrier_service_code.lower()}_"
                            f"{country_code.lower()}"
                        ),
                        "zone_label": destination,
                        "country_codes": country_code,
                        "postal_codes": "",
                        "cities": "",

                        # Preserve the original services.csv carrier-native values for
                        # ServiceLevel.metadata transparency. The generated sidecar row below
                        # intentionally uses KG for Karrio rating, but the source catalogue row
                        # may be declared in G/MM.
                        "carrier_weight_unit": (
                            _row_value(base_row, "carrier_weight_unit", "weight_unit")
                            or ""
                        ),
                        "carrier_dimension_unit": (
                            _row_value(base_row, "carrier_dimension_unit", "dimension_unit")
                            or ""
                        ),
                        "carrier_min_weight": (
                            _row_value(base_row, "carrier_min_weight", "min_weight")
                            or ""
                        ),
                        "carrier_max_weight": (
                            _row_value(base_row, "carrier_max_weight", "max_weight")
                            or ""
                        ),
                        "carrier_max_length": (
                            _row_value(base_row, "carrier_max_length", "max_length")
                            or ""
                        ),
                        "carrier_max_width": (
                            _row_value(base_row, "carrier_max_width", "max_width")
                            or ""
                        ),
                        "carrier_max_height": (
                            _row_value(base_row, "carrier_max_height", "max_height")
                            or ""
                        ),

                        "zone_min_weight": _format_number(
                            max(min_kg, 0.001)
                        ),
                        # Karrio universal rating uses min inclusive / max exclusive.
                        "zone_max_weight": _format_number(
                            max_kg + RATE_TABLE_BOUNDARY_EPSILON
                        ),
                        "rate": rate,
                        "cost": "",

                        # The sidecar table is explicitly in kg, whereas the placeholder
                        # services.csv Parcelforce rows are in grams. These normalized values
                        # are for Karrio rating only; carrier-native values are preserved above.
                        "weight_unit": "KG",
                        "min_weight": "0.001",
                        "max_weight": _format_number(
                            PARCELFORCE_OVERSIZED_THRESHOLD_KG
                        ),
                        "oversized_surcharge_amount_per_kg": "",
                        "oversized_surcharge_threshold_kg": _format_number(
                            PARCELFORCE_OVERSIZED_THRESHOLD_KG
                        ),
                        "oversized_surcharge_max_weight_kg": (
                            _row_value(
                                base_row,
                                "oversized_surcharge_max_weight_kg",
                                "oversize_surcharge_max_weight_kg",
                                "parcelforce_oversized_surcharge_max_weight_kg",
                                "parcelforce_oversize_surcharge_max_weight_kg",
                            )
                            or ""
                        ),
                        "oversized_surcharge_rounding": (
                            _row_value(
                                base_row,
                                "oversized_surcharge_rounding",
                                "oversize_surcharge_rounding",
                                "parcelforce_oversized_surcharge_rounding",
                                "parcelforce_oversize_surcharge_rounding",
                            )
                            or "ceil"
                        ),
                    }
                )

                generated_rows.append(generated_row)

    return generated_rows, metadata_by_service_code