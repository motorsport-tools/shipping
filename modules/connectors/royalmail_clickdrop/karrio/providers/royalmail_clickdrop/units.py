import csv
import pathlib
import typing
from decimal import Decimal, ROUND_HALF_UP

import karrio.lib as lib
import karrio.core.units as units
import karrio.core.models as models


class ConnectionConfig(lib.Enum):
    """Carrier connection configuration options."""

    base_url = lib.OptionEnum("base_url", str)
    carrier_name = lib.OptionEnum("carrier_name", str)
    shipping_options = lib.OptionEnum("shipping_options", list)
    shipping_services = lib.OptionEnum("shipping_services", list)
    label_type = lib.OptionEnum("label_type", str, "PDF")


class WeightUnit(lib.Enum):
    G = "G"
    KG = "KG"
    LB = "LB"


class DimensionUnit(lib.Enum):
    MM = "MM"
    CM = "CM"
    IN = "IN"


_WEIGHT_FACTORS = {
    "G": Decimal("1"),
    "KG": Decimal("1000"),
    "LB": Decimal("453.59237"),
    "OZ": Decimal("28.349523125"),
}

_DIMENSION_FACTORS = {
    "MM": Decimal("1"),
    "CM": Decimal("10"),
    "IN": Decimal("25.4"),
    "M": Decimal("1000"),
    "FT": Decimal("304.8"),
}


def _decimal(value) -> typing.Optional[Decimal]:
    if value in [None, ""]:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _unit_code(unit) -> typing.Optional[str]:
    if unit is None:
        return None

    value = getattr(unit, "value", unit)
    return str(value).upper() if value is not None else None


