"""Karrio Royal Mail Click and Drop shipment API implementation."""

import datetime
import typing
from decimal import Decimal, ROUND_HALF_UP

import karrio.core.models as models
import karrio.core.units as units
import karrio.lib as lib

import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.shipment_request as royalmail_clickdrop_req
import karrio.schemas.royalmail_clickdrop.shipment_response as royalmail_clickdrop_res


def _attr(obj, name, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value

    return None


def _text(value, max=None):
    return lib.text(value, max=max) if value is not None else None


def _first_present(*values):
    for value in values:
        if value not in [None, ""]:
            return value

    return None


def _value(source, *keys, default=None):
    for key in keys:
        value = provider_utils.get_value(source, key)
        if value not in [None, ""]:
            return value

    return default

def _option_state(source, name):
    option = getattr(source, name, None) if source is not None else None
    return getattr(option, "state", None)

def _resolve_selected_service(payload, options):
    requested_services = (
        getattr(payload, "services", None)
        or ([payload.service] if getattr(payload, "service", None) else None)
    )
    services = lib.to_services(
        requested_services,
        provider_units.ShippingService,
    )
    service = getattr(services, "first", None)

    return (
        options.service_code.state
        or _attr(service, "value_or_key")
        or _attr(service, "name_or_key")
        or payload.service
    )

def _is_northern_ireland(address) -> bool:
    postcode = (
        (
            provider_utils.get_value(address, "postal_code")
            or provider_utils.get_value(address, "postcode")
            or ""
        )
        .replace(" ", "")
        .upper()
    )
    return postcode.startswith("BT")


def _is_gb_to_northern_ireland(shipper, recipient) -> bool:
    return (
        (provider_utils.get_value(shipper, "country_code") or "").upper() == "GB"
        and (provider_utils.get_value(recipient, "country_code") or "").upper()
        == "GB"
        and not _is_northern_ireland(shipper)
        and _is_northern_ireland(recipient)
    )

def _to_int(value, default=None):
    if value in [None, ""]:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_decimal(value, default=None) -> typing.Optional[Decimal]:
    if value in [None, ""]:
        return default

    try:
        return Decimal(str(value))
    except Exception:
        return default


def _to_float(value, default=None):
    decimal_value = _to_decimal(value, None)
    if decimal_value is None:
        return default

    return float(decimal_value)


def _quantize_money(
    value,
    field: str,
    default=None,
    minimum: typing.Optional[Decimal] = Decimal("0.00"),
    maximum: typing.Optional[Decimal] = Decimal("999999.00"),
) -> typing.Optional[float]:
    amount = _to_decimal(value, None)
    if amount is None:
        return default

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if minimum is not None and amount < minimum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be greater than or equal to {minimum}."
        )

    if maximum is not None and amount > maximum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be less than or equal to {maximum}."
        )

    return float(amount)


def _bounded_int(
    value,
    field: str,
    default=None,
    minimum: typing.Optional[int] = None,
    maximum: typing.Optional[int] = None,
) -> typing.Optional[int]:
    number = _to_int(value, default)
    if number is None:
        return default

    if minimum is not None and number < minimum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be greater than or equal to {minimum}."
        )

    if maximum is not None and number > maximum:
        raise ValueError(
            f"Royal Mail Click & Drop `{field}` must be less than or equal to {maximum}."
        )

    return number


def _to_bool(value, default=None):
    if value in [None, ""]:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ["true", "1", "yes", "y"]:
            return True
        if normalized in ["false", "0", "no", "n"]:
            return False

    return bool(value)

def _parse_error_message(
    settings: provider_utils.Settings,
    code: str,
    message: str,
    operation: str,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code=code,
        message=message,
        details={"operation": operation},
    )

def _validate_billing_address(billing, source_label="billing"):
    if not billing:
        return

    address = provider_utils.get_value(billing, "address") or {}
    missing = []

    for field in ["addressLine1", "city", "countryCode"]:
        if provider_utils.get_value(address, field) in [None, ""]:
            missing.append(f"{source_label}.address.{field}")

    if missing:
        raise ValueError(
            "Royal Mail Click & Drop shipment validation failed. "
            f"Missing required billing field(s): {', '.join(missing)}"
        )


