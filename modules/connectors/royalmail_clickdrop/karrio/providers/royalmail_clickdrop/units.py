import csv
import pathlib
import typing
from decimal import Decimal, ROUND_HALF_UP

import karrio.lib as lib
import karrio.core.units as units
import karrio.core.models as models

class LabelType(lib.Enum):
    PDF = "PDF"


class ConnectionConfig(lib.Enum):
    """Carrier connection configuration options."""
    include_label_in_response = lib.OptionEnum("include_label_in_response", bool, True, True)
    include_return_label_in_response = lib.OptionEnum("include_return_label_in_response", bool, False, False)

    base_url = lib.OptionEnum("base_url", str)
    carrier_name = lib.OptionEnum("carrier_name", str)
    label_type = lib.OptionEnum("label_type", LabelType)

    shipping_options = lib.OptionEnum("shipping_options", list)
    shipping_services = lib.OptionEnum("shipping_services", list)


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
def _unit_code(unit) -> typing.Optional[str]:
    if unit is None:
        return None

    value = getattr(unit, "value", unit)
    return str(value).upper() if value is not None else None

def _source_value(source, *keys):
    if source is None:
        return None

    for key in keys:
        value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if value not in [None, ""]:
            return value

    return None


def dimension_to_mms(value, unit=None, default=None) -> typing.Optional[int]:
    amount = _decimal(value)
    code = _unit_code(unit)

    if amount is None:
        return default

    factor = _DIMENSION_FACTORS.get(code, Decimal("1")) if code is not None else Decimal("1")
    return _round_decimal(amount * factor)

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

    # Prefer the normalized grams value when available.
    # Karrio package weights may expose internal value/unit pairs that can
    # introduce conversion drift. Using `.G` first keeps Royal Mail shipment
    # payloads stable in grams, which is the carrier-native unit we need here.
    if hasattr(weight, "G"):
        grams = _decimal(weight.G)
        if grams is not None:
            return _round_decimal(grams)

    native = weight_to_grams(
        getattr(weight, "value", None),
        getattr(weight, "unit", None),
    )
    if native is not None:
        return native

    return weight_to_grams(weight, default=default)

def dimension_in_mms(measurement, default=None) -> typing.Optional[int]:
    if measurement is None:
        return default

    native = dimension_to_mms(
        getattr(measurement, "value", None),
        getattr(measurement, "unit", None),
    )
    if native is not None:
        return native

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

    mp7_01 = "MP7"

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

    # order-level controls
    order_reference = lib.OptionEnum("order_reference")
    order_date = lib.OptionEnum("order_date")
    planned_despatch_date = lib.OptionEnum("planned_despatch_date")
    special_instructions = lib.OptionEnum("special_instructions")
    service_code = lib.OptionEnum("service_code")
    package_format_identifier = lib.OptionEnum("package_format_identifier")

    # order totals
    subtotal = lib.OptionEnum("subtotal", float)
    shipping_cost_charged = lib.OptionEnum("shipping_cost_charged", float)
    other_costs = lib.OptionEnum("other_costs", float)
    customs_duty_costs = lib.OptionEnum("customs_duty_costs", float)
    order_tax = lib.OptionEnum("order_tax", float)
    total = lib.OptionEnum("total", float)
    currency = lib.OptionEnum("currency")

    # related objects
    address_book_reference = lib.OptionEnum("address_book_reference")
    billing = lib.OptionEnum("billing")
    importer = lib.OptionEnum("importer")
    tags = lib.OptionEnum("tags", list)

    # postage details
    send_notifications_to = lib.OptionEnum("send_notifications_to")
    carrier_name = lib.OptionEnum("carrier_name")
    service_register_code = lib.OptionEnum("service_register_code")
    consequential_loss = lib.OptionEnum("consequential_loss", int)
    receive_email_notification = lib.OptionEnum("receive_email_notification", bool)
    receive_sms_notification = lib.OptionEnum("receive_sms_notification", bool)
    request_signature_upon_delivery = lib.OptionEnum(
        "request_signature_upon_delivery",
        bool,
    )
    is_local_collect = lib.OptionEnum("is_local_collect", bool)
    safe_place = lib.OptionEnum("safe_place")
    department = lib.OptionEnum("department")
    air_number = lib.OptionEnum("air_number")
    ioss_number = lib.OptionEnum("ioss_number")
    requires_export_license = lib.OptionEnum("requires_export_license", bool)
    commercial_invoice_number = lib.OptionEnum("commercial_invoice_number")
    commercial_invoice_date = lib.OptionEnum("commercial_invoice_date")
    recipient_eori_number = lib.OptionEnum("recipient_eori_number")

    # label flags
    include_label_in_response = lib.OptionEnum("include_label_in_response", bool)
    include_cn = lib.OptionEnum("include_cn", bool)
    include_returns_label = lib.OptionEnum("include_returns_label", bool)

    # dangerous goods
    contains_dangerous_goods = lib.OptionEnum("contains_dangerous_goods", bool)
    dangerous_goods_un_code = lib.OptionEnum("dangerous_goods_un_code")
    dangerous_goods_description = lib.OptionEnum("dangerous_goods_description")
    dangerous_goods_quantity = lib.OptionEnum("dangerous_goods_quantity", int)

    # importer fallbacks
    importer_vat_number = lib.OptionEnum("importer_vat_number")
    importer_eori_number = lib.OptionEnum("importer_eori_number")
    importer_tax_code = lib.OptionEnum("importer_tax_code")

    # unified Karrio aliases
    shipment_date = order_date
    signature_confirmation = request_signature_upon_delivery
    dangerous_goods = contains_dangerous_goods

