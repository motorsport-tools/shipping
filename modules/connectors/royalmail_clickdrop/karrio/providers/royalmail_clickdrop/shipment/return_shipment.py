"""Karrio Royal Mail Click and Drop return shipment API implementation."""

import typing

import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.royalmail_clickdrop.error as error
import karrio.providers.royalmail_clickdrop.utils as provider_utils
import karrio.providers.royalmail_clickdrop.units as provider_units
import karrio.schemas.royalmail_clickdrop.return_request as royalmail_return_req
import karrio.schemas.royalmail_clickdrop.return_response as royalmail_return_res


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default) if obj is not None else default


def _split_name(name: str) -> typing.Tuple[str, str]:
    if not name:
        return "", ""

    parts = str(name).strip().split()
    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def _country_name(country_code: str) -> str:
    mapping = {
        "GB": "United Kingdom",
        "US": "United States",
        "IE": "Ireland",
        "FR": "France",
        "DE": "Germany",
    }

    if not country_code:
        return ""

    return mapping.get(country_code.upper(), country_code)


def _country_iso_code(country_code: str) -> str:
    mapping = {
        "GB": "GBR",
        "US": "USA",
        "IE": "IRL",
        "FR": "FRA",
        "DE": "DEU",
    }

    if not country_code:
        return ""

    return mapping.get(country_code.upper(), country_code.upper())


def _clean_dict(data: dict) -> dict:
    return {
        key: value
        for key, value in data.items()
        if value not in [None, "", [], {}]
    }


def _build_return_address(address) -> royalmail_return_req.AddressType:
    first_name, last_name = _split_name(_get(address, "person_name"))
    country_code = _get(address, "country_code")

    address_data = _clean_dict(
        {
            "title": None,
            "firstName": first_name or None,
            "lastName": last_name or None,
            "companyName": _get(address, "company_name"),
            "addressLine1": _get(address, "address_line1"),
            "addressLine2": _get(address, "address_line2"),
            "addressLine3": _get(address, "address_line3"),
            "city": _get(address, "city"),
            "county": _get(address, "state_name") or _get(address, "state_code"),
            "postcode": _get(address, "postal_code"),
            "country": _country_name(country_code),
            "countryIsoCode": _country_iso_code(country_code),
        }
    )

    return royalmail_return_req.AddressType(**address_data)


def return_shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    shipper = lib.to_address(payload.shipper)
    recipient = lib.to_address(payload.recipient)
    options = lib.to_shipping_options(
        payload.options or {},
        initializer=provider_units.shipping_options_initializer,
    )

    selected_service = (
        provider_utils.get_option(options, "service_code")
        or payload.service
        or "tracked_returns_48"
    )

    service_code = provider_units.resolve_carrier_service(selected_service)

    if service_code is None:
        raise ValueError(
            f"Invalid Royal Mail Click & Drop return service selector: {selected_service}"
        )

    if not provider_units.is_return_service(service_code):
        raise ValueError(
            f"Royal Mail Click & Drop return shipments require a return service code. Got: {selected_service}"
        )

    request = royalmail_return_req.ReturnRequestType(
        service=royalmail_return_req.ServiceType(
            serviceCode=service_code,
        ),
        shipment=royalmail_return_req.ShipmentType(
            shippingAddress=_build_return_address(shipper),
            returnAddress=_build_return_address(recipient),
            customerReference=royalmail_return_req.CustomerReferenceType(
                reference=payload.reference or getattr(payload, "id", None),
            ),
        ),
    )

    return lib.Serializable(request, lib.to_dict)

def parse_return_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[
    typing.Optional[models.ShipmentDetails],
    typing.List[models.Message],
]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    if any(messages):
        return None, messages

    data = lib.to_object(royalmail_return_res.ReturnResponseType, response)
    shipment = getattr(data, "shipment", None)

    if shipment is None:
        return None, messages

    documents = models.Documents(
        label=getattr(data, "label", None),
    )

    return (
        models.ShipmentDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            tracking_number=getattr(shipment, "trackingNumber", None),
            shipment_identifier=(
                getattr(shipment, "uniqueItemId", None)
                or getattr(shipment, "trackingNumber", None)
            ),
            label_type=settings.connection_config.label_type.state or "PDF",
            docs=documents,
            meta={
                "qr_code": getattr(data, "qrCode", None),
                "is_return": True,
            },
        ),
        messages,
    )
