"""Karrio Royal Mail Click and Drop shipment API implementation."""

import datetime
import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.shipment_request as royalmail_clickdrop_req
import karrio.schemas.royalmail_clickdrop.shipment_response as royalmail_clickdrop_res
from decimal import Decimal


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


def _required_weight_in_grams(value) -> int:
    if value is None:
        raise ValueError("Royal Mail Click & Drop parcel weight is required")

    return max(int(value), 1)


def _raw_parcel_weight_in_grams(raw_parcel, package) -> int:
    value = provider_units.weight_to_grams(
        _get(raw_parcel, "weight"),
        _get(raw_parcel, "weight_unit"),
        default=provider_units.weight_in_grams(getattr(package, "weight", None)),
    )

    return _required_weight_in_grams(value)



def _sum_items_value(packages) -> float:
    total = Decimal("0.00")

    for package in packages or []:
        for item in (package.items or []):
            quantity = Decimal(str(_attr(item, "quantity", 1) or 1))
            value = Decimal(str(_attr(item, "value_amount") or _attr(item, "value") or 0))
            total += quantity * value

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
    raw_parcels = list(payload.parcels or [])
    packages = lib.to_packages(payload.parcels, required=["weight"])
    options = lib.to_shipping_options(
        payload.options or {},
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )
    customs = lib.to_customs_info(payload.customs) if payload.customs else None

    selected_service = options.service_code.state or payload.service
    service = provider_units.resolve_carrier_service(selected_service)

    if service is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {selected_service}"
        )

    explicit_package_format = options.package_format_identifier.state
    billing = options.billing.state
    importer = options.importer.state

    subtotal = options.subtotal.state
    if subtotal is None:
        subtotal = (
            float(customs.invoice_amount)
            if customs is not None and customs.invoice_amount is not None
            else _sum_items_value(packages)
        )

    shipping_cost = (
        options.shipping_cost_charged.state
        if options.shipping_cost_charged.state is not None
        else 0.0
    )
    order_tax = options.order_tax.state if options.order_tax.state is not None else 0.0
    total = options.total.state
    if total is None:
        total = float(subtotal or 0.0) + float(shipping_cost or 0.0) + float(order_tax or 0.0)

    currency = (
        options.currency_code.state
        or provider_utils.get_option(options, "currency")
        or getattr(settings, "default_currency", None)
        or "GBP"
    )
    carrier_name = options.carrier_name.state or settings.shipping_carrier_name

    include_label_in_response = (
        True
        if options.include_label_in_response.state is None
        else bool(options.include_label_in_response.state)
    )
    include_cn = (
        None if options.include_cn.state is None else bool(options.include_cn.state)
    )
    include_returns_label = (
        None
        if options.include_returns_label.state is None
        else bool(options.include_returns_label.state)
    )

    request = royalmail_clickdrop_req.ShipmentRequestType(
        items=[
            royalmail_clickdrop_req.ItemType(
                orderReference=lib.text(
                    options.order_reference.state or payload.reference,
                    max=40,
                ),
                isRecipientABusiness=options.is_recipient_a_business.state,
                recipient=royalmail_clickdrop_req.BillingType(
                    address=royalmail_clickdrop_req.AddressType(
                        fullName=recipient.person_name or recipient.company_name,
                        companyName=recipient.company_name,
                        addressLine1=recipient.address_line1,
                        addressLine2=recipient.address_line2,
                        addressLine3=recipient.address_line3,
                        city=recipient.city,
                        county=recipient.state_code,
                        postcode=recipient.postal_code,
                        countryCode=recipient.country_code,
                    ),
                    phoneNumber=recipient.phone_number,
                    emailAddress=recipient.email,
                    addressBookReference=options.address_book_reference.state,
                ),
                sender=royalmail_clickdrop_req.SenderType(
                    tradingName=shipper.company_name or shipper.person_name,
                    phoneNumber=shipper.phone_number,
                    emailAddress=shipper.email,
                ),
                billing=(
                    royalmail_clickdrop_req.BillingType(
                        address=royalmail_clickdrop_req.AddressType(
                            fullName=_get(_get(billing, "address"), "fullName")
                            or _get(billing, "fullName"),
                            companyName=_get(_get(billing, "address"), "companyName")
                            or _get(billing, "companyName"),
                            addressLine1=_get(_get(billing, "address"), "addressLine1")
                            or _get(billing, "addressLine1")
                            or _get(billing, "address_line1"),
                            addressLine2=_get(_get(billing, "address"), "addressLine2")
                            or _get(billing, "addressLine2")
                            or _get(billing, "address_line2"),
                            addressLine3=_get(_get(billing, "address"), "addressLine3")
                            or _get(billing, "addressLine3")
                            or _get(billing, "address_line3"),
                            city=_get(_get(billing, "address"), "city")
                            or _get(billing, "city"),
                            county=_get(_get(billing, "address"), "county")
                            or _get(billing, "county")
                            or _get(billing, "state_code"),
                            postcode=_get(_get(billing, "address"), "postcode")
                            or _get(billing, "postcode")
                            or _get(billing, "postal_code"),
                            countryCode=_get(_get(billing, "address"), "countryCode")
                            or _get(billing, "countryCode")
                            or _get(billing, "country_code"),
                        ),
                        phoneNumber=_get(billing, "phoneNumber")
                        or _get(billing, "phone_number"),
                        emailAddress=_get(billing, "emailAddress")
                        or _get(billing, "email"),
                        addressBookReference=_get(billing, "addressBookReference")
                        or _get(billing, "address_book_reference"),
                    )
                    if billing
                    else None
                ),

                packages=[
                    royalmail_clickdrop_req.PackageType(
                        weightInGrams=_raw_parcel_weight_in_grams(
                            raw_parcels[index] if index < len(raw_parcels) else None,
                            package,
                        ),
                        packageFormatIdentifier=provider_units.resolve_package_format(
                            package=package,
                            explicit=explicit_package_format,
                        ),
                        dimensions=provider_units.build_dimensions(
                            package,
                            royalmail_clickdrop_req.DimensionsType,
                        ),
                        contents=[
                            royalmail_clickdrop_req.ContentType(
                                SKU=_to_text(_attr(item, "sku")),
                                name=_attr(item, "description")
                                or _attr(item, "title")
                                or _attr(item, "name"),
                                quantity=_to_int(_attr(item, "quantity"), 1),
                                unitValue=_to_float(
                                    _attr(item, "value_amount") or _attr(item, "value"),
                                    0.0,
                                ),
                                unitWeightInGrams=provider_units.weight_in_grams(
                                    _attr(item, "weight"),
                                    default=0,
                                ),
                                customsDescription=_attr(item, "description")
                                or _attr(item, "title")
                                or _attr(item, "name"),
                                extendedCustomsDescription=_attr(item, "description"),
                                customsCode=(
                                    "".join(
                                        character
                                        for character in str(_attr(item, "hs_code") or "")
                                        if character.isalnum()
                                    )
                                    or None
                                ),
                                originCountryCode=_attr(item, "origin_country"),
                                customsDeclarationCategory=_to_text(
                                    (_attr(item, "metadata", {}) or {}).get(
                                        "customs_declaration_category"
                                    )
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                requiresExportLicence=(
                                    (_attr(item, "metadata", {}) or {}).get(
                                        "requires_export_licence"
                                    )
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                stockLocation=_to_text(
                                    (_attr(item, "metadata", {}) or {}).get("stock_location")
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                useOriginPreference=(
                                    (_attr(item, "metadata", {}) or {}).get(
                                        "use_origin_preference"
                                    )
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                supplementaryUnits=_to_text(
                                    (_attr(item, "metadata", {}) or {}).get(
                                        "supplementary_units"
                                    )
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                licenseNumber=_to_text(
                                    (_attr(item, "metadata", {}) or {}).get("license_number")
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                                certificateNumber=_to_text(
                                    (_attr(item, "metadata", {}) or {}).get(
                                        "certificate_number"
                                    )
                                    if isinstance(_attr(item, "metadata", {}), dict)
                                    else None
                                ),
                            )
                            for item in (package.items or [])
                        ],
                    )
                    for index, package in enumerate(packages)
                ],
                orderDate=options.order_date.state or _iso_now(),
                plannedDespatchDate=options.planned_despatch_date.state,
                specialInstructions=lib.text(options.special_instructions.state, max=500),
                subtotal=_to_float(subtotal, 0.0),
                shippingCostCharged=_to_float(shipping_cost, 0.0),
                otherCosts=_to_float(options.other_costs.state),
                customsDutyCosts=_to_float(options.customs_duty_costs.state),
                total=_to_float(total, 0.0),
                currencyCode=currency,
                postageDetails=royalmail_clickdrop_req.PostageDetailsType(
                    sendNotificationsTo=options.send_notifications_to.state,
                    serviceCode=service,
                    carrierName=carrier_name,
                    serviceRegisterCode=options.service_register_code.state,
                    consequentialLoss=options.consequential_loss.state,
                    receiveEmailNotification=(
                        options.receive_email_notification.state
                        if options.receive_email_notification.state is not None
                        else (True if recipient.email else None)
                    ),
                    receiveSmsNotification=(
                        options.receive_sms_notification.state
                        if options.receive_sms_notification.state is not None
                        else (True if recipient.phone_number else None)
                    ),
                    requestSignatureUponDelivery=options.request_signature_upon_delivery.state,
                    isLocalCollect=options.is_local_collect.state,
                    safePlace=options.safe_place.state,
                    department=options.department.state,
                    AIRNumber=options.air_number.state,
                    IOSSNumber=options.ioss_number.state,
                    requiresExportLicense=options.requires_export_license.state,
                    commercialInvoiceNumber=options.commercial_invoice_number.state
                    or _attr(customs, "invoice_number"),
                    commercialInvoiceDate=options.commercial_invoice_date.state
                    or _attr(customs, "invoice_date"),
                    recipientEoriNumber=options.recipient_eori_number.state,
                ),
                tags=[
                    royalmail_clickdrop_req.TagType(
                        key=_get(tag, "key"),
                        value=_get(tag, "value"),
                    )
                    for tag in (options.tags.state or [])
                    if _get(tag, "key") is not None or _get(tag, "value") is not None
                ],
                label=royalmail_clickdrop_req.LabelType(
                    includeLabelInResponse=include_label_in_response,
                    includeCN=include_cn,
                    includeReturnsLabel=include_returns_label,
                ),
                orderTax=_to_float(order_tax, 0.0),
                containsDangerousGoods=options.contains_dangerous_goods.state,
                dangerousGoodsUnCode=options.dangerous_goods_un_code.state,
                dangerousGoodsDescription=options.dangerous_goods_description.state,
                dangerousGoodsQuantity=_to_float(
                    options.dangerous_goods_quantity.state
                ),
                importer=(
                    royalmail_clickdrop_req.ImporterType(
                        companyName=_get(importer, "companyName")
                        or _get(importer, "company_name"),
                        addressLine1=_get(importer, "addressLine1")
                        or _get(importer, "address_line1"),
                        addressLine2=_get(importer, "addressLine2")
                        or _get(importer, "address_line2"),
                        addressLine3=_get(importer, "addressLine3")
                        or _get(importer, "address_line3"),
                        city=_get(importer, "city"),
                        postcode=_get(importer, "postcode")
                        or _get(importer, "postal_code"),
                        country=_get(importer, "country"),
                        businessName=_get(importer, "businessName")
                        or _get(importer, "business_name"),
                        contactName=_get(importer, "contactName")
                        or _get(importer, "contact_name"),
                        phoneNumber=_get(importer, "phoneNumber")
                        or _get(importer, "phone_number"),
                        emailAddress=_get(importer, "emailAddress")
                        or _get(importer, "email"),
                        vatNumber=_get(importer, "vatNumber")
                        or _get(importer, "vat_number"),
                        taxCode=_get(importer, "taxCode")
                        or _get(importer, "tax_code"),
                        eoriNumber=_get(importer, "eoriNumber")
                        or _get(importer, "eori_number"),
                    )
                    if importer
                    else None
                ),
            )
        ]
    )

    return lib.Serializable(request, lib.to_dict)