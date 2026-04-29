"""Karrio Royal Mail Click and Drop return shipment API implementation."""

import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.schemas.royalmail_clickdrop.return_request as royalmail_return_req
import karrio.schemas.royalmail_clickdrop.return_response as royalmail_return_res

try:
    import pycountry
except ImportError:  # pragma: no cover
    pycountry = None


COUNTRY_ALPHA3_FALLBACK = {
    "US": "USA",
    "ES": "ESP",
    "GB": "GBR",
    "UK": "GBR",
    "FR": "FRA",
    "DE": "DEU",
    "IT": "ITA",
    "NL": "NLD",
    "BE": "BEL",
    "IE": "IRL",
    "AU": "AUS",
    "CA": "CAN",
    "NZ": "NZL",
    "CH": "CHE",
    "AT": "AUT",
    "DK": "DNK",
    "SE": "SWE",
    "NO": "NOR",
    "PT": "PRT",
    "PL": "POL",
    "CZ": "CZE",
    "HU": "HUN",
    "RO": "ROU",
    "BG": "BGR",
    "GR": "GRC",
    "JP": "JPN",
    "CN": "CHN",
    "HK": "HKG",
    "SG": "SGP",
    "MY": "MYS",
    "AE": "ARE",
    "SA": "SAU",
    "ZA": "ZAF",
    "IN": "IND",
}


def _split_name(name: str) -> typing.Tuple[str, str]:
    if not name:
        return "", ""

    parts = str(name).strip().split()
    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def _resolve_country_name(address) -> str:
    country_name = provider_utils.get_value(address, "country_name")
    country_code = provider_utils.get_value(address, "country_code")

    if country_name:
        return country_name

    if country_code:
        return lib.to_country_name(country_code) or country_code.upper()

    return ""


def _resolve_country_iso3(country_code: str) -> str:
    if not country_code:
        return ""

    code = str(country_code).upper()

    if pycountry is not None:
        country = pycountry.countries.get(alpha_2=code)
        if country is not None:
            return country.alpha_3

    return COUNTRY_ALPHA3_FALLBACK.get(code, code)


def _first_present(*values):
    for value in values:
        if value not in [None, ""]:
            return value

    return None


def _service_selector(service) -> typing.Optional[str]:
    if service in [None, ""]:
        return None

    if isinstance(service, dict):
        for key in [
            "service_code",
            "carrier_service_code",
            "code",
            "name",
            "id",
        ]:
            value = service.get(key)
            if value not in [None, ""]:
                return str(value).strip()

    for attr in [
        "service_code",
        "carrier_service_code",
        "code",
        "id",
        "value_or_key",
        "name_or_key",
        "value",
        "name",
    ]:
        value = getattr(service, attr, None)
        if value not in [None, ""]:
            return str(value).strip()

    selector = str(service).strip()
    return selector or None


def _resolve_selected_service(payload, options, default=None):
    explicit_selector = _service_selector(options.service_code.state)
    if explicit_selector is not None:
        return provider_units.resolve_service_code(explicit_selector) or explicit_selector

    requested_services = (
        getattr(payload, "services", None)
        or ([payload.service] if getattr(payload, "service", None) else [])
    )

    selector = next(
        (
            resolved
            for resolved in (
                _service_selector(service) for service in requested_services
            )
            if resolved not in [None, ""]
        ),
        None,
    )

    if selector is not None:
        return provider_units.resolve_service_code(selector) or selector

    default_selector = _service_selector(default)
    if default_selector is None:
        return None

    return provider_units.resolve_service_code(default_selector) or default_selector


def _build_customer_reference(reference: typing.Optional[str]):
    if reference in [None, ""]:
        return None

    return royalmail_return_req.CustomerReferenceType(reference=reference)


def _build_return_address(address) -> royalmail_return_req.AddressType:
    first_name, last_name = _split_name(address.person_name)

    return royalmail_return_req.AddressType(
        **(
            provider_utils.clean_payload(
                {
                    "title": None,
                    "firstName": first_name or None,
                    "lastName": last_name or None,
                    "companyName": address.company_name,
                    "addressLine1": address.address_line1,
                    "addressLine2": address.address_line2,
                    "addressLine3": address.address_line3,
                    "city": address.city,
                    "county": address.state_name or address.state_code,
                    "postcode": address.postal_code,
                    "country": _resolve_country_name(address),
                    "countryIsoCode": _resolve_country_iso3(address.country_code),
                }
            )
            or {}
        )
    )


def parse_return_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ShipmentDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(
        response,
        settings,
        context="order",
        operation="create_return_shipment",
    )
    if any(messages):
        return None, messages

    data = lib.to_object(royalmail_return_res.ReturnResponseType, response)

    if data.shipment is None:
        return None, [
            models.Message(
                carrier_id=settings.carrier_id,
                carrier_name=settings.carrier_name,
                code="return_shipment_error",
                message="Unable to parse return shipment response",
                details={"operation": "create_return_shipment"},
            )
        ]

    tracking_number = provider_utils.resolve_tracking_number(
        data.shipment.trackingNumber,
    )

    return (
        models.ShipmentDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            tracking_number=tracking_number,
            shipment_identifier=str(
                data.shipment.uniqueItemId or data.shipment.trackingNumber or ""
            ),
            label_type=settings.label_type,
            docs=(
                models.Documents(label=data.label, pdf_label=data.label)
                if data.label
                else None
            ),
            meta={
                key: value
                for key, value in {
                    "qr_code": data.qrCode,
                    "is_return": True,
                    "unique_item_id": data.shipment.uniqueItemId,
                    "tracking_number_provided": (
                        tracking_number != provider_utils.NO_TRACKING_NUMBER
                    ),
                }.items()
                if value is not None
            },
        ),
        [],
    )


def return_shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    shipper = lib.to_address(payload.shipper)
    return_address = lib.to_address(payload.return_address or payload.recipient)
    options = lib.to_shipping_options(
        payload.options or {},
        initializer=provider_units.shipping_options_initializer,
    )

    selected_service = _resolve_selected_service(
        payload,
        options,
        default="tracked_returns_48",
    )
    service_code = provider_units.resolve_carrier_service(selected_service)

    if service_code is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop return service selector: {selected_service}"
        )

    if not provider_units.is_return_service(service_code):
        raise ValueError(
            "Royal Mail Click & Drop return shipments require a return service "
            f"code. Got: {selected_service}"
        )

    request = royalmail_return_req.ReturnRequestType(
        service=royalmail_return_req.ServiceType(
            serviceCode=service_code,
        ),
        shipment=royalmail_return_req.ShipmentType(
            shippingAddress=_build_return_address(shipper),
            returnAddress=_build_return_address(return_address),
            customerReference=_build_customer_reference(
                _first_present(
                    payload.reference,
                    getattr(payload, "order_id", None),
                    getattr(payload, "id", None),
                )
            ),
        ),
    )

    request_data = provider_utils.clean_payload(lib.to_dict(request)) or {}

    return lib.Serializable(request_data, lambda data: data)