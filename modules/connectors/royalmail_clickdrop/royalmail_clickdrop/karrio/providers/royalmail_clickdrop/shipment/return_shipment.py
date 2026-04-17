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


def _resolve_country_name(address) -> str:
    country_name = _get(address, "country_name")
    country_code = _get(address, "country_code")

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

    return code


def _clean_dict(data: dict) -> dict:
    return {
        key: value
        for key, value in data.items()
        if value not in [None, "", [], {}]
    }

def parse_return_shipment_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.ShipmentDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    messages = error.parse_error_response(response, settings)

    if any(messages):
        return None, messages

    data = lib.to_object(royalmail_return_res.ReturnResponseType, response)

    if data.shipment is None:
        return None, []

    return (
        models.ShipmentDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            tracking_number=data.shipment.trackingNumber,
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
    recipient = lib.to_address(payload.recipient)
    options = lib.to_shipping_options(
        payload.options or {},
        initializer=provider_units.shipping_options_initializer,
    )

    selected_service = options.service_code.state or payload.service or "tracked_returns_48"
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

    shipper_first_name, shipper_last_name = _split_name(shipper.person_name)
    recipient_first_name, recipient_last_name = _split_name(recipient.person_name)

    request = royalmail_return_req.ReturnRequestType(
        service=royalmail_return_req.ServiceType(
            serviceCode=service_code,
        ),
        shipment=royalmail_return_req.ShipmentType(
            shippingAddress=royalmail_return_req.AddressType(
                **_clean_dict(
                    {
                        "title": None,
                        "firstName": shipper_first_name or None,
                        "lastName": shipper_last_name or None,
                        "companyName": shipper.company_name,
                        "addressLine1": shipper.address_line1,
                        "addressLine2": shipper.address_line2,
                        "addressLine3": shipper.address_line3,
                        "city": shipper.city,
                        "county": shipper.state_name or shipper.state_code,
                        "postcode": shipper.postal_code,
                        "country": _resolve_country_name(shipper),
                        "countryIsoCode": _resolve_country_iso3(shipper.country_code),
                    }
                )
            ),
            returnAddress=royalmail_return_req.AddressType(
                **_clean_dict(
                    {
                        "title": None,
                        "firstName": recipient_first_name or None,
                        "lastName": recipient_last_name or None,
                        "companyName": recipient.company_name,
                        "addressLine1": recipient.address_line1,
                        "addressLine2": recipient.address_line2,
                        "addressLine3": recipient.address_line3,
                        "city": recipient.city,
                        "county": recipient.state_name or recipient.state_code,
                        "postcode": recipient.postal_code,
                        "country": _resolve_country_name(recipient),
                        "countryIsoCode": _resolve_country_iso3(recipient.country_code),
                    }
                )
            ),
            customerReference=royalmail_return_req.CustomerReferenceType(
                reference=payload.reference or getattr(payload, "id", None),
            ),
        ),
    )

    return lib.Serializable(request, lib.to_dict)