OPTION_ALIASES = {
    # legacy / RM-style input keys
    "orderDate": "order_date",
    "shippingCharge": "shipping_cost_charged",
    "customsDutyCosts": "customs_duty_costs",
    "orderTotal": "total",
    "receiveEmailNotification": "receive_email_notification",
    "receiveSmsNotification": "receive_sms_notification",
    "requestSignatureUponDelivery": "request_signature_upon_delivery",
    "isLocalCollect": "is_local_collect",
    "safePlace": "safe_place",
    "AIRNumber": "air_number",
    "IOSSNumber": "ioss_number",
    "requiresExportLicense": "requires_export_license",
    "recipientEoriNumber": "recipient_eori_number",
    "includeCN": "include_cn",
    "includeReturnsLabel": "include_returns_label",
    "containsDangerousGoods": "contains_dangerous_goods",
    "dangerousGoodsUnCode": "dangerous_goods_un_code",
    "dangerousGoodsDescription": "dangerous_goods_description",
    "dangerousGoodsQuantity": "dangerous_goods_quantity",

    # current connector-specific legacy names
    "rm_order_date": "order_date",
    "rm_shipping_cost_charged": "shipping_cost_charged",
    "rm_customs_duty_costs": "customs_duty_costs",
    "rm_order_tax": "order_tax",
    "rm_total": "total",
    "rm_email_notification": "receive_email_notification",
    "rm_sms_notification": "receive_sms_notification",
    "rm_request_signature_upon_delivery": "request_signature_upon_delivery",
    "rm_is_local_collect": "is_local_collect",
    "rm_safe_place": "safe_place",
    "rm_department": "department",
    "rm_airnumber": "air_number",
    "rm_iossnumber": "ioss_number",
    "rm_requires_export_license": "requires_export_license",
    "rm_recipient_eori": "recipient_eori_number",
    "rm_contains_dangerous_goods": "contains_dangerous_goods",
    "rm_dangerous_goods_un_code": "dangerous_goods_un_code",
    "rm_dangerous_goods_description": "dangerous_goods_description",
    "rm_dangerous_goods_quantity": "dangerous_goods_quantity",
    "rm_importer_vat_number": "importer_vat_number",
    "rm_importer_eori_number": "importer_eori_number",
    "rm_importer_tax_code": "importer_tax_code",
}

def shipping_options_initializer(
    options: dict,
    package_options: units.ShippingOptions = None,
) -> units.ShippingOptions:
    """Apply default values to the given options."""
    resolved = dict(package_options.content if package_options is not None else {})
    resolved.update(options or {})

    if package_options is not None:
        resolved.update(package_options.content)

    for legacy_key, canonical_key in OPTION_ALIASES.items():
        if legacy_key in resolved and canonical_key not in resolved:
            resolved[canonical_key] = resolved[legacy_key]

    def items_filter(key: str) -> bool:
        return key in ShippingOption  # type: ignore

    return units.ShippingOptions(
        resolved,
        ShippingOption,
        items_filter=items_filter,
    )

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



def build_dimensions(package, dimension_type, raw_package=None):
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
    width_mm = (
        dimension_to_mms(_source_value(raw_package, "width"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )
    height_mm = (
        dimension_to_mms(_source_value(raw_package, "height"), raw_dimension_unit)
        if raw_dimension_unit is not None
        else None
    )

    if length_mm is None and package is not None:
        length_mm = dimension_in_mms(getattr(package, "length", None))
    if width_mm is None and package is not None:
        width_mm = dimension_in_mms(getattr(package, "width", None))
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

def resolve_customs_category(category):
    mapping = {
        "none": "none",
        "documents": "documents",
        "gift": "gift",
        "merchandise": "saleOfGoods",
        "sale_of_goods": "saleOfGoods",
        "commercial_sample": "commercialSample",
        "sample": "commercialSample",
        "return_merchandise": "returnedGoods",
        "returned_goods": "returnedGoods",
        "mixed_content": "mixedContent",
        "mixed": "mixedContent",
        "other": "other",
    }

    return mapping.get(category, "none")