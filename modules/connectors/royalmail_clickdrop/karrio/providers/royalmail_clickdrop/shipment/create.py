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

#used for debug
#from karrio.server.core.logging import logger


def _attr(obj, name, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value

    return None


def _is_northern_ireland(address) -> bool:
    postcode = (
        (provider_utils.get_value(address, "postal_code") or provider_utils.get_value(address, "postcode") or "")
        .replace(" ", "")
        .upper()
    )
    return postcode.startswith("BT")


def _is_gb_to_northern_ireland(shipper, recipient) -> bool:
    return (
        (provider_utils.get_value(shipper, "country_code") or "").upper() == "GB"
        and (provider_utils.get_value(recipient, "country_code") or "").upper() == "GB"
        and not _is_northern_ireland(shipper)
        and _is_northern_ireland(recipient)
    )

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

def _validate_billing_address(billing):
    if not billing:
        return

    address = provider_utils.get_value(billing, "address") or {}
    missing = []

    for field in ["addressLine1", "city", "countryCode"]:
        if provider_utils.get_value(address, field) in [None, ""]:
            missing.append(f"options.billing.address.{field}")

    if missing:
        raise ValueError(
            "Royal Mail Click & Drop shipment validation failed. "
            f"Missing required billing field(s): {', '.join(missing)}"
        )

def _build_item(item, customs) -> royalmail_clickdrop_req.ContentType:
    metadata = provider_utils.get_value(item, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    # Shipment item weights arrive as raw payload values, not normalized
    # package Weight objects. Convert the raw item weight directly using the
    # provided unit so customs content weights remain stable and predictable.
    item_weight_in_grams = provider_units.weight_to_grams(
        provider_utils.get_value(item, "weight"),
        provider_utils.get_value(item, "weight_unit") or "G",
        default=0,
    )

    customs_category = (
        metadata.get("customs_declaration_category")
        or provider_units.resolve_customs_category(
            getattr(customs, "content_type", None)
        )
        or "saleOfGoods"
    )

    return royalmail_clickdrop_req.ContentType(
        SKU=lib.text(provider_utils.get_value(item, "sku"), max=100),
        name=lib.text(
            provider_utils.get_value(item, "description")
            or provider_utils.get_value(item, "title")
            or provider_utils.get_value(item, "name"),
            max=800,
        ),
        quantity=int(float(provider_utils.get_value(item, "quantity", 1) or 1)),
        unitValue=_to_float(
            provider_utils.get_value(item, "value_amount") or provider_utils.get_value(item, "value"),
            0.0,
        ),
        unitWeightInGrams=item_weight_in_grams,
        customsDescription=lib.text(
            provider_utils.get_value(item, "description")
            or provider_utils.get_value(item, "title")
            or provider_utils.get_value(item, "name"),
            max=50,
        ),
        extendedCustomsDescription=lib.text(
            provider_utils.get_value(item, "description"),
            max=300,
        ),
        customsCode=lib.text(
            "".join(
                char
                for char in str(provider_utils.get_value(item, "hs_code") or "")
                if char.isalnum()
            ),
            max=10,
        ),
        originCountryCode=provider_utils.get_value(item, "origin_country"),
        customsDeclarationCategory=customs_category,
        requiresExportLicence=_coalesce(
            metadata.get("requires_export_licence"),
            metadata.get("requires_export_license"),
        ),
        stockLocation=lib.text(metadata.get("stock_location"), max=50),
        useOriginPreference=metadata.get("use_origin_preference"),

        # Royal Mail's schema defines `supplementaryUnits` as a string, but
        # Karrio/custom caller payloads may provide it as a number (for example
        # `1`). Coerce it to a string before passing it into `lib.text(...)`
        # so valid numeric inputs serialize correctly and do not raise.
        supplementaryUnits=lib.text(
            (
                str(metadata.get("supplementary_units"))
                if metadata.get("supplementary_units") not in [None, ""]
                else None
            ),
            max=17,
        ),

        licenseNumber=lib.text(metadata.get("license_number"), max=41),
        certificateNumber=lib.text(metadata.get("certificate_number"), max=41),
    )


def _build_package(
    package,
    raw_package,
    customs,
    explicit_package_format: typing.Optional[str] = None,
) -> royalmail_clickdrop_req.PackageType:
    # Use the original request payload for weight serialization.
    #
    # Royal Mail expects integer gram values, and Karrio's normalized package
    # objects can introduce unit defaults or rounding drift during conversion.
    # Using the raw parcel payload keeps `weightInGrams` and item
    # `unitWeightInGrams` stable and aligned with the request fixture.
    raw_weight = provider_utils.get_value(raw_package, "weight")
    raw_weight_unit = provider_utils.get_value(raw_package, "weight_unit") or "G"
    raw_items = provider_utils.get_value(raw_package, "items") or package.items or []

    return royalmail_clickdrop_req.PackageType(
        weightInGrams=provider_units.weight_to_grams(
            raw_weight,
            raw_weight_unit,
            default=provider_units.weight_in_grams(package.weight, default=1),
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
        contents=[_build_item(item, customs) for item in raw_items],
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

    selected_service = options.service_code.state or payload.service
    service = provider_units.resolve_carrier_service(selected_service)

    if service is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop service selector: {selected_service}"
        )

    explicit_package_format = options.package_format_identifier.state
    order_reference = lib.text(
        options.order_reference.state or payload.reference,
        max=40,
    )

    # Royal Mail expects date-time strings for both fields.
    order_date = (
        provider_utils.to_datetime_string(options.order_date.state)
        or datetime.datetime.now(datetime.UTC).isoformat()
    )
    planned_despatch_date = provider_utils.to_datetime_string(
        options.planned_despatch_date.state
    )

    subtotal = _coalesce(
        options.subtotal.state,
        _sum_items_value(packages),
    )
    shipping_cost = _coalesce(options.shipping_cost_charged.state, 0.0)
    other_costs = options.other_costs.state
    order_tax = _coalesce(options.order_tax.state, 0.0)
    customs_duty = options.customs_duty_costs.state
    total = _coalesce(
        options.total.state,
        float(subtotal or 0.0)
        + float(shipping_cost or 0.0)
        + float(order_tax or 0.0)
        + float(other_costs or 0.0)
        + float(customs_duty or 0.0),
    )
    currency = options.currency.state or settings.default_currency

    send_notifications_to = _coalesce(
        options.send_notifications_to.state,
        "recipient" if recipient.email else None,
    )
    carrier_name = _coalesce(
        options.carrier_name.state,
        settings.shipping_carrier_name,
    )
    commercial_invoice_number = _coalesce(
        options.commercial_invoice_number.state,
        getattr(customs, "invoice_number", None),
    )
    commercial_invoice_date = provider_utils.to_datetime_string(
        _coalesce(
            options.commercial_invoice_date.state,
            getattr(customs, "invoice_date", None),
        )
    )

    billing = provider_utils.get_value(raw_options, "billing")
    billing_address = provider_utils.get_value(billing, "address") or {}
    _validate_billing_address(billing)

    importer = provider_utils.get_value(raw_options, "importer")
    tags = provider_utils.get_value(raw_options, "tags")
    raw_parcels = list(payload.parcels or [])


    # YAML note:
    # `isRecipientABusiness` is only relevant for GB -> NI B2B shipments.
    # Never infer `True` from `recipient.residential is None`.
    is_recipient_a_business = None
    if (
        _is_gb_to_northern_ireland(shipper, recipient)
        and recipient.residential is not None
    ):
        is_recipient_a_business = not recipient.residential

    # YAML note:
    # - `includeLabelInResponse` is required in LabelGenerationRequest.
    # - `includeCN` should be requested for all international shipments.
    # - for domestic shipments, omit `includeCN` unless explicitly enabled.
    # - `includeReturnsLabel` is optional; omit it when false/unset.
    is_international = (
        (shipper.country_code or "").upper()
        != (recipient.country_code or "").upper()
    )
    include_label_in_response = _coalesce(
        options.include_label_in_response.state,
        settings.connection_config.include_label_in_response.state,
        True,
    )
    include_cn = (
        True
        if is_international
        else (True if options.include_cn.state is True else None)
    )
    include_returns_label = options.include_returns_label.state
    if include_returns_label is None:
        include_returns_label = (
            True
            if settings.connection_config.include_return_label_in_response.state
            else None
        )

    request = royalmail_clickdrop_req.ShipmentRequestType(
        items=[
            royalmail_clickdrop_req.ItemType(
                orderReference=order_reference,
                isRecipientABusiness=is_recipient_a_business,
                recipient=royalmail_clickdrop_req.BillingType(
                    address=royalmail_clickdrop_req.AddressType(
                        fullName=lib.identity(
                            recipient.person_name or recipient.company_name
                        ),
                        companyName=recipient.company_name,
                        addressLine1=recipient.address_line1,
                        addressLine2=recipient.address_line2,
                        addressLine3=recipient.address_line3,
                        city=recipient.city,
                        county=recipient.state_code or recipient.state_name,
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
                            fullName=provider_utils.get_value(billing_address, "fullName"),
                            companyName=provider_utils.get_value(billing_address, "companyName"),
                            addressLine1=provider_utils.get_value(billing_address, "addressLine1"),
                            addressLine2=provider_utils.get_value(billing_address, "addressLine2"),
                            addressLine3=provider_utils.get_value(billing_address, "addressLine3"),
                            city=provider_utils.get_value(billing_address, "city"),
                            county=provider_utils.get_value(billing_address, "county"),
                            postcode=provider_utils.get_value(billing_address, "postcode"),
                            countryCode=provider_utils.get_value(billing_address, "countryCode"),
                        ),
                        phoneNumber=provider_utils.get_value(billing, "phoneNumber"),
                        emailAddress=provider_utils.get_value(billing, "emailAddress"),
                    )
                    if billing
                    else None
                ),
                packages=[
                    _build_package(
                        package,
                        raw_parcels[index] if index < len(raw_parcels) else None,
                        customs,
                        explicit_package_format,
                    )
                    for index, package in enumerate(packages)
                ],
                orderDate=order_date,
                plannedDespatchDate=planned_despatch_date,
                specialInstructions=lib.text(
                    options.special_instructions.state,
                    max=500,
                ),
                subtotal=_to_float(subtotal, 0.0),
                shippingCostCharged=_to_float(shipping_cost, 0.0),
                otherCosts=(
                    _to_float(other_costs)
                    if other_costs is not None
                    else None
                ),
                # Royal Mail only supports customsDutyCosts for DDP services.
                customsDutyCosts=(
                    _to_float(customs_duty)
                    if customs is not None
                    and getattr(customs, "incoterm", None) == "DDP"
                    and customs_duty is not None
                    else None
                ),
                total=_to_float(total, 0.0),
                currencyCode=currency,
                postageDetails=royalmail_clickdrop_req.PostageDetailsType(
                    sendNotificationsTo=send_notifications_to,
                    serviceCode=service,
                    carrierName=carrier_name,
                    serviceRegisterCode=options.service_register_code.state,
                    consequentialLoss=options.consequential_loss.state,
                    receiveEmailNotification=_coalesce(
                        options.receive_email_notification.state,
                        bool(recipient.email),
                    ),
                    receiveSmsNotification=_coalesce(
                        options.receive_sms_notification.state,
                        False,
                    ),
                    requestSignatureUponDelivery=options.request_signature_upon_delivery.state,
                    isLocalCollect=options.is_local_collect.state,
                    safePlace=options.safe_place.state,
                    department=options.department.state,
                    # AIRNumber is only applicable for GB -> NI flows.
                    AIRNumber=(
                        options.air_number.state
                        if _is_gb_to_northern_ireland(shipper, recipient)
                        else None
                    ),
                    IOSSNumber=options.ioss_number.state,
                    requiresExportLicense=options.requires_export_license.state,
                    commercialInvoiceNumber=commercial_invoice_number,
                    commercialInvoiceDate=commercial_invoice_date,
                    recipientEoriNumber=options.recipient_eori_number.state,
                ),
                tags=(
                    [
                        royalmail_clickdrop_req.TagType(
                            key=provider_utils.get_value(tag, "key"),
                            value=provider_utils.get_value(tag, "value"),
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
                orderTax=_to_float(order_tax, 0.0),
                containsDangerousGoods=options.contains_dangerous_goods.state,
                dangerousGoodsUnCode=lib.text(
                    options.dangerous_goods_un_code.state,
                    max=4,
                ),
                dangerousGoodsDescription=lib.text(
                    options.dangerous_goods_description.state,
                    max=500,
                ),
                dangerousGoodsQuantity=options.dangerous_goods_quantity.state,
                importer=(
                    royalmail_clickdrop_req.ImporterType(
                        companyName=provider_utils.get_value(importer, "companyName")
                        or provider_utils.get_value(importer, "company_name"),
                        addressLine1=provider_utils.get_value(importer, "addressLine1")
                        or provider_utils.get_value(importer, "address_line1"),
                        addressLine2=provider_utils.get_value(importer, "addressLine2")
                        or provider_utils.get_value(importer, "address_line2"),
                        addressLine3=provider_utils.get_value(importer, "addressLine3")
                        or provider_utils.get_value(importer, "address_line3"),
                        city=provider_utils.get_value(importer, "city"),
                        postcode=provider_utils.get_value(importer, "postcode")
                        or provider_utils.get_value(importer, "postal_code"),
                        country=provider_utils.get_value(importer, "country")
                        or provider_utils.get_value(importer, "country_name"),
                        businessName=provider_utils.get_value(importer, "businessName")
                        or provider_utils.get_value(importer, "business_name"),
                        contactName=provider_utils.get_value(importer, "contactName")
                        or provider_utils.get_value(importer, "contact_name"),
                        phoneNumber=provider_utils.get_value(importer, "phoneNumber")
                        or provider_utils.get_value(importer, "phone_number"),
                        emailAddress=provider_utils.get_value(importer, "emailAddress")
                        or provider_utils.get_value(importer, "email"),
                        vatNumber=provider_utils.get_value(importer, "vatNumber")
                        or provider_utils.get_value(importer, "vat_number")
                        or options.importer_vat_number.state,
                        taxCode=provider_utils.get_value(importer, "taxCode")
                        or provider_utils.get_value(importer, "tax_code")
                        or options.importer_tax_code.state,
                        eoriNumber=provider_utils.get_value(importer, "eoriNumber")
                        or provider_utils.get_value(importer, "eori_number")
                        or options.importer_eori_number.state,
                    )
                    if importer and is_international
                    else None
                ),
            )
        ]
    )

    request_data = provider_utils.clean_payload(lib.to_dict(request)) or {}

    return lib.Serializable(request_data, lambda data: data)