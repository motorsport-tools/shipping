import csv
import pathlib
import typing


ROYALMAIL_INTERNATIONAL_SIDECAR_FLAG_COLUMNS = [
    "use_royalmail_international_sidecar_rates",
    "royalmail_international_sidecar_rates",
    "sidecar_rate_table",
]


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


def _base_rows_by_service_code(
    base_rows: typing.Iterable[dict],
) -> typing.Dict[str, dict]:
    """
    Index services.csv rows by Karrio service_code.

    Royal Mail international products often share the same Click & Drop
    carrier_service_code, for example OTA can represent tracked large letter,
    tracked small parcel, and tracked heavier medium parcel. Therefore the
    sidecar must join on Karrio service_code, not carrier_service_code.
    """
    rows_by_service_code: typing.Dict[str, dict] = {}

    for row in base_rows or []:
        service_code = _row_value(row, "service_code")

        if service_code is None:
            continue

        rows_by_service_code.setdefault(service_code, row)

    return rows_by_service_code


def _base_row_uses_royalmail_international_sidecar_rates(
    base_row: dict,
) -> bool:
    """
    Return whether a services.csv row is intended to be priced by the Royal Mail
    international sidecar.

    The sidecar itself is the source of truth. This flag is mainly useful for
    human readability in services.csv and for future safety checks.
    """
    explicit = _row_value(
        base_row,
        *ROYALMAIL_INTERNATIONAL_SIDECAR_FLAG_COLUMNS,
    )

    explicit_value = _to_bool(explicit, default=None)

    if explicit_value is not None:
        return explicit_value

    service_code = str(_row_value(base_row, "service_code") or "").lower()
    international = _to_bool(_row_value(base_row, "international"), default=False)

    return (
        international is True
        and service_code.startswith("royal_mail_international_")
        and not service_code.startswith("parcel_force_")
    )


def _sidecar_identity(row: dict) -> typing.Tuple:
    """Return a stable identity used to de-duplicate sidecar-generated rows."""
    return (
        _row_value(row, "service_code"),
        _row_value(row, "zone_id"),
        _row_value(row, "zone_label"),
        _row_value(row, "country_codes"),
        _row_value(row, "postal_codes"),
        _row_value(row, "cities"),
        _row_value(row, "zone_min_weight"),
        _row_value(row, "zone_max_weight"),
        _row_value(row, "rate"),
        _row_value(row, "cost"),
    )


def expand_royalmail_international_rows(
    base_rows: typing.Iterable[dict],
    csv_path: pathlib.Path,
) -> typing.List[dict]:
    """
    Convert royalmail-international-services.csv into services.csv-shaped rows.

    The sidecar uses a deliberately simple long-form structure:

        service_code,
        zone_id,
        zone_label,
        country_codes,
        postal_codes,
        cities,
        zone_min_weight,
        zone_max_weight,
        rate,
        cost,
        zone_transit_days

    Each sidecar row is copied over the matching services.csv catalogue row.
    That preserves service metadata such as:

    - carrier_service_code
    - service_register_code
    - package_format_identifier
    - features
    - dimensions
    - compensation
    - Click & Drop metadata

    The generated rows can then flow through the existing services.csv loader
    without adding Royal Mail international special-cases to the rating logic.
    """
    csv_path = pathlib.Path(csv_path)

    if not csv_path.exists():
        return []

    base_rows = list(base_rows or [])
    base_rows_by_service_code = _base_rows_by_service_code(base_rows)

    generated_rows: typing.List[dict] = []
    seen_rows: typing.Set[typing.Tuple] = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for sidecar_row in reader:
            service_code = _row_value(sidecar_row, "service_code", "ServiceCode")

            if service_code is None:
                continue

            base_row = base_rows_by_service_code.get(service_code)

            if base_row is None:
                continue

            if not _base_row_uses_royalmail_international_sidecar_rates(base_row):
                continue

            rate = _row_value(sidecar_row, "rate")

            if rate is None:
                # Do not create no-price zones from the sidecar. Catalogue-only
                # zones still belong in services.csv templates.
                continue

            zone_min_weight = _row_value(
                sidecar_row,
                "zone_min_weight",
                "zoneMinWeight",
                "min_weight",
            )
            zone_max_weight = _row_value(
                sidecar_row,
                "zone_max_weight",
                "zoneMaxWeight",
                "max_weight",
            )

            if zone_min_weight is None or zone_max_weight is None:
                continue

            generated_row = dict(base_row)

            generated_row.update(
                {
                    "active": "True",
                    "service_code": service_code,
                    "zone_id": _row_value(sidecar_row, "zone_id") or "",
                    "zone_label": _row_value(sidecar_row, "zone_label") or "",
                    "country_codes": _row_value(sidecar_row, "country_codes") or "",
                    "postal_codes": _row_value(sidecar_row, "postal_codes") or "",
                    "cities": _row_value(sidecar_row, "cities") or "",
                    "zone_min_weight": zone_min_weight,
                    "zone_max_weight": zone_max_weight,
                    "rate": rate,
                    "cost": _row_value(sidecar_row, "cost") or "",
                }
            )

            zone_transit_days = _row_value(sidecar_row, "zone_transit_days")

            if zone_transit_days is not None:
                generated_row["zone_transit_days"] = zone_transit_days

            # Optional sidecar overrides. These are not expected for the current
            # extracted Royal Mail table, but keeping them here makes the file
            # useful for future price-table imports.
            for optional_column in [
                "weight_unit",
                "dimension_unit",
                "transit_days",
                "min_weight",
                "max_weight",
                "max_length",
                "max_width",
                "max_height",
            ]:
                value = _row_value(sidecar_row, optional_column)

                if value is not None:
                    generated_row[optional_column] = value

            identity = _sidecar_identity(generated_row)

            if identity in seen_rows:
                continue

            seen_rows.add(identity)
            generated_rows.append(generated_row)

    return generated_rows