def _resolve_billing(payload, raw_options):
    option_billing = provider_utils.get_value(raw_options, "billing")
    if option_billing:
        _validate_billing_address(option_billing, "options.billing")
        return option_billing

    billing_address = getattr(payload, "billing_address", None)
    if billing_address is None:
        return None

    billing = lib.to_address(billing_address)
    resolved = {
        "address": {
            "fullName": billing.person_name,
            "companyName": billing.company_name,
            "addressLine1": billing.address_line1,
            "addressLine2": billing.address_line2,
            "addressLine3": billing.address_line3,
            "city": billing.city,
            "county": billing.state_code or billing.state_name,
            "postcode": billing.postal_code,
            "countryCode": billing.country_code,
        },
        "phoneNumber": billing.phone_number,
        "emailAddress": billing.email,
    }

    _validate_billing_address(resolved, "billing_address")
    return resolved

def _billing_email_address(billing) -> typing.Optional[str]:
    return _first_present(
        provider_utils.get_value(billing, "emailAddress"),
        provider_utils.get_value(billing, "email_address"),
    )


def _normalize_notification_target(value) -> typing.Optional[str]:
    if value in [None, ""]:
        return None

    normalized = str(value).strip()
    mapped = provider_units.NotificationTarget.map(normalized)

    if getattr(mapped, "enum", None) is None:
        mapped = provider_units.NotificationTarget.map(normalized.lower())

    if getattr(mapped, "enum", None) is None:
        return None

    return mapped.value_or_key


def _resolve_notification_target(
    raw_options,
    options,
    recipient,
    shipper,
    billing,
) -> typing.Optional[str]:
    explicit_target = _first_present(
        _value(raw_options, "send_notifications_to", "sendNotificationsTo"),
        options.send_notifications_to.state,
    )

    if explicit_target not in [None, ""]:
        normalized_target = _normalize_notification_target(explicit_target)

        if normalized_target is None:
            raise ValueError(
                "Royal Mail Click & Drop `send_notifications_to` must be one of "
                "`recipient`, `sender`, or `billing`."
            )

        return normalized_target

    explicit_email = _first_present(
        _value(raw_options, "email_notification_to"),
        options.email_notification_to.state,
    )

    if explicit_email not in [None, ""]:
        normalized_target = _normalize_notification_target(explicit_email)
        if normalized_target is not None:
            return normalized_target

        lookup = {
            (recipient.email or "").strip().lower(): "recipient",
            (shipper.email or "").strip().lower(): "sender",
            (_billing_email_address(billing) or "").strip().lower(): "billing",
        }
        resolved = lookup.get(str(explicit_email).strip().lower())

        if resolved is None:
            raise ValueError(
                "Royal Mail Click & Drop does not support arbitrary "
                "`email_notification_to` addresses. Use `send_notifications_to` "
                "or provide an email matching recipient, sender, or billing."
            )

        return resolved

    for target, email in [
        ("recipient", recipient.email),
        ("sender", shipper.email),
        ("billing", _billing_email_address(billing)),
    ]:
        if email not in [None, ""]:
            return target

    return None


def _notification_target_has_email(target, recipient, shipper, billing) -> bool:
    email_by_target = {
        "recipient": recipient.email,
        "sender": shipper.email,
        "billing": _billing_email_address(billing),
    }

    return email_by_target.get(target) not in [None, ""]

def _resolve_email_notification(
    raw_options,
    notification_target,
    recipient,
    shipper,
    billing,
) -> bool:
    explicit = _to_bool(
        _first_present(
            _value(
                raw_options,
                "receive_email_notification",
                "receiveEmailNotification",
                "email_notification",
            ),
        )
    )
    if explicit is not None:
        return explicit

    return _notification_target_has_email(
        notification_target,
        recipient,
        shipper,
        billing,
    )

def _build_billing_type(billing):
    if billing is None:
        return None

    billing_address = provider_utils.get_value(billing, "address") or {}

    return royalmail_clickdrop_req.BillingType(
        address=royalmail_clickdrop_req.AddressType(
            fullName=_text(
                provider_utils.get_value(billing_address, "fullName"), max=210
            ),
            companyName=_text(
                provider_utils.get_value(billing_address, "companyName"), max=100
            ),
            addressLine1=_text(
                provider_utils.get_value(billing_address, "addressLine1"), max=100
            ),
            addressLine2=_text(
                provider_utils.get_value(billing_address, "addressLine2"), max=100
            ),
            addressLine3=_text(
                provider_utils.get_value(billing_address, "addressLine3"), max=100
            ),
            city=_text(provider_utils.get_value(billing_address, "city"), max=100),
            county=_text(provider_utils.get_value(billing_address, "county"), max=100),
            postcode=_text(
                provider_utils.get_value(billing_address, "postcode"), max=20
            ),
            countryCode=_text(
                provider_utils.get_value(billing_address, "countryCode"), max=3
            ),
        ),
        phoneNumber=_text(provider_utils.get_value(billing, "phoneNumber"), max=25),
        emailAddress=_text(
            provider_utils.get_value(billing, "emailAddress"), max=254
        ),
    )


