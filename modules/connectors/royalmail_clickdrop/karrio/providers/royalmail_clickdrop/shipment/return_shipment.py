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


ISO3_FALLBACKS = {
    "GB": "GBR",
    "US": "USA",
    "ES": "ESP",
    "FR": "FRA",
    "DE": "DEU",
    "IE": "IRL",
    "IT": "ITA",
    "NL": "NLD",
    "BE": "BEL",
    "CH": "CHE",
    "AT": "AUT",
    "AU": "AUS",
    "CA": "CAN",
    "NZ": "NZL",
}


def _resolve_country_iso3(country_code: str) -> str:
    if not country_code:
        return ""

    code = str(country_code).strip().upper()

    if len(code) == 3 and code.isalpha():
        return code

    if pycountry is not None:
        country = pycountry.countries.get(alpha_2=code) or pycountry.countries.get(alpha_3=code)
        if country is not None:
            return country.alpha_3

    return ISO3_FALLBACKS.get(code, code)


def _first_present(*values):
    for value in values:
        if value not in [None, ""]:
            return value

    return None

def _resolve_selected_service(payload, options, default=None):
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
        or getattr(service, "value_or_key", None)
        or getattr(service, "name_or_key", None)
        or payload.service
        or default
    )

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
                data.shipment.uniqueItemId
                or data.shipment.trackingNumber
                or ""
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
