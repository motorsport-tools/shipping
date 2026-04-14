"""Karrio Royal Mail Click and Drop shipment API implementation."""


import datetime
import typing
from decimal import Decimal

import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.schemas.royalmail_clickdrop.shipment_request as royalmail_clickdrop_req
import karrio.schemas.royalmail_clickdrop.shipment_response as royalmail_clickdrop_res


def _attr(obj, name, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default) if obj is not None else default

def _to_text(value, default=None):
    if value in [None, ""]:
        return default

    return str(value)

def _to_int(value, default=None):
    if value in [None, ""]:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default=None):
    if value in [None, ""]:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_now() -> str:
    return (
        datetime.datetime.now(datetime.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _grams(weight) -> int:
    if weight is None:
        raise ValueError("Royal Mail Click & Drop parcel weight is required")

    if hasattr(weight, "G"):
        return max(int(round(weight.G)), 1)

    if hasattr(weight, "value"):
        return max(int(round(float(weight.value))), 1)

    value = _to_int(weight)
    if value is None:
        raise ValueError(f"Invalid parcel weight: {weight}")

    return max(value, 1)


def _mm(measurement):
    if measurement is None:
        return None

    if hasattr(measurement, "MM"):
        return int(round(measurement.MM))

    if hasattr(measurement, "value"):
        return int(round(float(measurement.value)))

    return _to_int(measurement)


def _build_address(address) -> royalmail_clickdrop_req.AddressType:
    return royalmail_clickdrop_req.AddressType(
        fullName=_get(address, "person_name") or _get(address, "fullName") or _get(address, "name"),
        companyName=_get(address, "company_name") or _get(address, "companyName"),
        addressLine1=_get(address, "address_line1") or _get(address, "addressLine1"),
        addressLine2=_get(address, "address_line2") or _get(address, "addressLine2"),
        addressLine3=_get(address, "address_line3") or _get(address, "addressLine3"),
        city=_get(address, "city"),
        county=_get(address, "state_code") or _get(address, "state_name") or _get(address, "county"),
        postcode=_get(address, "postal_code") or _get(address, "postcode"),
        countryCode=_get(address, "country_code") or _get(address, "countryCode"),
    )


def _build_contact(address, address_book_reference=None) -> royalmail_clickdrop_req.BillingType:
    return royalmail_clickdrop_req.BillingType(
        address=_build_address(address) if address is not None else None,
        phoneNumber=_get(address, "phone_number") or _get(address, "phoneNumber") or _get(address, "phone"),
        emailAddress=_get(address, "email") or _get(address, "emailAddress"),
        addressBookReference=address_book_reference,
    )


def _build_sender(address) -> royalmail_clickdrop_req.SenderType:
    if address is None:
        return None

    return royalmail_clickdrop_req.SenderType(
        tradingName=_get(address, "company_name") or _get(address, "person_name") or _get(address, "tradingName"),
        phoneNumber=_get(address, "phone_number") or _get(address, "phoneNumber") or _get(address, "phone"),
        emailAddress=_get(address, "email") or _get(address, "emailAddress"),
    )


def _build_importer(importer) -> royalmail_clickdrop_req.ImporterType:
    if importer is None:
        return None

    return royalmail_clickdrop_req.ImporterType(
        companyName=_get(importer, "companyName") or _get(importer, "company_name"),
        addressLine1=_get(importer, "addressLine1") or _get(importer, "address_line1"),
        addressLine2=_get(importer, "addressLine2") or _get(importer, "address_line2"),
        addressLine3=_get(importer, "addressLine3") or _get(importer, "address_line3"),
        city=_get(importer, "city"),
        postcode=_get(importer, "postcode") or _get(importer, "postal_code"),
        country=_get(importer, "country"),
        businessName=_get(importer, "businessName") or _get(importer, "business_name"),
        contactName=_get(importer, "contactName") or _get(importer, "contact_name"),
        phoneNumber=_get(importer, "phoneNumber") or _get(importer, "phone_number"),
        emailAddress=_get(importer, "emailAddress") or _get(importer, "email"),
        vatNumber=_get(importer, "vatNumber") or _get(importer, "vat_number"),
        taxCode=_get(importer, "taxCode") or _get(importer, "tax_code"),
        eoriNumber=_get(importer, "eoriNumber") or _get(importer, "eori_number"),
    )


def _build_tags(tags) -> typing.List[royalmail_clickdrop_req.TagType]:
    return [
        royalmail_clickdrop_req.TagType(
            key=_get(tag, "key"),
            value=_get(tag, "value"),
        )
        for tag in (tags or [])
    ]


def _build_item(item) -> royalmail_clickdrop_req.ContentType:
    metadata = _attr(item, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    return royalmail_clickdrop_req.ContentType(
        SKU=_to_text(_attr(item, "sku")),
        name=_attr(item, "description") or _attr(item, "title") or _attr(item, "name"),
        quantity=_to_int(_attr(item, "quantity"), 1),
        unitValue=_to_float(_attr(item, "value_amount") or _attr(item, "value"), 0.0),
        unitWeightInGrams=_to_int(_attr(item, "weight"), 0),
        customsDescription=_attr(item, "description") or _attr(item, "title"),
        extendedCustomsDescription=_attr(item, "description"),
        customsCode=_to_text(_attr(item, "hs_code")),
        originCountryCode=_to_text(_attr(item, "origin_country")),
        customsDeclarationCategory=_to_text(metadata.get("customs_declaration_category")),
        requiresExportLicence=metadata.get("requires_export_licence"),
        stockLocation=_to_text(metadata.get("stock_location")),
        useOriginPreference=metadata.get("use_origin_preference"),
        supplementaryUnits=_to_text(metadata.get("supplementary_units")),
        licenseNumber=_to_text(metadata.get("license_number")),
        certificateNumber=_to_text(metadata.get("certificate_number")),
    )


def _build_package(
    package,
    explicit_package_format: typing.Optional[str] = None,
) -> royalmail_clickdrop_req.PackageType:
    dimensions = None
    if all([package.length, package.width, package.height]):
        dimensions = royalmail_clickdrop_req.DimensionsType(
            heightInMms=_mm(package.height),
            widthInMms=_mm(package.width),
            depthInMms=_mm(package.length),
        )

    return royalmail_clickdrop_req.PackageType(
        weightInGrams=_grams(package.weight),
        packageFormatIdentifier=provider_units.resolve_package_format(
            package=package,
            explicit=explicit_package_format,
        ),
        dimensions=dimensions,
        contents=[_build_item(item) for item in (package.items or [])],
    )


def _sum_items_value(packages) -> float:
    total = Decimal("0.00")

    for package in packages or []:
        for item in (package.items or []):
            qty = Decimal(str(_attr(item, "quantity", 1) or 1))
            value = Decimal(str(_attr(item, "value_amount") or _attr(item, "value") or 0))
            total += qty * value

    return float(total)


def parse_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ShipmentDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    if any(messages):
        return None, messages

    shipment = _extract_details(response, settings)

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
    package_tracking_numbers = [p.trackingNumber for p in packages if getattr(p, "trackingNumber", None)]
    tracking_number = order.trackingNumber or (package_tracking_numbers[0] if any(package_tracking_numbers) else None)

    documents = models.Documents(
        label=order.label,
    )

    return models.ShipmentDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        tracking_number=tracking_number,
        shipment_identifier=str(order.orderIdentifier or order.orderReference or ""),
        label_type=settings.connection_config.label_type.state or "PDF",
        docs=documents,
        meta=dict(
            order_identifier=order.orderIdentifier,
            order_reference=order.orderReference,
            created_on=order.createdOn,
            order_date=order.orderDate,
            printed_on=order.printedOn,
            manifested_on=order.manifestedOn,
            shipped_on=order.shippedOn,
            package_tracking_numbers=package_tracking_numbers,
            generated_documents=order.generatedDocuments or [],
        ),
    )


def shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    shipper = lib.to_address(payload.shipper)
    recipient = lib.to_address(payload.recipient)
    packages = lib.to_packages(payload.parcels, required=["weight"])
    options = lib.to_shipping_options(
        payload.options,
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )

    selected_service = (
        provider_utils.get_option(options, "service_code")
        or payload.service
    )
    service = provider_units.resolve_carrier_service(selected_service)
    if service is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {selected_service}"
        )
    explicit_package_format = provider_utils.get_option(
        options, "package_format_identifier"
    )

    subtotal = provider_utils.get_option(options, "subtotal")
    if subtotal is None:
        subtotal = _sum_items_value(packages)

    shipping_cost = provider_utils.get_option(options, "shipping_cost_charged", 0.0)
    order_tax = provider_utils.get_option(options, "order_tax", 0.0)
    total = provider_utils.get_option(options, "total")
    if total is None:
        total = float(subtotal or 0) + float(shipping_cost or 0) + float(order_tax or 0)

    billing = provider_utils.get_option(options, "billing") or payload.billing_address

    item = royalmail_clickdrop_req.ItemType(
        orderReference=provider_utils.get_option(options, "order_reference") or payload.reference,
        isRecipientABusiness=provider_utils.get_option(options, "is_recipient_a_business"),
        recipient=_build_contact(
            recipient,
            address_book_reference=provider_utils.get_option(options, "address_book_reference"),
        ),
        sender=_build_sender(shipper),
        billing=_build_contact(billing) if billing else None,
        packages=[_build_package(package, explicit_package_format) for package in packages],
        orderDate=provider_utils.get_option(options, "order_date") or _iso_now(),
        plannedDespatchDate=provider_utils.get_option(options, "planned_despatch_date"),
        specialInstructions=provider_utils.get_option(options, "special_instructions"),
        subtotal=_to_float(subtotal, 0.0),
        shippingCostCharged=_to_float(shipping_cost, 0.0),
        otherCosts=_to_float(provider_utils.get_option(options, "other_costs"), None),
        customsDutyCosts=_to_float(provider_utils.get_option(options, "customs_duty_costs"), None),
        total=_to_float(total, 0.0),
        currencyCode=provider_utils.get_option(options, "currency_code"),
        postageDetails=royalmail_clickdrop_req.PostageDetailsType(
            sendNotificationsTo=provider_utils.get_option(options, "send_notifications_to"),
            serviceCode=service,
            carrierName=provider_utils.get_option(options, "carrier_name")
            or settings.shipping_carrier_name,
            serviceRegisterCode=provider_utils.get_option(options, "service_register_code"),
            consequentialLoss=_to_int(provider_utils.get_option(options, "consequential_loss"), None),
            receiveEmailNotification=provider_utils.get_option(options, "receive_email_notification"),
            receiveSmsNotification=provider_utils.get_option(options, "receive_sms_notification"),
            requestSignatureUponDelivery=provider_utils.get_option(options, "request_signature_upon_delivery"),
            isLocalCollect=provider_utils.get_option(options, "is_local_collect"),
            safePlace=provider_utils.get_option(options, "safe_place"),
            department=provider_utils.get_option(options, "department"),
            AIRNumber=provider_utils.get_option(options, "air_number"),
            IOSSNumber=provider_utils.get_option(options, "ioss_number"),
            requiresExportLicense=provider_utils.get_option(options, "requires_export_license"),
            commercialInvoiceNumber=provider_utils.get_option(options, "commercial_invoice_number"),
            commercialInvoiceDate=provider_utils.get_option(options, "commercial_invoice_date"),
            recipientEoriNumber=provider_utils.get_option(options, "recipient_eori_number"),
        ),
        tags=_build_tags(provider_utils.get_option(options, "tags", [])),
        label=royalmail_clickdrop_req.LabelType(
            includeLabelInResponse=provider_utils.get_option(options, "include_label_in_response", True),
            includeCN=provider_utils.get_option(options, "include_cn"),
            includeReturnsLabel=provider_utils.get_option(options, "include_returns_label"),
        ),
        orderTax=_to_float(order_tax, 0.0),
        containsDangerousGoods=provider_utils.get_option(options, "contains_dangerous_goods"),
        dangerousGoodsUnCode=provider_utils.get_option(options, "dangerous_goods_un_code"),
        dangerousGoodsDescription=provider_utils.get_option(options, "dangerous_goods_description"),
        dangerousGoodsQuantity=_to_float(provider_utils.get_option(options, "dangerous_goods_quantity"), None),
        importer=_build_importer(provider_utils.get_option(options, "importer")),
    )

    request = royalmail_clickdrop_req.ShipmentRequestType(items=[item])

    return lib.Serializable(request, lib.to_dict)