def _has_importer_data(importer, options, customs=None) -> bool:
    customs_options = getattr(customs, "options", None) if customs is not None else None

    return any(
        [
            importer,
            options.importer_vat_number.state,
            options.importer_tax_code.state,
            options.importer_eori_number.state,
            _option_state(customs_options, "vat_registration_number"),
            _option_state(customs_options, "eori_number"),
        ]
    )


def _resolve_importer_country(importer) -> typing.Optional[str]:
    country = _value(importer, "country", "country_name")
    if country not in [None, ""]:
        return country

    country_code = _value(importer, "countryCode", "country_code")
    if country_code in [None, ""]:
        return None

    try:
        return units.Country.map(country_code).value
    except Exception:
        return str(country_code)


def _build_importer_type(importer, options, customs=None):
    if not _has_importer_data(importer, options, customs):
        return None

    importer = importer or {}
    customs_options = getattr(customs, "options", None) if customs is not None else None

    return royalmail_clickdrop_req.ImporterType(
        companyName=_text(
            _value(importer, "companyName", "company_name"),
            max=100,
        ),
        addressLine1=_text(
            _value(importer, "addressLine1", "address_line1"),
            max=100,
        ),
        addressLine2=_text(
            _value(importer, "addressLine2", "address_line2"),
            max=100,
        ),
        addressLine3=_text(
            _value(importer, "addressLine3", "address_line3"),
            max=100,
        ),
        city=_text(_value(importer, "city"), max=100),
        postcode=_text(
            _value(importer, "postcode", "postal_code"),
            max=20,
        ),
        country=_text(
            _resolve_importer_country(importer),
            max=100,
        ),
        businessName=_text(
            _value(importer, "businessName", "business_name"),
            max=100,
        ),
        contactName=_text(
            _value(importer, "contactName", "contact_name"),
            max=100,
        ),
        phoneNumber=_text(
            _value(importer, "phoneNumber", "phone_number"),
            max=25,
        ),
        emailAddress=_text(
            _value(importer, "emailAddress", "email"),
            max=254,
        ),
        vatNumber=_text(
            _value(
                importer,
                "vatNumber",
                "vat_number",
                default=_first_present(
                    options.importer_vat_number.state,
                    _option_state(customs_options, "vat_registration_number"),
                ),
            ),
            max=15,
        ),
        taxCode=_text(
            _value(
                importer,
                "taxCode",
                "tax_code",
                default=options.importer_tax_code.state,
            ),
            max=25,
        ),
        eoriNumber=_text(
            _value(
                importer,
                "eoriNumber",
                "eori_number",
                default=_first_present(
                    options.importer_eori_number.state,
                    _option_state(customs_options, "eori_number"),
                ),
            ),
            max=18,
        ),
    )

