"""Karrio Royal Mail Click and Drop shipment API implementation."""

import datetime
import typing
from decimal import Decimal

import karrio.core.models as models
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


def _to_float(value, default=None):
    if value in [None, ""]:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
            _value(importer, "country", "country_name"),
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


def _build_item(
    item,
    customs,
    default_weight_unit=None,
) -> royalmail_clickdrop_req.ContentType:
    metadata = provider_utils.get_value(item, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    item_value = _to_float(
        _coalesce(
            provider_utils.get_value(item, "value_amount"),
            provider_utils.get_value(item, "value"),
        )
    )

    raw_item_weight = provider_utils.get_value(item, "weight")
    raw_item_weight_unit = _value(
        item,
        "weight_unit",
        "weightUnit",
        default=default_weight_unit,
    )
    item_weight_in_grams = (
        provider_units.weight_to_grams(raw_item_weight, raw_item_weight_unit)
        if raw_item_weight is not None and raw_item_weight_unit is not None
        else None
    )

    customs_category = (
        metadata.get("customs_declaration_category")
        or provider_units.resolve_customs_category(
            getattr(customs, "content_type", None)
        )
        or "saleOfGoods"
    )

    return royalmail_clickdrop_req.ContentType(
        SKU=_text(provider_utils.get_value(item, "sku"), max=100),
        name=_text(
            provider_utils.get_value(item, "description")
            or provider_utils.get_value(item, "title")
            or provider_utils.get_value(item, "name"),
            max=800,
        ),
        quantity=int(float(provider_utils.get_value(item, "quantity", 1) or 1)),
        unitValue=item_value,
        unitWeightInGrams=item_weight_in_grams,
        customsDescription=_text(
            provider_utils.get_value(item, "description")
            or provider_utils.get_value(item, "title")
            or provider_utils.get_value(item, "name"),
            max=50,
        ),
        extendedCustomsDescription=_text(
            provider_utils.get_value(item, "description"),
            max=300,
        ),
        customsCode=_text(
            "".join(
                char
                for char in str(provider_utils.get_value(item, "hs_code") or "")
                if char.isalnum()
            ),
            max=10,
        ),
        originCountryCode=_text(provider_utils.get_value(item, "origin_country"), max=3),
        customsDeclarationCategory=customs_category,
        requiresExportLicence=_coalesce(
            metadata.get("requires_export_licence"),
            metadata.get("requires_export_license"),
        ),
        stockLocation=_text(metadata.get("stock_location"), max=50),
        useOriginPreference=metadata.get("use_origin_preference"),
        supplementaryUnits=_text(
            (
                str(metadata.get("supplementary_units"))
                if metadata.get("supplementary_units") not in [None, ""]
                else None
            ),
            max=17,
        ),
        licenseNumber=_text(metadata.get("license_number"), max=41),
        certificateNumber=_text(metadata.get("certificate_number"), max=41),
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


def _resolve_package_items(package, raw_package, customs) -> typing.List[typing.Any]:
    package_items = list(
        provider_utils.get_value(raw_package, "items") or package.items or []
    )

    if any(package_items):
        return package_items

    return list(getattr(customs, "commodities", None) or []) if customs else []


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

    package_items = [
        item
        for index, package in enumerate(packages or [])
        for item in _resolve_package_items(
            package,
            raw_parcels[index] if index < len(raw_parcels) else None,
            customs,
        )
    ]
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
) -> royalmail_clickdrop_req.PackageType:
    raw_weight = provider_utils.get_value(raw_package, "weight")
    raw_weight_unit = _value(raw_package, "weight_unit", "weightUnit")
    package_items = _resolve_package_items(package, raw_package, customs)

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
        weightInGrams=_coalesce(
            raw_weight_in_grams,
            provider_units.weight_in_grams(package.weight, default=1),
            1,
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


def _sum_items_value(packages, raw_parcels=None, customs=None) -> float:
    total = Decimal("0.00")

    for index, package in enumerate(packages or []):
        raw_package = raw_parcels[index] if raw_parcels and index < len(raw_parcels) else None

        for item in _resolve_package_items(package, raw_package, customs):
            qty = Decimal(str(_attr(item, "quantity", 1) or 1))
            value = Decimal(
                str(_coalesce(_attr(item, "value_amount"), _attr(item, "value"), 0))
            )
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
    shipment = _extract_details(response, settings) if isinstance(response, dict) else None
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

    selected_service = options.service_code.state or payload.service
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
            options.shipment_date.state,
            options.shipping_date.state,
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
    total = _coalesce(
        options.total.state,
        float(subtotal or 0.0)
        + float(shipping_cost or 0.0)
        + float(order_tax or 0.0)
        + float(other_costs or 0.0)
        + float(customs_duty or 0.0),
    )
    currency = _resolve_currency_code(
        payload,
        packages,
        raw_parcels,
        customs,
        options,
        settings,
    )

    send_notifications_to = _coalesce(
        options.send_notifications_to.state,
        "recipient" if recipient.email else None,
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

    billing = _resolve_billing(payload, raw_options)
    importer = provider_utils.get_value(raw_options, "importer")
    tags = provider_utils.get_value(raw_options, "tags")

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
        options.include_label_in_response.state,
        settings.connection_config.include_label_in_response.state,
        True,
    )
    include_cn = (
        True if is_international else (True if options.include_cn.state is True else None)
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
                    )
                    for index, package in enumerate(packages)
                ],
                orderDate=order_date,
                plannedDespatchDate=planned_despatch_date,
                specialInstructions=special_instructions,
                subtotal=_to_float(subtotal, 0.0),
                shippingCostCharged=_to_float(shipping_cost, 0.0),
                otherCosts=(
                    _to_float(other_costs)
                    if other_costs is not None
                    else None
                ),
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
                    serviceCode=_text(service_code, max=10),
                    carrierName=_text(carrier_name, max=50),
                    serviceRegisterCode=_text(service_register_code, max=2),
                    consequentialLoss=options.consequential_loss.state,
                    receiveEmailNotification=_coalesce(
                        options.receive_email_notification.state,
                        options.email_notification.state,
                        bool(recipient.email),
                    ),
                    receiveSmsNotification=_coalesce(
                        options.receive_sms_notification.state,
                        options.sms_notification.state,
                        False,
                    ),
                    requestSignatureUponDelivery=options.request_signature_upon_delivery.state,
                    isLocalCollect=options.is_local_collect.state,
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
                    requiresExportLicense=options.requires_export_license.state,
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
                orderTax=_to_float(order_tax, 0.0),
                containsDangerousGoods=_coalesce(
                    options.contains_dangerous_goods.state,
                    options.dangerous_good.state,
                ),
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