def _round_decimal(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def weight_to_grams(value, unit=None, default=None) -> typing.Optional[int]:
    amount = _decimal(value)
    code = _unit_code(unit)

    if amount is None:
        return default

    factor = _WEIGHT_FACTORS.get(code, Decimal("1")) if code is not None else Decimal("1")
    return _round_decimal(amount * factor)


def weight_in_grams(weight, default=None) -> typing.Optional[int]:
    if weight is None:
        return default

    native = weight_to_grams(
        getattr(weight, "value", None),
        getattr(weight, "unit", None),
    )
    if native is not None:
        return native

    if hasattr(weight, "G"):
        grams = _decimal(weight.G)
        if grams is not None:
            return _round_decimal(grams)

    return weight_to_grams(weight, default=default)


def dimension_in_mms(measurement, default=None) -> typing.Optional[int]:
    if measurement is None:
        return default

    value = _decimal(getattr(measurement, "value", None))
    unit = _unit_code(getattr(measurement, "unit", None))

    # Prefer native value + unit to avoid float drift from computed properties.
    if value is not None:
        factor = _DIMENSION_FACTORS.get(unit, Decimal("1"))
        return _round_decimal(value * factor)

    if hasattr(measurement, "MM"):
        mms = _decimal(measurement.MM)
        if mms is not None:
            return _round_decimal(mms)

    raw = _decimal(measurement)
    return _round_decimal(raw) if raw is not None else default

class PackagingType(lib.StrEnum):
    """
    Royal Mail package format identifiers.

    Notes:
    - Royal Mail supports standard format identifiers:
      undefined, letter, largeLetter, smallParcel, mediumParcel, largeParcel, parcel, documents
    - ChannelShipper custom package formats may also be passed through as raw strings.
    """

    undefined = "undefined"
    letter = "letter"
    large_letter = "largeLetter"
    small_parcel = "smallParcel"
    medium_parcel = "mediumParcel"
    large_parcel = "largeParcel"
    parcel = "parcel"
    documents = "documents"

    # Unified Karrio mappings
    envelope = letter
    pak = large_letter
    small_box = small_parcel
    medium_box = medium_parcel
    large_box = large_parcel
    tube = parcel
    pallet = parcel
    your_packaging = parcel
    document = documents


class PackagePresets(lib.Enum):
    """Optional package presets for common Royal Mail formats."""

    royalmail_letter = lib.units.PackagePreset(
        packaging_type="letter",
        weight=0.1,
        width=24.0,
        height=0.5,
        length=16.5,
        weight_unit="KG",
        dimension_unit="CM",
    )
    royalmail_large_letter = lib.units.PackagePreset(
        packaging_type="large_letter",
        weight=0.75,
        width=35.3,
        height=2.5,
        length=25.0,
        weight_unit="KG",
        dimension_unit="CM",
    )
    royalmail_small_parcel = lib.units.PackagePreset(
        packaging_type="small_parcel",
        weight=2.0,
        width=45.0,
        height=16.0,
        length=35.0,
        weight_unit="KG",
        dimension_unit="CM",
    )
    royalmail_medium_parcel = lib.units.PackagePreset(
        packaging_type="medium_parcel",
        weight=20.0,
        width=61.0,
        height=46.0,
        length=46.0,
        weight_unit="KG",
        dimension_unit="CM",
    )


class ShippingService(lib.StrEnum):
    """
    Canonical Karrio-facing aliases for Royal Mail Click & Drop services.

    Notes:
    - These are convenience aliases only.
    - The full selectable service catalog comes from services.csv.
    - Duplicate posting-location variants belong in services.csv, not here.
    """

    # Domestic outbound
    first_class = "BPL1"
    second_class = "BPL2"
    first_class_signed = "BPR1"
    second_class_signed = "BPR2"

    royal_mail_24 = "CRL24"
    royal_mail_48 = "CRL48"

    tracked_24 = "TPN24"
    royal_mail_tracked_24_lbt = "TRN24"

    express_24 = "NDA"
    express_48 = "FE0"
    express_am = "FEE"
    express_48_large = "FEM"

    special_delivery_1pm = "SD1"
    special_delivery_9am = "SD4"

    first_class_account_mail = "STL1"
    second_class_account_mail = "STL2"

    # International outbound
    international_standard = "OLA"
    international_economy = "OLS"
    international_signed = "OSA"
    international_signed_extra_compensation = "OSB"
    international_tracked = "OTA"
    international_tracked_extra_compensation = "OTB"
    international_tracked_and_signed = "OTC"
    international_tracked_and_signed_extra_compensation = "OTD"

    international_tracked_ppi = "LLH"
    international_tracked_and_signed_ppi = "LLG"
    international_signed_for_ppi = "LLI"

    international_business_parcel_tracked = "MP1"
    international_business_parcel_tracked_extra_compensation = "MP4"
    international_business_parcel_signed = "MP5"
    international_business_parcel_signed_extra_compensation = "MP6"
    international_business_parcel_tracked_country_priced = "MP7"
    international_business_parcel_signed_country_priced = "MP9"
    international_business_parcel_tracked_ddp = "MPR"

    international_business_mail_tracked = "MTI"
    international_business_mail_tracked_extra_compensation = "MTJ"
    international_business_mail_tracked_country_priced = "MTK"
    international_business_mail_signed = "MTM"
    international_business_mail_signed_extra_compensation = "MTN"
    international_business_mail_signed_country_priced = "MTO"
    international_business_mail_signed_extra_compensation_country = "MTP"
    international_business_mail_tracked_and_signed = "MTC"
    international_business_mail_tracked_and_signed_extra_compensation = "MTD"
    international_business_mail_tracked_and_signed_country = "MTG"

    globalpriority_europe = "ECA"
    globalpriority_row = "GPA"
    europriority_dtp_ioss = "ERA"
    international_tracked_heavy_weight_premium = "BYD"
    international_tracked_heavy_weight_premium_extra_compensation = "BYH"

    # Returns
    express24_returns = "RT0"
    express48_returns = "RTA"
    tracked_returns_48 = "TSS"


class ShippingOption(lib.Enum):
    """Royal Mail Click & Drop carrier options."""

    service_code = lib.OptionEnum("service_code")
    package_format_identifier = lib.OptionEnum("package_format_identifier")
    service_register_code = lib.OptionEnum("service_register_code")

    order_reference = lib.OptionEnum("order_reference")
    order_date = lib.OptionEnum("order_date")
    planned_despatch_date = lib.OptionEnum("planned_despatch_date")
    subtotal = lib.OptionEnum("subtotal", float)
    shipping_cost_charged = lib.OptionEnum("shipping_cost_charged", float)
    other_costs = lib.OptionEnum("other_costs", float)
    customs_duty_costs = lib.OptionEnum("customs_duty_costs", float)
    total = lib.OptionEnum("total", float)
    currency_code = lib.OptionEnum("currency_code")
    special_instructions = lib.OptionEnum("special_instructions")
    order_tax = lib.OptionEnum("order_tax", float)

    include_label_in_response = lib.OptionEnum("include_label_in_response", bool)
    include_cn = lib.OptionEnum("include_cn", bool)
    include_returns_label = lib.OptionEnum("include_returns_label", bool)

    is_recipient_a_business = lib.OptionEnum("is_recipient_a_business", bool)
    send_notifications_to = lib.OptionEnum("send_notifications_to")
    receive_email_notification = lib.OptionEnum("receive_email_notification", bool)
    receive_sms_notification = lib.OptionEnum("receive_sms_notification", bool)
    request_signature_upon_delivery = lib.OptionEnum("request_signature_upon_delivery", bool)
    is_local_collect = lib.OptionEnum("is_local_collect", bool)
    safe_place = lib.OptionEnum("safe_place")
    department = lib.OptionEnum("department")
    consequential_loss = lib.OptionEnum("consequential_loss", int)

    air_number = lib.OptionEnum("air_number")
    ioss_number = lib.OptionEnum("ioss_number")
    requires_export_license = lib.OptionEnum("requires_export_license", bool)
    commercial_invoice_number = lib.OptionEnum("commercial_invoice_number")
    commercial_invoice_date = lib.OptionEnum("commercial_invoice_date")
    recipient_eori_number = lib.OptionEnum("recipient_eori_number")

    contains_dangerous_goods = lib.OptionEnum("contains_dangerous_goods", bool)
    dangerous_goods_un_code = lib.OptionEnum("dangerous_goods_un_code")
    dangerous_goods_description = lib.OptionEnum("dangerous_goods_description")
    dangerous_goods_quantity = lib.OptionEnum("dangerous_goods_quantity", float)

    billing = lib.OptionEnum("billing", dict)
    importer = lib.OptionEnum("importer", dict)
    tags = lib.OptionEnum("tags", list)
    address_book_reference = lib.OptionEnum("address_book_reference")
    carrier_name = lib.OptionEnum("carrier_name")


def shipping_options_initializer(
    options: dict,
    package_options: units.ShippingOptions = None,
) -> units.ShippingOptions:
    """Apply default values to the given options."""
    options = dict(options or {})

    if package_options is not None:
        options.update(package_options.content)

    def items_filter(key: str) -> bool:
        return key in ShippingOption  # type: ignore

    return units.ShippingOptions(options, ShippingOption, items_filter=items_filter)


def load_services_from_csv() -> list:
    csv_path = pathlib.Path(__file__).resolve().parent / "services.csv"

    if not csv_path.exists():
        return []

    services_dict: dict[str, dict] = {}

    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader((row for row in csvfile if row.strip()))
        for row in reader:
            service_code = row["service_code"]
            zone_label = row.get("zone_label", "")
            country_codes_str = row.get("country_codes", "")
            country_codes = (
                [c.strip() for c in country_codes_str.split(",") if c.strip()]
                if country_codes_str
                else None
            )

            zone = models.ServiceZone(
                label=zone_label or None,
                rate=0.0,
                transit_days=int(row["transit_days"]) if row.get("transit_days") else None,
                country_codes=country_codes,
            )

            if service_code not in services_dict:
                services_dict[service_code] = {
                    "service_name": row["service_name"],
                    "service_code": service_code,
                    "carrier_service_code": row.get("carrier_service_code", service_code),
                    "currency": row.get("currency", "GBP"),
                    "weight_unit": row.get("weight_unit", "KG"),
                    "dimension_unit": row.get("dimension_unit", "CM"),
                    "min_weight": float(row["min_weight"]) if row.get("min_weight") else None,
                    "max_weight": float(row["max_weight"]) if row.get("max_weight") else None,
                    "max_length": float(row["max_length"]) if row.get("max_length") else None,
                    "max_width": float(row["max_width"]) if row.get("max_width") else None,
                    "max_height": float(row["max_height"]) if row.get("max_height") else None,
                    "domicile": row.get("domicile", "").lower() == "true",
                    "international": row.get("international", "").lower() == "true",
                    "zones": [zone],
                }
            else:
                services_dict[service_code]["zones"].append(zone)

    return [models.ServiceLevel(**service_data) for service_data in services_dict.values()]


DEFAULT_SERVICES = load_services_from_csv()


def _services_index() -> dict[str, models.ServiceLevel]:
    return {str(svc.service_code).lower(): svc for svc in DEFAULT_SERVICES}


def _carrier_codes() -> set[str]:
    return {
        str(svc.carrier_service_code).upper()
        for svc in DEFAULT_SERVICES
        if svc.carrier_service_code
    }


SERVICES_INDEX = _services_index()
CARRIER_SERVICE_CODES = _carrier_codes()

RETURN_SERVICE_CODES = {
    "RT0", "RT1", "RT2", "RT3",
    "RTA", "RTB", "RTC", "RTD",
    "TSS",
}


def resolve_carrier_service(service: typing.Optional[str]) -> typing.Optional[str]:
    """
    Resolve a Karrio-facing service selector to a Royal Mail API service code.

    Supported inputs:
    - exact CSV service keys, e.g. 'tpn24_01'
    - exact enum aliases, e.g. 'tracked_24'
    - exact direct carrier codes, e.g. 'TPN24'

    Returns:
    - Royal Mail carrier service code string
    - None for empty or unknown input

    Notes:
    - Matching is strict.
    - Similar or normalized values such as 'express48' are not resolved.
    """
    if service is None:
        return None

    value = str(service).strip()
    if value == "":
        return None

    key = value.lower()

    # 1. exact CSV service key
    if key in SERVICES_INDEX:
        return SERVICES_INDEX[key].carrier_service_code

    # 2. exact enum alias
    alias_map = {
        name.lower(): member.value
        for name, member in ShippingService.__members__.items()
    }
    if key in alias_map:
        return alias_map[key]

    # 3. exact carrier code
    if value.upper() in CARRIER_SERVICE_CODES:
        return value.upper()

    # 4. strict mode: unknown services are invalid
    return None

def is_return_service(service: typing.Optional[str]) -> bool:
    resolved = resolve_carrier_service(service)
    return resolved in RETURN_SERVICE_CODES if resolved else False


def _grams(weight) -> typing.Optional[int]:
    if weight is None:
        return None

    if hasattr(weight, "G"):
        return int(round(weight.G))

    if hasattr(weight, "value"):
        return int(round(float(weight.value)))

    try:
        return int(round(float(weight)))
    except Exception:
        return None


def _mms(measurement) -> typing.Optional[int]:
    if measurement is None:
        return None

    if hasattr(measurement, "MM"):
        return int(round(measurement.MM))

    if hasattr(measurement, "value"):
        return int(round(float(measurement.value)))

    try:
        return int(round(float(measurement)))
    except Exception:
        return None

def build_dimensions(package, dimension_type):
    height_in_mms = dimension_in_mms(package.height)
    width_in_mms = dimension_in_mms(package.width)
    depth_in_mms = dimension_in_mms(package.length)

    if not all(value is not None for value in [height_in_mms, width_in_mms, depth_in_mms]):
        return None

    return dimension_type(
        heightInMms=height_in_mms,
        widthInMms=width_in_mms,
        depthInMms=depth_in_mms,
    )


def resolve_package_format(
    package=None,
    explicit: typing.Optional[str] = None,
) -> str:
    """
    Resolve Royal Mail package format identifier.

    Priority:
    1. Explicit option override
    2. Package packaging_type alias mapping
    3. Inference from dimensions/weight
    4. Fallback to smallParcel

    If explicit is an unknown string, it is passed through to support
    ChannelShipper custom package format identifiers.
    """
    if explicit:
        mapped = PackagingType.map(explicit).value_or_key
        return mapped if mapped is not None else str(explicit)

    if package is not None and getattr(package, "packaging_type", None):
        mapped = PackagingType.map(package.packaging_type).value_or_key
        if mapped is not None:
            return mapped

    weight_g = weight_in_grams(getattr(package, "weight", None)) if package is not None else None
    dims = [
        dimension_in_mms(getattr(package, "length", None)) if package is not None else None,
        dimension_in_mms(getattr(package, "width", None)) if package is not None else None,
        dimension_in_mms(getattr(package, "height", None)) if package is not None else None,
    ]
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