def _item_metadata(item) -> dict:
    metadata = provider_utils.get_value(item, "metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _item_value(item, *keys, default=None):
    metadata = _item_metadata(item)
    return _value(
        item,
        *keys,
        default=_value(metadata, *keys, default=default),
    )


def _normalize_country_code(value, max_length: int = 3) -> typing.Optional[str]:
    if value in [None, ""]:
        return None

    text = str(value).strip()
    if text == "":
        return None

    for candidate in [text, text.upper()]:
        mapped = units.Country.map(candidate)
        if getattr(mapped, "enum", None) is not None:
            return mapped.name

    return None


def _resolve_sku(item) -> typing.Optional[str]:
    return _text(
        _coalesce(
            _item_value(item, "SKU", "sku"),
            _item_value(item, "product_id", "productId"),
            _item_value(item, "variant_id", "variantId"),
            _item_value(item, "id"),
        ),
        max=100,
    )


def _resolve_item_name(item) -> typing.Optional[str]:
    return _text(
        _coalesce(
            _item_value(item, "name"),
            _item_value(item, "title"),
            _item_value(item, "description"),
        ),
        max=800,
    )


def _resolve_customs_description(item) -> typing.Optional[str]:
    return _text(
        _coalesce(
            _item_value(item, "customs_description", "customsDescription"),
            _item_value(item, "description"),
            _item_value(item, "name"),
            _item_value(item, "title"),
        ),
        max=50,
    )

def _resolve_extended_customs_description(item) -> typing.Optional[str]:
    return _text(
        _coalesce(
            _item_value(
                item,
                "extended_customs_description",
                "extendedCustomsDescription",
            ),
            _item_value(item, "description"),
            _item_value(item, "name"),
            _item_value(item, "title"),
            _item_value(item, "customs_description", "customsDescription"),
        ),
        max=300,
    )


def _resolve_customs_code(item) -> typing.Optional[str]:
    return _text(
        _coalesce(
            _item_value(item, "customs_code", "customsCode"),
            _item_value(item, "hs_code", "hsCode"),
            _item_value(item, "commodity_code", "commodityCode"),
            _item_value(item, "harmonized_code", "harmonizedCode"),
        ),
        max=10,
    )


def _resolve_origin_country_code(item) -> typing.Optional[str]:
    return _normalize_country_code(
        _coalesce(
            _item_value(item, "origin_country_code", "originCountryCode"),
            _item_value(item, "origin_country", "originCountry"),
            _item_value(item, "country_of_origin", "countryOfOrigin"),
        ),
        max_length=3,
    )


def _resolve_item_customs_category(item, customs) -> typing.Optional[str]:
    return provider_units.normalize_customs_category(
        _coalesce(
            _item_value(
                item,
                "customs_declaration_category",
                "customsDeclarationCategory",
            ),
            provider_units.resolve_customs_category(customs),
        )
    )


def _resolve_unit_value(item) -> typing.Optional[float]:
    return _quantize_money(
        _coalesce(
            _item_value(item, "unit_value", "unitValue"),
            _item_value(item, "value_amount", "valueAmount"),
            _item_value(item, "value"),
        ),
        field="unitValue",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )


def _resolve_unit_weight_in_grams(
    item,
    default_weight_unit: typing.Optional[str] = None,
) -> typing.Optional[int]:
    direct_value = _bounded_int(
        _item_value(item, "unitWeightInGrams"),
        field="unitWeightInGrams",
        default=None,
        minimum=0,
        maximum=999999,
    )
    if direct_value is not None:
        return direct_value

    raw_item_weight = _item_value(item, "weight")
    raw_item_weight_unit = _first_present(
        _item_value(item, "weight_unit", "weightUnit"),
        default_weight_unit,
    )
    raw_item_weight_in_grams = (
        provider_units.weight_to_grams(raw_item_weight, raw_item_weight_unit)
        if raw_item_weight is not None and raw_item_weight_unit is not None
        else None
    )

    item_weight = getattr(item, "weight", None) if not isinstance(item, dict) else None
    return _bounded_int(
        _coalesce(
            raw_item_weight_in_grams,
            provider_units.weight_in_grams(item_weight, default=None),
        ),
        field="unitWeightInGrams",
        default=None,
        minimum=0,
        maximum=999999,
    )


def _resolve_requires_export_licence(item) -> typing.Optional[bool]:
    return _to_bool(
        _item_value(
            item,
            "requires_export_licence",
            "requiresExportLicence",
        ),
        None,
    )


def _resolve_use_origin_preference(item) -> typing.Optional[bool]:
    return _to_bool(
        _item_value(
            item,
            "use_origin_preference",
            "useOriginPreference",
        ),
        None,
    )


def _resolve_supplementary_units(item) -> typing.Optional[str]:
    value = _item_value(item, "supplementary_units", "supplementaryUnits")
    if value in [None, ""]:
        return None

    return _text(str(value), max=17)

def _build_item(
    item,
    customs,
    default_weight_unit: typing.Optional[str] = None,
) -> royalmail_clickdrop_req.ContentType:
    return royalmail_clickdrop_req.ContentType(
        SKU=_resolve_sku(item),
        name=_resolve_item_name(item),
        quantity=_bounded_int(
            _coalesce(_item_value(item, "quantity"), 1),
            field="quantity",
            default=1,
            minimum=1,
            maximum=999999,
        ),
        unitValue=_resolve_unit_value(item),
        unitWeightInGrams=_resolve_unit_weight_in_grams(
            item,
            default_weight_unit=default_weight_unit,
        ),
        customsDescription=_resolve_customs_description(item),
        extendedCustomsDescription=_resolve_extended_customs_description(item),
        customsCode=_resolve_customs_code(item),
        originCountryCode=_resolve_origin_country_code(item),
        customsDeclarationCategory=_resolve_item_customs_category(item, customs),
        requiresExportLicence=_resolve_requires_export_licence(item),
        stockLocation=_text(
            _item_value(item, "stock_location", "stockLocation"),
            max=50,
        ),
        useOriginPreference=_resolve_use_origin_preference(item),
        supplementaryUnits=_resolve_supplementary_units(item),
        licenseNumber=_text(
            _item_value(item, "license_number", "licenseNumber"),
            max=41,
        ),
        certificateNumber=_text(
            _item_value(item, "certificate_number", "certificateNumber"),
            max=41,
        ),
    )

def _resolve_special_instructions(options):
    return _text(
        _first_present(
            options.special_instructions.state,
            options.shipment_note.state,
            options.shipper_instructions.state,
            options.recipient_instructions.state,
        ),
        max=500,
    )


def _explicit_package_items(package, raw_package) -> typing.List[typing.Any]:
    return list(
        provider_utils.get_value(raw_package, "items")
        or getattr(package, "items", None)
        or []
    )

def _shipment_items(
    packages,
    raw_parcels=None,
    customs=None,
) -> typing.List[typing.Any]:
    customs_items = list(getattr(customs, "commodities", None) or []) if customs else []
    if any(customs_items):
        return customs_items

    return [
        item
        for index, package in enumerate(packages or [])
        for item in _explicit_package_items(
            package,
            raw_parcels[index] if raw_parcels and index < len(raw_parcels) else None,
        )
    ]

def _resolve_package_items(
    package,
    raw_package,
    customs,
    package_count: int = 1,
) -> typing.List[typing.Any]:
    package_items = _explicit_package_items(package, raw_package)

    if any(package_items):
        return package_items

    if package_count == 1 and customs:
        return list(getattr(customs, "commodities", None) or [])

    return []

def _resolve_currency_code(
    payload: models.ShipmentRequest,
    packages,
    raw_parcels,
    customs,
    options,
    settings: provider_utils.Settings,
):
    payment = getattr(payload, "payment", None)
    duty = getattr(customs, "duty", None) if customs else None

    package_items = _shipment_items(
        packages,
        raw_parcels,
        customs,
    )
    item_currency = next(
        (
            _value(item, "value_currency", "valueCurrency", "currencyCode", "currency")
            for item in package_items
            if _value(item, "value_currency", "valueCurrency", "currencyCode", "currency")
            not in [None, ""]
        ),
        None,
    )

    return _first_present(
        options.currency.state,
        provider_utils.get_value(payment, "currency"),
        provider_utils.get_value(duty, "currency"),
        item_currency,
        settings.default_currency,
    )


def _build_package(
    package,
    raw_package,
    customs,
    explicit_package_format: typing.Optional[str] = None,
    package_count: int = 1,
) -> royalmail_clickdrop_req.PackageType:
    raw_weight = provider_utils.get_value(raw_package, "weight")
    raw_weight_unit = _value(raw_package, "weight_unit", "weightUnit")
    package_items = _resolve_package_items(
        package,
        raw_package,
        customs,
        package_count=package_count,
    )

    raw_weight_in_grams = (
        provider_units.weight_to_grams(raw_weight, raw_weight_unit)
        if raw_weight is not None and raw_weight_unit is not None
        else None
    )

    fallback_item_weight_unit = _first_present(
        _value(raw_package, "weight_unit", "weightUnit"),
        getattr(getattr(package, "weight", None), "unit", None),
    )

    return royalmail_clickdrop_req.PackageType(
        weightInGrams=_bounded_int(
            _coalesce(
                raw_weight_in_grams,
                provider_units.weight_in_grams(package.weight, default=1),
                1,
            ),
            field="weightInGrams",
            default=1,
            minimum=1,
            maximum=30000,
        ),
        packageFormatIdentifier=provider_units.resolve_package_format(
            package=package,
            raw_package=raw_package,
            explicit=explicit_package_format,
        ),
        dimensions=provider_units.build_dimensions(
            package,
            royalmail_clickdrop_req.DimensionsType,
            raw_package=raw_package,
        ),
        contents=[
            _build_item(
                item,
                customs,
                default_weight_unit=fallback_item_weight_unit,
            )
            for item in package_items
        ],
    )

def _sum_items_value(packages, raw_parcels=None, customs=None) -> typing.Optional[float]:
    total = Decimal("0.00")
    has_items = False

    for item in _shipment_items(packages, raw_parcels, customs):
        has_items = True
        qty = Decimal(
            str(
                _bounded_int(
                    _item_value(item, "quantity"),
                    field="quantity",
                    default=1,
                    minimum=1,
                    maximum=999999,
                )
            )
        )
        value = _to_decimal(
            _coalesce(
                _item_value(item, "unit_value", "unitValue"),
                _item_value(item, "value_amount", "valueAmount"),
                _item_value(item, "value"),
            ),
            None,
        )

        if value is None:
            return None

        total += qty * value

    if not has_items:
        return None

    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def parse_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ShipmentDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="create_shipment",
    )
    shipment = _extract_details(response, settings) if isinstance(response, dict) else None
    messages += _extract_label_messages(response, settings)

    if shipment is None and any(messages):
        return None, messages

    if shipment is None:
        return None, [
            _parse_error_message(
                settings,
                code="shipment_parse_error",
                message="Unable to parse Royal Mail Click & Drop shipment response",
                operation="create_shipment",
            )
        ]

    return shipment, messages


