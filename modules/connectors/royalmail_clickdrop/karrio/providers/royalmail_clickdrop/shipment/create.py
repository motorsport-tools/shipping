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
from karrio.core.units import Weight

from karrio.server.core.logging import logger


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


def _build_importer(importer, options) -> royalmail_clickdrop_req.ImporterType:
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
        vatNumber=lib.text(provider_utils.get_option(options, "rm_importer_vat_number", None), max=15),
        taxCode=lib.text(provider_utils.get_option(options, "rm_importer_tax_code", None), max=25),
        eoriNumber=lib.text(provider_utils.get_option(options, "rm_importer_eori_number", None), max=18)
    )


def _build_tags(tags) -> typing.List[royalmail_clickdrop_req.TagType]:
    return [
        royalmail_clickdrop_req.TagType(
            key=_get(tag, "key"),
            value=_get(tag, "value"),
        )
        for tag in (tags or [])
    ]

def _build_item(item, customs) -> royalmail_clickdrop_req.ContentType:
    metadata = _attr(item, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    item_weight = Weight(item.weight, item.weight_unit)
    weight_in_grams = int(item_weight.G or 0)

    return royalmail_clickdrop_req.ContentType(
        SKU=lib.text(_attr(item, "sku"), max=100),
        name=lib.text(_attr(item, "description") or _attr(item, "title") or _attr(item, "name"), max=800),
        quantity=_to_int(_attr(item, "quantity"), 1),
        unitValue=_to_float(_attr(item, "value_amount") or _attr(item, "value"), 0.0),
        unitWeightInGrams=weight_in_grams,
        customsDescription=lib.text(item.description or item.title, max=50),
        extendedCustomsDescription=lib.text(_attr(item, "description"), max=300),
        customsCode=lib.text("".join(char for char in item.hs_code if char.isalnum()), max=10),
        originCountryCode=item.origin_country,
        customsDeclarationCategory=(
            provider_units.resolve_customs_category(customs.content_type) 
            if customs is not None else "saleOfGoods"
        ),
        requiresExportLicence=metadata.get("requires_export_licence"),
        stockLocation=lib.text(metadata.get("stock_location"), max=50),
        useOriginPreference=metadata.get("use_origin_preference"),
        supplementaryUnits=lib.text(metadata.get("supplementary_units"), max=17),
        licenseNumber=lib.text(metadata.get("license_number"), max=41),
        certificateNumber=lib.text(metadata.get("certificate_number"), max=41),
    )


def _build_package(
    package,
    customs,
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
        dimensions=dimensions or None,
        contents=[_build_item(item, customs) for item in (package.items or [])],
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
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="create_shipment",
    )
    shipment = (
        _extract_details(response, settings)
        if isinstance(response, dict)
        else None
    )
    messages += _extract_label_messages(response, settings)

    if shipment is None and any(messages):
        return None, messages

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
    tracking_number = order.trackingNumber or (
        package_tracking_numbers[0] if any(package_tracking_numbers) else None
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
        docs=models.Documents(
            label=order.label,
            pdf_label=order.label,
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
            code = _get(item, "code") or "label_error"
            message = _get(item, "message") or ""

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
        payload.options,
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )

    service = provider_units.resolve_carrier_service(payload.service)

    customs = lib.to_customs_info(
        payload.customs,
        shipper=payload.shipper,
        recipient=payload.recipient,
        weight_unit="KG"
    )

    if service is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {service}"
        )
        
    explicit_package_format = provider_utils.get_option(
        options, "package_format_identifier"
    )


    subtotal = _sum_items_value(packages)

    shipping_cost = provider_utils.get_option(options, "rm_shipping_cost_charged", 0.0)
    customs_duty = provider_utils.get_option(options, "rm_customs_duty_costs", 0.0)

    order_tax = provider_utils.get_option(options, "rm_order_tax", 0.0)
    
    total = provider_utils.get_option(options, "rm_order_total")

    if total is None:
        total = float(subtotal or 0) + float(shipping_cost or 0) + float(order_tax or 0) + float(customs_duty or 0)


    options = lib.to_shipping_options(
        payload.options,
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )

    for key, value in vars(options).items():
        logger.info(f"{key}: {value}")

    currency = options.currency.state or settings.default_currency
    customs = lib.to_customs_info(payload.customs) if payload.customs else None

    request = royalmail_clickdrop_req.ShipmentRequestType(
        items=[
            royalmail_clickdrop_req.ItemType(
                orderReference=lib.text(payload.reference, max=40),
                isRecipientABusiness=not recipient.residential,
                recipient=royalmail_clickdrop_req.BillingType(
                    address=royalmail_clickdrop_req.AddressType(
                        fullName=lib.identity(
                            recipient.contact or recipient.company_name
                        ),
                        companyName=recipient.company_name,
                        addressLine1=recipient.address_line1,
                        addressLine2=recipient.address_line2,
                        city=recipient.city,
                        county=recipient.state_code,
                        postcode=recipient.postal_code,
                        countryCode=recipient.country_code,
                    ),
                    phoneNumber=recipient.phone_number,
                    emailAddress=recipient.email,
                    addressBookReference=(payload.metadata or {}).get("rm_address_book_reference")
                ),
                sender=royalmail_clickdrop_req.SenderType(
                    tradingName=shipper.company_name or None,
                    phoneNumber=shipper.phone_number,
                    emailAddress=shipper.email,
                ),
                packages=[
                    _build_package(package, customs, explicit_package_format) for package in packages
                ],
                orderDate=(lib.to_date(options.rm_order_date.state) or _iso_now()).isoformat(),
                subtotal=subtotal or 0.0,
                shippingCostCharged=_to_float(shipping_cost, 0.0),
                customsDutyCosts=_to_float(customs_duty) if customs and customs.incoterm == 'DDP' else None,
                total=total,
                currencyCode=currency,
                postageDetails=royalmail_clickdrop_req.PostageDetailsType(
                    serviceCode=service,
                    sendNotificationsTo=lib.identity(
                        "recipient" if recipient.email else None
                    ),
                    receiveEmailNotification=lib.identity(
                        options.rm_email_notification.state
                        if options.rm_email_notification.state is not None
                        else bool(recipient.email)
                    ),
                    receiveSmsNotification=lib.identity(
                        options.royalmail_sms_notification.state
                        if options.royalmail_sms_notification.state is not None
                        else False
                    ),
                    requestSignatureUponDelivery=options.rm_request_signature_upon_delivery.state,
                    isLocalCollect=options.rm_is_local_collect.state,
                    safePlace=options.rm_safe_place.state,
                    department=options.rm_department.state,
                    AIRNumber=options.rm_airnumber.state if recipient.country_code == 'NI' else None,
                    IOSSNumber=options.rm_iossnumber.state,
                    requiresExportLicense=options.rm_requires_export_license.state,
                    commercialInvoiceNumber=lib.identity(
                        customs.invoice_number if customs else None
                    ),
                    commercialInvoiceDate=lib.identity(
                        customs.invoice_date if customs else None
                    ),
                    recipientEoriNumber=options.rm_recipient_eori.state,
                ),
                label=royalmail_clickdrop_req.LabelType(
                    includeLabelInResponse=settings.connection_config.include_label_in_response.state,
                    includeCN=recipient.country_code != shipper.country_code,
                    includeReturnsLabel=settings.connection_config.include_return_label_in_response.state,
                ),
                orderTax=order_tax,
                containsDangerousGoods=options.rm_contains_dangerous_goods.state,
                dangerousGoodsUnCode=lib.text(options.rm_dangerous_goods_un_code.state, max=4),
                dangerousGoodsDescription=lib.text(options.rm_dangerous_goods_description.state, max=500),
                dangerousGoodsQuantity=options.rm_dangerous_goods_quantity.state or None,
                importer=_build_importer(recipient, options) if recipient.country_code != shipper.country_code and not recipient.residential else None
            )
        ]
    )
    
    return lib.Serializable(request, lib.to_dict)