def _extract_details(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.Optional[models.ShipmentDetails]:
    response = lib.to_object(royalmail_clickdrop_res.ShipmentResponseType, data)
    created_orders = response.createdOrders or []

    if len(created_orders) == 0:
        return None

    order = created_orders[0]
    packages = order.packages or []
    package_tracking_numbers = [
        package.trackingNumber
        for package in packages
        if getattr(package, "trackingNumber", None)
    ]
    tracking_number = provider_utils.resolve_tracking_number(
        order.trackingNumber,
        package_tracking_numbers,
    )

    shipment_identifiers = [
        str(value)
        for value in [order.orderIdentifier, order.orderReference]
        if value not in [None, ""]
    ]

    return models.ShipmentDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        tracking_number=tracking_number,
        shipment_identifier=str(order.orderIdentifier or order.orderReference or ""),
        label_type=settings.label_type,
        docs=(
            models.Documents(
                label=order.label,
                pdf_label=order.label,
            )
            if order.label
            else None
        ),
        meta=dict(
            order_identifier=order.orderIdentifier,
            order_reference=order.orderReference,
            created_on=order.createdOn,
            order_date=order.orderDate,
            printed_on=order.printedOn,
            manifested_on=order.manifestedOn,
            shipped_on=order.shippedOn,
            tracking_numbers=package_tracking_numbers,
            shipment_identifiers=shipment_identifiers,
            package_tracking_numbers=package_tracking_numbers,
            generated_documents=order.generatedDocuments or [],
            tracking_number_provided=(
                tracking_number != provider_utils.NO_TRACKING_NUMBER
            ),
        ),
    )


def _extract_label_messages(
    data: dict,
    settings: provider_utils.Settings,
) -> typing.List[models.Message]:
    if not isinstance(data, dict):
        return []

    response = lib.to_object(royalmail_clickdrop_res.ShipmentResponseType, data)
    messages: typing.List[models.Message] = []

    for order in response.createdOrders or []:
        for item in order.labelErrors or []:
            code = provider_utils.get_value(item, "code") or "label_error"
            message = (
                provider_utils.get_value(item, "message")
                or provider_utils.get_value(item, "description")
                or ""
            )

            if not any([code, message]):
                continue

            messages.append(
                models.Message(
                    carrier_id=settings.carrier_id,
                    carrier_name=settings.carrier_name,
                    code=code,
                    message=message,
                    details={
                        key: value
                        for key, value in dict(
                            operation="create_shipment",
                            order_identifier=order.orderIdentifier,
                            order_reference=order.orderReference,
                        ).items()
                        if value is not None
                    },
                )
            )

    return messages

def shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    shipper = lib.to_address(payload.shipper)
    recipient = lib.to_address(payload.recipient)
    packages = lib.to_packages(payload.parcels, required=["weight"])
    options = lib.to_shipping_options(
        payload.options or {},
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )
    raw_options = payload.options or {}
    raw_parcels = list(payload.parcels or [])

    customs = (
        lib.to_customs_info(
            payload.customs,
            shipper=payload.shipper,
            recipient=payload.recipient,
            weight_unit="KG",
        )
        if payload.customs
        else None
    )
    customs_options = getattr(customs, "options", None) if customs is not None else None

    selected_service = _resolve_selected_service(payload, options)
    service_code = provider_units.resolve_carrier_service(selected_service)
    service_register_code = (
        options.service_register_code.state
        or provider_units.resolve_service_register_code(selected_service)
    )

    if service_code is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {selected_service}"
        )

    explicit_package_format = options.package_format_identifier.state
    order_reference = _text(
        _first_present(
            options.order_reference.state,
            payload.reference,
            getattr(payload, "order_id", None),
        ),
        max=40,
    )

    order_date = (
        provider_utils.to_datetime_string(options.order_date.state)
        or datetime.datetime.now(datetime.UTC).isoformat()
    )
    planned_despatch_date = provider_utils.to_datetime_string(
        _first_present(
            options.planned_despatch_date.state,
            provider_utils.get_option(options, "shipment_date"),
            provider_utils.get_option(options, "shipping_date"),
        )
    )

    subtotal = _coalesce(
        options.subtotal.state,
        _sum_items_value(packages, raw_parcels, customs),
    )
    shipping_cost = _coalesce(options.shipping_cost_charged.state, 0.0)
    other_costs = options.other_costs.state
    order_tax = _coalesce(options.order_tax.state, 0.0)
    customs_duty = options.customs_duty_costs.state

    customs_duty_to_serialize = (
        customs_duty
        if customs is not None and getattr(customs, "incoterm", None) == "DDP"
        else None
    )

    serialized_subtotal = _quantize_money(
        subtotal,
        field="subtotal",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_shipping_cost = _quantize_money(
        shipping_cost,
        field="shippingCostCharged",
        default=0.0,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_other_costs = (
        _quantize_money(
            other_costs,
            field="otherCosts",
            default=None,
            minimum=Decimal("0.00"),
            maximum=Decimal("999999.00"),
        )
        if other_costs is not None
        else None
    )
    serialized_order_tax = _quantize_money(
        order_tax,
        field="orderTax",
        default=0.0,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )
    serialized_customs_duty = (
        _quantize_money(
            customs_duty_to_serialize,
            field="customsDutyCosts",
            default=None,
            minimum=Decimal("0.00"),
            maximum=Decimal("99999.99"),
        )
        if customs_duty_to_serialize is not None
        else None
    )

    total = _coalesce(
        options.total.state,
        (
            float(serialized_subtotal or 0.0)
            + float(serialized_shipping_cost or 0.0)
            + float(serialized_order_tax or 0.0)
            + float(serialized_other_costs or 0.0)
            + float(serialized_customs_duty or 0.0)
        )
        if serialized_subtotal is not None
        else None,
    )
    serialized_total = _quantize_money(
        total,
        field="total",
        default=None,
        minimum=Decimal("0.00"),
        maximum=Decimal("999999.00"),
    )

    if serialized_subtotal is None:
        raise ValueError(
            "Royal Mail Click & Drop requires `subtotal`. "
            "Provide `options.subtotal` or parcel/customs item values."
        )

    if serialized_total is None:
        raise ValueError(
            "Royal Mail Click & Drop requires `total`. "
            "Provide `options.total` or enough order values to derive it."
        )

    currency = _resolve_currency_code(
        payload,
        packages,
        raw_parcels,
        customs,
        options,
        settings,
    )

    billing = _resolve_billing(payload, raw_options)
    importer = provider_utils.get_value(raw_options, "importer")
    tags = provider_utils.get_value(raw_options, "tags")

    send_notifications_to = _resolve_notification_target(
        raw_options,
        options,
        recipient,
        shipper,
        billing,
    )
    carrier_name = _coalesce(
        options.carrier_name.state,
        settings.shipping_carrier_name,
    )
    commercial_invoice_number = _first_present(
        options.commercial_invoice_number.state,
        options.invoice_number.state,
        getattr(customs, "invoice", None),
    )
    commercial_invoice_date = provider_utils.to_datetime_string(
        _first_present(
            options.commercial_invoice_date.state,
            options.invoice_date.state,
            getattr(customs, "invoice_date", None),
        )
    )
    special_instructions = _resolve_special_instructions(options)

    is_recipient_a_business = None
    if (
        _is_gb_to_northern_ireland(shipper, recipient)
        and recipient.residential is not None
    ):
        is_recipient_a_business = not recipient.residential

    is_international = (
        (shipper.country_code or "").upper()
        != (recipient.country_code or "").upper()
    )
    include_label_in_response = _coalesce(
        _to_bool(options.include_label_in_response.state),
        _to_bool(settings.connection_config.include_label_in_response.state),
        True,
    )
    include_cn = (
        True
        if is_international
        else (True if _to_bool(options.include_cn.state) is True else None)
    )
    include_returns_label = _to_bool(options.include_returns_label.state)
    if include_returns_label is None:
        include_returns_label = (
            True
            if _to_bool(
                settings.connection_config.include_return_label_in_response.state,
                False,
            )
            is True
            else None
        )

    consequential_loss = _bounded_int(
        options.consequential_loss.state,
        field="consequentialLoss",
        default=None,
        minimum=0,
        maximum=10000,
    )
    receive_sms_notification = _coalesce(
        _to_bool(options.receive_sms_notification.state),
        _to_bool(options.sms_notification.state),
        False,
    )
    request_signature_upon_delivery = _to_bool(
        options.request_signature_upon_delivery.state
    )
    is_local_collect = _to_bool(options.is_local_collect.state)
    requires_export_license = _to_bool(options.requires_export_license.state)
    contains_dangerous_goods = _coalesce(
        _to_bool(options.contains_dangerous_goods.state),
        _to_bool(options.dangerous_good.state),
    )

    request = royalmail_clickdrop_req.ShipmentRequestType(
        items=[
            royalmail_clickdrop_req.ItemType(
                orderReference=order_reference,
                isRecipientABusiness=is_recipient_a_business,
                recipient=royalmail_clickdrop_req.BillingType(
                    address=royalmail_clickdrop_req.AddressType(
                        fullName=_text(
                            recipient.person_name or recipient.company_name,
                            max=210,
                        ),
                        companyName=_text(recipient.company_name, max=100),
                        addressLine1=_text(recipient.address_line1, max=100),
                        addressLine2=_text(recipient.address_line2, max=100),
                        addressLine3=_text(recipient.address_line3, max=100),
                        city=_text(recipient.city, max=100),
                        county=_text(recipient.state_code or recipient.state_name, max=100),
                        postcode=_text(recipient.postal_code, max=20),
                        countryCode=_text(recipient.country_code, max=3),
                    ),
                    phoneNumber=_text(recipient.phone_number, max=25),
                    emailAddress=_text(recipient.email, max=254),
                    addressBookReference=_text(options.address_book_reference.state, max=100),
                ),
                sender=royalmail_clickdrop_req.SenderType(
                    tradingName=_text(shipper.company_name or shipper.person_name, max=250),
                    phoneNumber=_text(shipper.phone_number, max=25),
                    emailAddress=_text(shipper.email, max=254),
                ),
                billing=_build_billing_type(billing),
                packages=[
                    _build_package(
                        package,
                        raw_parcels[index] if index < len(raw_parcels) else None,
                        customs,
                        explicit_package_format,
                        package_count=len(packages),
                    )
                    for index, package in enumerate(packages)
                ],
                orderDate=order_date,
                plannedDespatchDate=planned_despatch_date,
                specialInstructions=special_instructions,
                subtotal=serialized_subtotal,
                shippingCostCharged=serialized_shipping_cost,
                otherCosts=serialized_other_costs,
                customsDutyCosts=serialized_customs_duty,
                total=serialized_total,
                currencyCode=currency,
                postageDetails=royalmail_clickdrop_req.PostageDetailsType(
                    sendNotificationsTo=send_notifications_to,
                    serviceCode=_text(service_code, max=10),
                    carrierName=_text(carrier_name, max=50),
                    serviceRegisterCode=_text(service_register_code, max=2),
                    consequentialLoss=consequential_loss,
                    receiveEmailNotification=_resolve_email_notification(
                        raw_options,
                        send_notifications_to,
                        recipient,
                        shipper,
                        billing,
                    ),
                    receiveSmsNotification=receive_sms_notification,
                    requestSignatureUponDelivery=request_signature_upon_delivery,
                    isLocalCollect=is_local_collect,
                    safePlace=_text(options.safe_place.state, max=90),
                    department=_text(options.department.state, max=150),
                    AIRNumber=(
                        _text(
                            _first_present(
                                options.air_number.state,
                                _option_state(customs_options, "nip_number"),
                            ),
                            max=50,
                        )
                        if _is_gb_to_northern_ireland(shipper, recipient)
                        else None
                    ),
                    IOSSNumber=_text(
                        _first_present(
                            options.ioss_number.state,
                            _option_state(customs_options, "ioss"),
                        ),
                        max=50,
                    ),
                    requiresExportLicense=requires_export_license,
                    commercialInvoiceNumber=_text(commercial_invoice_number, max=35),
                    commercialInvoiceDate=commercial_invoice_date,
                    recipientEoriNumber=_text(
                        _first_present(
                            options.recipient_eori_number.state,
                            _option_state(customs_options, "eori_number"),
                        )
                    ),
                ),
                tags=(
                    [
                        royalmail_clickdrop_req.TagType(
                            key=_text(provider_utils.get_value(tag, "key"), max=100),
                            value=_text(provider_utils.get_value(tag, "value"), max=100),
                        )
                        for tag in tags
                    ]
                    if tags is not None
                    else None
                ),
                label=royalmail_clickdrop_req.LabelType(
                    includeLabelInResponse=include_label_in_response,
                    includeCN=include_cn,
                    includeReturnsLabel=include_returns_label,
                ),
                orderTax=serialized_order_tax,
                containsDangerousGoods=contains_dangerous_goods,
                dangerousGoodsUnCode=_text(
                    options.dangerous_goods_un_code.state,
                    max=4,
                ),
                dangerousGoodsDescription=_text(
                    options.dangerous_goods_description.state,
                    max=500,
                ),
                dangerousGoodsQuantity=options.dangerous_goods_quantity.state,
                importer=(
                    _build_importer_type(importer, options, customs)
                    if is_international and _has_importer_data(importer, options, customs)
                    else None
                ),
            )
        ]
    )

    request_data = provider_utils.clean_payload(lib.to_dict(request)) or {}

    return lib.Serializable(request_data, lambda data: data)